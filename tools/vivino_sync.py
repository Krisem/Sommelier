"""
Vivino ratings-sync — deterministisk merge av nye ratings inn i full_wine_list.csv.

Bakgrunn: Vivino har ingen offentlig eksport-API. Den kanoniske veien for å hente
de siste ratede vinene er å skrape den innloggede profil-feeden med Playwright-MCP
(se docs/vivino_refresh.md). Dette verktøyet tar de skrapede radene som JSON og
legger inn *kun de nye* i CSV-en (dedup på winery+wine+vintage), slik at man aldri
redigerer CSV-en for hånd.

Bruk:
    # rows.json = liste av dicts med CSV-kolonner (minst Winery/Wine name/Vintage/Your rating)
    python3 -m tools.vivino_sync rows.json
    cat rows.json | python3 -m tools.vivino_sync -

Etterpå: kjør `python3 tools/profile_stats.py` for å regenerere statistikk-blokka.
Verktøyet gjør IKKE dette selv (holder ansvaret rent + lar deg inspisere diffen først).

Merk: legger bare til NYE viner. Endrer ikke rating på viner som allerede finnes
(re-scoring er sjeldent; håndteres manuelt hvis det skjer).
"""

import csv
import json
import sys
import unicodedata
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "vivino" / "full_wine_list.csv"


def _norm(s: str) -> str:
    """Lowercase + strip diakritiske tegn, for robust dedup-nøkkel."""
    s = "".join(
        c for c in unicodedata.normalize("NFD", (s or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(s.split())


def _key(row: dict) -> tuple:
    return (
        _norm(row.get("Winery", "")),
        _norm(row.get("Wine name", "")),
        (row.get("Vintage", "") or "").strip() or "N.V.",
    )


def sync(new_rows: list, csv_path: Path = CSV_PATH) -> dict:
    """Legg til nye rader i CSV-en. Returnerer {'added': [...], 'skipped': [...]}"""
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        existing = {_key(r) for r in reader}

    added, skipped = [], []
    to_write = []
    for r in new_rows:
        k = _key(r)
        label = f"{r.get('Winery','')} {r.get('Wine name','')} {r.get('Vintage','')}".strip()
        if k in existing:
            skipped.append(label)
            continue
        existing.add(k)  # unngå duplikater innad i batchen
        to_write.append({col: r.get(col, "") for col in header})
        added.append(label)

    if to_write:
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writerows(to_write)

    return {"added": added, "skipped": skipped}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = sys.argv[1]
    raw = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8")
    rows = json.loads(raw)
    if isinstance(rows, dict):
        rows = [rows]
    result = sync(rows)
    print(f"La til {len(result['added'])} nye, hoppet over {len(result['skipped'])} (finnes fra før).")
    for a in result["added"]:
        print(f"  + {a}")
    if result["added"]:
        print("\nNeste steg: python3 tools/profile_stats.py")
