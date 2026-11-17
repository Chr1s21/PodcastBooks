import sqlite3
import time
from flask import Flask, render_template, request, redirect, url_for

from cover_suche import finde_cover, cover_von_olid

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


def ermittle_cover(conn, titel, autor_id, olid, cover_url_manuell):
    """Priorität: manuell eingetragene Bild-URL > Open Library ID > automatische Suche."""
    if cover_url_manuell:
        return cover_url_manuell.strip()
    if olid:
        return cover_von_olid(olid)
    return finde_cover(titel, autor_name(conn, autor_id))


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
        "SELECT COUNT(*) FROM buecher WHERE cover_url IS NULL OR cover_url=''"
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
        cover_url = ermittle_cover(conn, titel, autor_id, olid, cover_manuell)
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
        elif neu_suchen or titel_geaendert or olid_geaendert or not cover_manuell:
            cover_url = ermittle_cover(conn, titel, autor_id, olid, "")
        else:
            cover_url = alte_url                           # nichts geändert

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


# ---------------- COVER ----------------

@app.route("/covers_nachladen", methods=["POST"])
def covers_nachladen():
    """Sucht für alle Bücher ohne Cover automatisch eines."""
    conn = get_db_connection()
    offen = conn.execute(
        """
        SELECT b.id, b.titel, b.olid, a.name AS autor
        FROM buecher b LEFT JOIN autoren a ON a.id = b.autor_id
        WHERE b.cover_url IS NULL OR b.cover_url = ''
        """
    ).fetchall()

    gefunden = 0
    for b in offen:
        url = cover_von_olid(b["olid"]) if b["olid"] else finde_cover(b["titel"], b["autor"])
        if url:
            conn.execute("UPDATE buecher SET cover_url=? WHERE id=?", (url, b["id"]))
            conn.commit()
            gefunden += 1
        time.sleep(0.3)  # APIs nicht überlasten

    conn.close()
    meldung = f"{gefunden} von {len(offen)} Covern gefunden."
    return redirect(url_for("home", meldung=meldung))


@app.route("/cover_neu/<int:id>", methods=["POST"])
def cover_neu(id):
    """Cover für ein einzelnes Buch neu suchen."""
    conn = get_db_connection()
    b = conn.execute(
        """
        SELECT b.titel, b.olid, a.name AS autor
        FROM buecher b LEFT JOIN autoren a ON a.id = b.autor_id WHERE b.id=?
        """,
        (id,),
    ).fetchone()
    if b:
        url = cover_von_olid(b["olid"]) if b["olid"] else finde_cover(b["titel"], b["autor"])
        conn.execute("UPDATE buecher SET cover_url=? WHERE id=?", (url, id))
        conn.commit()
    conn.close()
    return redirect(url_for("home"))


# Läuft auch beim Start über "flask run"
init_db()

if __name__ == "__main__":
    app.run(debug=True)
