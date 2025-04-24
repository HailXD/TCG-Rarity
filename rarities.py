import sqlite3

db = "pokemon_cards.db"
conn = sqlite3.connect(db)

# print rarity column unique values and their counts in pokemon_cards.db cards table
cur = conn.cursor()
cur.execute("SELECT rarity, COUNT(*) FROM cards GROUP BY rarity")
rarities = cur.fetchall()
conn.close()

print("Rarity counts:")
x = []
for rarity, count in rarities:
    x.append((rarity, count))

# sort by count descending
x.sort(key=lambda x: x[1], reverse=True)
for rarity, count in x:
    print(f"{rarity}: {count}")

print([c[0] for c in x])