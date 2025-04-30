import sqlite3

SUFFIX = '''===
Format:
ID.Name (Organized in deck list format, but you only need to know the ID)
HP:Health
A:Attacks(C:Cost,N:Name,E:Effect,D:Damage,S:Suffix)
R:Retreat Cost
E:Effects
V:Vstar Power
T:Types
EF:Evolve From
===
Return your results a dictionary in the format:
```json
{
    ID: Count, # Name (Type)
    ID: Count, # Name (Type)
    "Dark Energy": Count, # (Type)
    "Lightning Energy: Count # (Type)
}
{
    ID: [Count,Name,Type],
    ID: [Count,Name,Type],
    "Dark Energy": [Count,Type],
    "Lightning Energy: [Count,Type]
}
2758.arcanine SP 304|...
As an example, if you wanted 3 Arcanine SP 304, that entry will look like
{
    2758: [4,arcanine SP 304,Pokemon]
}
```
===
Notes:
Explain the synergy and strategy
For energy, don't need write "Basic"
Do not use pokemon outside of the list
If retreat cost is not written, it is 1
Type can be Pokemon, Trainer or Energy
Names are only for energy cards that have no ID, if have ID, use ID
The notes does not need to be in dictionary form, it can be outside the markdown
After each Card, write comments after # (It's python) with the name and type of the card
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
        for idx, c in enumerate(selected):  
            n = ''
            found = False
            for i in c['number'].upper():
                if not i.isdigit():
                    n += i
                    continue
                if not found and i == '0':
                    continue
                n += i
                found = True

            s = f"{idx}.{c['name']} {c['set_name'].upper().replace('PROMO_SWSH', 'SP')} {n.replace('SWSH', '')}|"
            if c['hp'] and c['hp'].lower() != 'none':  
                s += f"HP:{c['hp']}|"
            if c['types'] and c['types'].lower() != 'none':  
                s += f"T:{c['types'][2:-2]}|"
            if c['effect'] and c['effect'].lower() != 'none':  
                s += f"E:{c['effect']}|"
            if c['vstar_power'] and c['vstar_power'].lower() != 'none':  
                s += f"V:{c['vstar_power']}|"
            if c['abilities'] and c['abilities'].lower() != 'none':  
                ab = "'".join(c['abilities'].split("effect': '", 1)[1].split("'")[:-1])
                s += f"AB:{ab}|"
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
                s += f"A:{attacks}|"
            if c['retreat'] is not None and str(c['retreat']).lower() not in ('none', '1'):  
                s += f"R:{c['retreat']}|"
            if c['evolve_from'] and c['evolve_from'].lower() != 'none':  
                s += f"EF:{c['evolve_from']}|"
            f.write(s[:-1] + '\n')
        f.write(SUFFIX)  
  

if __name__ == "__main__":  
    cards = fetch_cards()  
    write_cards_txt(cards)