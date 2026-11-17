# PodcastBooks

Buchempfehlungen der Gäste aus dem Tim Gabel Podcast (Flask + SQLite).

## Starten

```
python -m venv venv
venv\Scripts\activate        # Windows  (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python app.py
```

Dann http://127.0.0.1:5000 öffnen.

## Buchcover

Cover werden automatisch über Google Books (Fallback: Open Library) anhand von
Titel und Gastname gesucht – beim Speichern eines Buchs oder über den Button
„Fehlende Cover automatisch suchen“. Passt ein Cover nicht, unter „Bearbeiten“
eine eigene Bild-URL eintragen oder „Cover neu suchen“ klicken.

Optional (empfohlen): Google-Books-API-Schlüssel, damit Google nicht bremst.
`.env.example` kopieren, in `.env` umbenennen und Schlüssel eintragen:

```
GOOGLE_BOOKS_API_KEY=dein-schluessel
```

Die `.env` wird beim Start automatisch gelesen und nicht ins Repo hochgeladen.

## Gäste & Kategorien pflegen

`pflege/gaeste_update.py` enthält die Liste aller Folgen mit Namen und
Kategorien. Neue Folge? Eine Zeile in `GAESTE` ergänzen und ausführen:

```
python pflege/gaeste_update.py --probe   # nur anzeigen
python pflege/gaeste_update.py           # speichern
```

Kategorien: Influencer, Unternehmer, Wissenschaftler, Arzt, Sportler, Politiker,
Journalist, Musiker, Entertainer, Autor, Ex-Krimineller, Sicherheit & Militär,
Jurist, Abenteurer, Aktivist.
