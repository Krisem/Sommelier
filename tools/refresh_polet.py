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
   Kjør i browser-konteksten (browser_evaluate). Bygg URL-en med
   `polet_facets.search_url(query, page=n)` — IKKE for hånd:

       fetch(
         '/vmpws/v2/vmp/products/search'
         + '?q=:relevance:mainCategory:<c>:mainCountry:<co>'
         + '&pageSize=24&currentPage=<n>'
       ).then(r => r.text())

   der <c> = entry["mainCategory"], <co> = entry["mainCountry"].
   Bruk LOWERCASE koder (ADR-009: kode ≠ navn). Send svaret (dict ELLER rå
   JSON-streng) til:

       ingest_search_payload(payload, fetched_at=<ISO-stempel>)

   **`pageSize` har et SERVERTAK på 24** (live-målt 2026-08-29: 25, 48 og 50 gir
   alle `pagination.pageSize: 24` og 24 produkter). Denne runbooken sa tidligere
   `pageSize=50`, og HVERT eneste sveip kjørt etter den har vært stille avkortet
   til 24 rader per query. Mer enn 24 treff krever PAGINERING: les
   `pagination.totalResults` fra første svar, be `polet_facets.page_numbers()`
   om side-lista, og hent hver side med `currentPage`. `currentPage` er 0-basert
   og virker helt ut (side 573 av 574 ga de siste 23 radene, side 600 ga 0).

   `?fields=FULL` gir 400 — IKKE bruk det. Default-feltene holder; de har
   samme shape som data/polet/catalog.ndjson (code, name, price.value,
   main_category.code, main_country.code, district, url, alcohol, volume, …).

2b. KOMPLETT RØDVIN + KLOKKER — to sveip, se `spine_queries()` og
   `clock_sweep_queries()` under «SVEIP-PLAN» lenger nede i denne modulen.
   Ryggraden enumererer hele `mainCategory:rødvin` (574 sider); klokke-sveipet
   tagger hver vin med bøtte-trippelen sin. Klokke-fasettene som FAKTISK
   filtrerer er kun `Fylde`, `Friskhet` og `Tannin(Sulfates)` — `Garvestoffer`
   ignoreres stille og returnerer hele katalogen (se `polet_facets`-docstringen).
   Resultatet mates til `ingest_clock_sweep()` → `polet_store.set_clock_buckets()`.

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
from itertools import product
from pathlib import Path
from typing import Iterator, Sequence, Union

from tools import polet_facets, polet_store

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

# `pageSize` er kappet av SERVEREN på 24 — dette er et TAK, ikke et valg.
# Live-målt 2026-08-29: 24/25/48/50 gir alle `pagination.pageSize: 24` og 24
# produkter. Sto som 50 fram til da, og ga i praksis alltid 24: hvert sveip
# var stille avkortet. Å skru tallet opp igjen henter ikke flere rader, det
# gjør bare at planleggingen lyver. Mer enn 24 treff = paginering
# (`polet_facets.page_numbers`).
_PAGE_SIZE = polet_facets.PAGE_SIZE
_MAX_QUERIES = 10
_MIN_QUERIES = 6

# Ryggrad-sveipet: hele rødvins-kategorien. Live-målt 2026-08-29 — 13 775 treff
# (75 cl: 12 498 · 300 cl: 313). `volume` ligger på raden, så 3 l faller ut
# gratis av ryggraden og trenger ikke eget filter.
_SPINE_CATEGORY = "rødvin"
_SPINE_TOTAL_RESULTS = 13_775

# Klokke-sveipet: kartesisk produkt over de tre dimensjonene som FAKTISK
# filtrerer. 6×6×6 = 216 kombinasjoner. Rekkefølgen speiler `polet_facets`.
_SWEEP_DIMS: tuple[str, ...] = ("Fylde", "Friskhet", "Tannin(Sulfates)")

# Fasett-kode → nøkkel i mappingen `polet_store.set_clock_buckets` konsumerer.
# `Tannin(Sulfates)` er SØKE-koden; klokken heter «Garvestoffer» i detalj-JSON-en
# og lagres her som «Tannin» (avtalt med agent A — ikke endre uten å endre der).
_BUCKET_CODES = frozenset(polet_facets.clock_range_buckets(1, 12))

