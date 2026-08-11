import sqlite3
from flask import Flask, render_template, request, redirect, url_for

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
            autor_id INTEGER NOT NULL,
            FOREIGN KEY (autor_id) REFERENCES autoren(id)
        )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def home():
    # ← merkt sich den zuletzt ausgewählten Autor
    selected_autor = request.args.get("selected_autor")

    conn = get_db_connection()

    autoren_raw = conn.execute(
        "SELECT * FROM autoren ORDER BY folge DESC, id DESC"
    ).fetchall()

    buecher = conn.execute("SELECT * FROM buecher").fetchall()
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

    return render_template(
        "index.html",
        autoren=autoren,
        buecher=buecher,
        selected_autor=selected_autor,
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
    titel = request.form.get("titel")
    link = request.form.get("link")
    olid = request.form.get("olid")
    autor_id = request.form.get("autor_id")

    if olid:
        olid = olid.strip()

    if titel and autor_id:
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO buecher (titel, link, olid, autor_id)
            VALUES (?, ?, ?, ?)
            """,
            (titel, link, olid, autor_id),
        )
        conn.commit()
        conn.close()

    # ← merkt sich den zuletzt gewählten Autor
    return redirect(url_for("home", selected_autor=autor_id))


@app.route("/edit_buch/<int:id>", methods=["POST"])
def edit_buch(id):
    titel = request.form.get("titel")
    link = request.form.get("link")
    olid = request.form.get("olid")
    autor_id = request.form.get("autor_id")

    if olid:
        olid = olid.strip()

    if titel and autor_id:
        conn = get_db_connection()
        conn.execute(
            """
            UPDATE buecher
            SET titel=?, link=?, olid=?, autor_id=?
            WHERE id=?
            """,
            (titel, link, olid, autor_id, id),
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


if __name__ == "__main__":
    init_db()
    app.run(debug=True)