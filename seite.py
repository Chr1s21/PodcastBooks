"""
Daten und Einstellungen für die öffentliche Seite (nur lesen, nichts bearbeiten).

Die öffentliche Seite wird als statische HTML-Datei nach docs/ exportiert
(python pflege/seite_exportieren.py) und kann so z. B. über GitHub Pages
online gehen. Die Bearbeitungsansicht (app.py) bleibt auf deinem Rechner.
"""

# ---- Hier deine Angaben eintragen (erscheinen im Impressum) ----
SEITE = {
    "titel": "Podcastbücher",
    "untertitel": "Die Bücher der Gäste aus dem Tim Gabel Podcast",
    # Impressum (Pflicht für Seiten mit Partnerlinks in Deutschland)
    "name": "Christian Stier",          # Vor- und Nachname
    "strasse": "Lärchenweg 76",       # Straße und Hausnummer
    "ort": "71665 Vaihingen an der Enz",           # PLZ und Ort
    "email": "podcastbuecher@gmail.com",         # E-Mail-Adresse
}


def impressum_fehlt():
    return not all(SEITE[k].strip() for k in ("name", "strasse", "ort", "email"))


def oeffentliche_daten(conn, cover_fuer=None):
    """Gäste mit Büchern (neueste Folge zuerst) für die öffentliche Seite.

    cover_fuer(buch) -> Bild-URL oder None. Standard: gespeicherte cover_url.
    """
    cover_fuer = cover_fuer or (lambda b: b["cover_url"] or None)

    autoren = conn.execute(
        "SELECT * FROM autoren ORDER BY folge DESC, id DESC").fetchall()
    buecher = conn.execute(
        "SELECT * FROM buecher WHERE link IS NOT NULL AND link != '' ORDER BY id").fetchall()

    nach_autor = {}
    for b in buecher:
        nach_autor.setdefault(b["autor_id"], []).append({
            "titel": b["titel"],
            "link": b["link"],
            "cover": cover_fuer(b),
            "farbe": _farbe(b["titel"]),
        })

    gaeste, zaehler = [], {}
    for a in autoren:
        liste = nach_autor.get(a["id"])
        if not liste:
            continue
        kats = [k.strip() for k in (a["kategorie"] or "").split(",") if k.strip()]
        for k in kats:
            zaehler[k] = zaehler.get(k, 0) + 1
        gaeste.append({
            "folge": a["folge"],
            "name": a["name"],
            "kategorien": kats,
            "buecher": liste,
            "suchtext": " ".join([a["name"], *kats, *(b["titel"] for b in liste)]).lower(),
        })

    kategorien = [k for k, _ in sorted(zaehler.items(), key=lambda x: (-x[1], x[0]))]
    return {
        "gaeste": gaeste,
        "kategorien": kategorien,
        "anzahl_buecher": sum(len(g["buecher"]) for g in gaeste),
        "anzahl_gaeste": len(gaeste),
    }


# Ersatz-Cover ohne Bild: feste Farbe pro Titel aus einer ruhigen Palette
_FARBEN = ["#2B3A67", "#3E5C4A", "#6B3B3B", "#4A4E69", "#2F5D6B", "#5B4A2E", "#3D3B5C", "#58463F"]


def _farbe(titel):
    return _FARBEN[sum(map(ord, titel or "")) % len(_FARBEN)]
