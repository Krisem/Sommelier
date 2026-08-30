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

**Hvilke klokke-dimensjoner FILTRERER faktisk?** `facets[]` i API-svaret er
alltid tomt, så koder kan ikke oppdages — de må probes. Og svaret er
**kategori-avhengig**: se `_CLOCK_DIMS_BY_CATEGORY` for måletabellen.
Kortversjonen er at den tredje klokka bytter identitet mellom kategoriene —
`Tannin(Sulfates)` for rødvin, `Soedme` for hvitvin, musserende og rosé — mens
`Fylde` og `Friskhet` gjelder overalt. `Garvestoffer` ignoreres stille i alle
kategorier, og `Bitterhet` er tom overalt.

Også probet og forkastet for rødvin (ignoreres eller gir 0): `Garvestoff`,
`garvestoffer`, `Tannin`, `tannin`, `Tannins`, `Sulfates`, `Sodme`, `Sødme`,
`Sukker`.

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

# ─── KLOKKE-NAVNEROM: SAMME KLOKKE, TRE NAVN ─────────────────────────
#
# Garvestoff-klokken heter noe forskjellig i hvert av de tre lagene, og hver
# gang noen har krysset et lag uten å oversette, har det gått galt STILLE:
#
#   | Lag                                | Navn               | Verditype     |
#   |------------------------------------|--------------------|---------------|
#   | Produktside-JSON (`details/*.json`)| `Garvestoffer`     | heltall 1–12  |
#   | Katalograd (`clock_buckets`)       | `Tannin`           | bøtte "7-8"   |
#   | Søke-fasett (`vmpws`)              | `Tannin(Sulfates)` | bøtte "7-8"   |
#
# Sødme-klokka (den tredje for hvit/musserende/rosé) har samme problem, med en
# fjerde stavemåte i miksen — `Soedme` uten ø i søket og på katalograden,
# `Sødme` med ø i details. Målt 2026-08-30: 290 details-filer bruker `Sødme`.
#
# Historikken: ADR-009 (kode ≠ navn i fasett-oppslag), ADR-024 (`Garvestoffer`
# som fasett ga HELE katalogen tilbake i hver bøtte), og B3 2026-08-30 (å mate
# `clock_buckets` rett inn i `clock_distance` mister garvestoff-aksen uten et
# eneste synlig tegn — funksjonen regner videre på 2 av 3 akser).
#
# Derfor bor oversettelsen HER, ett sted, i stedet for som en dict i hver
# kallsted. `tools/vinmonopolet.py` importerer den.
#
# Kanonisk navn = detalj-navnet, siden det er det `CLOCK_DIMS` og hele
# similarity-veien i `vinmonopolet.py` bruker.
CLOCK_DIM_BY_CATALOG_DIM: dict[str, str] = {
    "Fylde": "Fylde",
    "Friskhet": "Friskhet",
    "Tannin": "Garvestoffer",
    # Begge stavemåtene godtas med vilje. Klokke-sveipen skriver `Soedme`
    # (søkekoden), men `Sødme` er navnet i details — og en katalograd som en dag
    # bærer det med ø skal ikke stille miste aksen. Å godta begge her koster
    # ingenting; å godta feil ville kostet en akse for hele hvitvinsbasen.
    "Soedme": "Sødme",
    "Sødme": "Sødme",
}

CLOCK_DIM_BY_FACET_DIM: dict[str, str] = {
    "Fylde": "Fylde",
    "Friskhet": "Friskhet",
    "Tannin(Sulfates)": "Garvestoffer",
    "Soedme": "Sødme",
}

# ─── HVILKE KLOKKER FILTRERER? DET AVHENGER AV KATEGORIEN ────────────
#
# Fram til 2026-08-30 sto dette som ÉN global tuple. Det var en skjult antagelse
# om at katalogen er homogen, og den holdt kun så lenge bare rødvin var
# kartlagt. Live-probet (rødvin 2026-08-29, øvrige 2026-08-30):
#
#   | Dimensjon        | rødvin | hvitvin | musserende | rosévin |
#   |------------------|--------|---------|------------|---------|
#   | Fylde            | 11 029 |   8 366 |      2 804 |     777 |
#   | Friskhet         | 10 986 |   8 365 |      2 798 |     777 |
#   | Tannin(Sulfates) |  5 401 |       0 |          0 |       0 |
#   | Soedme           |      0 |   8 348 |      2 794 |     777 |
#   | Bitterhet        |      0 |       0 |          0 |       0 |
#   | Garvestoffer     | totalen| totalen |    totalen | totalen |
#   | Xyzzy (kontroll) |   —    | totalen |    totalen | totalen |
#
# Kategoritotaler: rødvin 13 774 · hvitvin 9 762 · musserende 3 081 · rosé 782.
#
# `Xyzzy` er en oppdiktet kode brukt som kontroll. At den gir nøyaktig
# kategoritotalen bekrefter at ugyldige koder ignoreres STILLE — og at
# `Garvestoffer` oppfører seg identisk med en tullekode.
#
# **To helt ulike slags null, og de må ikke slås sammen:**
#   - «totalen» = koden ignoreres stille. Filteret gjør INGENTING; du får hele
#     kategorien tilbake og tror du har filtrert.
#   - «0» = koden gjenkjennes, men er tom for kategorien. Filteret fjerner ALT.
# Begge er verdiløse, men de feiler i hver sin retning, og en feilmelding som
# sier hvilken du har truffet er langt mer nyttig enn én felles.
_CLOCK_DIMS_BY_CATEGORY: dict[str, tuple[str, ...]] = {
    "rødvin": ("Fylde", "Friskhet", "Tannin(Sulfates)"),
    "hvitvin": ("Fylde", "Friskhet", "Soedme"),
    "musserende_vin": ("Fylde", "Friskhet", "Soedme"),
    "rosévin": ("Fylde", "Friskhet", "Soedme"),
}

