# deck_webui.py
# ------------------------------------------------------------
# A pure‑Python Streamlit web UI for selecting alternate printings
# for a Pokémon TCG deck‑list. Paste a deck‑list, inspect the card
# images pulled from your local **pokemon_cards.db** SQLite DB, and
# swap any printing simply by clicking its thumbnail. When you’re
# done, copy the regenerated deck‑list that matches your selections.
#
# -- Requirements --
#   pip install streamlit pillow streamlit-image-select
# ------------------------------------------------------------

from __future__ import annotations

import re
import sqlite3
import textwrap
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple

import requests
import streamlit as st
from PIL import Image

# ------------------------------------------------------------------
# Mandatory dependency: streamlit‑image‑select for a slick tile picker
# ------------------------------------------------------------------
try:
    from streamlit_image_select import image_select  # type: ignore
except ModuleNotFoundError:
    st.error(
        "Missing required package **streamlit-image-select**. Install it with:\n    pip install streamlit-image-select"
    )
    st.stop()

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
DB_PATH = Path("pokemon_cards.db")  # adjust if your DB lives elsewhere
THUMB_W, MAIN_W = 110, 300          # thumbnail & main‑image widths (px)
MAX_PARALLEL = 8                    # concurrent download workers

# ------------------------------------------------------------
# Helpers for deck parsing & DB access
# ------------------------------------------------------------
class DeckEntry(NamedTuple):
    quantity: int
    name: str
    set_code: str
    number: str


LINE_RE = re.compile(
    r"""
    ^\s*
    (\d+)\s+            # quantity
    (.*?)\s+             # card name (greedy, stops at 2nd whitespace zone)
    ([A-Z0-9]+)\s+       # set code
    (\d+)\s*            # card number
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

# ------------------------------------------------------------
# DB helpers – using the schema implied by the question
# ------------------------------------------------------------
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()


def fetch_printing(set_code: str, number: str):
    cur.execute(
        "SELECT * FROM cards WHERE lower(set_name) = ? AND number = ? LIMIT 1",
        (set_code.lower(), number),
    )
    return cur.fetchone()


def fetch_related(card_row):
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

# ------------------------------------------------------------
# Parallel image fetching (cached)
# ------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_images(urls: Tuple[str, ...]) -> List[Image.Image]:
    """Download multiple images in parallel and cache the result."""

    def _fetch(u: str) -> Image.Image:
        resp = requests.get(u, timeout=30)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content))

    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL, len(urls))) as pool:
        return list(pool.map(_fetch, urls))

# ------------------------------------------------------------
# Session‑state keys
# ------------------------------------------------------------
CARDS_KEY = "cards_data"
SELECTIONS_KEY = "picks"

# ------------------------------------------------------------
# Streamlit Layout
# ------------------------------------------------------------
st.set_page_config("Pokémon TCG – Deck Printing Picker", layout="wide")

st.title("Pokémon TCG Deck Printing Picker 🃏")
sub = (
    "Paste a Pokémon TCG deck list on the left, then pick the printing you want for each card. "
    "When you’re done, copy or download the regenerated deck‑list!"
)
st.markdown(sub)

with st.sidebar:
    sample_deck = textwrap.dedent(
        """
            Pokemon - 15
            1 Iono's Bellibolt ex JTG 183
            Trainer - 34
            1 Boss’s Orders (Ghetsis) PAL 172
            1 Boss’s Orders (Ghetsis) PAL 172
        """
    ).strip()

    raw_deck = st.text_area("Deck list", sample_deck, height=400)
    rebuild = st.button("Parse / Rebuild UI ↻", use_container_width=True)

# ------------------------------------------------------------
# Build data structures
# ------------------------------------------------------------
if rebuild or CARDS_KEY not in st.session_state:
    entries = parse_decklist(raw_deck)
    uniq: Dict[str, DeckEntry] = {}
    for e in entries:
        k = f"{e.name}|{e.set_code}|{e.number}"
        if k in uniq:
            uniq[k] = uniq[k]._replace(quantity=uniq[k].quantity + e.quantity)
        else:
            uniq[k] = e

    cards_data: List[Tuple[DeckEntry, List[sqlite3.Row]]] = []
    for entry in uniq.values():
        base = fetch_printing(entry.set_code, entry.number)
        if base is None:
            st.warning(f"Not found in DB → {entry}")
            continue
        cards_data.append((entry, fetch_related(base)))

    st.session_state[CARDS_KEY] = cards_data
    st.session_state[SELECTIONS_KEY] = {i: 0 for i in range(len(cards_data))}

cards_data = st.session_state.get(CARDS_KEY, [])
selections = st.session_state.get(SELECTIONS_KEY, {})

# ------------------------------------------------------------
# Interactive card pickers – sections expanded by default
# ------------------------------------------------------------
for idx, (entry, variations) in enumerate(cards_data):
    with st.expander(f"{entry.quantity}× {entry.name}", expanded=True):
        thumb_urls = tuple(row["img"] for row in variations)
        captions   = [f"{row['set_name'].upper()} {row['number']}" for row in variations]

        # Parallel fetch (cached) of all thumbnails
        thumb_imgs = load_images(thumb_urls)

        # Display current choice
        sel_idx = selections.get(idx, 0)
        st.image(
            thumb_imgs[sel_idx],
            width=MAIN_W,
            caption=captions[sel_idx],
        )

        # Image picker – click thumbnail to choose
        picked_idx = image_select(
            label="Choose another printing",
            images=thumb_imgs,
            captions=captions,
            index=sel_idx,
            return_value="index",
            key=f"pick-{idx}",
            use_container_width=False,
        )

        if picked_idx is not None and picked_idx != sel_idx:
            selections[idx] = picked_idx
            st.session_state[SELECTIONS_KEY] = selections
            st.experimental_rerun()

# ------------------------------------------------------------
# Output deck list
# ------------------------------------------------------------

def build_deck() -> str:
    out: List[str] = []
    for idx, (entry, variations) in enumerate(cards_data):
        row = variations[selections.get(idx, 0)]
        out.append(f"{entry.quantity} {entry.name} {row['set_name'].upper()} {row['number']}")
    return "\n".join(out)

st.markdown("---")
col_a, col_b = st.columns([3, 1])
with col_a:
    new_deck = build_deck()
    st.text_area("Updated deck list", new_deck, height=300)
with col_b:
    st.download_button("📄 Download", new_deck, "updated_decklist.txt", mime="text/plain")

# ------------------------------------------------------------
# Close connection on app shutdown
# ------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _close_conn():
    return conn
