"""
Pflege-Skript: Bücher der Gäste mit Amazon-Partnerlink eintragen.

Aufruf (im Projektordner):
    python pflege/buecher_update.py            # ändert datenbank.db
    python pflege/buecher_update.py --probe    # zeigt nur, was passieren würde

- Bücher werden über die Folgennummer dem Gast zugeordnet.
- Schon vorhandene Titel (gleicher Gast, gleicher Titel) werden übersprungen.
- Links sind zunächst Amazon-Suchlinks mit Partner-Tag. Der Button
  „Cover & Partnerlinks aktualisieren“ in der App macht daraus – sobald
  Google Books die ISBN liefert – direkte Produktlinks und lädt die Cover.
"""

import os
import re
import sqlite3
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from amazon import such_link  # noqa: E402

# Folge -> Liste von Buchtiteln (nur selbst geschriebene Bücher des Gastes)
BUECHER = {
    31: ["Souverän investieren mit Indexfonds und ETFs", "Souverän investieren für Einsteiger",
         "Souverän investieren vor und im Ruhestand", "Kaufen oder mieten?",
         "Der leichte Einstieg in die Welt der ETFs"],                              # Gerd Kommer
    32: ["Entscheide selbst, wie alt du bist", "Die Jungbrunnen-Formel",
         "7 Jahre jünger in 7 Wochen"],                                             # Sven Voelpel
    33: ["Mission Erde – Die Welt ist es wert, um sie zu kämpfen"],                 # Robert Marc Lehmann
    35: ["Der größte Raubzug der Geschichte", "Der Crash ist die Lösung", "Kapitalfehler",
         "Sonst knallt's!", "Der größte Crash aller Zeiten",
         "Die größte Chance aller Zeiten"],                                          # Marc Friedrich
    38: ["Mut steht uns gut!"],                                                     # Antje von Dewitz
    44: ["Globale Nomaden Osten", "Globale Nomaden Süden", "Zappenduster",
         "Ritual Knast"],                                                           # Hubertus Becker
    46: ["Du Täter, du Opfer"],                                                     # Carsten Stahl
    48: ["Wie wir uns täglich die Zukunft versauen", "Bright Future Business",
         "Die fünf Zukunftsbrillen", "30 Minuten Zukunftsmanagement"],              # Pero Micic
    50: ["Vegan-Klischee ade!", "Vegan-Klischee ade! Das Kochbuch", "Vegan Low Budget",
         "Vegan ist Unsinn!", "Vegan von Anfang an"],                               # Niko Rittenau
    52: ["Der Abenteurer"],                                                         # Fritz Meinecke
    55: ["Durchschaut", "Deal! Du gibst mir, was ich will!", "Entlarvt!",
          "Überzeugt!"],                                                            # Jack Nasher
    83: ["So läuft Start-up"],                                                      # Florian Gschwandtner
    125: ["Was Google wirklich will", "Zukunftsmedizin"],                            # Thomas Schulz
    131: ["Nachts allein im Ozean"],                                                # André Wiersig
    132: ["Ich weiß, was Hunger ist"],                                               # Tim Raue
    138: ["Ich weiß, was du denkst", "Denken Sie nicht an einen blauen Elefanten!"], # Thorsten Havener
    144: ["Deutschlands Energiewende – Fakten, Mythen und Irrsinn"],                # Andreas Luczak
    149: ["Die Darm-Hirn-Connection", "Higher Self"],                               # Gregor Hasler
    155: ["Die Selbstgerechten", "Reichtum ohne Gier", "Freiheit statt Kapitalismus",
          "Couragiert gegen den Strom"],                                            # Sahra Wagenknecht
    160: ["Von hier an anders", "Wer wir sein könnten"],                            # Robert Habeck
    162: ["Ein Leben ist zu wenig", "Was Politiker nicht sagen"],                   # Gregor Gysi
    166: ["Wer den Wind sät", "Die den Sturm ernten", "Hybris am Hindukusch",
          "Die scheinheilige Supermacht"],                                          # Michael Lüders
    167: ["Mythos Geldknappheit"],                                                  # Maurice Höfgen
    181: ["Differenziertes Krafttraining mit Schwerpunkt Wirbelsäule"],             # Axel Gottlob
    195: ["Illegale Kriege", "NATO-Geheimarmeen in Europa", "Imperium USA"],        # Daniele Ganser
    197: ["Chinas Bosse", "Shenzhen – Die Weltwirtschaft von morgen"],              # Wolfgang Hirn
    201: ["Das trügerische Gedächtnis", "Böse", "Bi", "Green Crime"],               # Julia Shaw
    203: ["Hitlers erster Krieg", "Wie Adolf Hitler zum Nazi wurde"],               # Thomas Weber
    205: ["Die Getriebenen", "Machtverfall", "Letzte Chance"],                      # Robin Alexander
    206: ["Lerne leiden ohne zu klagen"],                                           # Clemens Clausen
    207: ["Das Integrationsparadox", "Mythos Bildung", "Wozu Rassismus?",
          "Misstrauensgemeinschaften", "Kinder – Minderheit ohne Schutz"],          # Aladin El-Mafaalani
    210: ["Auf der Spur des Bösen", "Im Angesicht des Bösen"],                      # Axel Petermann
    212: ["Schattenseiten der Migration", "Darum haben Täter Erfolg"],              # Frank Urbaniok
    216: ["Amerikas Oligarchen"],                                                   # Julian Heißler
    218: ["Influencer – Die Ideologie der Werbekörper"],                            # Wolfgang M. Schmitt
    219: ["Ami, it's time to go!"],                                                 # Oskar Lafontaine
    222: ["Das Ärztehasserbuch", "Empathie"],                                       # Werner Bartens
    227: ["Big Tech muss weg!", "Atlas der digitalen Welt"],                        # Martin Andree
    230: ["Shaolin Life"],                                                          # Sacha Wenk
    234: ["Shore, Stein, Papier"],                                                  # $ick
    239: ["Digitale Demenz", "Cyberkrank!", "Einsamkeit", "Die Smartphone-Epidemie"],  # Manfred Spitzer
    244: ["Unterwegs in Nordkorea", "Nordkorea – Innenansichten eines totalen Staates"],  # Rüdiger Frank
    247: ["Wer hat Angst vorm BND?"],                                               # Gerhard Schindler
    254: ["Triebhaft – Zwischen Narzissten, Sadisten und Psychopathen"],           # Gilda Giebel
    255: ["Blackout", "Zero", "Helix", "Gier", "°C – Celsius"],                     # Marc Elsberg
    262: ["The Struggle for Democracy in Mainland China, Taiwan and Hong Kong"],    # Andreas Fulda
    # ---- Runde 2: einzeln recherchiert ----
    101: ["Das Rätsel Depression", "Depressiv?"],                                 # Ulrich Hegerl
    140: ["Come back stronger", "Fit & stark mit Sophia", "Einfach schlank und fit"],  # Sophia Thiel
    159: ["Der perfekte Augenblick", "Das Jochen Schweizer Prinzip", "Die Begegnung",
          "Warum Menschen fliegen können müssen"],                                # Jochen Schweizer
    161: ["Gefahr ist mein Beruf"],                                               # Josef Resch
    168: ["Requiem für die AfD"],                                                 # Frauke Petry
    169: ["1995 Lichterfelde"],                                                   # Samra
    248: ["Du bist Mentalist!", "Kennen wir uns?", "99 Mind Hacks",
          "Sei deiner Zeit voraus"],                                              # Timon Krause
    251: ["Der Adolf in mir"],                                                    # Serdar Somuncu
}

