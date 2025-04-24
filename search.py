import re
import sqlite3
from typing import Iterable, List, NamedTuple
import json 

deck = '''Pokemon - 23
4 Flaaffy SIT 3
4 Mareep LOT 75
2 Octillery BRS 3
1 Radiant Greninja ASR 46
4 Rayquaza V EVS 194
4 Rayquaza VMAX SIT 20
2 Remoraid BST 36
1 Sylveon V EVS 184
1 Sylveon V BRS 14
Trainer - 24
1 Earthen Vessel SFA 96
4 Korrina's Focus BST 160
2 Lysandre FLF 104
2 Marnie PR-SW SWSH121
2 Pokémon Communication HS 98
1 Professor's Research PR-SW SWSH152
4 Quick Ball SSH 216
1 Sabrina's Suggestion TEU 181
3 Tower of Waters BST 138
2 Ultra Ball PLF 122
1 Ultra Ball SUM 161
1 Ultra Ball BRS 186
Energy - 13
6 Fire Energy 10
7 Lightning Energy 135'''

rarities = ['common', 'uncommon', 'rare', 'rare holo', 'promo', 'ultra rare', 'no rarity', 'rainbow rare', 'rare holo ex', 'rare secret', 'shiny rare', 'holo rare v', 'illustration rare', 'double rare', 'rare holo gx', 'special illustration rare', 'holo rare vmax', 'trainer gallery holo rare', 'hyper rare', 'rare holo lv.x', 'trainer gallery holo rare v', 'ace spec rare', 'rare shiny gx', 'holo rare vstar', 'trainer gallery ultra rare', 'rare break', 'rare prism star', 'rare prime', 'rare holo star', 'legend', 'rare shining', 'shiny rare v or vmax', 'radiant rare', 'shiny ultra rare', 'trainer gallery secret rare', 'trainer gallery holo rare v or vmax', 'amazing rare']
exclusion = ['shiny', 'rainbow', 'hyper']
pokemon_exclusion = exclusion + ['ultra']

class DeckEntry(NamedTuple):
    quantity: int
    name: str
    set_code: str
    number: str


LINE_RE = re.compile(r"""
    ^\s*
    (\d+)\s+
    (.*?)\s+
    ([A-Z0-9]+)\s+
    (\d+)\s*
    $
""", re.VERBOSE)


def parse_decklist(lines: Iterable[str]) -> List[DeckEntry]:
    """Return a list of *playable* card entries from a raw deck‑list."""
    entries: List[DeckEntry] = []

    for raw in lines:
        line = raw.strip()
        if not line or not line[0].isdigit():
            continue

        match = LINE_RE.match(line)
        if not match:
            continue

        qty, name, set_code, card_no = match.groups()

        if set_code.lower() == "energy":
            continue

        entries.append(DeckEntry(int(qty), name.strip(), set_code, card_no))

    return entries


def fetch_printing(set_code: str, card_no: str) -> sqlite3.Row | None:
    cur.execute(
        "SELECT * FROM cards WHERE lower(set_name) = ? AND number = ? LIMIT 1",
        (set_code.lower(), card_no),
    )
    return cur.fetchone()

def fetch_related(card_row: sqlite3.Row) -> list[sqlite3.Row]:
    ctype = card_row["card_type"].lower()

    if ctype == "pokemon":
        first_attack = ""
        raw = card_row["attacks"]
        
        first_attack = raw.split("e': '", 1)[1].split("'", 1)[0]

        cur.execute(
            """
            SELECT *
            FROM cards
            WHERE name            = ?
                AND lower(card_type) = 'pokemon'
                AND lower(attacks)   LIKE ?
            ORDER BY julianday(date) ASC
            """,
            (card_row["name"], f"%{first_attack}%"),
        )
    
    else:
        cur.execute(
            """
            SELECT *
            FROM cards
            WHERE name              = ?
              AND lower(card_type)  = ?
            ORDER BY julianday(date) ASC
            """,
            (card_row["name"], ctype),
        )

    return cur.fetchall()



def print_row(row: sqlite3.Row) -> None:
    """Pretty-print a *cards* table row as a single line."""
    fields = (
        row["name"],
        row["card_type"],
        f"HP {row['hp']}" if row["card_type"].lower() == "pokemon" else None,
        row["regulation"],
        row["rarity"],
        row["set_name"].upper(),
        row["date"],
        row["number"],
        row["img"],
    )
    print("    " + " | ".join(str(f) for f in fields if f is not None))

entries = parse_decklist(deck.splitlines())
conn = sqlite3.connect("pokemon_cards.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

for qty, name, set_code, card_no in entries:
    header = f"{qty} {name} {set_code} {card_no}"
    print(header)
    printing = fetch_printing(set_code, card_no)
    if printing is None:
        print("    → printing not found in database (check set code & number)")
        print(set_code.lower(), card_no)
        continue

    related = fetch_related(printing)
    for row in related:
        print_row(row)
    print()

conn.close()
