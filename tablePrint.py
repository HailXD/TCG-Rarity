import sqlite3

def main():
    # Connect to the SQLite database file
    db_file = "pokemon_cards.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Retrieve the table names from the database
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    if not tables:
        print("No tables found in the database.")
        return

    # Process each table found in the database
    for table in tables:
        table_name = table[0]
        print(f"Database: pokemon_cards.db | Table: {table_name}")

        # Retrieve column information using PRAGMA table_info
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns_info = cursor.fetchall()
        column_names = [info[1] for info in columns_info]  # The second field is the column name
        print("Columns:", column_names)

        # Retrieve 5 random rows from the table
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY RANDOM() LIMIT 5;")
        rows = cursor.fetchall()

        print("5 Random Rows:")
        for row in rows:
            print(row)
        print("-" * 40)

    # Close the connection to the database
    conn.close()

if __name__ == "__main__":
    main()
