"""
Öffentliche Seite als statische Dateien nach docs/ exportieren.

Aufruf (im Projektordner):
    python pflege/seite_exportieren.py

- Erzeugt docs/index.html, docs/impressum.html und docs/datenschutz.html.
- Lädt alle Buchcover nach docs/covers/, damit Besucher keine Anfragen an
  Google oder Open Library schicken (Datenschutz). Schon geladene Cover
  werden übersprungen.
- docs/ kann direkt über GitHub Pages veröffentlicht werden
  (Repo → Settings → Pages → Branch: master, Ordner: /docs).
"""

import os
import sqlite3
import sys
import urllib.request

PROJEKT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJEKT)

from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: E402
from seite import SEITE, oeffentliche_daten, impressum_fehlt  # noqa: E402

ZIEL = os.path.join(PROJEKT, "docs")
COVER_ORDNER = os.path.join(ZIEL, "covers")
PFADE = {"start": "./", "impressum": "impressum.html", "datenschutz": "datenschutz.html"}


def cover_laden(buch, statistik):
    """Lokale Kopie des Covers anlegen; bei Fehlern die Original-URL verwenden."""
    url = buch["cover_url"]
    if not url:
        return None
    for endung in (".jpg", ".png"):
        name = f"{buch['id']}{endung}"
        if os.path.exists(os.path.join(COVER_ORDNER, name)):
            statistik["lokal"] += 1
            return f"covers/{name}"
    try:
        anfrage = urllib.request.Request(url, headers={"User-Agent": "Podcastbuecher/1.0"})
        with urllib.request.urlopen(anfrage, timeout=15) as antwort:
            daten = antwort.read()
            typ = antwort.headers.get("Content-Type", "")
        if len(daten) < 1000:  # leere Platzhalterbilder
            raise ValueError("Bild zu klein")
        name = f"{buch['id']}{'.png' if 'png' in typ else '.jpg'}"
        with open(os.path.join(COVER_ORDNER, name), "wb") as f:
            f.write(daten)
        statistik["geladen"] += 1
        return f"covers/{name}"
    except Exception:
        statistik["fremd"] += 1
        return url


def main():
    os.makedirs(COVER_ORDNER, exist_ok=True)
    conn = sqlite3.connect(os.path.join(PROJEKT, "datenbank.db"))
    conn.row_factory = sqlite3.Row

    statistik = {"lokal": 0, "geladen": 0, "fremd": 0}
    print("Cover werden geladen …")
    daten = oeffentliche_daten(conn, cover_fuer=lambda b: cover_laden(b, statistik))
    conn.close()

    env = Environment(loader=FileSystemLoader(os.path.join(PROJEKT, "templates")),
                      autoescape=select_autoescape(["html"]))
    gemeinsam = {"seite": SEITE, "pfade": PFADE, "impressum_fehlt": impressum_fehlt(),
                 "fremde_cover": statistik["fremd"] > 0}
    for vorlage, datei in (("oeffentlich.html", "index.html"),
                           ("impressum.html", "impressum.html"),
                           ("datenschutz.html", "datenschutz.html")):
        html = env.get_template(vorlage).render(daten=daten, **gemeinsam)
        with open(os.path.join(ZIEL, datei), "w", encoding="utf-8") as f:
            f.write(html)
    open(os.path.join(ZIEL, ".nojekyll"), "w").close()

    print(f"Fertig: docs/index.html mit {daten['anzahl_buecher']} Büchern von "
          f"{daten['anzahl_gaeste']} Gästen.")
    print(f"Cover: {statistik['geladen']} neu geladen, {statistik['lokal']} schon vorhanden, "
          f"{statistik['fremd']} nicht ladbar (werden extern eingebunden).")
    if impressum_fehlt():
        print("\n!! Impressum unvollständig: Name, Anschrift und E-Mail in seite.py eintragen, "
              "bevor die Seite online geht.")


if __name__ == "__main__":
    main()
