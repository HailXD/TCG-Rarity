import sqlite3
import json
import os
from pathlib import Path

# --- Configuration ---
SETS_FILE = Path("sets/en.json")
CARDS_DIR = Path("cards/en")
DB_NAME = "pokemon_cards.db"
TABLE_NAME = "cards"
# --- End Configuration ---

def create_connection(db_file):
    """ Create a database connection to the SQLite database specified by db_file """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print(f"Connected to database: {db_file}")
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
    return conn

def create_table(conn):
    """ Create the cards table """
    # Define columns based on common fields. Store complex types as JSON strings.
    # Add 'set_id' as the first column.
    sql_create_cards_table = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        set_id TEXT,
        card_id TEXT PRIMARY KEY,
        name TEXT,
        supertype TEXT,
        subtypes TEXT,
        hp TEXT,
        types TEXT,
        evolvesFrom TEXT,
        evolvesTo TEXT,
        rules TEXT,
        ancientTrait TEXT,
        abilities TEXT,
        attacks TEXT,
        weaknesses TEXT,
        resistances TEXT,
        retreatCost TEXT,
        convertedRetreatCost INTEGER,
        set_number TEXT, -- Renamed from 'number' to avoid SQL keyword conflict
        artist TEXT,
        rarity TEXT,
        flavorText TEXT,
        nationalPokedexNumbers TEXT,
        legalities TEXT,
        regulationMark TEXT,
        images TEXT
    );
    """
    try:
        c = conn.cursor()
        c.execute(sql_create_cards_table)
        print(f"Table '{TABLE_NAME}' created or already exists.")
    except sqlite3.Error as e:
        print(f"Error creating table: {e}")

def insert_card(conn, card_data):
    """ Insert a new card into the cards table """
    sql = f''' INSERT OR IGNORE INTO {TABLE_NAME}(
                    set_id, card_id, name, supertype, subtypes, hp, types,
                    evolvesFrom, evolvesTo, rules, ancientTrait, abilities, attacks,
                    weaknesses, resistances, retreatCost, convertedRetreatCost,
                    set_number, artist, rarity, flavorText, nationalPokedexNumbers,
                    legalities, regulationMark, images
                )
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) '''
    try:
        cur = conn.cursor()
        cur.execute(sql, card_data)
        return cur.lastrowid
    except sqlite3.Error as e:
        print(f"Error inserting card {card_data[1]}: {e}")
        # Optionally print the problematic data
        # print(f"Problematic data: {card_data}")
        return None

def process_files():
    """ Main function to process set and card files and populate the database """
    if not SETS_FILE.is_file():
        print(f"Error: Set file not found at {SETS_FILE}")
        return

    conn = create_connection(DB_NAME)
    if conn is None:
        return

    create_table(conn)

    try:
        with open(SETS_FILE, 'r', encoding='utf-8') as f:
            sets_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error reading or parsing {SETS_FILE}: {e}")
        conn.close()
        return
    except Exception as e:
        print(f"An unexpected error occurred reading {SETS_FILE}: {e}")
        conn.close()
        return

    total_cards_processed = 0
    sets_processed = 0
    sets_missing_cards = 0

    for pokemon_set in sets_data:
        set_id = pokemon_set.get('id')
        ptcgo_code = pokemon_set.get('ptcgoCode') # Can be None if missing

        if not set_id:
            print(f"Skipping set entry due to missing 'id': {pokemon_set.get('name', 'N/A')}")
            continue

        card_file_path = CARDS_DIR / f"{set_id}.json"

        if not card_file_path.is_file():
            print(f"Warning: Card file not found for set '{set_id}' ({pokemon_set.get('name', 'N/A')}) at {card_file_path}")
            sets_missing_cards += 1
            continue

        print(f"Processing set: {set_id} ({pokemon_set.get('name', 'N/A')}) - PTCGO Code: {ptcgo_code}")
        set_cards_inserted = 0
        try:
            with open(card_file_path, 'r', encoding='utf-8') as cf:
                cards_in_set = json.load(cf)

            if not isinstance(cards_in_set, list):
                print(f"Warning: Expected a list of cards in {card_file_path}, found {type(cards_in_set)}. Skipping file.")
                continue

            for card in cards_in_set:
                # Prepare data tuple, handling potentially missing keys safely
                # Use card.get(key, default_value)
                # Use json.dumps for list/dict fields to store as TEXT
                card_values = (
                    ptcgo_code,
                    card.get('id'),
                    card.get('name'),
                    card.get('supertype'),
                    json.dumps(card.get('subtypes')) if card.get('subtypes') else None,
                    card.get('hp'),
                    json.dumps(card.get('types')) if card.get('types') else None,
                    card.get('evolvesFrom'),
                    json.dumps(card.get('evolvesTo')) if card.get('evolvesTo') else None,
                    json.dumps(card.get('rules')) if card.get('rules') else None,
                    json.dumps(card.get('ancientTrait')) if card.get('ancientTrait') else None,
                    json.dumps(card.get('abilities')) if card.get('abilities') else None,
                    json.dumps(card.get('attacks'), sort_keys=True) if card.get('attacks') else None,
                    json.dumps(card.get('weaknesses')) if card.get('weaknesses') else None,
                    json.dumps(card.get('resistances')) if card.get('resistances') else None,
                    json.dumps(card.get('retreatCost')) if card.get('retreatCost') else None,
                    card.get('convertedRetreatCost'),
                    card.get('number'), # 'set_number' column
                    card.get('artist'),
                    card.get('rarity'),
                    card.get('flavorText'),
                    json.dumps(card.get('nationalPokedexNumbers')) if card.get('nationalPokedexNumbers') else None,
                    json.dumps(card.get('legalities')) if card.get('legalities') else None,
                    card.get('regulationMark'),
                    json.dumps(card.get('images')) if card.get('images') else None
                )
                # print(card_values) # Uncomment for debugging specific card data
                if insert_card(conn, card_values):
                   set_cards_inserted += 1

            conn.commit() # Commit after each set's cards are processed
            print(f"  Inserted {set_cards_inserted} cards from set {set_id}.")
            total_cards_processed += set_cards_inserted
            sets_processed += 1

        except json.JSONDecodeError as e:
            print(f"Error reading or parsing {card_file_path}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred processing {card_file_path}: {e}")

    # Final commit and close
    if conn:
        conn.commit() # Final commit just in case
        conn.close()
        print("\n--- Processing Summary ---")
        print(f"Total sets processed: {sets_processed}")
        print(f"Total card files missing: {sets_missing_cards}")
        print(f"Total cards inserted into database: {total_cards_processed}")
        print(f"Database '{DB_NAME}' created successfully.")

if __name__ == '__main__':
    process_files()