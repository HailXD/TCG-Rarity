from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path
from typing import Iterable, List, NamedTuple, Sequence
import itertools
import datetime

RARITIES_ORDER = [
    'common', 'uncommon', 'rare', 'rare holo', 'promo', 'ultra rare', 'no rarity',
    'rainbow rare', 'rare holo ex', 'rare secret', 'shiny rare', 'holo rare v',
    'illustration rare', 'double rare', 'rare holo gx', 'special illustration rare',
    'holo rare vmax', 'trainer gallery holo rare', 'hyper rare', 'rare holo lv.x',
    'trainer gallery holo rare v', 'ace spec rare', 'rare shiny gx', 'holo rare vstar',
    'trainer gallery ultra rare', 'rare break', 'rare prism star', 'rare prime',
    'rare holo star', 'legend', 'rare shining', 'shiny rare v or vmax', 'radiant rare',
    'shiny ultra rare', 'trainer gallery secret rare', 'trainer gallery holo rare v or vmax',
    'amazing rare'
]

EXCLUSION = ['shiny', 'rainbow', 'hyper']
SUPPORT_EXCLUSION = EXCLUSION + ['gallery']
POKEMON_EXCLUSION = EXCLUSION + ['ultra']

LINE_RE = re.compile(r"""
    ^\s*
    (\d+)\s+          # quantity
    (.*?)\s+          # card name
    ([A-Z0-9]+)\s+    # set code
    (\d+)\s*          # card number
    $
""", re.VERBOSE)

class DeckEntry(NamedTuple):
    quantity: int
    name: str
    set_code: str
    number: str
    raw_line: str

def parse_decklist(lines: Iterable[str]) -> tuple[List[DeckEntry], List[str]]:
    """
    Return a list of *playable* card entries from a raw deck-list,
    and also collect any basic-energy lines so we can re-add them.
    """
    entries: List[DeckEntry] = []
    basic_energies: List[str] = []

    for raw in lines:
        line = raw.strip()
        if not line or not line[0].isdigit():
            continue
        
        if line.lower().split(' ')[-2] == "energy":
            basic_energies.append(line)
            continue

        match = LINE_RE.match(line)
        if not match:
            continue

        qty_str, name, set_code, card_no = match.groups()
        qty = int(qty_str)
        entries.append(DeckEntry(qty, name.strip(), set_code, card_no, raw))

    return entries, basic_energies

def get_rarity_rank(rarity: str) -> int:
    """
    Return the index of rarity in our RARITIES_ORDER,
    or -1 if not found (meaning we treat it as "lowest" or skip).
    """
    rarity = rarity.strip().lower()
    try:
        return RARITIES_ORDER.index(rarity)
    except ValueError:
        return -1

def contains_any(string: str, words: list[str]) -> bool:
    """Check if 'string' contains any of the items in 'words' as a substring."""
    s = string.lower()
    return any(w.lower() in s for w in words)

def select_preferred_printing(
    card_type: str,
    base_printing: sqlite3.Row,
    related_printings: list[sqlite3.Row]
) -> sqlite3.Row:
    """
    Given the card_type and the 'related_printings' (plus the base_printing itself),
    apply the filtering rules to pick the final printing we want in the deck:
    - filter out certain rarities (e.g. 'shiny', 'rainbow', 'hyper' for supporters/pokémon),
    - among what's left, pick the printing with the highest rarity rank
      (i.e. largest index in RARITIES_ORDER)
    - if there's a tie, pick the one with the latest date
      (sorted by real date from parse_card_date).
    """
    ctype = card_type.lower()

    if ctype == "special energy":
        return base_printing

    if ctype in ["stadium", "item", "pokemon tool"]:
        uncommons = [r for r in related_printings if r["rarity"].lower() in ["uncommon", "common"]]
        if uncommons:
            uncommons.sort(key=lambda r: r["date"])
            return uncommons[-1]
        else:
            related_printings.sort(key=lambda r: r["date"])
            return related_printings[-1]

    if ctype == "supporter":
        filtered = [r for r in related_printings
                    if not contains_any(r["rarity"], SUPPORT_EXCLUSION)]
        if not filtered:
            return base_printing
        filtered.sort(key=lambda r: (get_rarity_rank(r["rarity"]), r["date"]))
        return filtered[-1]

    if ctype == "pokemon":
        filtered = [r for r in related_printings
                    if not contains_any(r["rarity"], POKEMON_EXCLUSION)]
        if not filtered:
            return base_printing
        filtered.sort(key=lambda r: (get_rarity_rank(r["rarity"]), r["date"]))
        return filtered[-1]

    return base_printing

