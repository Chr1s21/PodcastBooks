import sqlite3
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('datenbank.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    
    # 1. Tabelle für die Autoren
    conn.execute('''
        CREATE TABLE IF NOT EXISTS autoren (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            kategorie TEXT     
        )
    ''')
    
    # 2. Tabelle für die Bücher (verknüpft mit der Autoren-ID)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS buecher (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titel TEXT NOT NULL,
            link TEXT,     
            autor_id INTEGER NOT NULL,
            FOREIGN KEY (autor_id) REFERENCES autoren (id)
        )
    ''')
    
  

@app.route('/')
def home():
    conn = get_db_connection()
    
    # Wir holen alle Autoren
    autoren = conn.execute('SELECT * FROM autoren').fetchall()
    
    # Wir holen alle Bücher
    buecher = conn.execute('SELECT * FROM buecher').fetchall()
    
    conn.close()
    
    # Wir übergeben sowohl Autoren als auch Bücher an das HTML
    return render_template('index.html', autoren=autoren, buecher=buecher)

# Route 1: Neuen Autoren hinzufügen
@app.route('/add_autor', methods=['POST'])
def add_autor():
    name = request.form['name']
    if name:
        conn = get_db_connection()
        conn.execute('INSERT INTO autoren (name, kategorie) VALUES (?, ?)', (name, request.form['kategorie']))
        conn.commit()
        conn.close()
    return redirect(url_for('home'))

# Route 2: Neues Buch hinzufügen
@app.route('/add_buch', methods=['POST'])
def add_buch():
    titel = request.form['titel']
    link = request.form['link']
    autor_id = request.form['autor_id']
    
    if titel and autor_id:
        conn = get_db_connection()
        conn.execute('INSERT INTO buecher (titel, link, autor_id) VALUES (?, ?, ?)', 
                     (titel, link, autor_id))
        conn.commit()
        conn.close()
    return redirect(url_for('home'))

# Route zum Löschen eines Buches
@app.route('/delete_buch/<int:id>', methods=['POST'])
def delete_buch(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM buecher WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

# Route zum Löschen eines Autors
@app.route('/delete_autor/<int:id>', methods=['POST'])
def delete_autor(id):
    conn = get_db_connection()
    
    # Optional, aber sauber: Wenn ein Autor gelöscht wird, 
    # löschen wir auch all seine Bücher (Kaskadierung)
    conn.execute('DELETE FROM buecher WHERE autor_id = ?', (id,))
    
    # Jetzt den Autor selbst löschen
    conn.execute('DELETE FROM autoren WHERE id = ?', (id,))
    
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)