import sqlite3
import re
import os
from pprint import pprint

DB_FILE = 'pokemon_cards.db'
TABLE_NAME = 'cards'
DECK_LIST_INPUT = """Pokemon - 18
2 Budew PRE 4
3 Charizard ex PAF 234
3 Charmander MEW 168
1 Charmeleon PAF 110
1 Dusclops SFA 69
2 Dusknoir SFA 70
2 Duskull SFA 68
1 Fezandipiti ex SFA 92
1 Munkidori SFA 72
1 Pecharunt ex PRE 163
1 Squawkabilly ex PAL 264
Trainer - 35
1 Artazon OBF 229
4 Arven PAF 235
2 Binding Mochi SFA 55
1 Boss's Orders RCL 189
4 Buddy-Buddy Poffin TWM 223
2 Carmine TWM 217
1 Counter Catcher PAR 264
1 Defiance Band SVI 169
1 Earthen Vessel SFA 96
2 Iono PAL 269
2 Nest Ball SVI 255
1 Pal Pad SSH 172
1 Pokémon League Headquarters OBF 192
1 Prime Catcher TEF 157
4 Rare Candy PLB 105
2 Super Rod PAL 276
1 Technical Machine: Evolution PAR 178
4 Ultra Ball PLF 122
Energy - 7
1 Basic Darkness Energy 98
6 Basic Fire Energy 230"""

RARITY_ORDER = [
    "None",
    "Common",
    "Uncommon",
    "Promo",
    "Rare",
    "Rare Holo",
    "Trainer Gallery Rare Holo",
    "Rare Holo V",
    "Rare Holo VSTAR",
    "Rare Holo VMAX",
    "Rare BREAK",
    "Rare Prime",
    "Rare Holo GX",
    "Rare Holo EX",
    "Rare Shining",
    "Rare Holo Star",
    "Rare Holo LV.X",
    "Rare Ultra",
    "Double Rare",
    "Rare ACE",
    "ACE SPEC Rare",
    "Rare Shiny",
    "Shiny Rare",
    "Rare Shiny GX",
    "Rare Prism Star",
    "Amazing Rare",
    "Radiant Rare",
    "Ultra Rare",
    "Hyper Rare",
    "Rare Rainbow",
    "Illustration Rare",
    "Special Illustration Rare",
    "Shiny Ultra Rare",
    "Classic Collection",
    "Rare Secret",
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
                    f"SELECT name, supertype, subtypes, attacks, rules FROM {TABLE_NAME} WHERE set_id = ? AND set_number = ?",
                    (set_id, set_number)
                )
                initial_card_data = cursor.fetchone()

                if not initial_card_data:
                    output_lines.append(original_line)
                    continue

                card_name_from_db = initial_card_data['name']
                supertype = initial_card_data['supertype']
                subtype = initial_card_data['subtypes']
                if supertype == "Pokémon":
                    identifier_column = "attacks"
                    identifier_value = initial_card_data['attacks']
                    if identifier_value is None:
                        query = f"SELECT set_id, set_number, rarity FROM {TABLE_NAME} WHERE name = ? AND {identifier_column} IS NULL"
                        params = (card_name_from_db,)
                    else:
                        query = f"SELECT set_id, set_number, rarity FROM {TABLE_NAME} WHERE name = ? AND {identifier_column} = ?"
                        params = (card_name_from_db, identifier_value)
                elif supertype == "Energy":
                    cleaned_name = re.sub(r'\s*\(.*?\)', '', card_name_from_db).strip()
                    output_lines.append(f"{count} {cleaned_name}")
                    continue
                elif 'Item' in subtype:
                    cleaned_name = re.sub(r'\s*\(.*?\)', '', card_name_from_db).strip()
                    output_lines.append(f"{count} {cleaned_name}")
                    continue
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

def compile_and_sort_deck_list(processed_deck):
    lines = processed_deck.strip().split("\n")
    compiled = {}
    category_order = []
    current_category = None

    for line in lines:
        header_match = re.match(r"^(Pokemon|Trainer|Energy)\s*-\s*\d+\s*$", line, re.IGNORECASE)
        if header_match:
            current_category = header_match.group(1)
            if current_category not in compiled:
                compiled[current_category] = {}
                category_order.append(current_category)
        else:
            card_match = re.match(r"^(\d+)\s+(.+)$", line)
            if card_match and current_category is not None:
                count = int(card_match.group(1))
                card_info = card_match.group(2).strip()
                if card_info in compiled[current_category]:
                    compiled[current_category][card_info] += count
                else:
                    compiled[current_category][card_info] = count

    output_lines = []
    for cat in category_order:
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
