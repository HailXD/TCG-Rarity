import sqlite3, re, os, textwrap

DB = 'pokemon_cards.db'
TBL = 'cards'

DECK = textwrap.dedent("""Pokemon - 18
2 Budew PRE 4
3 Charizard ex PAF 234
3 Charmander MEW 168
1 Charmeleon PAF 110
1 Dusclops SFA 69
2 Dusknoir SFA 70
2 Duskull SFA 68
1 Fezandipiti ex SFA 92
1 Munkidori SFA 72
1 Pecharunt ex PRE 163
1 Squawkabilly ex PAL 264
Trainer - 35
1 Artazon OBF 229
4 Arven PAF 235
2 Binding Mochi SFA 55
1 Boss's Orders RCL 189
4 Buddy-Buddy Poffin TWM 223
2 Carmine TWM 217
1 Counter Catcher PAR 264
1 Defiance Band SVI 169
1 Earthen Vessel SFA 96
2 Iono PAL 269
2 Nest Ball SVI 255
1 Pal Pad SSH 172
1 Pokémon League Headquarters OBF 192
1 Prime Catcher TEF 157
4 Rare Candy PLB 105
2 Super Rod PAL 276
1 Technical Machine: Evolution PAR 178
4 Ultra Ball PLF 122
Energy - 7
1 Basic Darkness Energy 98
6 Basic Fire Energy 230""")

RARITY_ORDER = [
    "None", "Common", "Uncommon", "Promo", "Rare", "Rare Holo",
    "Trainer Gallery Rare Holo", "Rare Holo V", "Rare Holo VSTAR",
    "Rare Holo VMAX", "Rare BREAK", "Rare Prime", "Rare Holo GX",
    "Rare Holo EX", "Rare Shining", "Rare Holo Star", "Rare Holo LV.X",
    "Rare Ultra", "Double Rare", "Rare ACE", "ACE SPEC Rare", "Rare Shiny",
    "Shiny Rare", "Rare Shiny GX", "Rare Prism Star", "Amazing Rare",
    "Radiant Rare", "Ultra Rare", "Hyper Rare", "Rare Rainbow",
    "Illustration Rare", "Special Illustration Rare", "Shiny Ultra Rare",
    "Classic Collection", "Rare Secret", "LEGEND"
]

RMAP = {r: i for i, r in enumerate(RARITY_ORDER)}
BAN = ["Hyper", "Secret", "Shiny", "Rainbow"]
BAN_PKM = BAN + ["Ultra"]


def s_key(r):
    return RMAP.get(r or "None", -1)


def banned(r, sup):
    words = BAN_PKM if sup == "Pokémon" else BAN
    return any(w in (r or "") for w in words)


def best_print(sid, snum, name, sup, atk, cur):
    if sup == "Pokémon":
        if atk is None:
            rows = cur.execute(
                f"SELECT set_id, set_number, rarity FROM {TBL} WHERE name=? AND attacks IS NULL",
                (name,),
            ).fetchall()
        else:
            rows = cur.execute(
                f"SELECT set_id, set_number, rarity FROM {TBL} WHERE name=? AND attacks=?",
                (name, atk),
            ).fetchall()
    elif sup == "Trainer":
        clean = re.sub(r"\s*\(.*?\)", "", name).strip()
        rows = cur.execute(
            f"SELECT set_id, set_number, rarity FROM {TBL} WHERE name LIKE ?",
            (clean + "%",),
        ).fetchall()
        name = clean
    else:
        return sid, snum, name

    if not rows:
        return sid, snum, name

    rows.sort(key=lambda r: s_key(r["rarity"]))
    for r in reversed(rows):
        if not banned(r["rarity"], sup):
            return r["set_id"], r["set_number"], name
    return sid, snum, name


def process(deck):
    if not os.path.exists(DB):
        return "Database missing"

    out = []
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        for ln in deck.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            if re.match(r"^(Pokemon|Trainer|Energy)\s*-", ln, re.I):
                out.append(ln)
                continue
            m = re.match(r"^(\d+)\s+Basic\s+(.+?)\s+Energy", ln, re.I)
            if m:
                out.append(f"{m[1]} {m[2]} Energy")
                continue
            m = re.match(r"^(\d+)\s+(.+?)\s+([A-Z0-9-]+)\s+(\w+)$", ln)
            if not m:
                out.append(ln)
                continue

            cnt, name, sid, snum = m.groups()
            row = cur.execute(
                f"SELECT name, supertype, subtypes, attacks FROM {TBL} WHERE set_id=? AND set_number=?",
                (sid, snum),
            ).fetchone()
            if not row:
                out.append(ln)
                continue

            sup, sub, nm = row["supertype"], row["subtypes"], row["name"]
            if sup == "Energy" or (sub and "Item" in sub):
                nm = re.sub(r"\s*\(.*?\)", "", nm).strip()
                out.append(f"{cnt} {nm}")
                continue

            sid, snum, nm = best_print(sid, snum, nm, sup, row["attacks"], cur)
            out.append(f"{cnt} {nm} {sid} {snum}")

    return "\n".join(out)


def compile(deck):
    cat = None
    data, order = {}, []
    for l in deck.splitlines():
        h = re.match(r"^(Pokemon|Trainer|Energy)\s*-", l, re.I)
        if h:
            cat = h[1]
            order.append(cat)
            data.setdefault(cat, {})
            continue
        m = re.match(r"^(\d+)\s+(.+)$", l)
        if m and cat:
            data[cat][m[2]] = data[cat].get(m[2], 0) + int(m[1])

    out = []
    for cat in order:
        items = sorted(data[cat].items())
        out.append(f"{cat} - {sum(n for _, n in items)}")
        out.extend(f"{n} {k}" for k, n in items)
    return "\n".join(out)


if __name__ == "__main__":
    print(compile(process(DECK)))
