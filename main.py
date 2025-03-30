import sqlite3
import re
import os

DB_FILE = 'pokemon_cards.db'
TABLE_NAME = 'cards'
DECK_LIST_INPUT = """Pokemon - 15
1 Umbreon VMAX BRS TG23
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
    "Ultra Rare",
    "Rare Ultra",
    "Rare Secret",
    "Rare Rainbow",
    "Rare Prism Star",
    "Radiant Rare",
    "Amazing Rare",
    "Double Rare",
    "Illustration Rare",
    "Special Illustration Rare",
    "Hyper Rare",
    "Rare Shiny",
    "Shiny Rare",
    "Shiny Ultra Rare",
    "ACE SPEC Rare",
    "Classic Collection",
    "Trainer Gallery Rare Holo",
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
    """
    Processes the deck list to find the rarest legal printings.

    Args:
        deck_content (str): The deck list as a multi-line string.
        db_path (str): The path to the SQLite database file.

    Returns:
        str: The processed deck list with updated card codes.
    """
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
                energy_num = basic_energy_match.group(3)
                if energy_num:
                     output_lines.append(f"{count} {energy_type} Energy {energy_num}")
                else:
                     output_lines.append(f"{count} {energy_type} Energy")
                continue

            card_match = re.match(r"^\s*(\d+)\s+(.+?)\s+([A-Z0-9-]+)\s+([A-Za-z0-9]+)\s*$", line)
            if card_match:
                count = card_match.group(1)
                name = card_match.group(2).strip()
                set_id = card_match.group(3)
                set_number = card_match.group(4)
                original_line = f"{count} {name} {set_id} {set_number}"

                cursor.execute(f"SELECT name, attacks, rules FROM {TABLE_NAME} WHERE set_id = ? AND set_number = ?", (set_id, set_number))
                initial_card_data = cursor.fetchone()

                if not initial_card_data:
                    output_lines.append(original_line)
                    continue

                identifier_attacks = initial_card_data['attacks']
                identifier_rules = initial_card_data['rules']
                identifier_column = None
                identifier_value = None

                if identifier_attacks is not None:
                    identifier_column = 'attacks'
                    identifier_value = identifier_attacks
                elif identifier_rules is not None:
                    identifier_column = 'rules'
                    identifier_value = identifier_rules
                else:
                    output_lines.append(original_line)
                    continue


                if identifier_value is None:
                    query = f"SELECT set_id, set_number, rarity FROM {TABLE_NAME} WHERE name = ? AND {identifier_column} IS NULL"
                    params = (name,)
                else:
                    query = f"SELECT set_id, set_number, rarity FROM {TABLE_NAME} WHERE name = ? AND {identifier_column} = ?"
                    params = (name, identifier_value)

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
                found_replacement = False

                for card in reversed(sorted_cards):
                    card_rarity = card['rarity']
                    if not is_rarity_banned(card_rarity):
                        best_set_id = card['set_id']
                        best_set_number = card['set_number']
                        found_replacement = True
                        break
                if not found_replacement:
                    pass
                
                updated_line = f"{count} {name} {best_set_id} {best_set_number}"
                output_lines.append(updated_line)
            else:
                output_lines.append(line)

    except sqlite3.Error as e:
        return f"Database error: {e}"
    finally:
        if conn:
            conn.close()

    return "\n".join(output_lines)

if __name__ == "__main__":
    processed_deck = process_deck_list(DECK_LIST_INPUT, DB_FILE)
    print(processed_deck)

