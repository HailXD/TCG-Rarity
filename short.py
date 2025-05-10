import sqlite3

SUFFIX = '''===
Format:
Name
HP:Health
A:Attacks(C:Cost,N:Name,E:Effect,D:Damage,S:Suffix)
R:Retreat Cost(If not written, is 1)
E:Effects
V:Vstar Power
T:Types
F:Evolve From
===
Return your results a dictionary in the format:
```json
{
    "Pokemon Set_Name": [Count, "Pokemon"],
    "Trainer Name": [Count, "Trainer"],
    "Energy Type": [Count, "Energy"],
}
```
As an example, if you wanted 3 Arcanine SP, 1 Wiglett PAR 51, 3 drayton, 2 Darkness Energy and 1 Lightning Energy, that entry will look like
```json
{
    "arcanine SP": [3,"Pokemon"],
    "wiglett PAR 51": [1, "Pokemon"],
    "drayton": [3,"Trainer"],
    "Darkness Energy": [2,"Energy"],
    "Lightning Energy": [1,"Energy"]
}
Pokemon only need to have set names, don't need card numbers
Trainer does not need to have set names or card numbers
Energy does not need to have set names or card numbers

```
===
Notes:
Decks should have 60 cards
Explain the synergy and strategy
Don't write comments in the json
For energy, don't need write "Basic"
Do not any cards outside of the list
Send the deck after the explanations
Type can be Pokemon, Trainer or Energy
For Special Energies, classify them as "Energy"
The notes does not need to be in dictionary form, it should be outside the json block
Card Names Can be in 3 formats:
Card_Name (e.g drayton) - Used for trainers or energies since they have the same effect regardless of set
Card_Name Set_Name (e.g arcanine SP) - For pokemon that only has 1 type (Same attacks with different prints) in the same set
Card_Name Set_Name Card_Number (e.g wiglett PAR 51) - For pokemon that has the same name but different types in the same set
In the output use the name format given in the list
Pokemon attacks cost are shortened to one letter, where: C = Colorless;G = Grass;R = Fire;W = Water;L = Lightning;P = Psychic;M = Metal;F = Fighting;D = Darkness
===
Create a deck'''  

RARITIES_ORDER = [
    'common', 'uncommon', 'rare', 'rare holo', 'promo', 'ultra rare', 'no rarity',
    'rainbow rare', 'rare holo ex', 'rare secret', 'shiny rare', 'holo rare v',
    'illustration rare', 'double rare', 'rare holo gx', 'special illustration rare',
    'holo rare vmax', 'trainer gallery holo rare', 'hyper rare', 'rare holo lv.x',
    'trainer gallery holo rare v', 'ace spec rare', 'rare shiny gx', 'holo rare vstar',
    'trainer gallery ultra rare', 'rare break', 'rare prism star', 'rare prime',
    'rare holo star', 'legend', 'rare shining', 'shiny rare v or vmax', 'radiant rare',
    'shiny ultra rare', 'trainer gallery secret rare', 'trainer gallery holo rare v or vmax',
    'amazing rare'
]

SHORTENED_ENERGY = {
    'grass': 'g',
    'fire': 'r',
    'water': 'w',
    'lightning': 'l',
    'psychic': 'p',
    'fighting': 'f',
    'metal': 'm',
    'darkness': 'd',
    'metal': 'm',
    'colorless': 'c',    
}

def fetch_cards(db_path="pokemon_cards.db"):  
    conn = sqlite3.connect(db_path)  
    conn.row_factory = sqlite3.Row  
    cur = conn.cursor()  
    cur.execute("""  
        SELECT name, set_name, types, number, hp, effect, abilities, attacks, retreat, evolve_from, rarity, card_type, vstar_power  
        FROM cards  
        WHERE regulation IN ('g', 'h', 'i', 'f')  
        ORDER BY set_name, CAST(number AS INTEGER)  
    """)  
    rows = cur.fetchall()  
    conn.close()  
    return rows  
  
def rarity_index(rarity: str) -> int:
    """Return the index of a rarity in RARITIES_ORDER, or a large number if unknown."""
    try:
        return RARITIES_ORDER.index(rarity.lower())
    except ValueError:
        return len(RARITIES_ORDER)
    
def write_cards_txt(cards, out_path="cards.txt"):  
    grouped = {}  
    for c in cards:  
        card_type = (c['card_type'] or '').lower()  
        if card_type == 'pokemon':  
            key = (c['name'], c['attacks'] or '')  
        else:
            key = c['effect'] or None  
        if key is None:
            grouped[key] = c  
        else:
            if key not in grouped:  
                grouped[key] = c  
            else:  
                if rarity_index(c['rarity']) < rarity_index(grouped[key]['rarity']):  
                    grouped[key] = c
  
    selected = list(grouped.values())  
    selected.sort(key=lambda c: (c['card_type'] != 'pokemon', c['set_name'], c['number']))
  
    with open(out_path, 'w', encoding='utf-8') as f:  
        for c in selected:  
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

            if c['card_type'] == 'pokemon':
                s = f"{c['name']} {c['set_name'].upper().replace('PROMO_SWSH', 'SP')}|"
            else:
                s = f"{' '.join(c['name'].split(' '))}|"
            if c['rarity'] == 'ace spec rare':
                s += 'ace spec|'
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
                s += f"F:{c['evolve_from']}|"
            f.write(s[:-1].replace('\n','\\') + '\n')
        f.write(SUFFIX)  
  

if __name__ == "__main__":  
    cards = fetch_cards()  
    write_cards_txt(cards)
