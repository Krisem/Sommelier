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

# Klokke-dimensjonene i deterministisk emit-rekkefølge (viktig for testbarhet).
_CLOCK_DIMS: tuple[str, ...] = (
    "Fylde", "Friskhet", "Garvestoffer", "Soedme", "Tannin(Sulfates)", "Bitterhet",
)
_CLOCK_DIMS_SET = frozenset(_CLOCK_DIMS)


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
    - `sort`: sorterings-nøkkel, default `"relevance"`.

    Deterministisk rekkefølge: `:{sort}` først, så klokker i fast dim-rekkefølge,
    så `mainCategory`, så `mainCountry`.

    Eksempel:
        `:relevance:Fylde:7-8:Friskhet:9-10:mainCategory:rødvin:mainCountry:argentina`
    """
    clocks = clocks or {}

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
    - Ukjent dim → `ValueError`.
    """
    clock_ranges = clock_ranges or {}
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
