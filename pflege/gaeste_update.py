"""
Pflege-Skript: Gäste ergänzen, Namen korrigieren, Kategorien vereinheitlichen.

Aufruf (im Projektordner):
    python pflege/gaeste_update.py              # ändert datenbank.db
    python pflege/gaeste_update.py --probe      # zeigt nur, was sich ändern würde
    python pflege/gaeste_update.py pfad/zur.db  # andere Datenbank

Das Skript kann gefahrlos mehrfach laufen: Gäste werden über die Folgennummer
erkannt, nichts wird doppelt angelegt. Bücher werden nicht angefasst.
"""

import sqlite3
import sys

# ---------------------------------------------------------------------------
# Feste Kategorien (Reihenfolge = Reihenfolge der Filter-Buttons)
# ---------------------------------------------------------------------------
KATEGORIEN = [
    "Influencer", "Unternehmer", "Wissenschaftler", "Arzt", "Sportler",
    "Politiker", "Journalist", "Musiker", "Entertainer", "Autor",
    "Ex-Krimineller", "Sicherheit & Militär", "Jurist", "Abenteurer", "Aktivist",
]

# Kurzschreibweise -> Kategorie
K = {
    "I": "Influencer", "U": "Unternehmer", "W": "Wissenschaftler", "A": "Arzt",
    "S": "Sportler", "P": "Politiker", "J": "Journalist", "M": "Musiker",
    "E": "Entertainer", "Au": "Autor", "X": "Ex-Krimineller",
    "Si": "Sicherheit & Militär", "R": "Jurist", "Ab": "Abenteurer", "Ak": "Aktivist",
}

