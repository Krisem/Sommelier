"""
Rene bygge-/parse-funksjoner for Vinmonopolets `vmpws`-søke-API.

INGEN nettverk her: Polets webshop-API er WAF-blokkert for `requests` (ADR-019),
så selve HTTP-kallene skjer i en browser andre steder. Denne modulen er ren og
fixture-testbar.

**Viktig om klokke-fasettene (verifisert live 2026-07-02):** Klokkene
(Fylde/Friskhet/…) er BØTTER på skala 1–12 (`1-2`, `3-4`, `5-6`, `7-8`, `9-10`,
`11-12`). Repeterte facet-tokens i `vmpws` er **AND, ikke OR** — så
`:Friskhet:7-8:Friskhet:9-10` gir 0 treff (en vin kan ikke ligge i to bøtter).
Et klokke-INTERVALL må derfor kjøres som FLERE queries (én per bøtte) som
caller unionerer client-side. Derfor:

- `build_facet_query` tar ÉN bøtte per klokke-dim → én gyldig query.
- `build_facet_queries` tar (min,max)-intervall per dim → LISTE av queries
  (kartesisk produkt over bøttene); kjør hver, union på `code`.
- `parse_search_products` plukker de kjøpbare produktene ut av et ferdig-hentet
  API-svar, med felt-shape UENDRET (identisk med catalog-linjene i
  `data/polet/catalog.ndjson`).

**Hvilke klokke-dimensjoner FILTRERER faktisk (live-målt 2026-08-29)?** Målt mot
`mainCategory:rødvin`, som har 13 775 treff totalt. `facets[]` i API-svaret er
alltid tomt, så koder kan ikke oppdages — de må probes. Resultatet:

| Dimensjon        | `:<dim>:7-8` gir      | Dom                                  |
|------------------|-----------------------|--------------------------------------|
| `Fylde`          | 5 668                 | ✅ filtrerer                          |
| `Friskhet`       | 6 468                 | ✅ filtrerer                          |
| `Tannin(Sulfates)` | 5 401               | ✅ filtrerer — dette ER garvestoffer  |
| `Garvestoffer`   | **13 775 i HVER bøtte** | ❌ ignoreres STILLE → hele katalogen |
| `Soedme`         | 0                     | ❌ ikke gyldig for rødvin             |
| `Bitterhet`      | 0                     | ❌ ikke gyldig for rødvin             |

Også probet og forkastet (ignoreres eller gir 0): `Garvestoff`, `garvestoffer`,
`Tannin`, `tannin`, `Tannins`, `Sulfates`, `Sodme`, `Sødme`, `Sukker`. Kun
`Tannin(Sulfates)` virker.

`Garvestoffer` er den farlige: en query som «filtrerer» på den returnerer HELE
katalogen mens kalleren tror den har filtrert. Den er derfor IKKE en gyldig
fasett her og gir `ValueError` med en peker til `Tannin(Sulfates)` — se
`_TRAP_DIMS`. NB: `Garvestoffer` er samtidig det RIKTIGE navnet i produktsidens
detalj-JSON (`content.characteristics`), som `tools/vinmonopolet.py` leser. Det
er navnet på klokken i DETALJENE, ikke koden på fasetten i SØKET — samme klokke,
to ulike navnerom, og det er nettopp derfor fella er lett å gå i.

**Paginering (live-målt 2026-08-29):** `pageSize` har et SERVERTAK på 24 — 25,
48 og 50 gir alle `pagination.pageSize: 24` og 24 produkter. `currentPage` er
0-basert og virker helt ut (side 573 av 574 ga de siste 23 produktene, side 600
ga 0). Full enumerering krever derfor paginering: `page_numbers` +
`search_url`.
"""

from __future__ import annotations

from itertools import product
from typing import Optional

# ─── KONSTANTER ──────────────────────────────────────────────────────

# Gyldige klokke-bøtter på skala 1–12 (stigende). Hver dekker et lukket 2-intervall.
_CLOCK_BUCKETS: tuple[tuple[int, int], ...] = (
    (1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12),
)
_BUCKET_CODES = frozenset(f"{lo}-{hi}" for lo, hi in _CLOCK_BUCKETS)

# Klokke-dimensjonene som BEVISELIG filtrerer (live-målt 2026-08-29, se
# modul-docstringen), i deterministisk emit-rekkefølge (viktig for testbarhet).
_CLOCK_DIMS: tuple[str, ...] = ("Fylde", "Friskhet", "Tannin(Sulfates)")
_CLOCK_DIMS_SET = frozenset(_CLOCK_DIMS)

