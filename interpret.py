import sys, sqlite3, ast, re

def read_until_double_newline():
    """
    Read from stdin until two consecutive blank lines are encountered.
    Strip trailing ' # comment' from each line.
    """
    lines = []
    for raw in sys.stdin:
        line = re.sub(r'\s+#.*$', '', raw)
        lines.append(line)
        if '}' in raw:
            break
    return "".join(lines)

def load_deck(input_text):
    """
    Safely parse the dict literal from input_text.
    Expecting: { "card name": [count, "Category"], ... }
    """
    try:
        deck = ast.literal_eval(input_text)
        if not isinstance(deck, dict):
            raise ValueError("Expected a dict of cards")
        return deck
    except Exception as e:
        sys.exit(f"Failed to parse deck list: {e}")

def lookup_card(name, cursor):
    """
    Find all cards matching exactly `name` in the 'cards' table,
    ordered by date, and return the last (most recent) row's
    (set_name, number). Returns (None, None) if not found.
    """
    cursor.execute("""
        SELECT set_name, number, date, card_type
          FROM cards
        WHERE name = ? AND (rarity IS NULL OR rarity IN ('common', 'uncommon', 'ace spec rare', 'rare'))
      ORDER BY date ASC
    """, (name.lower(),))
    rows = cursor.fetchall()
    if not rows:
        return None, None
    return rows[-1][0], rows[-1][1]

def compile_deck(deck_dict, db_path="pokemon_cards.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    groups = {"Pokemon": [], "Trainer": [], "Energy": []}

    for full_key, (count, category) in deck_dict.items():
        if category == "Pokemon":
            groups["Pokemon"].append((count, full_key))
        elif category in ("Trainer", "Energy"):
            for i in range(0, 2):
                full_key = full_key.replace('Dark Energy', 'Darkness Energy')
                parts = full_key.split(" ")
                if i == 0:
                    set_name, number = lookup_card(full_key, cur)
                else:
                    set_name, number = lookup_card(' '.join(parts[:-i]), cur)
                if set_name:
                    break
            if set_name is None:
                sys.stderr.write(f"Warning: no entry found in DB for {full_key!r}\n")
                continue
            groups[category].append((count, full_key, set_name, number))
        else:
            sys.stderr.write(f"Warning: unsupported category {category!r} for {full_key!r}\n")

    conn.close()
    return groups

def print_deck(groups):
    ttotal = 0
    for cat in ("Pokemon", "Trainer", "Energy"):
        entries = groups.get(cat, [])
        if not entries:
            continue
        total = sum(e[0] for e in entries)
        ttotal += total
        print(f"{cat} – {total}")
        for e in entries:
            if cat == "Pokemon":
                count, full = e
                print(f"{count} {full}")
            else:
                count, name, set_name, number = e
                print(f"{count} {name} {set_name.upper()} {number}")
        print()
    print(f"Total – {ttotal}")

def main():
    raw = read_until_double_newline()
    deck = load_deck(raw)
    groups = compile_deck(deck)
    print_deck(groups)

if __name__ == "__main__":
    main()