# ---- Runde 3: blockweise geprüft und abgesegnet ----
BUECHER.update({
    30: ["Im Bann der AfD"],                                                      # Alexander Leschik
    43: ["Out of the Dark"],                                                      # Martin Frost
    54: ["Zone C"],                                                               # Sebastian Caspar
    60: ["Kopfarbeit"],                                                           # Peter Vajkoczy
    49: ["Snapshot Stories"],                                                     # Pascal Kerouche
    59: ["Digital Unplugged"],                                                    # Philipp Westermeyer
    51: ["Edeltalk"],                                                             # Papaplatte
})

# Vielschreiber: weitere Bestseller
BUECHER[239] = BUECHER[239] + ["Lernen"]                                         # Manfred Spitzer
BUECHER[166] = BUECHER[166] + ["Iran: Der falsche Krieg"]                        # Michael Lüders


def _norm(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    probe = "--probe" in sys.argv
    db_pfad = args[0] if args else "datenbank.db"

    conn = sqlite3.connect(db_pfad)
    conn.row_factory = sqlite3.Row
    spalten = [r["name"] for r in conn.execute("PRAGMA table_info(buecher)")]
    if "cover_url" not in spalten and not probe:
        conn.execute("ALTER TABLE buecher ADD COLUMN cover_url TEXT")
    gaeste = {r["folge"]: r for r in conn.execute("SELECT * FROM autoren")}

    neu = uebersprungen = 0
    for folge, titel_liste in sorted(BUECHER.items()):
        gast = gaeste.get(folge)
        if gast is None:
            print(f"  ! Folge {folge} nicht in der DB – übersprungen")
            continue
        vorhanden = {_norm(r["titel"]) for r in
                     conn.execute("SELECT titel FROM buecher WHERE autor_id=?", (gast["id"],))}
        for titel in titel_liste:
            if _norm(titel) in vorhanden:
                uebersprungen += 1
                continue
            print(f"  + #{folge} {gast['name']}: {titel}")
            if not probe:
                conn.execute(
                    "INSERT INTO buecher (titel, link, olid, cover_url, autor_id) "
                    "VALUES (?, ?, '', NULL, ?)",
                    (titel, such_link(titel, gast["name"]), gast["id"]),
                )
            neu += 1

    if not probe:
        conn.commit()
    conn.close()
    modus = "Probelauf – nichts gespeichert" if probe else "gespeichert"
    print(f"\n{neu} Bücher eingetragen, {uebersprungen} schon vorhanden ({modus}).")


if __name__ == "__main__":
    main()
