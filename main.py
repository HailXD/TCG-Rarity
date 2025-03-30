import sqlite3
import re
import os

DB_FILE = 'pokemon_cards.db'
TABLE_NAME = 'cards'
DECK_LIST_INPUT = """Pokemon - 15
3 Archaludon ex SSP 224
3 Duraludon SCR 106
1 Fezandipiti ex SFA 38
2 Munkidori PRE 44
1 Relicanth TEF 84
1 Scizor OBF 205
1 Scizor PAF 191
1 Scyther OBF 4
1 Scyther TEF 1
1 Squawkabilly ex PAL 247
Trainer - 35
1 Black Belt's Training PRE 97
3 Boss’s Orders (Ghetsis) PAL 172
2 Calamitous Snowy Mountain PAL 174
3 Earthen Vessel PAR 163
3 Iono PAL 185
1 Kieran TWM 154
3 Nest Ball SVI 181
4 Night Stretcher SFA 61
1 Pal Pad SVI 182
3 Pokégear 3.0 SSH 174
3 Professor Turo's Scenario PRE 121
1 Professor's Research PAF 88
1 Professor's Research PAF 87
1 Professor's Research PRE 124
1 Secret Box TWM 163
1 Ultra Ball PAF 91
3 Ultra Ball SVI 196
Energy - 10
2 Basic Darkness Energy 15
8 Basic Metal Energy 16"""

RARITY_ORDER = [
    "None",
    "Promo",
    "Common",
    "Uncommon",
    "Rare",
    "Rare Holo",
    "Rare Shining",
    "Rare Holo EX",
    "Rare Holo Star",
    "Rare Holo LV.X",
    "Rare Prime",
    "Rare ACE",
    "Rare BREAK",
    "Rare Holo GX",
    "Rare Shiny GX",
    "Rare Holo V",
    "Rare Holo VMAX",
    "Rare Holo VSTAR",
    "Ultra Rare",
    "Rare Ultra",
    "Rare Secret",
    "Rare Rainbow",
    "Rare Prism Star",
    "Radiant Rare",
    "Amazing Rare",
    "Double Rare",
    "Illustration Rare",
    "Trainer Gallery Rare Holo",
    "Special Illustration Rare",
    "Hyper Rare",
    "Rare Shiny",
    "Shiny Rare",
    "Shiny Ultra Rare",
    "ACE SPEC Rare",
    "Classic Collection",
    "LEGEND"
]
RARITY_MAP = {rarity: index for index, rarity in enumerate(RARITY_ORDER)}

BANNED_RARITY_WORDS = ["Hyper", "Secret", "Shiny", "Rainbow"]

def get_rarity_sort_key(rarity_str):
    """Gets the sort key for a given rarity string."""
    if rarity_str is None:
        rarity_str = "None"
    return RARITY_MAP.get(rarity_str, -1)

def is_rarity_banned(rarity_str):
    """Checks if a rarity string contains any banned words."""
    if rarity_str is None:
        return False
    return any(banned in rarity_str for banned in BANNED_RARITY_WORDS)

