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

## Amazon-Partnerlinks

Partner-Tag: `podcastbueche-21` (änderbar über `AMAZON_PARTNER_TAG=` in der `.env`).

- Neues Buch ohne Link → Partnerlink wird automatisch erstellt.
- Automatische Links führen zur Amazon-Buchsuche nach Titel + Autor
  (`amazon.de/s?k=…&tag=…`). Direkte Produktlinks über die ISBN liefen oft ins
  Leere, weil Amazon.de die Ausgabe aus Google Books nicht führt.
- Willst du für ein Buch einen direkten Link, trag ihn beim Buch selbst ein
  (z. B. per SiteStripe `link.amazon/…`). Eigene Links bleiben immer unverändert.
- **„🔎 Alle Gäste auf fehlende Bücher prüfen“**: geht alle Gäste in 15er-Blöcken
  bei Google Books durch, zeigt pro Gast die bis zu 5 beliebtesten fehlenden Bücher.
- Pro Gast: **„📚 Bücher vorschlagen“** listet alle Bücher, die Google Books
  von diesem Autor kennt – anhaken, speichern, fertig.

## Gäste & Kategorien pflegen

`pflege/gaeste_update.py` enthält die Liste aller Folgen mit Namen und
Kategorien. Neue Folge? Eine Zeile in `GAESTE` ergänzen und ausführen:

```
python pflege/gaeste_update.py --probe   # nur anzeigen
python pflege/gaeste_update.py           # speichern
```

Bücher in größerer Menge: `pflege/buecher_update.py` (Folge → Titel-Liste).

Kategorien: Influencer, Unternehmer, Wissenschaftler, Arzt, Sportler, Politiker,
Journalist, Musiker, Entertainer, Autor, Ex-Krimineller, Sicherheit & Militär,
Jurist, Abenteurer, Aktivist.

## Öffentliche Seite (online stellen)

Besucher sehen eine eigene Seite ohne Bearbeiten-Funktionen. Die Bearbeitungsansicht
(`python app.py`) bleibt auf deinem Rechner und geht nicht online.

1. **Impressum eintragen:** In `seite.py` Name, Anschrift und E-Mail ausfüllen.
   Die Datenschutzerklärung (`templates/datenschutz.html`) ist eine Vorlage – bitte prüfen.
2. **Vorschau ansehen:** App starten und `http://127.0.0.1:5000/vorschau` öffnen.
3. **Exportieren:** `python pflege/seite_exportieren.py`
   – erzeugt `docs/` mit der fertigen Seite und lädt alle Cover nach `docs/covers/`.
4. **Hochladen:** `docs/` committen und pushen.
5. **Einmalig GitHub Pages einschalten:** Repo → Settings → Pages →
   „Deploy from a branch“, Branch `master`, Ordner `/docs`.
   Die Seite ist dann unter `https://chr1s21.github.io/PodcastBooks/` erreichbar.

Nach jeder Änderung an Büchern oder Gästen: Schritt 3 und 4 wiederholen.
