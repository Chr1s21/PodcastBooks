"""
Buchdaten-Suche: Cover, ISBN und Bücherlisten pro Autor.

Quellen:
  1. Google Books (sehr gute Abdeckung bei deutschen Büchern)
  2. Open Library (Fallback)

Google Books erlaubt ohne API-Schlüssel nur wenige Anfragen pro Minute.
Optional einen kostenlosen Schlüssel in die Datei .env im Projektordner
schreiben (wird automatisch geladen, ist per .gitignore vom Repo ausgeschlossen):
    GOOGLE_BOOKS_API_KEY=dein-schluessel

Wenn Google bremst (HTTP 429) oder Open Library nicht antwortet, wird die
jeweilige Quelle kurz pausiert. Keine zusätzlichen Pakete nötig.
"""

import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

import env_laden  # noqa: F401  (.env einlesen)
from amazon import autor_sauber

TIMEOUT = 8               # Google antwortet schnell
TIMEOUT_OPENLIBRARY = 20  # Open Library braucht oft deutlich länger
HEADERS = {"User-Agent": "PodcastBuecher/1.0 (privates Projekt)"}
GOOGLE_API_KEY = os.environ.get("GOOGLE_BOOKS_API_KEY", "").strip()

# Bis zu diesem Zeitpunkt (time.time()) wird die Quelle nicht mehr gefragt
_google_pause_bis = 0.0
GOOGLE_PAUSE_SEKUNDEN = 120
_ol_pause_bis = 0.0
_ol_timeouts_in_folge = 0
OL_PAUSE_SEKUNDEN = 120


class QuelleGesperrt(Exception):
    pass


GoogleGesperrt = QuelleGesperrt  # alter Name


def google_pausiert():
    return time.time() < _google_pause_bis


def openlibrary_pausiert():
    return time.time() < _ol_pause_bis


