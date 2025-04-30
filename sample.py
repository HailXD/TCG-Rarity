import sqlite3

def main():
    connection = sqlite3.connect("pokemon_cards.db")
    cursor = connection.cursor()

    cursor.execute("PRAGMA table_info(cards)")
    columns_info = cursor.fetchall()
    
    columns = [col[1] for col in columns_info]
    print('pokemon_cards.db')
    print("Columns in 'cards' table:")
    print(columns)
    print()

    cursor.execute("SELECT * FROM cards ORDER BY RANDOM() LIMIT 5;")
    rows = cursor.fetchall()

    for row in rows:
        print(list(row))

    connection.close()

if __name__ == "__main__":
    main()
