"""
Refresh-PLUMBING for Polet-snapshotet — ingest + planlegging, IKKE nettverk.

Polets webshop-API (`vmpws`) er WAF-blokkert (ADR-019): en ren Python-prosess
som `fetch()`-er selv blir 403-et. Den bekreftede transporten er en EKTE
nettleser drevet av Claude (Playwright-MCP), som navigerer til forsiden
(passerer WAF) og kjører `fetch()` i browser-konteksten. Denne modulen tar imot
det browseren henter og mater det inn i `polet_store` sine write-helpers (som
gjør all validering). Den planlegger også hvilke søk browseren bør sveipe for å
holde value_score sin peer-percentile mettet.

Refresh er DEVICE-AGNOSTISK (ADR-021): den foretrukne veien — på alle enheter,
også desktop — er å peke Playwright-MCP på en REMOTE browser via CDP
(`browser.cdpEndpoint`, f.eks. Browserbase). Da skjer browsingen på tjenestens
rene egress og passerer Cloudflare uavhengig av lokal proxy. Lokal chromium i et
MITM-proxy-miljø (Claude Code on the web bak Egress Gateway) blir hard-blokkert
(403) og kan IKKE refreshe. Oppsett: docs/polet_refresh.md.

──────────────────────────────────────────────────────────────────────────
RUNBOOK — Claude-drevet refresh (Playwright-MCP, remote browser via CDP)
──────────────────────────────────────────────────────────────────────────
Forutsetning: Playwright-MCP koblet til en remote browser (CDP-endpoint).
Ingen `requests`/Python-fetch — den 403-es. All nettverkstrafikk går gjennom
den ekte nettleseren.

1. NAVIGER til forsiden for å etablere WAF-godkjent sesjon:
       browser_navigate("https://www.vinmonopolet.no/")

2. PEER-POOL (bredde) — for hver entry fra `peer_pool_queries()`:
   Kjør i browser-konteksten (browser_evaluate). EKSAKT URL-format:

       fetch(
         '/vmpws/v2/vmp/products/search'
         + '?q=:relevance:mainCategory:<c>:mainCountry:<co>'
         + '&pageSize=<n>'
       ).then(r => r.text())

   der <c> = entry["mainCategory"], <co> = entry["mainCountry"],
   <n> = entry["pageSize"]. Bruk LOWERCASE koder (ADR-009: kode ≠ navn).
   Send svaret (dict ELLER rå JSON-streng) til:

       ingest_search_payload(payload, fetched_at=<ISO-stempel>)

   `?fields=FULL` gir 400 — IKKE bruk det. Default-feltene holder; de har
   samme shape som data/polet/catalog.ndjson (code, name, price.value,
   main_category.code, main_country.code, district, url, alcohol, volume, …).

3. DYBDE (details) — for finalist-viner uten ferske details:
   For hver produkt-URL `url` (relativ /p/... eller absolutt), hent HTML i
   browseren:

       fetch(url).then(r => r.text())

   og send den til:

       ingest_details_html(code, url, html, fetched_at=<ISO-stempel>)

   Validering skjer i polet_store.save_details: HTML må inneholde varenr +
   produktnavn + (klokker ELLER pris). Challenge-HTML kaster ValueError —
   la den boble (det er signalet om at WAF slo til; naviger på nytt og prøv
   igjen, IKKE skriv søppel til snapshot).

4. VERIFISER at git-diffen er linjebasert og ren (NDJSON er sortert på code,
   details er sort_keys+indent) — `git diff --stat data/polet/`. Commit
   gjøres som et eget, bevisst steg (ikke av denne modulen).

Bruk ett felles `fetched_at`-stempel for hele kjøringen, f.eks.
    from datetime import datetime, timezone
    fetched_at = datetime.now(timezone.utc).isoformat()
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Union

from tools import polet_store

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VIVINO_CSV = _REPO_ROOT / "data" / "vivino" / "full_wine_list.csv"

# Default peer-sveip når Vivino-CSV ikke er tilgjengelig. Speiler dagens
# katalog-dekning (rødvin dominerer) + brukerens kjente domene. LOWERCASE
# koder (ADR-009). Musserende har koden `musserende_vin`.
_STATIC_PEER_QUERIES: list[tuple[str, str]] = [
    ("rødvin", "italia"),
    ("rødvin", "frankrike"),
    ("rødvin", "spania"),
    ("hvitvin", "italia"),
    ("hvitvin", "frankrike"),
    ("musserende_vin", "frankrike"),
]

# Vivino bruker engelske etiketter; Polet-fasettene er norske LOWERCASE koder.
_WINE_TYPE_TO_CODE = {
    "red wine": "rødvin",
    "white wine": "hvitvin",
    "rosé wine": "rosévin",
    "rose wine": "rosévin",
    "sparkling": "musserende_vin",
    "dessert wine": "sterkvin",
    "fortified wine": "sterkvin",
}

_COUNTRY_TO_CODE = {
    "italy": "italia",
    "france": "frankrike",
    "spain": "spania",
    "germany": "tyskland",
    "south africa": "sør-afrika",
    "united states": "usa",
    "usa": "usa",
    "argentina": "argentina",
    "portugal": "portugal",
    "austria": "østerrike",
    "australia": "australia",
    "chile": "chile",
    "new zealand": "new-zealand",
    "united kingdom": "storbritannia",
    "greece": "hellas",
}

_PAGE_SIZE = 50
_MAX_QUERIES = 10
_MIN_QUERIES = 6


# ─── INGEST (browser → snapshot) ─────────────────────────────────────

def ingest_search_payload(payload: Union[dict, str], *, fetched_at: str) -> int:
    """
    Ta imot et vmpws-søkesvar (parset dict `{products:[...]}` ELLER rå
    JSON-streng), trekk ut `products`, og upsert dem i katalogen.

    Robust: ugyldig/tom JSON eller manglende `products` → returnér 0 (krasjer
    ikke; browseren kan ha fått et tomt eller uventet svar).

    Returnerer antall opprørte produkter.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, ValueError):
            return 0

    if not isinstance(payload, dict):
        return 0

    products = payload.get("products")
    if not products:
        return 0

    return polet_store.upsert_products(products, fetched_at=fetched_at)


