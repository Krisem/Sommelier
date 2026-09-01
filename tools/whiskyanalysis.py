"""
whiskyanalysis.com Meta-Critic → repo-committet snapshot i `data/whiskyanalysis/`.

Meta-Critic er Andre Girards aggregering av ~30 whisky-anmeldere til én
normalisert score per flaske, med standardavvik og antall anmeldere. Den er den
eneste åpne kilden vi fant som gir whisky et referanselag tilsvarende det
`knowledge/scores/` gir vin — se ADR-034 for hvorfor det ikke ble Whiskybase.

**Hvorfor ÉN modul, ikke `refresh_X` + `X` som Aperitif.** Aperitif-paret finnes
fordi `tools.aperitif` også slår opp ÉN vin av gangen mot nettverket. Her finnes
ingen per-produkt-vei: hele databasen er én HTML-tabell på én URL. En andre
modul ville vært et tomt skall.

**Hvorfor IKKE `knowledge/scores/*.md`.** Den mappa er dokumentert som
bruker-kuratert og høyeste tillit i `value_score`. Meta-Critic skal ikke ha den
plassen — se forbeholdene under.

Målt ved henting 2026-09-01 (1 812 rader):

- Score 6,47–9,58, median 8,61. Median 9 anmeldere per flaske (min 3, maks 34).
- Skottland 965 · USA 304 · Canada 221 · Irland 83 · Japan 79 · Sverige 63.

To forbehold som må følge dataene overalt hvor de brukes:

1. **Prisbias.** Spearman(score, prisbånd) = **+0,64** over 1 809 rader med
   prisbånd. Aperitif ligger på +0,66. Meta-Critic løser altså IKKE
   prisbias-problemet — den arver det. Rangering krever prissone-lås.
2. **Den er ikke uavhengig av Aperitif.** På brukerens egne flasker korrelerer
   de to kildene **+0,90** med hverandre, og begge går motsatt vei av ham
   (−0,26 og −0,95). En tredje dommer tilfører nesten ingenting; det den
   tilfører er STDEV og antall anmeldere, altså UENIGHET — ikke en bedre dom.

**Databasen er sist oppdatert 20. januar 2023.** Det er ikke et refresh-problem
vi kan fikse; kilden står stille. Standarduttrykk (Talisker 10, Lagavulin 16) er
dekket, nyere lanseringer finnes ikke. `meta.json` bærer `source_updated` slik at
alderen aldri leses av `generated_at` alene.

`robots.txt` (verifisert 2026-09-01): kun `/wp-admin/` er blokkert. Vi henter én
side.

Kjør: `python3 -m tools.whiskyanalysis --refresh` ✍️  (skriver til data/)
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import statistics
import sys
import unicodedata
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
WA_DIR = _REPO_ROOT / "data" / "whiskyanalysis"
SCORES = WA_DIR / "metacritic.ndjson"
META = WA_DIR / "meta.json"

SOURCE_URL = "https://whiskyanalysis.com/index.php/database/"

# Kolonnene slik de står i tabell-headeren. Endres de, har siden endret shape og
# radene under kan ikke stoles på — vi feiler hardt i stedet for å parse videre.
EXPECTED_HEADER = (
    "Whisky", "Meta Critic", "STDEV", "#", "Cost",
    "Class", "Super Cluster", "Cluster", "Country", "Type",
)

FIELDS = (
    "whisky", "meta_critic", "stdev", "n_reviewers", "cost_band",
    "class", "super_cluster", "cluster", "country", "type",
)

# Radgulv for drift-vernet. Hentingen 2026-09-01 ga 1 812; kilden er statisk
# siden januar 2023, så et fall under dette betyr at parsingen er ødelagt —
# ikke at databasen har krympet.
MIN_ROWS = 1500

# Prisbåndene ($ … $$$$$+) er ordinale. Rangen brukes til å måle prisbias og til
# prissone-lås; den er IKKE en pris i kroner og skal aldri presenteres som det.
COST_RANK = {"$": 1, "$$": 2, "$$$": 3, "$$$$": 4, "$$$$$": 5, "$$$$$+": 6}


# ─── PARSING (ren, fixture-testbar — ingen nettverk) ─────────────────

_TAG = re.compile(r"<[^>]*>")
_ROW = re.compile(r"<tr.*?</tr>", re.S)
_CELL = re.compile(r"<t[dh].*?</t[dh]>", re.S)
_TABLE = re.compile(r"<table.*?</table>", re.S)


def _cells(row_html: str) -> list[str]:
    return [
        html_lib.unescape(_TAG.sub("", c)).replace("\xa0", " ").strip()
        for c in _CELL.findall(row_html)
    ]


def _num(raw: str) -> Optional[float]:
    try:
        return float(raw.replace(",", "."))
    except (TypeError, ValueError):
        return None


def parse_database_page(html: str, *, min_rows: int = MIN_ROWS) -> list[dict]:
    """
    Parse Meta-Critic-tabellen ut av databasesiden.

    Feiler HARDT (`ValueError`) på drift — feil header, ingen tabell, eller
    for få rader. En stille degradering her ville gitt et snapshot som ser
    gyldig ut og bærer feil tall, og `value_score` ville ikke merket det.

    `min_rows` er parametrisert utelukkende for at testene skal kunne kjøre mot
    en liten fixture. Sveipen bruker alltid defaulten — senk den aldri der for å
    få en kjøring til å gå gjennom; en kjøring som gir for få rader ER feilen.
    """
    tables = _TABLE.findall(html)
    if not tables:
        raise ValueError(
            f"Fant ingen <table> på {SOURCE_URL}. Siden har endret shape, "
            "eller hentingen ga en feilside."
        )

    rows = _ROW.findall(tables[0])
    if not rows:
        raise ValueError("Tabellen finnes, men har ingen <tr>.")

    header = tuple(_cells(rows[0]))
    if header != EXPECTED_HEADER:
        raise ValueError(
            "Kolonneheaderen har endret seg — parsingen kan ikke stoles på.\n"
            f"  forventet: {EXPECTED_HEADER}\n"
            f"  fikk:      {header}"
        )

    out: list[dict] = []
    for row_html in rows[1:]:
        cells = _cells(row_html)
        if len(cells) < len(FIELDS):
            continue
        rad = dict(zip(FIELDS, cells[: len(FIELDS)]))
        if not rad["whisky"]:
            continue
        rad["meta_critic"] = _num(rad["meta_critic"])
        rad["stdev"] = _num(rad["stdev"])
        rad["n_reviewers"] = int(rad["n_reviewers"]) if rad["n_reviewers"].isdigit() else None
        rad["cost_rank"] = COST_RANK.get(rad["cost_band"])
        if rad["meta_critic"] is None:
            continue
        out.append(rad)

    if len(out) < min_rows:
        raise ValueError(
            f"Bare {len(out)} rader parset, gulvet er {min_rows}. Kilden har "
            "stått stille siden januar 2023, så dette betyr at parsingen er "
            "ødelagt — ikke at databasen har krympet."
        )
    return out


# ─── NORMALISERING (delt med whisky_match) ───────────────────────────

# Ord som ikke identifiserer en flaske. `single malt whisky` skiller ingenting
# når hele populasjonen er whisky; `12 yo` gjør det, og håndteres som alder.
GENERIC_TOKENS = frozenset({
    "single", "malt", "grain", "whisky", "whiskey", "scotch", "irish", "the",
    "of", "a", "kentucky", "straight", "bourbon", "tennessee", "speyside",
    "highland", "islay", "reserve", "edition", "batch", "all", "reviews",
    "years", "old", "yo", "yr", "yrs", "year",
})

_PARENS = re.compile(r"\(.*?\)")
_AGE = re.compile(r"\b(\d{1,2})\s*(?:yo|yr|yrs|years?\s*old|years?)\b")
_NONWORD = re.compile(r"[^a-z0-9]+")


def normalise(name: str) -> tuple[list[str], Optional[int]]:
    """
    → (identifiserende tokens, aldersangivelse eller None).

    Alder trekkes UT som eget felt i stedet for å bli et token, fordi den er
    diskriminerende på en annen måte enn resten: «Aberlour 12» og «Aberlour 18»
    er ulike flasker, mens «Aberlour Single Malt» og «Aberlour» er samme.
    """
    s = unicodedata.normalize("NFKD", (name or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _PARENS.sub(" ", s)
    ages = _AGE.findall(s)
    age = int(ages[0]) if ages else None
    s = _AGE.sub(" ", s)
    s = _NONWORD.sub(" ", s)
    tokens = [t for t in s.split() if t not in GENERIC_TOKENS and len(t) > 1]
    return tokens, age


# ─── SNAPSHOT-LESING (offline) ───────────────────────────────────────

def read_snapshot() -> list[dict]:
    """Alle Meta-Critic-rader fra snapshotet. Mangler filen → []."""
    if not SCORES.exists():
        return []
    out = []
    for line in SCORES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def read_meta() -> dict:
    if not META.exists():
        return {}
    try:
        return json.loads(META.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def source_updated() -> Optional[str]:
    """
    Datoen KILDEN sist ble oppdatert — ikke da vi hentet den.

    De to må aldri forveksles: et ferskt `generated_at` på et snapshot av en
    database som sto stille i 2023 ville lest som ferske data.
    """
    return read_meta().get("source_updated")


def percentile_rank(score: float, rows: Optional[list[dict]] = None) -> Optional[float]:
    """
    Hvor `score` ligger i Meta-Critics egen fordeling, 0–1.

    Rå score kan ikke sammenlignes med Aperitifs 1–100 — skalaene har ulik form
    (Meta-Critic ligger klemt mellom 6,5 og 9,6). Persentil innenfor hver kildes
    EGEN fordeling er det som gjør de to sammenlignbare.
    """
    rows = read_snapshot() if rows is None else rows
    alle = sorted(r["meta_critic"] for r in rows if r.get("meta_critic") is not None)
    if not alle:
        return None
    under = sum(1 for v in alle if v < score)
    lik = sum(1 for v in alle if v == score)
    return (under + lik / 2) / len(alle)


# ─── SVEIP (nettverk) ────────────────────────────────────────────────

def fetch_page(url: str = SOURCE_URL, timeout: int = 60) -> str:
    import requests

    r = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
            )
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.text


def build_meta(rows: list[dict], *, generated_at: str, source_updated_at: Optional[str]) -> dict:
    scores = [r["meta_critic"] for r in rows if r.get("meta_critic") is not None]
    ns = [r["n_reviewers"] for r in rows if r.get("n_reviewers")]
    ranked = [(r["cost_rank"], r["meta_critic"]) for r in rows
              if r.get("cost_rank") and r.get("meta_critic") is not None]
    return {
        "generated_at": generated_at,
        "source": SOURCE_URL,
        "source_updated": source_updated_at,
        "rows_written": len(rows),
        "score_range": [min(scores), max(scores)] if scores else None,
        "score_median": round(statistics.median(scores), 2) if scores else None,
        "reviewers_median": statistics.median(ns) if ns else None,
        "reviewers_min": min(ns) if ns else None,
        "prisbias_spearman": round(_spearman([c for c, _ in ranked],
                                             [s for _, s in ranked]), 3) if ranked else None,
        "forbehold": {
            "prisbias": (
                "Spearman(score, prisbånd) ≈ +0,64 — praktisk talt identisk med Aperitifs "
                "+0,66. Meta-Critic arver prisbiasen, den løser den ikke. Rangering uten "
                "prissone-lås er ugyldig."
            ),
            "ikke_uavhengig": (
                "Meta-Critic og Aperitif korrelerer +0,90 på brukerens egne flasker, og begge "
                "går motsatt vei av ham (−0,26 / −0,95). Verdien ligger i STDEV og antall "
                "anmeldere (uenighet), ikke i en bedre dom. Derfor styrer den ikke "
                "value_verdict — se ADR-034."
            ),
            "alder": (
                "Kilden er sist oppdatert 20. januar 2023 og står stille. Standarduttrykk er "
                "dekket; lanseringer etter 2023 finnes ikke. Et ferskt generated_at sier bare "
                "når VI hentet, ikke hvor ferske tallene er."
            ),
            "dekning": (
                "Målt mot Aperitifs 316 whiskyer: 26 % eksakt join, 4 % sterk, 19 % må "
                "bekreftes, 51 % ingen match. Det manglende halve er i stor grad norske "
                "hyllevare-blends som ingen kritiker har vurdert — et tak, ikke en feil."
            ),
        },
    }


def _spearman(xs: list[float], ys: list[float]) -> float:
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else 0.0


_RE_SOURCE_UPDATED = re.compile(
    r"[Dd]atabase last updated\s+([A-Z][a-z]+ \d{1,2},? \d{4})"
)


def extract_source_updated(html: str) -> Optional[str]:
    """Datoen siden selv oppgir. Finnes den ikke, returnér None — ikke gjett."""
    flat = html_lib.unescape(_TAG.sub(" ", html))
    m = _RE_SOURCE_UPDATED.search(flat)
    return m.group(1) if m else None


def write_snapshot(rows: list[dict], meta: dict, *, directory: Path = WA_DIR) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    body = "\n".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True)
        for r in sorted(rows, key=lambda r: r["whisky"].casefold())
    )
    (directory / SCORES.name).write_text(body + "\n", encoding="utf-8")
    (directory / META.name).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: Optional[list[str]] = None) -> int:
    from datetime import datetime, timezone

    ap = argparse.ArgumentParser(description="Sveip whiskyanalysis.com Meta-Critic")
    ap.add_argument("--refresh", action="store_true", help="hent og skriv snapshot")
    ap.add_argument("--from-file", help="parse en lokal HTML-fil i stedet for å hente")
    args = ap.parse_args(argv)

    if not (args.refresh or args.from_file):
        rows = read_snapshot()
        meta = read_meta()
        print(f"Snapshot: {len(rows)} rader, hentet {meta.get('generated_at', '—')}, "
              f"kilde sist oppdatert {meta.get('source_updated', '—')}")
        return 0

    html = (Path(args.from_file).read_text(encoding="utf-8", errors="replace")
            if args.from_file else fetch_page())
    rows = parse_database_page(html)
    meta = build_meta(
        rows,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        source_updated_at=extract_source_updated(html),
    )
    write_snapshot(rows, meta)
    print(f"Skrev {len(rows)} rader til {SCORES}")
    print(f"  kilde sist oppdatert: {meta['source_updated']}")
    print(f"  prisbias (Spearman):  {meta['prisbias_spearman']:+.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
