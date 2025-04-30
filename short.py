import sqlite3

SUFFIX = '''===
Format:
Name (Organized in deck list format, you just need to add number of the cards you want)
HP:Health
AS:Ace Spec
ST:Stadium
IT:Item
TO:Tool
A:Attacks(C:Cost,N:Name,E:Effect,D:Damage,S:Suffix)
R:Retreat Cost
E:Effects
V:Vstar Power
T:Types
EF:Evolve From
===
Format of deck:
```deck
Pokemon (4)
4 wingull JTG 38
Trainer (3)
3 professor's research JTG 155
Energy (9)
3 Darkness Energy (Don't need write Basic)
6 Lightning Energy
```
===
Notes:
Explain the synergy and strategy
For energy, don't need write "Basic"
Do not use pokemon outside of the list
If retreat cost is not written, it is 1
Do not write notes in the deck list or anything else in the decklist other than the cards
===
Create a deck'''  

def fetch_cards(db_path="pokemon_cards.db"):  
    conn = sqlite3.connect(db_path)  
    conn.row_factory = sqlite3.Row  
    cur = conn.cursor()  
    cur.execute("""  
        SELECT name, set_name, types, number, hp, effect, abilities, attacks, retreat, evolve_from, rarity, card_type, vstar_power  
        FROM cards  
        WHERE regulation IN ('f', 'g', 'h', 'i')  
        ORDER BY set_name, CAST(number AS INTEGER)  
    """)  
    rows = cur.fetchall()  
    conn.close()  
    return rows  
  

def write_cards_txt(cards, out_path="cards.txt"):  
    grouped = {}  
    for c in cards:  
        card_type = (c['card_type'] or '').lower()  
        if card_type == 'pokemon':  
            key = (c['name'], c['attacks'] or '')  
        else:  
            key = c['effect'] or None  
        grouped[key] = c  
  
    selected = list(grouped.values())  
    selected.sort(key=lambda c: (int(''.join(filter(str.isdigit, c['number'])))))  
  
    with open(out_path, 'w', encoding='utf-8') as f:  
        for c in selected:  
            n = ''
            found = False
            for i in c['number'].upper():
                if not i.isdigit():
                    n += i
                elif not found and i != '0':
                    n += i
                    found = True


            f.write(f"{c['name']} {c['set_name'].upper().replace('PROMO_SWSH', 'SP')} {n}\n")
            if c['card_type'] and c['card_type'].lower() == 'stadium':  
                f.write("ST\n")  
            if c['card_type'] and c['card_type'].lower() == 'item':  
                f.write("IT\n")  
            if c['card_type'] and c['card_type'].lower() == 'tool':  
                f.write("TO\n")  
            if c['hp'] and c['hp'].lower() != 'none':  
                f.write(f"HP:{c['hp']}\n")  
            if c['types'] and c['types'].lower() != 'none':  
                f.write(f"T:{c['types'][2:-2]}\n")  
            if c['effect'] and c['effect'].lower() != 'none':  
                f.write(f"E:{c['effect']}\n")  
            if c['vstar_power'] and c['vstar_power'].lower() != 'none':  
                f.write(f"V:{c['vstar_power']}\n")  
            if c['abilities'] and c['abilities'].lower() != 'none':  
                ab = c['abilities'].split("effect': '", 1)[1].split("'", 1)[0]  
                f.write(f"AB:{ab}\n")  
            if c['attacks'] and c['attacks'].lower() != 'none':  
                attacks = c['attacks'][2:-2]  
                attacks = (attacks.replace('}, {', '|')  
                                 .replace(", 'effect': none", '')  
                                 .replace("'amount': ", '')  
                                 .replace(", 'damage': none", '')  
                                 .replace(': ', ':')  
                                 .replace(', ', ',')  
                                 .replace("'", '')  
                                 .replace(",suffix:", ''))  
                f.write(f"A:{attacks}\n")  
            if c['retreat'] is not None and str(c['retreat']).lower() not in ('none', '1'):  
                f.write(f"R:{c['retreat']}\n")  
            if c['evolve_from'] and c['evolve_from'].lower() != 'none':  
                f.write(f"EF:{c['evolve_from']}\n")  
        f.write(SUFFIX)  
  

if __name__ == "__main__":  
    cards = fetch_cards()  
    write_cards_txt(cards)