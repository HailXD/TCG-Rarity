import sqlite3
import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple
import ast
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
SUPPORT_EXCLUSION = EXCLUSION + ["gallery", "secret"]
POKEMON_EXCLUSION = EXCLUSION + ["ultra"]

THUMB_W, MAIN_W = 110, 300
MAX_PARALLEL = 8
DB_PATH = Path("pokemon_cards.db")


class DeckEntry(NamedTuple):
    quantity: int
    name: str
    set_code: str
    number: str


LINE_RE = re.compile(
    r"""
    ^\s*
    (\d+)\s+
    (.*?)\s+
    ([A-Z0-9]+)\s+
    (\d+)\s*
    $
    """,
    re.VERBOSE,
)


def parse_decklist(raw: str) -> List[DeckEntry]:
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
    cur.execute(
        """
        SELECT * FROM cards
        WHERE (lower(set_code) = ? OR lower(set_name) = ?)
          AND number = ?
        LIMIT 1
        """,
        (set_code.lower(), set_code.lower(), number),
    )
    return cur.fetchone()


def fetch_related(card_row):
    ctype = (card_row["card_type"] or "").lower()
    if ctype == "pokemon":
        raw = card_row["attacks"] or ""
        raw2 = card_row["abilities"] or ""
        cur.execute(
            """
            SELECT * FROM cards
            WHERE name=? AND lower(card_type)='pokemon' AND lower(attacks) LIKE ? AND lower(abilities) LIKE ?
            ORDER BY julianday(date) ASC
            """,
            (card_row["name"], f"%{raw.lower()}%", f"%{raw2.lower()}%"),
        )
    else:
        cur.execute(
            """
            SELECT * FROM cards
            WHERE name=? ORDER BY julianday(date) ASC
            """,
            (card_row["name"],),
        )
    return cur.fetchall() or [card_row]


def _rarity_rank(rarity: str) -> int:
    rarity = rarity.lower()
    try:
        return RARITIES_ORDER.index(rarity)
    except ValueError:
        return -1


def _default_variation_index(variations: List[sqlite3.Row]) -> int:
    best_idx = 0
    best_rank = -1
    for i, row in enumerate(variations):
        rarity = (row["rarity"] or "").lower()
        ctype = (row["card_type"] or "").lower()
        if ctype in ["item", "pokemon tool", "stadium"] and rarity in ["common", "uncommon"]:
            return i
        if ctype == "item":
            continue
        exclusions = POKEMON_EXCLUSION if ctype == "pokemon" else SUPPORT_EXCLUSION
        if any(token in rarity for token in exclusions):
            continue
        rank = _rarity_rank(rarity)
        if rank > best_rank:
            best_idx = i
            best_rank = rank
    return best_idx


@st.cache_data(show_spinner=False)
def load_images(urls: Tuple[str, ...]) -> List[Image.Image]:
    def _fetch(u: str) -> Image.Image:
        resp = requests.get(u, timeout=30)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content))
    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL, len(urls))) as pool:
        return list(pool.map(_fetch, urls))


CARDS_KEY = "cards_data"
SELECTIONS_KEY = "picks"

st.set_page_config("TCG Picker", layout="wide")
st.title("TCG Picker")

with st.sidebar:
    json_input = st.text_area("Deck JSON", "", height=200)
    load_json = st.button("Load JSON ↻", use_container_width=True)
    if load_json:
        try:
            deck_dict = ast.literal_eval(json_input)
            raw = "\n".join(f"{v[0]} {k}" for k, v in deck_dict.items())
        except Exception:
            st.error("Invalid JSON")
            raw = ""
    else:
        raw = st.session_state.get("raw_deck_input", "")
    raw_deck = st.text_area("Deck list", raw, height=400, key="raw_deck_input")
    rebuild = st.button("Submit ↻", use_container_width=True)

cards_data = st.session_state.get(CARDS_KEY, [])
selections: Dict[int, int] = st.session_state.get(SELECTIONS_KEY, {})

if rebuild or CARDS_KEY not in st.session_state:
    parsed_entries = parse_decklist(raw_deck)
    aggregated: Dict[Tuple[str, ...], Dict[str, object]] = {}
    for entry in parsed_entries:
        base = fetch_printing(entry.set_code, entry.number)
        if base is None:
            st.warning(f"Not found in DB → {entry}")
            continue
        key = (base["name"].lower(),)
        if key not in aggregated:
            variations = fetch_related(base)
            aggregated[key] = {
                "entry": DeckEntry(entry.quantity, base["name"], base["set_code"], base["number"]),
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

for idx, (entry, variations) in enumerate(cards_data):
    if len(variations) == 1:
        row = variations[0]
        st.write(f"{entry.quantity}× {entry.name} — {row['set_name'].upper()} {row['number']}")
        selections[idx] = 0
        continue
    with st.expander(f"{entry.quantity}× {entry.name}", expanded=True):
        thumb_urls = [v["img"] for v in variations]
        captions    = [f"{v['set_name'].upper()} {v['number']}" for v in variations]
        default_idx = selections.get(idx, _default_variation_index(variations))
        img_placeholder = st.empty()
        img_placeholder.image(
            thumb_urls[default_idx],
            width=MAIN_W,
            caption=captions[default_idx],
        )
        picked = image_select(
            label="Choose another printing",
            images=thumb_urls,
            captions=captions,
            index=default_idx,
            return_value="index",
            key=f"pick-{idx}",
            use_container_width=False,
        )
        if picked is None:
            picked = default_idx
        selections[idx] = picked
        st.session_state[SELECTIONS_KEY] = selections
        img_placeholder.image(
            thumb_urls[picked],
            width=MAIN_W,
            caption=captions[picked],
        )


def _is_basic_energy_line(line: str) -> bool:
    if "energy" not in line.lower():
        return False
    if "basic" in line.lower():
        return True
    return LINE_RE.match(line) is None

def build_deck(raw_deck: str) -> str:
    out: List[str] = []
    for idx, (entry, variations) in enumerate(cards_data):
        pick = selections.get(idx, 0)
        row = variations[pick]
        out.append(f"{entry.quantity} {entry.name} {row['set_name'].upper()} {row['number']}")
    for line in raw_deck.splitlines():
        line = line.rstrip()
        if not line or not line[0].isdigit():
            continue
        if not _is_basic_energy_line(line):
            continue
        cleaned = re.sub(r"\s{2,}", " ", line.replace("Basic", "", 1)).strip()
        out.append(cleaned)
    return "\n".join(out)

st.markdown("---")
col_a, col_b = st.columns([3, 1])
with col_a:
    new_deck = build_deck(raw_deck)
    st.text_area("Updated deck list", new_deck, height=300)

@st.cache_resource(show_spinner=False)
def _close_conn():
    return conn
