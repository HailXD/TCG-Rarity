import sqlite3
import re
import os
from pprint import pprint

DB_FILE = 'pokemon_cards.db'
TABLE_NAME = 'cards'
DECK_LIST_INPUT = """Pokemon - 15
3 Iron Crown ex TEF 81
2 Iron Hands TEF 61
2 Iron Jugulis PAR 158
2 Iron Thorns TEF 62
2 Latias ex SSP 76
3 Miraidon TEF 121
1 Miraidon ex TEF 122
Trainer - 30
2 Ciphermaniac's Codebreaking PRE 104
3 Crispin PRE 105
2 Energy Retrieval SVI 171
2 Energy Search BCR 128
2 Energy Switch SSH 162
4 Future Booster Energy Capsule PAR 164
2 Larry's Skill PRE 115
3 Miriam SVI 179
1 Professor Turo's Scenario PAR 171
1 Professor's Research PAF 88
1 Reboot Pod TEF 158
2 Super Rod PAL 188
3 Techno Radar PAR 180
2 Trekking Shoes CRZ 145
Energy - 15
8 Basic Lightning Energy 12
5 Basic Psychic Energy 13
2 Double Turbo Energy BRS 151"""

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
    "Rare Ultra",
    "Rare Secret",
    "Rare Rainbow",
    "Rare Prism Star",
    "Radiant Rare",
    "Amazing Rare",
    "Double Rare",
    "Ultra Rare",
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

                candidate_cards = [card for card in matching_cards if not is_rarity_banned(card['rarity'])]
                if candidate_cards:
                    best_rarity_key = max(get_rarity_sort_key(card['rarity']) for card in candidate_cards)
                    best_candidates = [card for card in candidate_cards if get_rarity_sort_key(card['rarity']) == best_rarity_key]
                    
                    total_count = int(count)
                    if len(best_candidates) == 1:
                        chosen = best_candidates[0]
                        output_lines.append(f"{count} {card_name_from_db} {chosen['set_id']} {chosen['set_number']}")
                    else:
                        num_candidates = len(best_candidates)
                        base_count = total_count // num_candidates
                        remainder = total_count % num_candidates
                        for i, candidate in enumerate(best_candidates):
                            candidate_count = base_count + (1 if i < remainder else 0)
                            if candidate_count > 0:
                                output_lines.append(f"{candidate_count} {card_name_from_db} {candidate['set_id']} {candidate['set_number']}")
                else:
                    output_lines.append(original_line)
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
