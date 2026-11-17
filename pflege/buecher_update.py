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
         "Vegan ist Unsinn!"],                               # Niko Rittenau
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
    197: ["Chinas Bosse", "Shenzhen"],              # Wolfgang Hirn
    201: ["Das trügerische Gedächtnis", "Böse", "Bi", "Green Crime"],               # Julia Shaw
    203: ["Hitlers erster Krieg", "Wie Adolf Hitler zum Nazi wurde"],               # Thomas Weber
    205: ["Die Getriebenen", "Machtverfall", "Letzte Chance"],                      # Robin Alexander
    206: ["Lerne leiden ohne zu klagen"],                                           # Clemens Clausen
    207: ["Das Integrationsparadox", "Mythos Bildung", "Wozu Rassismus?",
          "Misstrauensgemeinschaften", "Kinder – Minderheit ohne Schutz"],          # Aladin El-Mafaalani
    210: ["Auf der Spur des Bösen", "Im Angesicht des Bösen"],                      # Axel Petermann
    212: ["Schattenseiten der Migration"],              # Frank Urbaniok
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

# ---- Runde 4: Blöcke 61–210 geprüft und abgesegnet ----
RUNDE_4 = {
    68: ["My Miracle Mindset"],                                                   # Urs Kalecinski
    69: ["Shaolin Spirit"],                                                       # Shi Heng Yi
    71: ["Die Arthrose-Sprechstunde"],                                            # Markus Klingenberg
    77: ["Green Power"],                                                          # Paul Unterleitner
    79: ["Meisterkurs Rhetorik", "Meisterkurs Schlagfertigkeit"],                 # Redefabrik
    81: ["Ich höre dich"],                                                        # Veronika Wolter
    82: ["Let's rock education", "Der Classroom-Coach"],                          # Daniel Jung
    89: ["Der Protein-Fasten-Trick"],                                             # Christian Wolf
    90: ["Nach ganz oben"],                                                       # David Döbele
    93: ["Trail der Träume", "HOMERUN"],                                          # Savas Coban
    100: ["Becoming Bulletproof"],                                                # Otto Bulletproof
    101: ["Depressionen bewältigen"],                                             # Ulrich Hegerl
    102: ["Glück gehabt!!!"],                                                     # Aaron Troschke
    106: ["Ich! Die Kraft des Narzissmus"],                                       # Mitja Back
    113: ["Feel good"],                                                           # Doc Felix
    119: ["Mutproben"],                                                           # Thomas Hitzlsperger
    127: ["Hypertrophietraining"],                                                # Stephan Geisler
    132: ["My Way", "Herr Raue reist", "Rezepte aus der Brasserie", "360° Berlin"],  # Tim Raue
    133: ["Erfolgreich wissenschaftlich investieren"],                            # Andreas Beck
    138: ["Denk doch, was du willst", "Ich sehe das, was du nicht sagst",
          "Sag es keinem weiter"],                                                # Thorsten Havener
    139: ["Und täglich grüßt der Tigervater", "Kartoffelbrei mit Stäbchen"],      # Thomas Derksen
    140: ["Fitness Sweets", "Mit Meal Prep zur Traumfigur"],                      # Sophia Thiel
    149: ["Resilienz: Der Wir-Faktor", "Was uns wirklich nährt"],                 # Gregor Hasler
    160: ["Den Bach rauf"],                                                       # Robert Habeck
    162: ["Mein Leben in 13 Büchern", "Marx und wir", "Gysi vs. Sonneborn"],      # Gregor Gysi
    167: ["Teuer!"],                                                              # Maurice Höfgen
    176: ["Jeden Tag einen Schritt"],                                                     # Philip Hopf
    186: ["Nimm dir alles, gib viel", "Die Supermilf"],                           # Verona Pooth
    188: ["Deine Atmung ändert alles!"],                                          # Tom Sietas
    190: ["Janez"],                                                               # Janez Ekart
    193: ["Wenn Jugendliche trinken"],                                            # Rainer Thomasius
    195: ["Europa im Erdölrausch", "Kampf der Giganten"],                         # Daniele Ganser
    197: ["Der Tech-Krieg", "Herausforderung China"],                             # Wolfgang Hirn
    198: ["All in"],                                                              # Fedor Holz
    210: ["Der Profiler", "Im Auftrag der Toten", "Die Psyche des Bösen"],        # Axel Petermann
}
# ---- Runde 5: Block 211–262 geprüft und abgesegnet ----
RUNDE_4.update({
    215: ["TITAN. (D)ein Weg ins Cockpit"],                                       # Gerald Groß
    218: ["Die kleinen Holzdiebe und das Rätsel des Juggernaut"],                 # Wolfgang M. Schmitt
    219: ["Das Herz schlägt links", "Die Wut wächst"],                            # Oskar Lafontaine
    222: ["Körperglück", "Was Paare zusammenhält", "Emotionale Gewalt"],          # Werner Bartens
    227: ["Krieg der Medien"],                                                    # Martin Andree
    228: ["Der Taschenanwalt", "Das einzige Buch über Recht, das du lesen musst",
          "Welches Recht gilt bei Mord im Weltraum?", "WTF?! So tickt das Netz",
          "Recht im Online-Marketing"],                                           # Christian Solmecke
    234: ["Räuberpistolen"],                                                      # $ick
    236: ["Das einzige Buch, das Du über Finanzen lesen solltest"],               # Finanzfluss
    238: ["Heute komme ich zuerst", "Gesundgevögelt", "Life Changing Sex"],       # Susanne Wendel
    243: ["König im Schatten"],                                                   # Manuellsen
    245: ["Die Akte Tengelmann", "Wir verlieren dieses Land"],                    # Liv von Boetticher
    249: ["Im Ministerium der Lügen"],                                            # Boris Bondarew
    253: ["Darm gut, alles gut"],                                                 # Luisa Werner
    257: ["Mit Physik auf der Suche nach dem Sinn des Lebens",
          "Mit Physik auf der Suche nach der Zukunft der Menschheit"],            # Tim Vollert
})
for _folge, _titel in RUNDE_4.items():
    BUECHER[_folge] = BUECHER.get(_folge, []) + _titel

