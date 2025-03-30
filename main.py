import sqlite3
import re
import os

DB_FILE = 'pokemon_cards.db'
TABLE_NAME = 'cards'
DECK_LIST_INPUT = """Pokemon - 14
1 Applin TWM 185
3 Applin TWM 126
2 Dipplin TWM 18
1 Hydrapple ex SCR 167
2 Hydrapple ex SCR 156
1 Mew ex MEW 205
1 Teal Mask Ogerpon ex TWM 25
1 Teal Mask Ogerpon ex TWM 221
1 Teal Mask Ogerpon ex PRE 12
1 Teal Mask Ogerpon ex TWM 190
Trainer - 31
1 Bosss Orders BRS 132
1 Bosss Orders (Ghetsis) PAL 172
2 Buddy-Buddy Poffin TEF 144
2 Bug Catching Set PRE 102
2 Bug Catching Set TWM 143
1 Earthen Vessel PAR 163
2 Energy Retrieval SVI 171
1 Iono PAF 80
2 Iono PAL 185
2 Nest Ball PAF 84
2 Nest Ball SVI 181
1 Night Stretcher SFA 61
1 Prime Catcher TEF 157
3 Professor's Research PRE 122
1 Professor's Research (Professor Sada) SVI 189
4 Rare Candy CRZ 141
1 Super Rod PAL 188
1 Ultra Ball SVI 196
1 Ultra Ball PAF 91
Energy - 15
15 Basic Grass Energy"""

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
                    print(original_line)
                    output_lines.append(original_line)
                    continue

                name = initial_card_data['name']
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
                
                name = re.sub(r'\s*\(.*?\)', '', name)
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

