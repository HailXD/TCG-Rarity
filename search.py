import re
import sqlite3
from typing import Iterable, List, NamedTuple

deck = '''Pokemon - 15
3 Iono's Bellibolt ex JTG 53
3 Iono's Kilowattrel JTG 55
3 Iono's Tadbulb JTG 52
2 Iono's Voltorb JTG 47
3 Iono's Wattrel JTG 54
1 Skwovet SVI 151
Trainer - 28
3 Boss’s Orders (Ghetsis) PAL 172
2 Brock's Scouting JTG 146
4 Buddy-Buddy Poffin TEF 144
1 Counter Catcher PAR 160
4 Iono PAL 185
3 Levincia JTG 150
1 Nest Ball SVI 181
2 Night Stretcher SFA 61
1 Prime Catcher TEF 157
3 Superior Energy Retrieval PAL 189
4 Ultra Ball SVI 196
Energy - 17
17 Basic Lightning Energy 12'''

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