# Dimensjoner som SER gyldige ut, men ikke er det. De sto i `_CLOCK_DIMS` fram
# til 2026-08-29, så eksisterende kall må avvises HØYT — ikke stille.
_TRAP_DIMS: dict[str, str] = {
    "Garvestoffer": (
        "«Garvestoffer» er IKKE en fasett-kode i vmpws — den ignoreres stille, og "
        "queryen returnerer HELE katalogen ufiltrert (målt 2026-08-29: 13 775 treff "
        "i HVER bøtte for mainCategory:rødvin, altså hele katalogen). Riktig kode er "
        "«Tannin(Sulfates)». NB: «Garvestoffer» ER riktig navn på klokken i "
        "produktsidens detalj-JSON (tools/vinmonopolet.py) — men det er et annet "
        "navnerom enn søke-fasettene."
    ),
    "Soedme": (
        "«Soedme» gir 0 treff for rødvin (målt 2026-08-29) — dimensjonen er ikke "
        "gyldig her. Ta den ut av queryen i stedet for å filtrere alt bort."
    ),
    "Bitterhet": (
        "«Bitterhet» gir 0 treff for rødvin (målt 2026-08-29) — dimensjonen er ikke "
        "gyldig her. Ta den ut av queryen i stedet for å filtrere alt bort."
    ),
}

# `pageSize` er kappet av SERVEREN på 24 (målt 2026-08-29: 25/48/50 gir alle
# `pagination.pageSize: 24`). Dette er et tak, ikke et valg — å skru det opp
# gjør ingenting annet enn å gjøre koden usann.
PAGE_SIZE = 24

_SEARCH_PATH = "/vmpws/v2/vmp/products/search"


def _reject_trap_dims(dims) -> None:
    """
    Kast `ValueError` med en KONKRET forklaring for dimensjoner som ser gyldige
    ut men ikke filtrerer. Generisk «ukjent dimensjon» er ikke godt nok her:
    `Garvestoffer` var gyldig i denne modulen fram til 2026-08-29, og en query
    som bruker den returnerer hele katalogen mens kalleren tror den filtrerte.
    """
    trapped = sorted(set(dims) & set(_TRAP_DIMS))
    if trapped:
        raise ValueError(" ".join(_TRAP_DIMS[d] for d in trapped))


# ─── BØTTER ──────────────────────────────────────────────────────────

def clock_range_buckets(min_v: int, max_v: int) -> list[str]:
    """
    Bøtte-kodene (f.eks. `"7-8"`) som overlapper det lukkede intervallet
    [min_v, max_v], i stigende rekkefølge. `(7, 12)` → `["7-8", "9-10", "11-12"]`.
    Reversert input tolkes som [min, max].
    """
    lo, hi = (min_v, max_v) if min_v <= max_v else (max_v, min_v)
    return [f"{b_lo}-{b_hi}" for b_lo, b_hi in _CLOCK_BUCKETS if b_lo <= hi and b_hi >= lo]


# ─── BYGGE QUERY ─────────────────────────────────────────────────────

def build_facet_query(
    *,
    category: Optional[str] = None,
    country: Optional[str] = None,
    clocks: Optional[dict[str, str]] = None,
    sort: str = "relevance",
) -> str:
    """
    Bygg ÉN `query`-VERDI på Hybris-fasett-format (ikke URL-encodet — caller encoder).

    - `category`: kategori-kode (lowercase), f.eks. `"rødvin"`. Utelates hvis None.
    - `country`: land-kode (lowercase), f.eks. `"argentina"`. Utelates hvis None.
    - `clocks`: dict dim→ÉN bøtte-kode, f.eks. `{"Friskhet": "9-10", "Fylde": "7-8"}`.
      Ulike dimensjoner AND-es sammen (gyldig). Ukjent dim eller ugyldig bøtte-kode
      → `ValueError`. (For et INTERVALL over flere bøtter, bruk `build_facet_queries`.)
      `Garvestoffer`/`Soedme`/`Bitterhet` → `ValueError` med forklaring: de
      filtrerer ikke (se modul-docstringen og `_TRAP_DIMS`).
    - `sort`: sorterings-nøkkel, default `"relevance"`.

    Deterministisk rekkefølge: `:{sort}` først, så klokker i fast dim-rekkefølge,
    så `mainCategory`, så `mainCountry`.

    Eksempel:
        `:relevance:Fylde:7-8:Friskhet:9-10:mainCategory:rødvin:mainCountry:argentina`
    """
    clocks = clocks or {}

    _reject_trap_dims(clocks)
    unknown = set(clocks) - _CLOCK_DIMS_SET
    if unknown:
        raise ValueError(
            f"Ukjent(e) klokke-dimensjon(er): {sorted(unknown)}. Gyldige: {list(_CLOCK_DIMS)}"
        )
    bad = {d: b for d, b in clocks.items() if b not in _BUCKET_CODES}
    if bad:
        raise ValueError(
            f"Ugyldig(e) bøtte-kode(r): {bad}. Gyldige: {sorted(_BUCKET_CODES)}"
        )

    tokens: list[str] = [sort]
    for dim in _CLOCK_DIMS:
        if dim in clocks:
            tokens.extend((dim, clocks[dim]))
    if category is not None:
        tokens.extend(("mainCategory", category))
    if country is not None:
        tokens.extend(("mainCountry", country))

    return ":" + ":".join(tokens)