# Titelkorrekturen: (Folge, alter Titel) -> neuer Titel
UMBENENNEN = {
    (197, "Shenzhen – Die Weltwirtschaft von morgen"): "Shenzhen",                # Wolfgang Hirn
    (10, "Bitcoin und der Gelduntergang"): "Der Bitcoin-Gelduntergang",           # Christian Rieck
    (13, "Die Autobiografie: Startup-DNA"): "Startup-DNA",                         # Frank Thelen
    (176, "Next Level"): "Jeden Tag einen Schritt",                                # Philip Hopf (NXT LVL = Verlag)
}

# Prüfung aller Bücher: existieren nicht oder sind nicht vom Gast -> entfernen
LOESCHEN = {
    2: ["Die Kamerahure"],                                                        # Marcus von Anhalt
    10: ["Von PowerPoint zum Kraftpunkt", "Fernglas-Praxis",
         "Theorie des rationalen Bauherrn"],                                      # Christian Rieck
    11: ["Sozialpsychologie für Dummies"],                                        # Autor: Daniel Richardson
    14: ["Kieleck"],                                                              # Maximilian Pollux
    16: ["Brückenschläge"],                                                       # Christian Lindner
    21: ["Der Paradiesjäger (Band 1)", "Der Paradiesjäger (Band 2)",
         "Der Paradiesjäger (Band 3)"],                                           # Gangerl
    28: ["Potzblitz"],                                                            # Sammelband anderer Hrsg.
    29: ["Der Fairness-Faktor"],                                                  # Henning Beck
    50: ["Vegan von Anfang an"],                                                  # Autor nicht belegt
    212: ["Darum haben Täter Erfolg"],                                            # nicht belegt
}


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

    for (folge, alt), neu_titel in UMBENENNEN.items():
        gast = gaeste.get(folge)
        if gast is None:
            continue
        for b in conn.execute("SELECT id, link FROM buecher WHERE autor_id=? AND titel=?",
                              (gast["id"], alt)).fetchall():
            print(f"  ~ #{folge} {gast['name']}: {alt} -> {neu_titel}")
            if not probe:
                link = b["link"]
                if not link or "amazon.de/s?" in link:
                    link = such_link(neu_titel, gast["name"])
                conn.execute("UPDATE buecher SET titel=?, link=? WHERE id=?",
                             (neu_titel, link, b["id"]))

    for folge, titel_liste in LOESCHEN.items():
        gast = gaeste.get(folge)
        if gast is None:
            continue
        weg = {_norm(t) for t in titel_liste}
        for b in conn.execute("SELECT id, titel FROM buecher WHERE autor_id=?", (gast["id"],)).fetchall():
            if _norm(b["titel"]) in weg:
                print(f"  - #{folge} {gast['name']}: {b['titel']}")
                if not probe:
                    conn.execute("DELETE FROM buecher WHERE id=?", (b["id"],))

    # /dp/-Links laufen oft ins Leere -> Amazon-Suche nach Titel + Autor
    umgestellt = 0
    for b in conn.execute("SELECT b.id, b.titel, a.name FROM buecher b JOIN autoren a "
                          "ON a.id = b.autor_id WHERE b.link LIKE '%amazon.de/dp/%'").fetchall():
        umgestellt += 1
        if not probe:
            conn.execute("UPDATE buecher SET link=? WHERE id=?", (such_link(b["titel"], b["name"]), b["id"]))
    if umgestellt:
        print(f"  {umgestellt} Produktlinks (/dp/) auf die Amazon-Suche umgestellt")

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