# Gyldig i ALLE probede kategorier — de eneste som kan brukes uten å oppgi
# kategori, siden gyldigheten da ikke kan slås opp.
_UNIVERSAL_CLOCK_DIMS: tuple[str, ...] = ("Fylde", "Friskhet")

# Kategorier som IKKE er probet. Sterkvin, perlende_vin, fruktvin og
# aromatisert_vin er aldri målt — vi vet ikke om noen klokke filtrerer der, og
# «sannsynligvis som hvitvin» er nøyaktig den gjetningen som skapte denne
# feilklassen i utgangspunktet.
PROBED_CATEGORIES = frozenset(_CLOCK_DIMS_BY_CATEGORY)

# Dimensjoner som ignoreres STILLE i alle kategorier — den farligste sorten,
# fordi queryen returnerer hele katalogen mens kalleren tror den filtrerte.
_SILENT_TRAP_DIMS: frozenset[str] = frozenset({"Garvestoffer"})

# Gjenkjent av API-et, men tom i ALLE probede kategorier.
_ALWAYS_ZERO_DIMS: frozenset[str] = frozenset({"Bitterhet"})

# `pageSize` er kappet av SERVEREN på 24 (målt 2026-08-29: 25/48/50 gir alle
# `pagination.pageSize: 24`). Dette er et tak, ikke et valg — å skru det opp
# gjør ingenting annet enn å gjøre koden usann.
PAGE_SIZE = 24

_SEARCH_PATH = "/vmpws/v2/vmp/products/search"


def clock_dims_for_category(category: Optional[str]) -> tuple[str, ...]:
    """
    Klokke-dimensjonene som BEVISELIG filtrerer for `category`.

    `None` → de universelle (`Fylde`, `Friskhet`), altså de eneste som kan
    brukes uten å vite kategorien. Uprobet kategori → `ValueError`.
    """
    if category is None:
        return _UNIVERSAL_CLOCK_DIMS
    key = category.casefold()
    for kat, dims in _CLOCK_DIMS_BY_CATEGORY.items():
        if kat.casefold() == key:
            return dims
    raise ValueError(
        f"Kategorien «{category}» er ikke probet — vi vet ikke hvilke klokker "
        f"som filtrerer der. Probede kategorier: {sorted(PROBED_CATEGORIES)}. "
        "Prob den mot vmpws før du bygger klokke-queries: en ugyldig kode "
        "feiler STILLE og gir hele kategorien tilbake (bekreftet med "
        "kontrollkoden «Xyzzy», 2026-08-30)."
    )


def _reject_invalid_clock_dims(dims, category: Optional[str]) -> None:
    """
    Kast `ValueError` med en KONKRET, kategori-navngitt forklaring for
    dimensjoner som ikke filtrerer.

    Generisk «ukjent dimensjon» er ikke godt nok. Det er tre ulike feil her, og
    de krever hvert sitt råd:
      1. Stille felle (`Garvestoffer`) — queryen ville gitt hele kategorien.
      2. Gjenkjent, men tom for DENNE kategorien (`Soedme` på rødvin,
         `Tannin(Sulfates)` på hvitvin) — queryen ville filtrert bort alt.
      3. Ukjent kode.
    """
    dims = list(dims)
    if not dims:
        return

    feil: list[str] = []

    for d in sorted(set(dims) & _SILENT_TRAP_DIMS):
        feil.append(
            f"«{d}» er IKKE en fasett-kode i vmpws — den ignoreres stille, og "
            "queryen returnerer HELE kategorien ufiltrert (målt 2026-08-29: "
            "13 775 treff i HVER bøtte for mainCategory:rødvin, altså hele "
            "katalogen; samme oppførsel som kontrollkoden «Xyzzy» i hvitvin, "
            "musserende og rosé 2026-08-30). For rødvin er riktig kode "
            "«Tannin(Sulfates)»; hvitvin, musserende og rosé har ingen "
            "garvestoff-klokke i det hele tatt. NB: «Garvestoffer» ER riktig "
            "navn på klokken i produktsidens detalj-JSON — men det er et annet "
            "navnerom enn søke-fasettene."
        )

    gyldige = clock_dims_for_category(category)
    kat = f"«{category}»" if category else "en uspesifisert kategori"

    for d in sorted(set(dims) - _SILENT_TRAP_DIMS - set(gyldige)):
        andre = sorted(
            k for k, v in _CLOCK_DIMS_BY_CATEGORY.items() if d in v
        )
        if d in _ALWAYS_ZERO_DIMS:
            feil.append(
                f"«{d}» gir 0 treff i alle probede kategorier (målt 2026-08-29/30) "
                "— dimensjonen er ikke gyldig noe sted. Ta den ut av queryen i "
                "stedet for å filtrere alt bort."
            )
        elif andre and category is not None:
            feil.append(
                f"«{d}» gir 0 treff for {kat} (målt 2026-08-30) — koden "
                "gjenkjennes, men er tom for denne kategorien, så queryen ville "
                f"filtrert bort alt. Den er gyldig for {andre}. Gyldige klokker "
                f"for {kat}: {list(gyldige)}."
            )
        elif andre:
            feil.append(
                f"«{d}» er kategori-avhengig og krever at du oppgir kategori — "
                f"den filtrerer kun for {andre}. Uten kategori kan bare "
                f"{list(_UNIVERSAL_CLOCK_DIMS)} brukes, siden gyldigheten ellers "
                "ikke kan slås opp."
            )
        else:
            feil.append(
                f"Ukjent klokke-dimensjon «{d}». Gyldige for {kat}: "
                f"{list(gyldige)}."
            )

    if feil:
        raise ValueError(" ".join(feil))


