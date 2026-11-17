"""
Automatische Buchcover-Suche.

Quellen:
  1. Google Books (sehr gute Abdeckung bei deutschen Büchern)
  2. Open Library (Fallback, ohne Limit-Probleme)

Google Books erlaubt ohne API-Schlüssel nur wenige Anfragen pro Minute.
Optional einen kostenlosen Schlüssel in die Datei .env im Projektordner
schreiben (wird automatisch geladen, ist per .gitignore vom Repo ausgeschlossen):
    GOOGLE_BOOKS_API_KEY=dein-schluessel
Schlüssel anlegen: https://console.cloud.google.com/apis/credentials
(vorher „Books API“ aktivieren). Damit sind ~1000 Anfragen/Tag frei.

Ohne Schlüssel funktioniert alles auch – wenn Google bremst (HTTP 429),
pausiert die Suche Google automatisch und nimmt nur noch Open Library.

Benötigt keine zusätzlichen Pakete (nur Python-Standardbibliothek).
"""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

def _lade_env_datei():
    """Liest KEY=WERT-Zeilen aus .env (im Projektordner) in os.environ.
    Bereits gesetzte Umgebungsvariablen haben Vorrang."""
    pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(pfad):
        return
    with open(pfad, encoding="utf-8-sig") as f:
        for zeile in f:
            zeile = zeile.strip()
            if not zeile or zeile.startswith("#") or "=" not in zeile:
                continue
            key, wert = zeile.split("=", 1)
            key = key.strip().removeprefix("export ").strip()
            wert = wert.strip().strip('"').strip("'")
            os.environ.setdefault(key, wert)


_lade_env_datei()

TIMEOUT = 8
HEADERS = {"User-Agent": "PodcastBuecher/1.0 (privates Projekt)"}
GOOGLE_API_KEY = os.environ.get("GOOGLE_BOOKS_API_KEY", "").strip()

# Bis zu diesem Zeitpunkt (time.time()) wird Google nicht mehr gefragt
_google_pause_bis = 0.0
GOOGLE_PAUSE_SEKUNDEN = 120

# Titel/Präfixe, die als Autor-Suchbegriff nichts taugen
_AUTOR_PRAEFIXE = re.compile(r"\b(Prof\.|Dr\.|med\.|Dipl\.|-Ing\.)\s*", re.IGNORECASE)
_PART = re.compile(r"\s+Part\s+\d+\s*$", re.IGNORECASE)


class GoogleGesperrt(Exception):
    pass


def google_pausiert():
    """True, wenn Google gerade wegen zu vieler Anfragen pausiert wird."""
    return time.time() < _google_pause_bis


def _get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _autor_nachname(autor):
    """'Prof. Dr. Wolfgang Schöllhorn Part 2' -> 'Schöllhorn'"""
    if not autor:
        return None
    sauber = _PART.sub("", _AUTOR_PRAEFIXE.sub("", autor)).strip()
    teile = sauber.split()
    return teile[-1] if teile else None


def _titel_kurz(titel):
    """Untertitel abschneiden: 'Letzte Chance: Der neue Kanzler...' -> 'Letzte Chance'"""
    return re.split(r"\s[:\-–|]\s|: ", titel)[0].strip()


# ---------------- Google Books ----------------

def _google_cover(titel, autor=None):
    global _google_pause_bis
    if google_pausiert():
        raise GoogleGesperrt()

    q = f'intitle:"{titel}"'
    if autor:
        q += f" inauthor:{autor}"
    params = {"q": q, "maxResults": 5, "printType": "books"}
    if GOOGLE_API_KEY:
        params["key"] = GOOGLE_API_KEY
    url = "https://www.googleapis.com/books/v1/volumes?" + urllib.parse.urlencode(params)

    try:
        daten = _get_json(url)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            warte = e.headers.get("Retry-After")
            pause = int(warte) if warte and warte.isdigit() else GOOGLE_PAUSE_SEKUNDEN
            _google_pause_bis = time.time() + pause
            print(f"[Cover-Suche] Google Books bremst (429) – pausiere Google für {pause}s, "
                  f"nutze solange nur Open Library.")
            raise GoogleGesperrt()
        raise

    for item in daten.get("items", []):
        links = item.get("volumeInfo", {}).get("imageLinks", {})
        bild = links.get("thumbnail") or links.get("smallThumbnail")
        if bild:
            return bild.replace("http://", "https://").replace("&edge=curl", "")
    return None


# ---------------- Open Library ----------------

def _openlibrary_cover(titel, autor=None):
    params = {"title": titel, "limit": 5, "fields": "cover_i"}
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
    """Probiert die Quellen der Reihe nach und gibt die erste Cover-URL zurück."""
    if not titel:
        return None
    nachname = _autor_nachname(autor)
    kurz = _titel_kurz(titel)

    # Max. 2 Google-Anfragen pro Buch, Rest über Open Library
    versuche = [
        (_google_cover, titel, nachname),
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
        except GoogleGesperrt:
            continue  # leise überspringen, Meldung kam schon einmal
        except Exception as e:  # Netzwerkfehler usw. -> nächste Quelle
            print(f"[Cover-Suche] {funktion.__name__}({t!r}, {a!r}) fehlgeschlagen: {e}")
    return None
