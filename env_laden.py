"""Liest KEY=WERT-Zeilen aus der .env im Projektordner in os.environ.
Bereits gesetzte Umgebungsvariablen haben Vorrang. Wird beim Import ausgeführt."""

import os


def lade_env_datei():
    pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(pfad):
        return
    with open(pfad, encoding="utf-8-sig") as f:
        for zeile in f:
            zeile = zeile.strip()
            if not zeile or zeile.startswith("#") or "=" not in zeile:
                continue
            key, wert = zeile.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            os.environ.setdefault(key, wert.strip().strip('"').strip("'"))


lade_env_datei()