# ─── BØTTER ──────────────────────────────────────────────────────────

def clock_range_buckets(min_v: int, max_v: int) -> list[str]:
    """
    Bøtte-kodene (f.eks. `"7-8"`) som overlapper det lukkede intervallet
    [min_v, max_v], i stigende rekkefølge. `(7, 12)` → `["7-8", "9-10", "11-12"]`.
    Reversert input tolkes som [min, max].
    """
    lo, hi = (min_v, max_v) if min_v <= max_v else (max_v, min_v)
    return [f"{b_lo}-{b_hi}" for b_lo, b_hi in _CLOCK_BUCKETS if b_lo <= hi and b_hi >= lo]


def bucket_midpoint(bucket: str) -> float:
    """
    Midtpunktet i en bøtte-kode: `"7-8"` → `7.5`. Ugyldig kode → `ValueError`.

    Midtpunkt, ikke nedre grense: bøtta er et lukket 2-intervall, så midtpunktet
    har maks 0,5 i feil mot den eksakte klokka. Det er under klokkeskalaens egen
    oppløsning på 1, og gjør bøtte-verdier direkte sammenlignbare med de eksakte
    heltallene fra `details/` i samme avstandsregning.
    """
    if bucket not in _BUCKET_CODES:
        raise ValueError(
            f"Ugyldig bøtte-kode {bucket!r} — gyldige er {sorted(_BUCKET_CODES)}"
        )
    lo, hi = bucket.split("-")
    return (int(lo) + int(hi)) / 2


def clocks_from_buckets(clock_buckets: dict) -> dict[str, float]:
    """
    Oversett en katalograds `clock_buckets` til klokke-profilen `clock_distance`
    forventer: detalj-navnerommet, med numeriske midtpunkter.

        {"Fylde": "7-8", "Friskhet": "9-10", "Tannin": "5-6"}
        → {"Fylde": 7.5, "Friskhet": 9.5, "Garvestoffer": 5.5}

    Legg merke til at `Tannin` BLIR `Garvestoffer`. Uten den oversettelsen ser
    profilen riktig ut, men mangler garvestoff-aksen — se navnerom-tabellen
    øverst i modulen.

    Ukjente dimensjoner beholder navnet sitt (en framtidig fjerde klokke skal
    ikke krasje en similarity-kjøring). Sikringen mot en STILLE tapt akse ligger
    i `clock_distance`, som kaster når en dimensjon den er bedt om å regne på
    mangler — ikke her.

    Ugyldig bøtte-verdi → `ValueError`.
    """
    if not isinstance(clock_buckets, dict):
        raise ValueError(
            f"clock_buckets må være en dict, fikk {type(clock_buckets).__name__}"
        )
    return {
        CLOCK_DIM_BY_CATALOG_DIM.get(dim, dim): bucket_midpoint(bucket)
        for dim, bucket in clock_buckets.items()
    }


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

    _reject_invalid_clock_dims(clocks, category)
    bad = {d: b for d, b in clocks.items() if b not in _BUCKET_CODES}
    if bad:
        raise ValueError(
            f"Ugyldig(e) bøtte-kode(r): {bad}. Gyldige: {sorted(_BUCKET_CODES)}"
        )

    tokens: list[str] = [sort]
    # Kategori-oppslaget kjøres kun når det faktisk er klokker å ordne — en
    # uprobet kategori er helt uproblematisk så lenge ingen klokke er med.
    for dim in clock_dims_for_category(category) if clocks else ():
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
    _reject_invalid_clock_dims(clock_ranges, category)

    if not clock_ranges:
        return [build_facet_query(category=category, country=country, sort=sort)]

    # Dimensjoner i fast rekkefølge; hver med sin liste av bøtter.
    dims = [d for d in clock_dims_for_category(category) if d in clock_ranges]

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
