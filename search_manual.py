import re
import sqlite3
from typing import Iterable, List, NamedTuple

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
        entries.append(DeckEntry(int(qty_str), name.strip(), set_code, card_no, raw))

    return entries, basic_energies


def get_rarity_rank(rarity: str) -> int:
    rarity = rarity.strip().lower()
    try:
        return RARITIES_ORDER.index(rarity)
    except ValueError:
        return -1


def contains_any(string: str, words: list[str]) -> bool:
    s = string.lower()
    return any(w.lower() in s for w in words)


def select_preferred_printing(
    card_type: str,
    base_printing: sqlite3.Row,
    related_printings: list[sqlite3.Row]
) -> sqlite3.Row:
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
        filtered = [r for r in related_printings if not contains_any(r["rarity"], SUPPORT_EXCLUSION)]
        if not filtered:
            return base_printing
        filtered.sort(key=lambda r: (get_rarity_rank(r["rarity"]), r["date"]))
        return filtered[-1]

    if ctype == "pokemon":
        filtered = [r for r in related_printings if not contains_any(r["rarity"], POKEMON_EXCLUSION)]
        if not filtered:
            return base_printing
        filtered.sort(key=lambda r: (get_rarity_rank(r["rarity"]), r["date"]))
        return filtered[-1]

    return base_printing


def print_option(idx: int, row: sqlite3.Row) -> None:
    """Print a numbered option for selection."""
    card_no = f"{row['set_code']}-{row['number']}"
    print(
        f"    {idx:>{IDX_WIDTH}}. "
        f"{row['rarity']:<{RARITY_WIDTH}} | "
        f"{row['set_name'].upper():<{SET_NAME_WIDTH}} | "
        f"{row['number']:<{NUMBER_WIDTH}} | "
        f"{row['date']:<{DATE_WIDTH}} | "
        f"{row['img']:<{IMG_WIDTH}} | "
        f"{card_no}"
    )


def main():
    deck_text = '''Pokemon - 15
1 Iono's Bellibolt ex JTG 183
2 Iono's Bellibolt ex JTG 53
2 Iono's Kilowattrel JTG 55
3 Iono's Tadbulb JTG 52
1 Iono's Voltorb JTG 47
2 Iono's Wattrel JTG 54
3 Raging Bolt ex TEF 123
1 Squawkabilly ex PAL 169
Trainer - 34
2 Boss’s Orders (Ghetsis) PAL 172
1 Boss’s Orders (Ghetsis) PAL 172
1 Buddy-Buddy Poffin PRE 101
3 Earthen Vessel PRE 106
3 Energy Switch SVI 173
1 Iono PAF 80
2 Iono PAF 80
3 Levincia JTG 150
3 Nest Ball PAF 84
2 Night Stretcher SFA 61
2 Professor Sada's Vitality PRE 120
3 Professor's Research PRE 125
2 Superior Energy Retrieval PAL 189
2 Ultra Ball PAF 91'''

    lines = deck_text.strip().splitlines()
    entries, basic_energy_lines = parse_decklist(lines)

    conn = sqlite3.connect("pokemon_cards.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    deck_counts: dict[tuple[str, str, str, str], int] = {}

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
        base = fetch_printing(entry.set_code, entry.number)
        if not base:
            print(f"Warning: Base printing not found for {entry.name} {entry.set_code} {entry.number}")
            continue

        related = fetch_related(base)
        options = list(related)
        if base not in related:
            options.append(base)

        # Compute column widths based on longest values
        global IDX_WIDTH, RARITY_WIDTH, SET_NAME_WIDTH, NUMBER_WIDTH, DATE_WIDTH, IMG_WIDTH
        IDX_WIDTH = len(str(len(options)))
        RARITY_WIDTH = max(len(r["rarity"]) for r in options)
        SET_NAME_WIDTH = max(len(r["set_name"].upper()) for r in options)
        NUMBER_WIDTH = max(len(r["number"]) for r in options)
        DATE_WIDTH = max(len(r["date"]) for r in options)
        IMG_WIDTH = max(len(r["img"]) for r in options)

        print(f"Select printing for {entry.name} ({entry.set_code} {entry.number}):")
        for idx, opt in enumerate(options, 1):
            print_option(idx, opt)

        default_row = select_preferred_printing(base["card_type"], base, options)
        default_idx = options.index(default_row) + 1
        if len(options) == 1:
            choice = '1'
        else:
            choice = input(f"Enter choice [default {default_idx}]: ").strip()
        try:
            selected_idx = int(choice) if choice else default_idx
        except ValueError:
            selected_idx = default_idx

        if not 1 <= selected_idx <= len(options):
            print(f"Invalid choice, using default {default_idx}.")
            selected_idx = default_idx

        final = options[selected_idx - 1]
        key = (final["name"], final["set_name"], final["number"], final["card_type"].lower())
        deck_counts[key] = deck_counts.get(key, 0) + entry.quantity

    conn.close()

    def get_section(ctype: str) -> str:
        ct = ctype.lower()
        if ct == "pokemon": return "Pokemon"
        if ct in ("energy", "special energy"): return "Energy"
        return "Trainer"

    final_list = [(get_section(t[3]), q, t[0], t[1], t[2]) for t,q in deck_counts.items()]
    SECTION_ORDER = ["Pokemon", "Trainer", "Energy"]
    final_list.sort(key=lambda x: (SECTION_ORDER.index(x[0]) if x[0] in SECTION_ORDER else 999, x[2]))

    from collections import defaultdict
    grouped = defaultdict(list)
    for section, q, name, sname, num in final_list:
        grouped[section].append((q, name, sname, num))
    for be_line in basic_energy_lines:
        qty = int(be_line.split(' ')[0])
        items = ' '.join(be_line.split(' ')[1:])
        grouped['Energy'].append((qty, items.replace('Basic ', ''), '', ''))

    for sect in SECTION_ORDER:
        if sect not in grouped: continue
        lines = grouped[sect]
        total = sum(x[0] for x in lines)
        print(f"{sect} - {total}")
        for q,name,snum,num in lines:
            if snum and num:
                print(f"{q} {name} {snum.upper()} {num.upper()}")
            else:
                print(f"{q} {name}")
        print()

if __name__ == "__main__":
    main()