_SWEEP_RESULT_KEYS: dict[str, str] = {
    "fylde": "Fylde",
    "friskhet": "Friskhet",
    "tannin": "Tannin",
}


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

    Hver entry: {"mainCategory": <kode>, "mainCountry": <kode>, "pageSize": 24}.
    Alle koder er LOWERCASE (ADR-009: kode ≠ navn). Lista holdes ~6-10 lang.

    `pageSize` er 24 fordi det er SERVERTAKET (se `_PAGE_SIZE`) — en entry gir
    altså de 24 første peerne, ikke alle. Trengs full dekning per kombinasjon,
    paginer med `polet_facets.page_numbers` + `search_url`.
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


# ─── SVEIP-PLAN (komplett rødvin + klokker) ──────────────────────────

def spine_queries(total_results: int = _SPINE_TOTAL_RESULTS) -> Iterator[dict]:
    """
    RYGGRADEN: full enumerering av `mainCategory:rødvin`, én entry per side.

    Med det live-målte tallet (13 775 treff, 2026-08-29) blir det **574 sider**
    a 24. Volum ligger på produkt-raden, så både 75 cl og de 313 3-liters
    faller ut av samme sveip — ingen egne volum-queries.

    `total_results` kan overstyres når sveiperen allerede har probet en ferskere
    `pagination.totalResults` fra side 0; defaulten er måletallet så
    `spine_queries()` uten argumenter planlegger et komplett sveip.

    Hver entry:
        {"page": 0, "query": ":relevance:mainCategory:rødvin", "url": "/vmpws/…"}

    Generator (ikke liste): 574 entries er billig, men kalleren skal kunne stoppe
    midtveis uten å ha materialisert resten.
    """
    query = polet_facets.build_facet_query(category=_SPINE_CATEGORY)
    for page in polet_facets.page_numbers(total_results):
        yield {"page": page, "query": query, "url": polet_facets.search_url(query, page=page)}


def clock_sweep_queries() -> Iterator[dict]:
    """
    KLOKKE-SVEIPET: det kartesiske produktet Fylde × Friskhet × Tannin(Sulfates)
    = 6×6×6 = **216 kombinasjoner** innenfor `mainCategory:rødvin`.

    Poenget er å tagge hver vin med sin bøtte-TRIPPEL i ÉN passering (~460 sider
    + 216 probe-kall) i stedet for tre separate 1-dim-sveip (~1 370 sider). Det
    virker fordi ulike dimensjoner AND-es i vmpws (ADR-023) — en trippel er ett
    presist søk, og en vin kan per definisjon bare ligge i én trippel.

    Sidetallet per kombinasjon kan ikke planlegges på forhånd: `facets[]` i
    svaret er alltid tomt, så antall treff må probes. Derfor gir hver entry en
    `probe_url` (side 0). Proben er ikke bortkastet — side 0 inneholder de 24
    første radene. Sveiperen leser `pagination.totalResults` fra proben og
    henter resten:

        pages = polet_facets.page_numbers(total)          # [0, 1, …]
        for n in pages[1:]:
            fetch(polet_facets.search_url(entry["query"], page=n))

    Hver entry:
        {"fylde": "7-8", "friskhet": "9-10", "tannin": "5-6",
         "query": ":relevance:Fylde:7-8:…:mainCategory:rødvin",
         "probe_url": "/vmpws/…&currentPage=0"}

    Kombinasjoner som gir 0 treff er normalt og forventet (klokke-dekningen er
    hullete: ~2 750 av de 13 775 røde har ingen klokker i det hele tatt) — de
    skal hoppes over, ikke retries.
    """
    buckets = polet_facets.clock_range_buckets(1, 12)
    for combo in product(buckets, repeat=len(_SWEEP_DIMS)):
        clocks = dict(zip(_SWEEP_DIMS, combo))
        query = polet_facets.build_facet_query(category=_SPINE_CATEGORY, clocks=clocks)
        yield {
            "fylde": clocks["Fylde"],
            "friskhet": clocks["Friskhet"],
            "tannin": clocks["Tannin(Sulfates)"],
            "query": query,
            "probe_url": polet_facets.search_url(query, page=0),
        }


