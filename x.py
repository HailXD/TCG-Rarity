import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple

import requests
import streamlit as st
from PIL import Image

try:
    from streamlit_image_select import image_select
except ModuleNotFoundError:
    st.error(
        "Missing required package **streamlit-image-select**. Install it with:\n    pip install streamlit-image-select"
    )
    st.stop()


RARITIES_ORDER: List[str] = [
    "common",
    "uncommon",
    "rare",
    "rare holo",
    "promo",
    "ultra rare",
    "no rarity",
    "rainbow rare",
    "rare holo ex",
    "rare secret",
    "shiny rare",
    "holo rare v",
    "illustration rare",
    "double rare",
    "rare holo gx",
    "special illustration rare",
    "holo rare vmax",
    "trainer gallery holo rare",
    "hyper rare",
    "rare holo lv.x",
    "trainer gallery holo rare v",
    "ace spec rare",
    "rare shiny gx",
    "holo rare vstar",
    "trainer gallery ultra rare",
    "rare break",
    "rare prism star",
    "rare prime",
    "rare holo star",
    "legend",
    "rare shining",
    "shiny rare v or vmax",
    "radiant rare",
    "shiny ultra rare",
    "trainer gallery secret rare",
    "trainer gallery holo rare v or vmax",
    "amazing rare",
]

EXCLUSION = ["shiny", "rainbow", "hyper"]
SUPPORT_EXCLUSION = EXCLUSION + ["gallery"]
POKEMON_EXCLUSION = EXCLUSION + ["ultra"]


def _rarity_rank(rarity: str) -> int:
    """Return the index of *rarity* inside RARITIES_ORDER (−1 if unknown)."""
    rarity = rarity.lower()
    try:
        return RARITIES_ORDER.index(rarity)
    except ValueError:
        return -1


def _default_variation_index(variations: List[sqlite3.Row]) -> int:
    """Pick the best variation according to rarity & exclusion rules."""
    best_idx = 0
    best_rank = -1

    for i, row in enumerate(variations):
        rarity = (row["rarity"] or "").lower()
        ctype = (row["card_type"] or "").lower()
        exclusions = POKEMON_EXCLUSION if ctype == "pokemon" else SUPPORT_EXCLUSION

        if any(token in rarity for token in exclusions):
            continue

        rank = _rarity_rank(rarity)
        if rank > best_rank:
            best_idx = i
            best_rank = rank

    return best_idx


DB_PATH = Path("pokemon_cards.db")
THUMB_W, MAIN_W = 110, 300
MAX_PARALLEL = 8


class DeckEntry(NamedTuple):
    quantity: int
    name: str
    set_code: str
    number: str


LINE_RE = re.compile(
    r"""
    ^\s*
    (\d+)\s+             # quantity
    (.*?)\s+             # card name (greedy, stops at 2nd whitespace zone)
    ([A-Z0-9]+)\s+       # set code
    (\d+)\s*             # card number
    $
    """,
    re.VERBOSE,
)


def parse_decklist(raw: str) -> List[DeckEntry]:
    """Return all typed-line deck entries (Energy lines ignored)."""
    entries: List[DeckEntry] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or not line[0].isdigit():
            continue
        m = LINE_RE.match(line)
        if not m:
            continue
        qty, name, set_code, num = m.groups()
        if set_code.lower() == "energy":
            continue
        entries.append(DeckEntry(int(qty), name.strip(), set_code, num))
    return entries


conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()


def fetch_printing(set_code: str, number: str):
    """Return a single card row for one exact printing (case-insensitive set)."""
    cur.execute(
        "SELECT * FROM cards WHERE lower(set_name) = ? AND number = ? LIMIT 1",
        (set_code.lower(), number),
    )
    return cur.fetchone()


def fetch_related(card_row):
    """Return *all* printings that are functionally the same card.

    For Pokémon we approximate this by matching the *first* attack name,
    for Trainers / Energy just match the exact card name & type.
    Rows are returned oldest → newest so that the **latest** printing is
    the list tail (index -1).
    """
    ctype = card_row["card_type"].lower()
    if ctype == "pokemon":
        raw = card_row["attacks"] or ""
        try:
            first_attack = raw.split("e': '", 1)[1].split("'", 1)[0]
        except IndexError:
            first_attack = ""
        cur.execute(
            """
            SELECT * FROM cards
            WHERE name=? AND lower(card_type)='pokemon' AND lower(attacks) LIKE ?
            ORDER BY julianday(date) ASC
            """,
            (card_row["name"], f"%{first_attack.lower()}%"),
        )
    else:
        cur.execute(
            """
            SELECT * FROM cards
            WHERE name=? AND lower(card_type)=? ORDER BY julianday(date) ASC
            """,
            (card_row["name"], ctype),
        )
    return cur.fetchall() or [card_row]