# ---------------------------------------------------------------------------
# Folge -> (Name, Kategorien). Name = None heißt: Name bleibt wie er ist.
# ---------------------------------------------------------------------------
GAESTE = {
    1: (None, "U I"), 2: (None, "U I"), 3: (None, "W"), 4: (None, "U X"),
    5: (None, "I"), 6: (None, "I"), 7: (None, "X"), 8: (None, "J P"),
    9: (None, "M"), 10: (None, "W I"), 11: (None, "W"), 12: (None, "U"),
    13: (None, "U"), 14: (None, "X I"), 15: (None, "P"), 16: (None, "P"),
    17: (None, "U X"), 18: (None, "X"), 19: (None, "I"), 20: (None, "I"),
    21: (None, "Ab"), 22: (None, "X"), 23: (None, "Ak"), 24: (None, "I"),
    25: (None, "W"), 26: (None, "W A"), 27: (None, "M"), 28: (None, "W I"),
    29: (None, "W"), 30: (None, "P"), 31: (None, "U"), 32: (None, "W"),
    33: (None, "Ak W I"), 34: (None, "I"), 35: (None, "U I"), 36: (None, "U I"),
    37: (None, "I S"), 38: (None, "U"), 39: (None, "W"), 40: (None, "X"),
    41: (None, "U"), 42: (None, "U"), 43: (None, "X"), 44: (None, "X"),
    45: (None, "I S"), 46: (None, "Ak I"), 47: (None, "I"), 48: (None, "W U"),
    49: (None, "U"), 50: (None, "W I"), 51: (None, "I"), 52: (None, "I Ab"),
    53: (None, "U"), 54: (None, "X I"), 55: (None, "W U"), 56: (None, "J"),
    57: (None, "W"), 58: ("Frank Thelen Part 2", "U"), 59: (None, "U"),
    60: (None, "A"), 61: (None, "U"), 62: ("Prof. Dr. Philipp Sandner Part 2", "W"),
    63: ("Ron Bielecki Part 3", "I S"), 64: (None, "I"), 65: (None, "M"),
    66: (None, "U"), 67: (None, "I"), 68: (None, "S I"), 69: (None, "S I"),
    70: (None, "S"), 71: (None, "A"), 72: (None, "I"), 73: (None, "S U"),
    74: (None, "W U"), 75: (None, "W I"), 76: (None, "S U I"), 77: (None, "S I"),
    78: (None, "I"), 79: (None, "I"), 80: (None, "I U"), 81: (None, "A"),
    82: (None, "I U"), 83: (None, "U"), 84: (None, "S I"), 85: (None, "M"),
    86: (None, "U"), 87: (None, "S I"), 88: (None, "I"), 89: (None, "U I"),
    90: (None, "U I"), 91: (None, "U"), 92: (None, "I"), 93: (None, "S Ab"),
    94: (None, "I"), 95: (None, "U"), 96: (None, "U"), 97: (None, "S"),
    98: (None, "U"), 99: (None, "I"), 100: (None, "I Si"), 101: (None, "A W"),
    102: (None, "I"), 103: (None, "I"), 104: ("Prof. Dr. Christian Rieck Part 2", "W I"),
    105: (None, "U I"), 106: (None, "W"), 107: (None, "I S"), 108: (None, "W U"),
    109: (None, "I"), 110: (None, "S"), 111: (None, "I"), 112: (None, "I"),
    113: (None, "A I"), 114: (None, "S"), 115: (None, "U"), 116: (None, "S I"),
    117: (None, "U"), 118: (None, "I"), 119: (None, "S"), 120: (None, "I"),
    121: (None, "I"), 122: (None, "I U"), 123: (None, "S X"), 124: (None, "A"),
    125: (None, "J"), 126: ("Jakob Johnson Part 2", "S"), 127: (None, "W I"),
    128: (None, "S I"), 129: (None, "S"), 130: (None, "A W"), 131: (None, "S Ab"),
    132: (None, "U"), 133: ("Dr. Andreas Beck", "U W"), 134: (None, "W"),
    135: (None, "I"), 136: (None, "I"), 137: (None, "W"), 138: (None, "E"),
    139: (None, "I"), 140: (None, "I S"), 141: (None, "W"),
    142: ("Simon Weiss Part 3", "W"), 143: (None, "P"), 144: (None, "W"),
    145: (None, "U I"), 146: (None, "I"), 147: (None, "Ab I"), 148: (None, "W U"),
    149: (None, "A W"), 150: (None, "S I"), 151: (None, "R"),
    152: ("Dr. Susanne Winter", "W"), 153: ("Christian Lindner Part 2", "P"),
    154: (None, "S I"), 155: (None, "P"), 156: ("Sampagne", "M"), 157: (None, "S"),
    158: (None, "U"), 159: (None, "U"), 160: (None, "P"), 161: (None, "Si"),
    162: (None, "P"), 163: (None, "U"), 164: (None, "P"), 165: (None, "Si"),
    166: (None, "J"), 167: (None, "W J"), 168: (None, "P"), 169: (None, "M"),
    170: (None, "U"), 171: ("Max Coga", "S I"), 172: (None, "U I"), 173: (None, "I"),
    174: ("Prof. Dr. Maximilian Fichtner", "W"), 175: (None, "I"), 176: (None, "U I"),
    178: (None, "W"), 179: (None, "I S"), 180: (None, "U"), 181: (None, "W"),
    182: (None, "U W"), 183: (None, "A"), 184: (None, "Si"), 185: (None, "P"),
    186: (None, "E U"), 187: (None, "I"), 188: (None, "S"), 189: (None, "P"),
    190: (None, "X"), 191: (None, "M"), 192: (None, "I"),
    193: ("Prof. Dr. Rainer Thomasius", "A W"), 194: (None, "I"), 195: (None, "W"),
    196: (None, "W I"), 197: ("Wolfgang Hirn", "J"), 198: (None, "S U"),
    199: (None, "S I"), 200: (None, "U"), 201: (None, "W"), 202: (None, "S I"),
    203: (None, "W"), 204: (None, "W"), 205: (None, "J"), 206: (None, "Si"),
    207: (None, "W"), 208: (None, "Si"), 209: (None, "I"), 210: (None, "Si"),
    211: (None, "U"), 212: (None, "A W"), 213: (None, "Si"), 214: (None, "U I"),
    215: (None, "Si"), 216: (None, "J"), 217: (None, "I"), 218: (None, "I J"),
    219: (None, "P"), 220: (None, "I"), 221: (None, "J"), 222: (None, "A J"),
    223: (None, "S"), 224: (None, "U"), 225: (None, "W"), 226: (None, "J I"),
    227: (None, "W"), 228: (None, "R I"), 229: (None, "J"), 230: (None, "S I"),
    231: (None, "A"), 232: (None, "I U"), 233: (None, "Ak I"), 234: (None, "X Au"),
    235: (None, "Si"), 236: (None, "U I"), 237: (None, "Ab I"), 238: (None, "Au W"),
    239: (None, "A W"), 240: (None, "I"), 241: (None, "S"), 242: (None, "U W"),
    243: (None, "M"), 244: (None, "W"),
    # ---- neue Folgen ab August 2026 -------------------------------------
    245: ("Liv von Boetticher", "J"),                 # 16.08.2026
    246: ("Anni The Duck", "I"),                      # 23.08.2026
    247: ("Gerhard Schindler", "Si"),                 # 30.08.2026 Ex-BND-Präsident
    248: ("Timon Krause", "E"),                       # 06.09.2026 Mentalist
    249: ("Boris Bondarew", "P"),                     # 13.09.2026 Ex-Diplomat
    250: ("Dr. Bea Merscher", "A"),                   # 16.09.2026
    251: ("Serdar Somuncu", "E"),                     # 20.09.2026
    252: ("Christian Solmecke Part 2", "R I"),        # 23.09.2026 Fall Karl Ess
    253: ("Dr. Luisa Werner", "A I"),                 # 27.09.2026
    254: ("Dr. Gilda Giebel", "W Au"),                # 04.10.2026
    255: ("Marc Elsberg", "Au"),                      # 11.10.2026 Blackout
    256: ("Jerry Vsan", "E"),                         # 14.10.2026
    257: ("Tim Vollert", "I W"),                      # 18.10.2026
    258: ("Salim Samatou", "I"),                      # 25.10.2026
    259: ("Julius van de Laar Part 2", "P"),          # 01.11.2026
    260: ("Pietro Lombardi", "M E"),                  # 08.11.2026
    261: ("Kim Gottwald Part 2", "S I"),              # 11.11.2026 Spaziergang
    262: ("Dr. Andreas Fulda", "W"),                  # 15.11.2026 Taiwan
}