deck_text = '''Pokemon - 16
3 Iono's Bellibolt ex JTG 183
2 Iono's Kilowattrel JTG 55
3 Iono's Tadbulb JTG 52
2 Iono's Voltorb JTG 47
2 Iono's Wattrel JTG 54
1 Miraidon ex SVI 81
3 Raging Bolt ex TEF 123
Trainer - 30
2 Colress's Tenacity SFA 57
1 Counter Catcher PAR 160
3 Earthen Vessel PRE 106
1 Iono PAL 269
2 Jacq SVI 175
3 Levincia JTG 150
1 Nest Ball PAF 84
2 Professor Sada's Vitality PAR 256
3 Professor's Research PR-SW SWSH152
2 Rigid Band MEW 165
1 Scoop Up Cyclone PRE 128
2 Superior Energy Retrieval PAL 189
2 Switch SVI 194

Pokemon - 17
3 Croconaw TEF 40
3 Feraligatr TEF 41
2 Mimikyu PAL 97
2 Munkidori TWM 95
2 Relicanth TEF 84
4 Totodile TEF 39
Trainer - 34
2 Artazon PAF 76
2 Arven OBF 186
1 Boss’s Orders (Ghetsis) PAL 172
3 Colress's Tenacity SFA 57
3 Counter Catcher PAR 160
1 Crispin PRE 105
1 Earthen Vessel PRE 106
1 Grand Tree SCR 136
3 Iono PAL 269
3 Lana's Aid TWM 155
2 Luxurious Cape PAR 166
1 Night Stretcher SFA 61
4 Pokégear 3.0 SVI 186
2 Professor's Research PRE 125
1 Rescue Board PRE 126
Energy - 1
1 Luminous Energy PAL 191

Pokemon - 14
2 Cornerstone Mask Ogerpon ex TWM 112
1 Fezandipiti ex SFA 38
1 Lumineon V BRS 40
4 Okidogi TWM 111
4 Okidogi ex SFA 36
1 Pecharunt ex SFA 39
Trainer - 34
2 Arven OBF 186
1 Boss’s Orders (Ghetsis) PAL 172
4 Bravery Charm PAL 173
4 Crispin SCR 133
2 Earthen Vessel PAR 163
2 Energy Switch SVI 173
1 Hisuian Heavy Ball ASR 146
2 Janine's Secret Art SFA 59
2 Judge SVI 176
2 Lost Vacuum CRZ 135
4 Nest Ball PAF 84
1 Penny SVI 183
2 Switch SVI 194
Energy - 12
4 Luminous Energy PAL 191

Pokemon - 20
4 dedenne SIT 85
2 minun PAR 194
3 morpeko SIT 116
4 pikachu SIT 49
2 plusle PAR 193
4 togedemaru SIT 127

Trainer - 30
3 arven PAF 235
3 beach court SVI 167
2 boss's orders PAL 265
3 buddy-buddy poffin PRE 101
2 clemont's quick wit SSP 243
4 defiance band SVI 169
2 earthen vessel PRE 106
3 electric generator PAF 79
2 lana's aid TWM 219
2 nemona PAF 238
4 nest ball PAF 84'''


lines = deck_text.strip().splitlines()
entries, basic_energy_lines = parse_decklist(lines)

conn = sqlite3.connect("pokemon_cards.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

deck_counts = {}

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

for entry in entries:
    printing = fetch_printing(entry.set_code, entry.number)
    if not printing:
        continue

    related = fetch_related(printing)

    if printing not in related:
        related = list(related) + [printing]

    final_row = select_preferred_printing(
        printing["card_type"], printing, related
    )

    final_name = final_row["name"]
    final_set = final_row["set_name"]
    final_num = final_row["number"]
    final_type = final_row["card_type"].lower()

    key = (final_name, final_set, final_num, final_type)
    deck_counts[key] = deck_counts.get(key, 0) + entry.quantity

conn.close()

def get_section(ctype: str) -> str:
    ctype = ctype.lower()
    if ctype == "pokemon":
        return "Pokemon"
    elif ctype == "energy" or ctype == "special energy":
        return "Energy"
    else:
        return "Trainer"

final_list = []
for (name, set_name, number, ctype), q in deck_counts.items():
    final_list.append((get_section(ctype), q, name, set_name, number, ctype))

SECTION_ORDER = ["Pokemon", "Trainer", "Energy"]

def section_sort_key(tup):
    try:
        idx = SECTION_ORDER.index(tup[0])
    except ValueError:
        idx = 999
    return (idx, tup[2])

final_list.sort(key=section_sort_key)

from collections import defaultdict
grouped = defaultdict(list)
for section, q, name, sname, num, ctype in final_list:
    grouped[section].append((q, name, sname, num))

for be_line in basic_energy_lines:
    qty = int(be_line.split(' ')[0])
    items = ' '.join(be_line.split(' ')[1:])
    grouped["Energy"].append((qty, f"{items.replace('Basic ', '')}", "", ""))

output_lines = []
for section_name in SECTION_ORDER:
    if section_name not in grouped:
        continue
    lines_for_section = grouped[section_name]
    total_count = sum(x[0] for x in lines_for_section)
    output_lines.append(f"{section_name} - {total_count}")
    for (q, name, sname, num) in lines_for_section:
        if sname and num:
            output_lines.append(f"{q} {name} {sname.upper()} {num.upper()}")
        else:
            output_lines.append(f"{q} {name}")
    output_lines.append("")

final_decklist = "\n".join(output_lines).strip("\n")
print(final_decklist)