@st.cache_data(show_spinner=False)
def load_images(urls: Tuple[str, ...]) -> List[Image.Image]:
    """Download multiple images in parallel and cache the result."""

    def _fetch(u: str) -> Image.Image:
        resp = requests.get(u, timeout=30)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content))

    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL, len(urls))) as pool:
        return list(pool.map(_fetch, urls))


CARDS_KEY = "cards_data"
SELECTIONS_KEY = "picks"

st.set_page_config("Pokémon TCG – Deck Printing Picker", layout="wide")

st.title("Pokémon TCG Deck Printing Picker 🃏")
sub = (
    "Paste a Pokémon TCG deck list on the left, then pick the printing you want for each card. "
    "When you’re done, copy or download the regenerated deck-list!"
)
st.markdown(sub)

with st.sidebar:
    raw_deck = st.text_area("Deck list", "", height=400)
    rebuild = st.button("Parse / Rebuild UI ↻", use_container_width=True)


def _canonical_key(card_row: sqlite3.Row) -> Tuple[str, str]:
    """Return a key that uniquely identifies play-equivalent printings."""
    ctype = card_row["card_type"].lower()
    if ctype == "pokemon":
        raw = card_row["attacks"] or ""
        try:
            first_attack = raw.split("e': '", 1)[1].split("'", 1)[0].lower()
        except IndexError:
            first_attack = ""
        return (card_row["name"].lower(), first_attack)
    return (card_row["name"].lower(), ctype)


if rebuild or CARDS_KEY not in st.session_state:
    parsed_entries = parse_decklist(raw_deck)

    aggregated: Dict[Tuple[str, str], Dict[str, object]] = {}

    for entry in parsed_entries:
        base = fetch_printing(entry.set_code, entry.number)
        if base is None:
            st.warning(f"Not found in DB → {entry}")
            continue

        key = _canonical_key(base)

        if key not in aggregated:
            variations = fetch_related(base)
            aggregated[key] = {
                "entry": DeckEntry(entry.quantity, base["name"], "", ""),
                "variations": variations,
            }
        else:
            old_entry: DeckEntry = aggregated[key]["entry"]
            aggregated[key]["entry"] = old_entry._replace(
                quantity=old_entry.quantity + entry.quantity
            )
            seen = {(v["set_name"], v["number"]) for v in aggregated[key]["variations"]}
            for v in fetch_related(base):
                if (v["set_name"], v["number"]) not in seen:
                    aggregated[key]["variations"].append(v)

    cards_data: List[Tuple[DeckEntry, List[sqlite3.Row]]] = []
    for key in aggregated:
        rec = aggregated[key]
        rec_variations = list(reversed(rec["variations"]))

        rare_idx = _default_variation_index(rec_variations)
        if rare_idx > 0:
            rec_variations.insert(0, rec_variations.pop(rare_idx))

        cards_data.append((rec["entry"], rec_variations))

    default_picks: Dict[int, int] = {}
    for idx, (_, variations) in enumerate(cards_data):
        default_picks[idx] = _default_variation_index(variations)

    st.session_state[CARDS_KEY] = cards_data
    st.session_state[SELECTIONS_KEY] = default_picks


cards_data = st.session_state.get(CARDS_KEY, [])
selections: Dict[int, int] = st.session_state.get(SELECTIONS_KEY, {})

for idx, (entry, variations) in enumerate(cards_data):
    with st.expander(f"{entry.quantity}× {entry.name}", expanded=True):
        thumb_urls = tuple(row["img"] for row in variations)
        captions = [f"{row['set_name'].upper()} {row['number']}" for row in variations]
        thumb_imgs = load_images(thumb_urls)

        sel_idx = selections.get(idx, _default_variation_index(variations))

        st.image(
            thumb_imgs[sel_idx],
            width=MAIN_W,
            caption=captions[sel_idx],
        )

        picked_idx = image_select(
            label="Choose another printing",
            images=thumb_imgs,
            captions=captions,
            index=sel_idx,
            return_value="index",
            key=f"pick-{idx}",
            use_container_width=False,
        )

        if picked_idx is not None:
            sel_idx = picked_idx
        selections[idx] = sel_idx
        st.session_state[SELECTIONS_KEY] = selections



def build_deck() -> str:
    out: List[str] = []
    for idx, (entry, variations) in enumerate(cards_data):
        pick = selections.get(idx, 0)
        row = variations[pick]
        out.append(f"{entry.quantity} {entry.name} {row['set_name'].upper()} {row['number']}")
    return "\n".join(out)


st.markdown("---")
col_a, col_b = st.columns([3, 1])
with col_a:
    new_deck = build_deck()
    st.text_area("Updated deck list", new_deck, height=300)
with col_b:
    st.download_button("📄 Download", new_deck, "updated_decklist.txt", mime="text/plain")


@st.cache_resource(show_spinner=False)
def _close_conn():
    return conn