def kategorien_text(kuerzel):
    return ", ".join(K[k] for k in kuerzel.split())


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    probe = "--probe" in sys.argv
    db_pfad = args[0] if args else "datenbank.db"

    conn = sqlite3.connect(db_pfad)
    conn.row_factory = sqlite3.Row
    vorhanden = {r["folge"]: r for r in conn.execute("SELECT * FROM autoren")}

    neu = umbenannt = kat_geaendert = 0
    for folge, (name, kuerzel) in sorted(GAESTE.items()):
        kat = kategorien_text(kuerzel)
        alt = vorhanden.get(folge)
        if alt is None:
            if name is None:
                print(f"  ! Folge {folge} fehlt in der DB und hat keinen Namen – übersprungen")
                continue
            print(f"  + #{folge} {name}  [{kat}]")
            if not probe:
                conn.execute(
                    "INSERT INTO autoren (folge, name, kategorie) VALUES (?, ?, ?)",
                    (folge, name, kat),
                )
            neu += 1
            continue

        neuer_name = name if name else alt["name"].strip()
        if neuer_name != alt["name"]:
            print(f"  ~ #{folge} Name: {alt['name']!r} -> {neuer_name!r}")
            umbenannt += 1
        if kat != (alt["kategorie"] or ""):
            kat_geaendert += 1
        if not probe:
            conn.execute(
                "UPDATE autoren SET name=?, kategorie=? WHERE id=?",
                (neuer_name, kat, alt["id"]),
            )

    unbekannt = sorted(set(vorhanden) - set(GAESTE))
    if unbekannt:
        print(f"  ! Folgen in der DB, die das Skript nicht kennt (unverändert): {unbekannt}")

    if not probe:
        conn.commit()
    conn.close()
    modus = "Probelauf – nichts gespeichert" if probe else "gespeichert"
    print(f"\n{neu} neue Gäste, {umbenannt} Namen korrigiert, "
          f"{kat_geaendert} Kategorien angepasst ({modus}).")


if __name__ == "__main__":
    main()