def ingest_details_html(code: str, url: str, html: str, *, fetched_at: str) -> dict:
    """
    Tynn wrapper rundt polet_store.save_details. save_details gjør parse +
    POSITIV validering (varenr + navn + klokker/pris); ValueError fra
    challenge-HTML eller feil varenr får boble opp slik at caller ser at
    søppel ble avvist (og kan navigere på nytt før retry).
    """
    return polet_store.save_details(code, url, html, fetched_at=fetched_at)


# ─── PLANLEGGING (hvilke søk browseren bør sveipe) ───────────────────

def _read_vivino_combos() -> list[tuple[str, str]]:
    """
    Les Vivino-historikken og utled (mainCategory, mainCountry)-kombinasjoner
    sortert på hvor ofte brukeren faktisk drikker dem. Tom liste hvis CSV
    mangler eller ingen rad kan mappes til kjente koder.
    """
    if not _VIVINO_CSV.exists():
        return []

    counts: Counter[tuple[str, str]] = Counter()
    try:
        with _VIVINO_CSV.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                cat = _WINE_TYPE_TO_CODE.get((row.get("Wine type") or "").strip().lower())
                country = _COUNTRY_TO_CODE.get((row.get("Country") or "").strip().lower())
                if cat and country:
                    counts[(cat, country)] += 1
    except (OSError, csv.Error):
        return []

    return [combo for combo, _ in counts.most_common()]


def peer_pool_queries() -> list[dict]:
    """
    Lista av fasett-kombinasjoner desktop bør sveipe slik at value_score sin
    peer-percentile får ≥5 peers per relevant kategori+land.

    Domenet utledes fra hva brukeren faktisk drikker (Vivino-historikken):
    de vanligste (mainCategory, mainCountry)-kombinasjonene. Faller tilbake
    til en statisk liste basert på dagens katalog-dekning hvis CSV mangler.
    Statiske kjerne-kombinasjoner suppleres alltid inn slik at peer-poolen
    ikke kollapser til kun det brukeren har drukket mest av.

    Hver entry: {"mainCategory": <kode>, "mainCountry": <kode>, "pageSize": 50}.
    Alle koder er LOWERCASE (ADR-009: kode ≠ navn). Lista holdes ~6-10 lang.
    """
    ordered: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _add(combo: tuple[str, str]) -> None:
        if combo not in seen:
            seen.add(combo)
            ordered.append(combo)

    # 1) Brukerens faktiske drikke-mønster først (mest drukket → høyest prioritet).
    for combo in _read_vivino_combos():
        _add(combo)

    # 2) Statisk kjerne sikrer dekning selv ved tynn/manglende CSV.
    for combo in _STATIC_PEER_QUERIES:
        _add(combo)

    # Hold lista i målbåndet ~6-10. Garanter minst kjernen.
    trimmed = ordered[:_MAX_QUERIES]
    if len(trimmed) < _MIN_QUERIES:
        trimmed = ordered[:_MIN_QUERIES]

    return [
        {"mainCategory": cat, "mainCountry": country, "pageSize": _PAGE_SIZE}
        for cat, country in trimmed
    ]


if __name__ == "__main__":
    import json as _json

    print("peer_pool_queries():")
    print(_json.dumps(peer_pool_queries(), ensure_ascii=False, indent=2))