def build_facet_queries(
    *,
    category: Optional[str] = None,
    country: Optional[str] = None,
    clock_ranges: Optional[dict[str, tuple[int, int]]] = None,
    sort: str = "relevance",
) -> list[str]:
    """
    Bygg LISTEN av queries som til sammen dekker klokke-INTERVALLENE, siden
    repeterte facets er AND i `vmpws` (et intervall over flere bøtter kan ikke
    uttrykkes i én query). Returnerer det kartesiske produktet over hver dims
    overlappende bøtter; caller kjører hver query og unionerer på `code`.

    - `clock_ranges`: dict dim→(min,max) på 1–12. `{"Fylde": (7,8), "Friskhet": (7,12)}`
      → 1×3 = 3 queries (Fylde 7-8 × Friskhet {7-8, 9-10, 11-12}).
    - Uten `clock_ranges` → `[build_facet_query(...)]` (én query).
    - Ukjent dim → `ValueError`. `Garvestoffer`/`Soedme`/`Bitterhet` likeså, med
      en forklaring på hvorfor de ikke filtrerer.
    """
    clock_ranges = clock_ranges or {}
    _reject_trap_dims(clock_ranges)
    unknown = set(clock_ranges) - _CLOCK_DIMS_SET
    if unknown:
        raise ValueError(
            f"Ukjent(e) klokke-dimensjon(er): {sorted(unknown)}. Gyldige: {list(_CLOCK_DIMS)}"
        )

    # Dimensjoner i fast rekkefølge; hver med sin liste av bøtter.
    dims = [d for d in _CLOCK_DIMS if d in clock_ranges]
    if not dims:
        return [build_facet_query(category=category, country=country, sort=sort)]

    bucket_lists = [clock_range_buckets(*clock_ranges[d]) for d in dims]
    queries: list[str] = []
    for combo in product(*bucket_lists):
        clocks = dict(zip(dims, combo))
        queries.append(
            build_facet_query(category=category, country=country, clocks=clocks, sort=sort)
        )
    return queries


# ─── PAGINERING ──────────────────────────────────────────────────────

def page_numbers(total_results: int, *, page_size: int = PAGE_SIZE) -> list[int]:
    """
    `currentPage`-verdiene som til sammen dekker `total_results` treff, i
    stigende rekkefølge. 0-BASERT (målt 2026-08-29: rødvin har 13 775 treff →
    574 sider, og side 573 ga de siste 23 produktene mens side 600 ga 0).

    `13775` → `[0, 1, ..., 573]` (574 sider). `0` → `[]` (ingenting å hente).
    Negativ input behandles som 0.

    `page_size` er default `PAGE_SIZE` (24) — servertaket. Parameteren finnes
    bare for testbarhet; å sende noe høyere gjør ikke sidene større, det gjør
    bare at man planlegger for få sider og avkorter sveipet stille.
    """
    if total_results <= 0:
        return []
    if page_size <= 0:
        raise ValueError(f"page_size må være > 0, fikk {page_size}")
    return list(range(-(-total_results // page_size)))


def search_url(query: str, *, page: int = 0, page_size: int = PAGE_SIZE) -> str:
    """
    Bygg den relative søke-URL-en browseren skal `fetch()`-e, for ÉN side.

        search_url(":relevance:mainCategory:rødvin", page=3)
        → "/vmpws/v2/vmp/products/search?q=:relevance:mainCategory:rødvin"
          "&pageSize=24&currentPage=3"

    `query` sendes UENCODET (som i runbooken og som live-målt): browserens
    URL-parser prosent-encoder `ø` og lignende selv, og `(`/`)` i
    `Tannin(Sulfates)` er lovlige i en query-streng. `?fields=FULL` gir 400 og
    legges derfor aldri på.

    Negativ `page` → `ValueError` (0-basert paginering; -1 er ikke «siste side»).
    """
    if page < 0:
        raise ValueError(f"page er 0-basert og må være >= 0, fikk {page}")
    return f"{_SEARCH_PATH}?q={query}&pageSize={page_size}&currentPage={page}"


# ─── PARSE SVAR ──────────────────────────────────────────────────────

def parse_search_products(api_json: dict) -> list[dict]:
    """
    Plukk de KJØPBARE produktene ut av et ferdig-hentet `vmpws`-søkesvar.

    Felt-shapen bevares UENDRET (identisk med catalog-linjene). Robust:
    - tomt/manglende/ikke-liste `products` → `[]`
    - produkter uten sann `buyable` ekskluderes
    """
    if not isinstance(api_json, dict):
        return []
    products = api_json.get("products")
    if not isinstance(products, list):
        return []
    return [p for p in products if isinstance(p, dict) and p.get("buyable")]
