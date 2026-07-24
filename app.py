import sqlite3
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('datenbank.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    
    # 1. Tabelle für Autoren/Gäste
    conn.execute('''
        CREATE TABLE IF NOT EXISTS autoren (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folge INTEGER,
            name TEXT NOT NULL,
            kategorie TEXT     
        )
    ''')
    
    # 2. Tabelle für Bücher (ausschließlich Open Library ID + Link)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS buecher (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titel TEXT NOT NULL,
            link TEXT,
            olid TEXT,               -- Open Library ID (z.B. OL50534585M)
            autor_id INTEGER NOT NULL,
            FOREIGN KEY (autor_id) REFERENCES autoren (id)
        )
    ''')
    
    conn.commit()
    conn.close()

@app.route('/')
def home():
    conn = get_db_connection()
    
    # Sortierung: Neueste Folgen/Einträge immer zuerst (DESC)
    autoren_raw = conn.execute('SELECT * FROM autoren ORDER BY folge DESC, id DESC').fetchall()
    buecher = conn.execute('SELECT * FROM buecher').fetchall()
    conn.close()

    # Kategorien (z.B. "Influencer, Finanzen") in eine Python-Liste umwandeln
    autoren = []
    for autor in autoren_raw:
        a_dict = dict(autor)
        if a_dict['kategorie']:
            a_dict['kategorien_liste'] = [k.strip() for k in a_dict['kategorie'].split(',') if k.strip()]
        else:
            a_dict['kategorien_liste'] = []
        autoren.append(a_dict)

    return render_template('index.html', autoren=autoren, buecher=buecher)

# --- AUTOR ROUTEN ---

@app.route('/add_autor', methods=['POST'])
def add_autor():
    folge = request.form.get('folge')
    name = request.form.get('name')
    kategorie = request.form.get('kategorie')
    
    if name:
        conn = get_db_connection()
        conn.execute('INSERT INTO autoren (folge, name, kategorie) VALUES (?, ?, ?)', 
                     (folge, name, kategorie))
        conn.commit()
        conn.close()
    return redirect(url_for('home'))

@app.route('/edit_autor/<int:id>', methods=['POST'])
def edit_autor(id):
    folge = request.form.get('folge')
    name = request.form.get('name')
    kategorie = request.form.get('kategorie')
    
    if name:
        conn = get_db_connection()
        conn.execute('UPDATE autoren SET folge = ?, name = ?, kategorie = ? WHERE id = ?',
                     (folge, name, kategorie, id))
        conn.commit()
        conn.close()
    return redirect(url_for('home'))

@app.route('/delete_autor/<int:id>', methods=['POST'])
def delete_autor(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM buecher WHERE autor_id = ?', (id,))
    conn.execute('DELETE FROM autoren WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

# --- BUCH ROUTEN ---

@app.route('/add_buch', methods=['POST'])
def add_buch():
    titel = request.form.get('titel')
    link = request.form.get('link')
    olid = request.form.get('olid')
    autor_id = request.form.get('autor_id')
    
    if olid:
        olid = olid.strip()

    if titel and autor_id:
        conn = get_db_connection()
        conn.execute('INSERT INTO buecher (titel, link, olid, autor_id) VALUES (?, ?, ?, ?)',
                     (titel, link, olid, autor_id))
        conn.commit()
        conn.close()
    return redirect(url_for('home'))

@app.route('/edit_buch/<int:id>', methods=['POST'])
def edit_buch(id):
    titel = request.form.get('titel')
    link = request.form.get('link')
    olid = request.form.get('olid')
    autor_id = request.form.get('autor_id')
    
    if olid:
        olid = olid.strip()

    if titel and autor_id:
        conn = get_db_connection()
        conn.execute('UPDATE buecher SET titel = ?, link = ?, olid = ?, autor_id = ? WHERE id = ?',
                     (titel, link, olid, autor_id, id))
        conn.commit()
        conn.close()
    return redirect(url_for('home'))

@app.route('/delete_buch/<int:id>', methods=['POST'])
def delete_buch(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM buecher WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)