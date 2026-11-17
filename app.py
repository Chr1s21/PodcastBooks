import sqlite3
import time
from flask import Flask, render_template, request, redirect, url_for

from cover_suche import (finde_buchdaten, cover_von_olid, buecher_von_autor,
                         google_pausiert, openlibrary_pausiert, QuelleGesperrt, _norm)
from amazon import partner_link, dp_link, ist_suchlink, autor_sauber
from seite import SEITE, oeffentliche_daten, impressum_fehlt

app = Flask(__name__)


def get_db_connection():
    conn = sqlite3.connect("datenbank.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS autoren (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folge INTEGER,
            name TEXT NOT NULL,
            kategorie TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS buecher (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titel TEXT NOT NULL,
            link TEXT,
            olid TEXT,
            cover_url TEXT,
            autor_id INTEGER NOT NULL,
            FOREIGN KEY (autor_id) REFERENCES autoren(id)
        )
    """)

    # Bestehende Datenbank um die Spalte cover_url erweitern (einmalig)
    spalten = [r["name"] for r in conn.execute("PRAGMA table_info(buecher)")]
    if "cover_url" not in spalten:
        conn.execute("ALTER TABLE buecher ADD COLUMN cover_url TEXT")

    conn.commit()
    conn.close()


def autor_name(conn, autor_id):
    row = conn.execute("SELECT name FROM autoren WHERE id=?", (autor_id,)).fetchone()
    return row["name"] if row else None


def ermittle_cover_und_link(conn, titel, autor_id, olid, cover_manuell, link):
    """Cover: eigene Bild-URL > Open Library ID > automatische Suche.
    Link: eigener Link bleibt; leer oder Amazon-Suchlink -> Partnerlink
    (direkt aufs Produkt, wenn eine ISBN gefunden wird)."""
    autor = autor_name(conn, autor_id)
    link = (link or "").strip()
    cover = cover_manuell.strip() if cover_manuell else (cover_von_olid(olid) if olid else None)

    braucht_suche = not cover or not link or ist_suchlink(link)
    daten = finde_buchdaten(titel, autor) if braucht_suche else {"cover": None, "isbn10": None}

    cover = cover or daten["cover"]
    if not link or ist_suchlink(link):
        link = partner_link(titel, autor, daten["isbn10"])
    return cover, link


@app.route("/")
def home():
    # ← merkt sich den zuletzt ausgewählten Autor
    selected_autor = request.args.get("selected_autor")
    meldung = request.args.get("meldung")

    conn = get_db_connection()

    autoren_raw = conn.execute(
        "SELECT * FROM autoren ORDER BY folge DESC, id DESC"
    ).fetchall()

    buecher = conn.execute("SELECT * FROM buecher").fetchall()
    ohne_cover = conn.execute(
        "SELECT COUNT(*) FROM buecher WHERE cover_url IS NULL OR cover_url='' "
        "OR link IS NULL OR link='' OR link LIKE '%amazon.de/s?%'"
    ).fetchone()[0]
    conn.close()

    autoren = []
    for autor in autoren_raw:
        a = dict(autor)
        if a["kategorie"]:
            a["kategorien_liste"] = [
                k.strip() for k in a["kategorie"].split(",") if k.strip()
            ]
        else:
            a["kategorien_liste"] = []
        autoren.append(a)

    # Kategorien mit Anzahl für die Filter-Buttons (häufigste zuerst)
    zaehler = {}
    for a in autoren:
        for k in a["kategorien_liste"]:
            zaehler[k] = zaehler.get(k, 0) + 1
    alle_kategorien = sorted(zaehler.items(), key=lambda x: (-x[1], x[0]))

    return render_template(
        "index.html",
        autoren=autoren,
        buecher=buecher,
        selected_autor=selected_autor,
        ohne_cover=ohne_cover,
        meldung=meldung,
        alle_kategorien=alle_kategorien,
    )


# ---------------- ÖFFENTLICHE SEITE (Vorschau) ----------------
# So sehen Besucher die Seite. Online geht sie als statischer Export
# (python pflege/seite_exportieren.py), nicht über diese App.

VORSCHAU_PFADE = {"start": "/vorschau", "impressum": "/vorschau/impressum",
                  "datenschutz": "/vorschau/datenschutz"}


def _vorschau(vorlage):
    conn = get_db_connection()
    daten = oeffentliche_daten(conn)
    conn.close()
    return render_template(vorlage, daten=daten, seite=SEITE, pfade=VORSCHAU_PFADE,
                           impressum_fehlt=impressum_fehlt(), fremde_cover=True)


@app.route("/vorschau")
def vorschau():
    return _vorschau("oeffentlich.html")


@app.route("/vorschau/impressum")
def vorschau_impressum():
    return _vorschau("impressum.html")


@app.route("/vorschau/datenschutz")
def vorschau_datenschutz():
    return _vorschau("datenschutz.html")


# ---------------- AUTOREN ----------------

@app.route("/add_autor", methods=["POST"])
def add_autor():
    folge = request.form.get("folge")
    name = request.form.get("name")
    kategorie = request.form.get("kategorie")

    if name:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO autoren (folge, name, kategorie) VALUES (?, ?, ?)",
            (folge, name, kategorie),
        )
        conn.commit()
        conn.close()

    return redirect(url_for("home"))


@app.route("/edit_autor/<int:id>", methods=["POST"])
def edit_autor(id):
    folge = request.form.get("folge")
    name = request.form.get("name")
    kategorie = request.form.get("kategorie")

    if name:
        conn = get_db_connection()
        conn.execute(
            "UPDATE autoren SET folge=?, name=?, kategorie=? WHERE id=?",
            (folge, name, kategorie, id),
        )
        conn.commit()
        conn.close()

    return redirect(url_for("home"))


@app.route("/delete_autor/<int:id>", methods=["POST"])
def delete_autor(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM buecher WHERE autor_id=?", (id,))
    conn.execute("DELETE FROM autoren WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("home"))


# ---------------- BÜCHER ----------------

@app.route("/add_buch", methods=["POST"])
def add_buch():
    titel = (request.form.get("titel") or "").strip()
    link = request.form.get("link")
    olid = (request.form.get("olid") or "").strip()
    cover_manuell = (request.form.get("cover_url") or "").strip()
    autor_id = request.form.get("autor_id")

    if titel and autor_id:
        conn = get_db_connection()
        cover_url, link = ermittle_cover_und_link(conn, titel, autor_id, olid, cover_manuell, link)
        conn.execute(
            """
            INSERT INTO buecher (titel, link, olid, cover_url, autor_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (titel, link, olid, cover_url, autor_id),
        )
        conn.commit()
        conn.close()

    # ← merkt sich den zuletzt gewählten Autor
    return redirect(url_for("home", selected_autor=autor_id))


@app.route("/edit_buch/<int:id>", methods=["POST"])
def edit_buch(id):
    titel = (request.form.get("titel") or "").strip()
    link = request.form.get("link")
    olid = (request.form.get("olid") or "").strip()
    cover_manuell = (request.form.get("cover_url") or "").strip()
    neu_suchen = request.form.get("neu_suchen") == "1"
    autor_id = request.form.get("autor_id")

    if titel and autor_id:
        conn = get_db_connection()
        alt = conn.execute("SELECT * FROM buecher WHERE id=?", (id,)).fetchone()

        alte_url = (alt["cover_url"] or "") if alt else ""
        titel_geaendert = alt is not None and alt["titel"] != titel
        olid_geaendert = alt is not None and (alt["olid"] or "") != olid
        url_von_hand_geaendert = cover_manuell and cover_manuell != alte_url

        if url_von_hand_geaendert and not neu_suchen:
            cover_url = cover_manuell                      # eigene Bild-URL gewinnt
            if not (link or "").strip():
                _, link = ermittle_cover_und_link(conn, titel, autor_id, olid, cover_url, "")
        elif neu_suchen or titel_geaendert or olid_geaendert or not cover_manuell:
            if titel_geaendert and ist_suchlink(link):
                link = ""                                  # Suchlink passt nicht mehr zum Titel
            cover_url, link = ermittle_cover_und_link(conn, titel, autor_id, olid, "", link)
        else:
            cover_url = alte_url                           # nichts geändert
            if not (link or "").strip():
                _, link = ermittle_cover_und_link(conn, titel, autor_id, olid, cover_url, "")

        conn.execute(
            """
            UPDATE buecher
            SET titel=?, link=?, olid=?, cover_url=?, autor_id=?
            WHERE id=?
            """,
            (titel, link, olid, cover_url, autor_id, id),
        )
        conn.commit()
        conn.close()

    return redirect(url_for("home"))


@app.route("/delete_buch/<int:id>", methods=["POST"])
def delete_buch(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM buecher WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("home"))


# ---------------- COVER & PARTNERLINKS ----------------

def _buch_aktualisieren(conn, b):
    """Fehlendes Cover suchen und Amazon-Suchlinks auf Produktlinks umstellen.
    Gibt (cover_neu, link_neu) als bool zurück."""
    hat_cover = bool(b["cover_url"])
    link = b["link"] or ""
    if hat_cover and link and not ist_suchlink(link):
        return False, False

    if b["olid"] and not hat_cover:
        daten = {"cover": cover_von_olid(b["olid"]), "isbn10": None}
        if not link or ist_suchlink(link):
            daten["isbn10"] = finde_buchdaten(b["titel"], b["autor"])["isbn10"]
    else:
        daten = finde_buchdaten(b["titel"], b["autor"])

    cover_neu = link_neu = False
    if not hat_cover and daten["cover"]:
        conn.execute("UPDATE buecher SET cover_url=? WHERE id=?", (daten["cover"], b["id"]))
        cover_neu = True
    if daten["isbn10"] and (not link or ist_suchlink(link)):
        conn.execute("UPDATE buecher SET link=? WHERE id=?", (dp_link(daten["isbn10"]), b["id"]))
        link_neu = True
    elif not link:
        conn.execute("UPDATE buecher SET link=? WHERE id=?",
                     (partner_link(b["titel"], b["autor"]), b["id"]))
        link_neu = True
    conn.commit()
    return cover_neu, link_neu


@app.route("/covers_nachladen", methods=["POST"])
def covers_nachladen():
    """Sucht fehlende Cover und macht aus Amazon-Suchlinks direkte Produktlinks."""
    conn = get_db_connection()
    offen = conn.execute(
        """
        SELECT b.id, b.titel, b.olid, b.cover_url, b.link, a.name AS autor
        FROM buecher b LEFT JOIN autoren a ON a.id = b.autor_id
        WHERE b.cover_url IS NULL OR b.cover_url = ''
           OR b.link IS NULL OR b.link = '' OR b.link LIKE '%amazon.de/s?%'
        """
    ).fetchall()

    covers = links = 0
    gebremst = False
    for b in offen:
        c, l = _buch_aktualisieren(conn, b)
        covers += c
        links += l
        if google_pausiert() or openlibrary_pausiert():
            gebremst = True
        time.sleep(1.0)  # APIs nicht überlasten

    conn.close()
    meldung = f"{len(offen)} Bücher geprüft: {covers} Cover gefunden, {links} Partnerlinks verbessert."
    if gebremst:
        meldung += (" Google Books oder Open Library war zwischendurch überlastet – für die restlichen "
                    "in ein paar Minuten nochmal auf den Button klicken.")
    return redirect(url_for("home", meldung=meldung))


@app.route("/cover_neu/<int:id>", methods=["POST"])
def cover_neu(id):
    """Cover (und ggf. Partnerlink) für ein einzelnes Buch neu suchen."""
    conn = get_db_connection()
    b = conn.execute(
        """
        SELECT b.id, b.titel, b.olid, b.link, a.name AS autor
        FROM buecher b LEFT JOIN autoren a ON a.id = b.autor_id WHERE b.id=?
        """,
        (id,),
    ).fetchone()
    if b:
        b = dict(b)
        b["cover_url"] = None  # erzwingt neue Cover-Suche
        conn.execute("UPDATE buecher SET cover_url=NULL WHERE id=?", (id,))
        _buch_aktualisieren(conn, b)
    conn.close()
    return redirect(url_for("home"))


# ---------------- BÜCHER-VORSCHLÄGE PRO GAST ----------------

@app.route("/vorschlaege/<int:autor_id>")
def vorschlaege(autor_id):
    """Zeigt Bücher, die Google Books zu diesem Gast als Autor kennt."""
    conn = get_db_connection()
    autor = conn.execute("SELECT * FROM autoren WHERE id=?", (autor_id,)).fetchone()
    vorhandene = {_norm(r["titel"]) for r in
                  conn.execute("SELECT titel FROM buecher WHERE autor_id=?", (autor_id,))}
    conn.close()
    if not autor:
        return redirect(url_for("home"))

    fehler = None
    try:
        treffer = buecher_von_autor(autor["name"])
    except QuelleGesperrt:
        treffer, fehler = [], ("Google Books bremst gerade (zu viele Anfragen). "
                               "Bitte in ein paar Minuten nochmal versuchen – "
                               "mit API-Schlüssel in der .env passiert das kaum.")
    except Exception as e:
        treffer, fehler = [], f"Google Books nicht erreichbar: {e}"

    for t in treffer:
        t["schon_da"] = _norm(t["titel"]) in vorhandene
    return render_template("vorschlaege.html", autor=autor, treffer=treffer,
                           fehler=fehler, suchname=autor_sauber(autor["name"]))


@app.route("/vorschlaege/<int:autor_id>", methods=["POST"])
def vorschlaege_speichern(autor_id):
    conn = get_db_connection()
    autor = autor_name(conn, autor_id)
    anzahl = 0
    for wert in request.form.getlist("buch"):
        # Format: isbn10|cover|titel  (isbn/cover können leer sein)
        isbn10, cover, titel = (wert.split("|", 2) + ["", "", ""])[:3]
        if not titel:
            continue
        conn.execute(
            "INSERT INTO buecher (titel, link, olid, cover_url, autor_id) VALUES (?, ?, '', ?, ?)",
            (titel, partner_link(titel, autor, isbn10 or None), cover or None, autor_id),
        )
        anzahl += 1
    conn.commit()
    conn.close()
    return redirect(url_for("home", selected_autor=autor_id,
                            meldung=f"{anzahl} Bücher für {autor} hinzugefügt."))


# ---------------- ALLE GÄSTE PRÜFEN ----------------

PRUEF_BLOCK = 15        # Gäste pro Seite
MAX_PRO_GAST = 5        # bei Vielschreibern nur die beliebtesten


@app.route("/pruefen")
def pruefen():
    """Prüft blockweise jeden Gast gegen Google Books und schlägt fehlende Bücher vor."""
    start = max(int(request.args.get("start", 0) or 0), 0)
    conn = get_db_connection()
    alle = conn.execute("SELECT * FROM autoren ORDER BY folge, id").fetchall()

    # Gleiche Person (Part 2, Part 3 …) nur einmal prüfen, Bücher gehören zum ersten Eintrag
    personen, gesehen = [], {}
    for a in alle:
        schluessel = _norm(autor_sauber(a["name"]))
        if schluessel in gesehen:
            gesehen[schluessel]["ids"].append(a["id"])
            continue
        eintrag = {"autor": a, "ids": [a["id"]]}
        gesehen[schluessel] = eintrag
        personen.append(eintrag)

    block = personen[start:start + PRUEF_BLOCK]
    ergebnisse, fehler = [], None
    for p in block:
        ids = p["ids"]
        vorhandene = {_norm(r["titel"]) for r in conn.execute(
            f"SELECT titel FROM buecher WHERE autor_id IN ({','.join('?' * len(ids))})", ids)}
        try:
            treffer = buecher_von_autor(p["autor"]["name"])
        except QuelleGesperrt:
            fehler = ("Google Books bremst gerade. Bitte kurz warten und die Seite neu laden "
                      "(mit API-Schlüssel in der .env passiert das kaum).")
            break
        except Exception as e:
            fehler = f"Google Books nicht erreichbar: {e}"
            break
        neu = [t for t in treffer if _norm(t["titel"]) not in vorhandene]
        neu.sort(key=lambda t: (not t["exakt"], -t["bewertungen"], not t["isbn10"]))
        if neu:
            ergebnisse.append({"autor": p["autor"], "treffer": neu[:MAX_PRO_GAST],
                               "weitere": max(len(neu) - MAX_PRO_GAST, 0)})
        time.sleep(0.3)
    conn.close()

    weiter = start + PRUEF_BLOCK if start + PRUEF_BLOCK < len(personen) else None
    return render_template("pruefen.html", ergebnisse=ergebnisse, fehler=fehler,
                           start=start, ende=min(start + PRUEF_BLOCK, len(personen)),
                           gesamt=len(personen), weiter=weiter, block=block)


@app.route("/pruefen", methods=["POST"])
def pruefen_speichern():
    conn = get_db_connection()
    anzahl = 0
    for wert in request.form.getlist("buch"):
        # Format: autor_id|isbn10|cover|titel
        teile = (wert.split("|", 3) + ["", "", "", ""])[:4]
        autor_id, isbn10, cover, titel = teile
        if not (autor_id and titel):
            continue
        autor = autor_name(conn, autor_id)
        conn.execute(
            "INSERT INTO buecher (titel, link, olid, cover_url, autor_id) VALUES (?, ?, '', ?, ?)",
            (titel, partner_link(titel, autor, isbn10 or None), cover or None, autor_id),
        )
        anzahl += 1
    conn.commit()
    conn.close()
    weiter = request.form.get("weiter")
    if weiter:
        return redirect(url_for("pruefen", start=weiter))
    return redirect(url_for("home", meldung=f"Prüfung fertig – zuletzt {anzahl} Bücher hinzugefügt."))


# Läuft auch beim Start über "flask run"
init_db()

if __name__ == "__main__":
    app.run(debug=True)