def _get_json(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------- Hilfsfunktionen ----------------

def _norm(text):
    """Für Titelvergleiche: klein, ohne Akzente/Satzzeichen."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _autor_nachname(autor):
    teile = autor_sauber(autor).split()
    return teile[-1] if teile else None


def _titel_kurz(titel):
    """Untertitel abschneiden: 'Letzte Chance: Der neue Kanzler...' -> 'Letzte Chance'"""
    return re.split(r"\s[:\-–|]\s|: ", titel)[0].strip()


def _titel_passt(gesucht, gefunden):
    a, b = _norm(_titel_kurz(gesucht)), _norm(gefunden)
    return bool(a) and (a in b or b in a)


def isbn13_zu_10(isbn13):
    isbn13 = re.sub(r"\D", "", isbn13 or "")
    if len(isbn13) != 13 or not isbn13.startswith("978"):
        return None
    kern = isbn13[3:12]
    summe = sum((10 - i) * int(z) for i, z in enumerate(kern))
    pruef = (11 - summe % 11) % 11
    return kern + ("X" if pruef == 10 else str(pruef))


def _isbn10_aus_google(volume_info):
    ids = {i.get("type"): i.get("identifier") for i in volume_info.get("industryIdentifiers", [])}
    if ids.get("ISBN_10"):
        return ids["ISBN_10"]
    return isbn13_zu_10(ids.get("ISBN_13"))


def _bild_aus_google(volume_info):
    links = volume_info.get("imageLinks", {})
    bild = links.get("thumbnail") or links.get("smallThumbnail")
    if bild:
        return bild.replace("http://", "https://").replace("&edge=curl", "")
    return None


# ---------------- Google Books ----------------

def _google_items(q, max_results=10):
    global _google_pause_bis
    if google_pausiert():
        raise QuelleGesperrt()
    params = {"q": q, "maxResults": max_results, "printType": "books"}
    if GOOGLE_API_KEY:
        params["key"] = GOOGLE_API_KEY
    url = "https://www.googleapis.com/books/v1/volumes?" + urllib.parse.urlencode(params)
    try:
        return _get_json(url).get("items", [])
    except urllib.error.HTTPError as e:
        if e.code == 429:
            warte = e.headers.get("Retry-After")
            pause = int(warte) if warte and warte.isdigit() else GOOGLE_PAUSE_SEKUNDEN
            _google_pause_bis = time.time() + pause
            print(f"[Buchsuche] Google Books bremst (429) – pausiere Google für {pause}s, "
                  f"nutze solange nur Open Library.")
            raise QuelleGesperrt()
        raise


def _google_buchdaten(titel, autor=None):
    q = f'intitle:"{titel}"'
    if autor:
        q += f" inauthor:{autor}"
    items = _google_items(q, 5)
    cover = isbn = None
    for item in items:
        info = item.get("volumeInfo", {})
        if not cover:
            cover = _bild_aus_google(info)
        if not isbn and _titel_passt(titel, info.get("title", "")):
            isbn = _isbn10_aus_google(info)
        if cover and isbn:
            break
    if cover or isbn:
        return {"cover": cover, "isbn10": isbn}
    return None


# ---------------- Open Library ----------------

def _openlibrary_buchdaten(titel, autor=None):
    global _ol_pause_bis, _ol_timeouts_in_folge
    if openlibrary_pausiert():
        raise QuelleGesperrt()
    params = {"title": titel, "limit": 5, "fields": "title,cover_i,isbn"}
    if autor:
        params["author"] = autor
    url = "https://openlibrary.org/search.json?" + urllib.parse.urlencode(params)
    try:
        daten = _get_json(url, timeout=TIMEOUT_OPENLIBRARY)
        _ol_timeouts_in_folge = 0
    except (TimeoutError, urllib.error.URLError) as e:
        if isinstance(e, urllib.error.HTTPError):
            raise
        _ol_timeouts_in_folge += 1
        if _ol_timeouts_in_folge >= 3:
            _ol_pause_bis = time.time() + OL_PAUSE_SEKUNDEN
            _ol_timeouts_in_folge = 0
            print(f"[Buchsuche] Open Library antwortet nicht (3x Zeitüberschreitung) – "
                  f"pausiere Open Library für {OL_PAUSE_SEKUNDEN}s.")
            raise QuelleGesperrt()
        raise

    cover = isbn = None
    for doc in daten.get("docs", []):
        if not cover and doc.get("cover_i"):
            cover = f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-L.jpg"
        if not isbn and _titel_passt(titel, doc.get("title", "")):
            isbns = doc.get("isbn", [])
            isbn = next((i for i in isbns if len(i) == 10), None) or \
                next((isbn13_zu_10(i) for i in isbns if isbn13_zu_10(i)), None)
        if cover and isbn:
            break
    if cover or isbn:
        return {"cover": cover, "isbn10": isbn}
    return None


def cover_von_olid(olid):
    """Manuell eingetragene Open-Library-ID weiterhin unterstützen."""
    olid = (olid or "").strip()
    if not olid:
        return None
    return f"https://covers.openlibrary.org/b/olid/{olid}-L.jpg?default=false"


# ---------------- Öffentliche Funktionen ----------------

def finde_buchdaten(titel, autor=None):
    """Sucht Cover-URL und ISBN-10. Gibt {'cover': ..., 'isbn10': ...} zurück
    (Werte können None sein)."""
    ergebnis = {"cover": None, "isbn10": None}
    if not titel:
        return ergebnis
    nachname = _autor_nachname(autor)
    kurz = _titel_kurz(titel)

    # Max. 2 Google-Anfragen pro Buch, Rest über Open Library
    versuche = [
        (_google_buchdaten, titel, nachname),
        (_openlibrary_buchdaten, titel, nachname),
        (_google_buchdaten, kurz, None),
        (_openlibrary_buchdaten, kurz, None),
    ]
    gesehen = set()
    for funktion, t, a in versuche:
        if ergebnis["cover"] and ergebnis["isbn10"]:
            break
        schluessel = (funktion.__name__, t, a)
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        try:
            daten = funktion(t, a)
        except QuelleGesperrt:
            continue  # leise überspringen, Meldung kam schon einmal
        except Exception as e:  # Netzwerkfehler usw. -> nächste Quelle
            print(f"[Buchsuche] {funktion.__name__}({t!r}, {a!r}) fehlgeschlagen: {e}")
            continue
        if daten:
            ergebnis["cover"] = ergebnis["cover"] or daten["cover"]
            ergebnis["isbn10"] = ergebnis["isbn10"] or daten["isbn10"]
    return ergebnis


def finde_cover(titel, autor=None):
    return finde_buchdaten(titel, autor)["cover"]


def buecher_von_autor(autor, max_results=40):
    """Listet Bücher eines Autors über Google Books.
    Gibt Liste von dicts {titel, untertitel, jahr, isbn10, cover} zurück."""
    name = autor_sauber(autor)
    nachname = _autor_nachname(autor)
    if not name:
        return []
    items = _google_items(f'inauthor:"{name}"', max_results)

    ergebnisse, gesehen = [], set()
    for item in items:
        info = item.get("volumeInfo", {})
        autoren = " ".join(info.get("authors", []))
        if nachname and _norm(nachname) not in _norm(autoren):
            continue
        titel = info.get("title", "").strip()
        schluessel = _norm(titel)
        if not titel or schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        autoren_liste = info.get("authors", [])
        ergebnisse.append({
            "exakt": any(_norm(x) == _norm(name) for x in autoren_liste),
            "bewertungen": info.get("ratingsCount", 0) or 0,
            "sprache": info.get("language", ""),
            "titel": titel,
            "untertitel": info.get("subtitle", ""),
            "autoren": ", ".join(info.get("authors", [])),
            "jahr": (info.get("publishedDate") or "")[:4],
            "isbn10": _isbn10_aus_google(info),
            "cover": _bild_aus_google(info),
        })
    return ergebnisse
