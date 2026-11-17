"""
Amazon-Partnerlinks erzeugen.

Partner-ID (Tracking-ID) kann in der .env überschrieben werden:
    AMAZON_PARTNER_TAG=podcastbueche-21
"""

import os
import re
import urllib.parse

import env_laden  # noqa: F401  (.env einlesen)

PARTNER_TAG = os.environ.get("AMAZON_PARTNER_TAG", "podcastbueche-21").strip()

_PRAEFIXE = re.compile(r"\b(Prof\.|Dr\.|med\.|Dipl\.|-Ing\.)\s*", re.IGNORECASE)
_PART = re.compile(r"\s+Part\s+\d+\s*$", re.IGNORECASE)


def autor_sauber(autor):
    """'Prof. Dr. Manfred Spitzer Part 2' -> 'Manfred Spitzer'"""
    if not autor:
        return ""
    return _PART.sub("", _PRAEFIXE.sub("", autor)).strip()


def such_link(titel, autor=None):
    """Partnerlink auf die Amazon-Buchsuche (funktioniert immer)."""
    suchbegriff = f"{titel} {autor_sauber(autor)}".strip()
    params = {"k": suchbegriff, "i": "stripbooks", "tag": PARTNER_TAG}
    return "https://www.amazon.de/s?" + urllib.parse.urlencode(params)


def dp_link(isbn10):
    """Partnerlink direkt auf die Produktseite (ISBN-10 = ASIN bei Printbüchern)."""
    return f"https://www.amazon.de/dp/{isbn10}?tag={PARTNER_TAG}"


def ist_suchlink(url):
    return bool(url) and "amazon.de/s?" in url


def ist_dp_link(url):
    return bool(url) and "amazon.de/dp/" in url


def partner_link(titel, autor=None, isbn10=None):
    """Immer die Amazon-Buchsuche nach Titel + Autor.

    Direkte Produktlinks (/dp/ISBN) laufen oft ins Leere, weil die ISBN aus
    Google Books zu einer Ausgabe gehört, die Amazon.de nicht führt. Die Suche
    zeigt das Buch zuverlässig ganz oben; der Partner-Tag gilt trotzdem."""
    return such_link(titel, autor)
