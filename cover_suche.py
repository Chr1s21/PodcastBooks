"""
Automatische Buchcover-Suche.

Reihenfolge:
  1. Google Books (sehr gute Abdeckung bei deutschen Büchern)
  2. Open Library (Fallback)

Jede Quelle wird erst mit Titel + Autor, dann nur mit Titel abgefragt.
Ergebnis ist eine fertige Bild-URL (https) oder None.
Benötigt keine zusätzlichen Pakete (nur Python-Standardbibliothek).
"""

import json
import re
import urllib.parse
import urllib.request

TIMEOUT = 8
HEADERS = {"User-Agent": "PodcastBuecher/1.0 (privates Projekt)"}

# Titel/Präfixe, die als Autor-Suchbegriff nichts taugen
_AUTOR_PRAEFIXE = re.compile(r"\b(Prof\.|Dr\.|med\.|Dipl\.|-Ing\.)\s*", re.IGNORECASE)


def _get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _autor_nachname(autor):
    """'Prof. Dr. Wolfgang Schöllhorn' -> 'Schöllhorn'"""
    if not autor:
        return None
    sauber = _AUTOR_PRAEFIXE.sub("", autor).strip()
    teile = sauber.split()
    return teile[-1] if teile else None


def _titel_kurz(titel):
    """Untertitel abschneiden: 'Letzte Chance: Der neue Kanzler...' -> 'Letzte Chance'"""
    return re.split(r"\s[:\-–|]\s|: ", titel)[0].strip()


# ---------------- Google Books ----------------

def _google_cover(titel, autor=None):
    q = f'intitle:"{titel}"'
    if autor:
        q += f" inauthor:{autor}"
    url = (
        "https://www.googleapis.com/books/v1/volumes?"
        + urllib.parse.urlencode({"q": q, "maxResults": 5, "printType": "books"})
    )
    daten = _get_json(url)
    for item in daten.get("items", []):
        links = item.get("volumeInfo", {}).get("imageLinks", {})
        bild = links.get("thumbnail") or links.get("smallThumbnail")
        if bild:
            bild = bild.replace("http://", "https://")
            bild = bild.replace("&edge=curl", "")
            # zoom=1 ist das Standard-Thumbnail; höhere Werte liefern oft kein Bild
            return bild
    return None


# ---------------- Open Library ----------------

def _openlibrary_cover(titel, autor=None):
    params = {"title": titel, "limit": 5, "fields": "cover_i,cover_edition_key"}
    if autor:
        params["author"] = autor
    url = "https://openlibrary.org/search.json?" + urllib.parse.urlencode(params)
    daten = _get_json(url)
    for doc in daten.get("docs", []):
        if doc.get("cover_i"):
            return f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-L.jpg"
    return None


def cover_von_olid(olid):
    """Manuell eingetragene Open-Library-ID weiterhin unterstützen."""
    olid = (olid or "").strip()
    if not olid:
        return None
    return f"https://covers.openlibrary.org/b/olid/{olid}-L.jpg?default=false"


def finde_cover(titel, autor=None):
    """Probiert alle Quellen durch und gibt die erste gefundene Cover-URL zurück."""
    if not titel:
        return None
    nachname = _autor_nachname(autor)
    kurz = _titel_kurz(titel)

    versuche = [
        (_google_cover, titel, nachname),
        (_google_cover, kurz, nachname),
        (_openlibrary_cover, titel, nachname),
        (_google_cover, kurz, None),
        (_openlibrary_cover, kurz, None),
    ]
    gesehen = set()
    for funktion, t, a in versuche:
        schluessel = (funktion.__name__, t, a)
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        try:
            url = funktion(t, a)
            if url:
                return url
        except Exception as e:  # Netzwerkfehler, Rate-Limit usw. -> nächste Quelle
            print(f"[Cover-Suche] {funktion.__name__}({t!r}, {a!r}) fehlgeschlagen: {e}")
    return None
