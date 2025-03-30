import sqlite3
import re

deck = '''Pokemon - 15
3 Iron Crown ex TEF 81
2 Iron Hands TEF 61
2 Iron Jugulis PAR 158
2 Iron Thorns TEF 62
2 Latias ex SSP 76
3 Miraidon TEF 121
1 Miraidon ex TEF 122
Trainer - 30
2 Ciphermaniac's Codebreaking PRE 104
3 Crispin PRE 105
2 Energy Retrieval SVI 171
2 Energy Search BCR 128
2 Energy Switch SSH 162
4 Future Booster Energy Capsule PAR 164
2 Larry's Skill PRE 115
3 Miriam SVI 179
1 Professor Turo's Scenario PAR 171
1 Professor's Research PAF 88
1 Reboot Pod TEF 158
2 Super Rod PAL 188
3 Techno Radar PAR 180
2 Trekking Shoes CRZ 145
Energy - 15
8 Basic Lightning Energy 12
5 Basic Psychic Energy 13
2 Double Turbo Energy BRS 151'''

def load_cards_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM cards")
    rows = cur.fetchall()
    cards = [dict(row) for row in rows]
    conn.close()
    return cards

def process_deck(deck_str, card_db):
    new_deck_lines = []
    banned_words = ["Hyper", "Secret", "Shiny", "Rainbow"]
    
    def contains_banned(text):
        if not text:
            return False
        return any(banned in text for banned in banned_words)
    
    def to_int(s):
        try:
            return int(s)
        except:
            return 0

    current_section = None
    for line in deck_str.splitlines():
        # Sections like "Pokemon - 15" or "Trainer - 30" are passed through
        if not re.match(r'^\d+', line):
            current_section = line.split(" - ")[0].strip()
            new_deck_lines.append(line)
            continue
        
        # Energy section special handling: remove the word "Basic" if present.
        if current_section == "Energy":
            tokens = line.split()
            if len(tokens) > 1 and tokens[1].lower() == "basic":
                new_tokens = [tokens[0]] + tokens[2:]
                new_line = " ".join(new_tokens)
            else:
                new_line = line
            new_deck_lines.append(new_line)
            continue

        tokens = line.split()
        if not tokens[-1].isdigit() or len(tokens) < 3:
            new_deck_lines.append(line)
            continue

        # Parse the line into quantity, card_name, set_id and set_number.
        quantity = int(tokens[0])
        set_number = tokens[-1]
        set_id = tokens[-2]
        card_name = " ".join(tokens[1:-2])
        
        # Find the matching card using the provided set info.
        matching_card = None
        for card in card_db:
            if str(card.get('set_number')) == set_number and card.get('set_id') == set_id:
                matching_card = card
                break
        
        if not matching_card:
            new_deck_lines.append(line)
            continue

        card_detail = matching_card.get('attacks') or matching_card.get('rules')
        if card_detail is None:
            new_deck_lines.append(line)
            continue

        # Skip processing if any banned word is present in key fields.
        if (contains_banned(matching_card.get('name', '')) or
            contains_banned(card_detail) or
            contains_banned(matching_card.get('rarity', ''))):
            new_deck_lines.append(line)
            continue

        # Collect all candidate cards with the same name and detail.
        candidate_cards = []
        for card in card_db:
            if card.get('name') == matching_card.get('name'):
                detail = card.get('attacks') or card.get('rules')
                if detail == card_detail:
                    if (not contains_banned(card.get('name', '')) and
                        (not detail or not contains_banned(detail)) and
                        not contains_banned(card.get('rarity', ''))):
                        candidate_cards.append(card)
        
        if candidate_cards:
            # Sort candidates in descending order by set_number.
            candidate_cards_sorted = sorted(candidate_cards, key=lambda c: to_int(c.get('set_number', '0')), reverse=True)
            # For each copy, choose a distinct candidate if possible.
            variants = []
            for i in range(quantity):
                if i < len(candidate_cards_sorted):
                    chosen = candidate_cards_sorted[i]
                else:
                    # If not enough distinct versions, reuse the lowest available.
                    chosen = candidate_cards_sorted[-1]
                # Output each copy as a separate line (with quantity 1).
                line_variant = f"1 {card_name} {chosen.get('set_id')} {chosen.get('set_number')}"
                variants.append(line_variant)
            new_deck_lines.extend(variants)
        else:
            # If no candidate variants found, leave the line unchanged.
            new_deck_lines.append(line)
        
    return "\n".join(new_deck_lines)

db_path = "pokemon_cards.db"
card_db = load_cards_db(db_path)

updated_deck = process_deck(deck, card_db)
print(updated_deck)