def ingest_clock_sweep(results: Sequence[dict]) -> dict:
    """
    Bygg klokke-bøtte-mappingen ut av et ferdig klokke-sveip.

    Input er sveipe-resultatene, én entry per (trippel, batch) — samme trippel
    kan gjerne opptre flere ganger (sveiperen dumper gjerne per side):

        [{"fylde": "7-8", "friskhet": "9-10", "tannin": "5-6",
          "codes": ["759901", …]}, …]

    Output er en RAPPORT; mappingen ligger under `"mapping"` og er akkurat den
    `polet_store.set_clock_buckets(mapping, *, fetched_at=…)` konsumerer:

        {"mapping": {"759901": {"Fylde": "7-8", "Friskhet": "9-10",
                                "Tannin": "5-6"}, …},
         "codes": <antall unike varenr>,
         "buckets_seen": <antall unike tripler med minst én kode>,
         "collisions": [{"code": …, "buckets": [<trippel>, <trippel>]}, …],
         "collision_count": len(collisions)}

    **Kollisjoner er et DATAFEIL-SIGNAL, ikke en detalj.** En vin kan ikke ligge
    i to bøtter — det var nettopp det funnet som ga AND-semantikken i ADR-023.
    Dukker samme kode opp under to ULIKE tripler, betyr det at sveipet eller
    dumpen er korrupt (blandede batcher, feil trippel på fila). Vi lar derfor
    ikke siste skriver vinne stille: FØRSTE trippel beholdes i mappingen, alle
    de motstridende triplene rapporteres, og kalleren må se på tallet før den
    skriver til snapshotet. Samme kode under SAMME trippel er derimot bare en
    overlappende batch og telles ikke som kollisjon.

    Ugyldig bøtte-kode eller manglende dimensjon → `ValueError`. Et sveip som
    har mistet en dimensjon underveis skal ikke kunne skrive halve klokker inn
    i snapshotet.
    """
    mapping: dict[str, dict[str, str]] = {}
    origin: dict[str, tuple[str, str, str]] = {}
    conflicts: dict[str, list[tuple[str, str, str]]] = {}
    buckets_seen: set[tuple[str, str, str]] = set()

    for i, entry in enumerate(results):
        if not isinstance(entry, dict):
            raise ValueError(f"Sveipe-entry #{i} er ikke en dict: {entry!r}")

        triple = []
        for field in _SWEEP_RESULT_KEYS:
            bucket = entry.get(field)
            if bucket not in _BUCKET_CODES:
                raise ValueError(
                    f"Sveipe-entry #{i} har ugyldig/manglende «{field}»: {bucket!r}. "
                    f"Gyldige bøtte-koder: {sorted(_BUCKET_CODES)}"
                )
            triple.append(bucket)
        key = tuple(triple)

        codes = entry.get("codes") or []
        if not isinstance(codes, (list, tuple)):
            raise ValueError(f"Sveipe-entry #{i} har «codes» som ikke er en liste: {codes!r}")
        if codes:
            buckets_seen.add(key)

        clocks = dict(zip(_SWEEP_RESULT_KEYS.values(), key))
        for raw_code in codes:
            code = str(raw_code)
            previous = origin.get(code)
            if previous is None:
                origin[code] = key
                # Egen dict per kode: mappingen skal ikke dele muterbar state
                # mellom viner som tilfeldigvis kom i samme batch.
                mapping[code] = dict(clocks)
            elif previous != key:
                # Første trippel vinner; konflikten rapporteres i stedet for å
                # overskrives stille.
                seen = conflicts.setdefault(code, [previous])
                if key not in seen:
                    seen.append(key)

    collisions = [
        {"code": code, "buckets": [dict(zip(_SWEEP_RESULT_KEYS.values(), k)) for k in ks]}
        for code, ks in sorted(conflicts.items())
    ]

    return {
        "mapping": mapping,
        "codes": len(mapping),
        "buckets_seen": len(buckets_seen),
        "collisions": collisions,
        "collision_count": len(collisions),
    }


if __name__ == "__main__":
    import json as _json

    print("peer_pool_queries():")
    print(_json.dumps(peer_pool_queries(), ensure_ascii=False, indent=2))

    spine = list(spine_queries())
    sweep = list(clock_sweep_queries())
    print(f"\nspine_queries():      {len(spine)} sider  (a {_PAGE_SIZE} rader)")
    print(f"  første: {spine[0]['url']}")
    print(f"  siste:  {spine[-1]['url']}")
    print(f"\nclock_sweep_queries(): {len(sweep)} kombinasjoner (probe-kall)")
    print(f"  første: {sweep[0]['probe_url']}")
