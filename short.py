import sqlite3

def fetch_jtg_cards(db_path="pokemon_cards.db"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT name, set_name, types, number, hp, effect, abilities, attacks, retreat, evolve_from
        FROM cards
        WHERE regulation in ('g', 'h', 'i')
        ORDER BY set_name, CAST(number AS INTEGER)
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

suff = '''===
Format:
Name (Organized in deck list format, you just need to add number of the cards you want)
HP:Health
A:Attacks(C:Cost,N:Name,E:Effect,D:Damage,S:Suffix)
R:Retreat Cost
E:Effects
T:Types
EF:Evolve From
===
Example of deck
Pokemon (4)
4 wingull JTG 38
Trainer (3)
3 professor's research JTG 155
Energy (9)
3 Darkness Energy (Don't need write Basic)
6 Lightning Energy
===
Explain the synergy and strategy
For energy, don't need write "Basic"
Do not write notes in the deck list or anything else in the decklist other than the cards
Create a deck'''

def write_cards_txt(cards, out_path="cards.txt"):
    seen = {}
    with open(out_path, 'w', encoding='utf-8') as f:
        for c in cards:
            key = (c['name'], c['hp'], c['types'], c['abilities'], c['attacks'], c['retreat'], c['evolve_from'])
            if c['name'] in seen and seen[c['name']] == key:
                continue
            seen[c['name']] = key

            f.write(f"{c['name']} {c['set_name'].upper()} {c['number']}\n")
            if c['hp'] and c['hp'].lower() != 'none':
                f.write(f"HP:{c['hp']}\n")
            if c['types'] and c['types'].lower() != 'none':
                f.write(f"T:{c['types'][2:-2]}\n")
            if c['effect'] and c['effect'].lower() != 'none':
                f.write(f"E:{c['effect']}\n")
            if c['abilities'] and c['abilities'].lower() != 'none':
                ab = c['abilities'].split("effect': '", 1)[1].split("'", 1)[0]
                f.write(f"AB:{ab}\n")
            if c['attacks'] and c['attacks'].lower() != 'none':
                attacks = c['attacks'][2:-2].replace('}, {', '|').replace(", 'suffix': ''", '').replace(", 'effect': none", '').replace("'amount': ", '').replace(", 'damage': none", '').replace(': ', ':').replace(', ', ',').replace("'", '')
                attacks = attacks.replace("'cost'", "C").replace("'name'", "N").replace("'effect'", "E").replace("'damage'", "D").replace(',suffix:', '').replace('{', '').replace('}', '')
                f.write(f"A:{attacks}\n")
            if c['retreat'] is not None and str(c['retreat']).lower() != 'none':
                f.write(f"R:{c['retreat']}\n")
            if c['evolve_from'] and c['evolve_from'].lower() != 'none':
                f.write(f"EF:{c['evolve_from']}\n")
        f.write(suff)

if __name__ == "__main__":
    cards = fetch_jtg_cards()
    write_cards_txt(cards)