def process_deck_list(deck_content, db_path):
    if not os.path.exists(db_path):
        return f"Error: Database file not found at {db_path}"

    output_lines = []
    lines = deck_content.strip().split('\n')

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if re.match(r"^\s*(Pokemon|Trainer|Energy)\s*-\s*\d+\s*$", line, re.IGNORECASE):
                output_lines.append(line)
                continue

            basic_energy_match = re.match(r"^\s*(\d+)\s+Basic\s+(.+?)\s+Energy(?:\s+(\d+))?\s*$", line, re.IGNORECASE)
            if basic_energy_match:
                count = basic_energy_match.group(1)
                energy_type = basic_energy_match.group(2)
                output_lines.append(f"{count} {energy_type} Energy")
                continue

            card_match = re.match(r"^\s*(\d+)\s+(.+?)\s+([A-Z0-9-]+)\s+([A-Za-z0-9]+)\s*$", line)
            if card_match:
                count = card_match.group(1)
                name = card_match.group(2).strip()
                set_id = card_match.group(3)
                set_number = card_match.group(4)
                original_line = f"{count} {name} {set_id} {set_number}"

                cursor.execute(
                    f"SELECT name, supertype, attacks, rules FROM {TABLE_NAME} WHERE set_id = ? AND set_number = ?",
                    (set_id, set_number)
                )
                initial_card_data = cursor.fetchone()

                if not initial_card_data:
                    output_lines.append(original_line)
                    continue

                card_name_from_db = initial_card_data['name']
                supertype = initial_card_data['supertype']

                if supertype == "Pokémon":
                    identifier_column = "attacks"
                    identifier_value = initial_card_data['attacks']
                    if identifier_value is None:
                        query = f"SELECT set_id, set_number, rarity FROM {TABLE_NAME} WHERE name = ? AND {identifier_column} IS NULL"
                        params = (card_name_from_db,)
                    else:
                        query = f"SELECT set_id, set_number, rarity FROM {TABLE_NAME} WHERE name = ? AND {identifier_column} = ?"
                        params = (card_name_from_db, identifier_value)
                elif supertype == "Trainer":
                    cleaned_name = re.sub(r'\s*\(.*?\)', '', card_name_from_db).strip()
                    query = f"SELECT set_id, set_number, rarity FROM {TABLE_NAME} WHERE name LIKE ?"
                    params = (cleaned_name + '%',)
                    card_name_from_db = cleaned_name
                else:
                    output_lines.append(original_line)
                    continue

                cursor.execute(query, params)
                matching_cards = cursor.fetchall()

                if not matching_cards:
                    output_lines.append(original_line)
                    continue

                sorted_cards = sorted(
                    matching_cards,
                    key=lambda card: get_rarity_sort_key(card['rarity'])
                )

                best_set_id = set_id
                best_set_number = set_number

                for card in reversed(sorted_cards):
                    card_rarity = card['rarity']
                    if not is_rarity_banned(card_rarity):
                        best_set_id = card['set_id']
                        best_set_number = card['set_number']
                        break

                updated_line = f"{count} {card_name_from_db} {best_set_id} {best_set_number}"
                output_lines.append(updated_line)
            else:
                output_lines.append(line)

    except sqlite3.Error as e:
        return f"Database error: {e}"
    finally:
        if conn:
            conn.close()

    return "\n".join(output_lines)


def compile_and_sort_deck_list(processed_deck, db_path=DB_FILE):
    lines = processed_deck.strip().split("\n")
    compiled = {'Pokémon': {}, 'Trainer': {}, 'Energy': {}}

    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
    else:
        conn = None
        cursor = None

    for line in lines:
        card_match = re.match(r"^(\d+)\s+(.+)$", line)
        if card_match:
            count = int(card_match.group(1))
            card_details = card_match.group(2).strip()

            if "Energy" in card_details:
                category = "Energy"
            elif cursor:
                parts = card_details.split()
                if len(parts) >= 3:
                    possible_set_number = parts[-1]
                    possible_set_id = parts[-2]
                    cursor.execute(
                        f"SELECT supertype FROM {TABLE_NAME} WHERE set_id = ? AND set_number = ?",
                        (possible_set_id, possible_set_number)
                    )
                    row = cursor.fetchone()
                    if row:
                        category = row['supertype']
                    else:
                        category = "Trainer"
                else:
                    category = "Trainer"
            else:
                category = "Trainer"

            if card_details in compiled.get(category, {}):
                compiled[category][card_details] += count
            else:
                compiled[category][card_details] = count

    if conn:
        conn.close()

    output_lines = []
    for cat in ['Pokémon', 'Trainer', 'Energy']:
        sorted_cards = sorted(compiled[cat].items(), key=lambda x: x[0])
        total_count = sum(count for _, count in sorted_cards)
        output_lines.append(f"{cat} - {total_count}")
        for card_info, count in sorted_cards:
            output_lines.append(f"{count} {card_info}")
    return "\n".join(output_lines)


if __name__ == "__main__":
    processed_deck = process_deck_list(DECK_LIST_INPUT, DB_FILE)
    compiled_sorted_deck = compile_and_sort_deck_list(processed_deck)
    print(compiled_sorted_deck)
