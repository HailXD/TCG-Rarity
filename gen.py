import sys
import ast

def read_until_two_blank_lines():
    """
    Read lines from stdin, stopping after two consecutive blank lines.
    """
    lines = []
    blank_count = 0
    for line in sys.stdin:
        if line.strip() == "":
            blank_count += 1
            if blank_count >= 2:
                break
        else:
            blank_count = 0
            lines.append(line)
    return "".join(lines)

def parse_deck_input(raw):
    """
    Strip any trailing '===' delimiters and parse to a Python dict.
    """
    raw = raw.strip()
    if raw.endswith('==='):
        raw = raw[:-3].rstrip()
    return ast.literal_eval(raw)

def build_deck_list(deck_dict, cards_txt_path="Cards.txt"):
    """
    For each entry in deck_dict, look up the card line in Cards.txt (by numeric ID)
    and extract:
      - name (everything after 'id.' up to the last two tokens)
      - set code and card number (the last two tokens before the first '|')
    If the key isn't numeric (e.g. 'Grass Energy'), use the key itself as the name
    and leave set_number empty.
    Returns a list of dicts: {type, count, name, set_number}.
    """
    with open(cards_txt_path, encoding="utf-8") as f:
        lines = f.readlines()

    deck_list = []
    last_idx = 0
    for key, val in deck_dict.items():
        count, ctype = val[0], val[1]
        name = key
        set_number = ""

        if key.isdigit():
            prefix = f"{key}."
            for idx in range(last_idx, len(lines)):
                line = lines[idx]
                if line.startswith(prefix):
                    header = line.split("|", 1)[0]
                    # header is e.g. "308.murkrow SVP 21"
                    dot = header.find(".")
                    entry = header[dot+1:].strip()
                    # split off the last two tokens as set code + number
                    parts = entry.rsplit(" ", 2)
                    if len(parts) == 3:
                        name_part, set_code, card_num = parts
                        name = name_part
                        set_number = f"{set_code} {card_num}"
                    last_idx = idx + 1
                    break

        deck_list.append({
            "type": ctype,
            "count": count,
            "name": name,
            "set_number": set_number
        })

        if len(deck_list) >= len(deck_dict):
            break

    return deck_list

def print_grouped(deck_entries):
    """
    Group by 'type', compute total counts, and print in the requested format.
    """
    from collections import OrderedDict
    grouped = OrderedDict()
    for e in deck_entries:
        grouped.setdefault(e["type"], []).append(e)

    for ctype, entries in grouped.items():
        total = sum(e["count"] for e in entries)
        print(f"{ctype} – {total}")
        for e in entries:
            if e["set_number"]:
                print(f"{e['count']} {e['name']} {e['set_number']}")
            else:
                print(f"{e['count']} {e['name']}")
        print()  # blank line between sections

def main():
    raw_input = read_until_two_blank_lines()
    deck_dict = parse_deck_input(raw_input)
    deck_entries = build_deck_list(deck_dict)
    print_grouped(deck_entries)

if __name__ == "__main__":
    main()
