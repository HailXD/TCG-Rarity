import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('pokemon_cards.db')

# Create a cursor object using the cursor method
cursor = conn.cursor()

# SQL query to fetch all unique rarities from the 'cards' table
query = "SELECT DISTINCT rarity FROM cards"

# Executing the SQL query
cursor.execute(query)

# Fetch all unique rarities
rarities = cursor.fetchall()

# Print each rarity
for rarity in rarities:
    print(rarity[0])

# Close the cursor and connection to the database
cursor.close()
conn.close()
