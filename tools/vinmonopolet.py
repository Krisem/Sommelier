"""
Vinmonopolet helpers – repo-snapshot via polet_store

Polets webshop-API (`vmpws`) er WAF-blokkert (ADR-019/ADR-020) — `requests`-kall
gir 403. Varig Polet-data ligger derfor git-committet i `data/polet/` og leses
gjennom `tools.polet_store` (device-agnostisk, portabelt til Android uten
browser). Refresh av snapshotet skjer separat på desktop via Playwright-MCP
(se `docs/polet_refresh.md`) — denne modulen er ren read-side.

Bruk dette scriptet i prosjektet for å:
- Søke etter viner (snapshot-katalog)
- Hente klokker, lukt, smak, drueblanding fra produktdetaljer
- Sammenligne mot brukerens preferanser
- Finne nærmeste vin på klokke-profil (find_similar_by_clocks)

Cache-miss (vin ikke i snapshotet) → `PoletRefreshRequired` med refresh-hint.

**To ting det er verdt å vite før du kaller noe her (begge rettet 2026-08-30):**

1. `search` filtrerer FØR den avkorter. Send pris/kategori/land inn i `search`,
   ikke på resultatet etterpå — `filter_results(search(q), max_price=X)` ser
   bare de N første varenumrene. `page_size=None` gir hele populasjonen.
2. `find_similar_by_clocks` er et GROVFILTER for stil-slektskap, ikke en
   kvalitets- eller preferansemodell (ADR-025). Resultatet bærer forbeholdet og
   dekningstallene selv — vis `.summary()`.
"""

import math
import re
from typing import Iterable, Optional

import requests  # beholdt: find_similar_by_clocks fanger requests.RequestException

# Gjør fila kjørbar både som modul (`python3 -m tools.vinmonopolet`) og som skript
# (`python3 tools/vinmonopolet.py`) — sistnevnte er kommandoen CLAUDE.md dokumenterer.
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))

from tools import polet_facets, polet_store
from tools.polet_store import PoletRefreshRequired

# Privat i polet_store, men bevisst importert framfor kopiert: den ER den ene
# autoriteten på ADR-009-regelen «kode ≠ navn, begge skal matche». En kopi her
# ville blitt den fjerde utgaven av nøyaktig den navnerom-kollisjonen dette
# repoet allerede har gått i tre ganger.
from tools.polet_store import _matches_label

BASE = "https://www.vinmonopolet.no"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _search_url(query: str) -> str:
    """Bygg vmpws-søke-URL for query — kun til PoletRefreshRequired-hint."""
    return f"{BASE}/vmpws/v2/vmp/products/search?q={query}"


# Feltene fritekst-søket ser på. `name` alene gjorde 38 av 74 Etna-rødviner
# usynlige (`19245001` Vino di Anna Sfuso står i sub_District «Etna», men har
# ikke ordet i navnet). Målt 2026-08-30 over hele katalogen hva bredden koster:
# geografiske termer vinner mye (Rioja 41 → 327, Sicilia 16 → 227, Etna 36 → 75),
# drue- og produsentnavn nærmest ingenting (Nebbiolo ±0, Fenocchio ±0,
# Barbera +3, Amarone +1). Bredden henter altså inn nettopp de radene et
# navnesøk ikke KAN se, uten å drukne de søkene som allerede virket.
#
# NB: kun `.name` på distrikts-objektene, aldri `.code` — distriktskoden bærer
# landprefiks (`frankrike_languedoc-roussillon`), så et `.code`-søk på
# «frankrike» ville stille returnert hver eneste franske vin.
SEARCH_FIELDS = ("name", "district", "sub_District")


def _field_text(product: dict, field: str) -> str:
    """Tekstverdien i ett søkefelt. Fasett-objekter ({code,name}) → `.name`."""
    value = product.get(field)
    if isinstance(value, dict):
        return str(value.get("name") or "")
    return str(value or "")


def _matches_text(product: dict, needle: str, fields: Iterable[str]) -> bool:
    """True hvis `needle` er delstreng (case-insensitivt) i minst ett av `fields`."""
    n = needle.casefold()
    return any(n in _field_text(product, f).casefold() for f in fields)


def search(
    query: str,
    page_size: Optional[int] = 10,
    use_cache: bool = True,
    *,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    category: Optional[str] = None,
    country: Optional[str] = None,
    fields: Iterable[str] = SEARCH_FIELDS,
) -> list[dict]:
    """
    Søk etter produkter i repo-snapshotet (fritekst mot navn + distrikt).

    Returnerer liste med dicts som inneholder:
    - code (varenummer), name, price.value
    - alcohol.value, volume.value
    - main_category, main_country, district, sub_District
    - product_selection, clock_buckets
    - url (relativ sti til produktsiden)

    **Filtrene filtrerer FØR `page_size` avkorter.** Det er hele poenget med at
    de ligger her og ikke bare i `filter_results`: fram til 2026-08-30 tok
    `search` de N første treffene og lot kalleren filtrere etterpå, slik at
    `filter_results(search("Barbera"), max_price=250)` ga 3 av 94 mulige. Taket
    er legitimt — brukeren skal ha topp-N — men det må legges på til slutt.
    Trenger du hele populasjonen (peer-utvalg, similarity), send
    `page_size=None`.

    Merk at katalogen er sortert på varenummer, ikke relevans. «Topp-N» er
    derfor N vilkårlige treff med mindre du snevrer inn med filtrene først.

    `fields` styrer hvilke felter fritekst matcher mot (default
    `SEARCH_FIELDS` = navn + distrikt + underdistrikt). Sett den til
    `("name",)` for gammel, ren navne-oppførsel.

    `use_cache` beholdes for bakoverkompat (no-op — snapshotet ER cachen).

    Ingen fritekst-treff → `PoletRefreshRequired` (vinen mangler i snapshotet).
    Treff som filtrene tømmer → tom liste, IKKE exception: da mangler det ingen
    data, og et refresh-hint ville vært feil råd.
    """
    matched = [p for p in polet_store.read_catalog() if _matches_text(p, query, fields)]
    if not matched:
        raise PoletRefreshRequired(
            f"Ingen snapshot-treff på '{query}'",
            url=_search_url(query),
            hint=(
                "Søket ga ingen treff i repo-snapshotet — refresh katalogen fra "
                "desktop (se docs/polet_refresh.md)"
            ),
        )
    filtered = filter_results(
        matched,
        max_price=max_price,
        min_price=min_price,
        category=category,
        country=country,
    )
    return filtered if page_size is None else filtered[:page_size]


def search_with_facets(
    facets: dict,
    page_size: int = 50,
    use_cache: bool = True,
) -> list[dict]:
    """
    Søk snapshotet med fasett-filter (kategori/land) — mappet til polet_store.query.

    Eksempel:
        peers = search_with_facets(
            {"mainCategory": "rødvin", "mainCountry": "italia"},
            page_size=50,
        )

    Argumenter:
        facets: dict med fasett-koder → kode-/navn-verdi. `mainCategory` og
                `mainCountry` mappes til query(category=, country=); begge matcher
                både `.code` og `.name` (case-insensitivt) i polet_store.
                  - mainCategory: 'rødvin' | 'hvitvin' | 'musserende_vin' | ...
                  - mainCountry:  'italia' | 'frankrike' | 'spania' | ...
        page_size: maks antall produkter
        use_cache: beholdt for bakoverkompat (no-op).

    Returnerer samme produkt-struktur som search(). Resultatet kan være tynt
    (value_score håndterer peer-terskelen selv). Tomt → `PoletRefreshRequired`.
    """
    category = facets.get("mainCategory")
    country = facets.get("mainCountry")

    products = polet_store.query(category=category, country=country)
    if not products:
        parts = [f"{k}:{v}" for k, v in sorted(facets.items())]
        query = ":relevance:" + ":".join(parts) if parts else ":relevance"
        raise PoletRefreshRequired(
            f"Ingen snapshot-treff på fasetter {facets}",
            url=_search_url(query),
            hint=(
                "Fasett-søket ga ingen treff i repo-snapshotet — refresh "
                "katalogen fra desktop (se docs/polet_refresh.md)"
            ),
        )
    return products[:page_size]


def filter_results(
    results: list[dict],
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    category: Optional[str] = None,  # "Rødvin", "Hvitvin", "Musserende vin", "Rosévin"
    country: Optional[str] = None,
) -> list[dict]:
    """
    Filtrer søkeresultater på pris, kategori og land.

    `category`/`country` matcher BÅDE `.code` og `.name` case-insensitivt, altså
    samme regel som `polet_store.query` — «Rødvin» og «rødvin» er samme filter.
    Før 2026-08-30 krevde denne funksjonen eksakt `.name`, mens `polet_store`
    godtok begge; det er ADR-009-fella (kode ≠ navn) i miniatyr, og den er nå
    lukket ved å bruke polet_stores egen regel i stedet for å kopiere den hit.
    """
    out = []
    for p in results:
        price = p.get("price", {}).get("value", 9999)
        if max_price is not None and price > max_price:
            continue
        if min_price is not None and price < min_price:
            continue
        if category and not _matches_label(p.get("main_category"), category):
            continue
        if country and not _matches_label(p.get("main_country"), country):
            continue
        out.append(p)
    return out


def parse_product_html(html: str) -> dict:
    """
    Trekk ut klokker, druer, stil, lukt, smak, alkohol, sukker, syre osv. fra
    rå produktside-HTML. Ren funksjon — ingen I/O. Skilt ut fra
    `get_product_details` slik at den kan testes mot en pinned HTML-fixture
    (tests/fixtures/vinmonopolet/) for å fange Polet-DOM-drift.
    """
    result: dict = {}

    # Klokker (Fylde, Friskhet, Garvestoffer, Sødme – skala 1-12)
    clocks = {}
    for klokke in ["Fylde", "Friskhet", "Garvestoffer", "Sødme", "Frukt", "Krydder og urter"]:
        m = re.search(
            rf'"name":"{klokke}","readableValue":"{klokke}, (\d+) av 12"',
            html,
        )
        if m:
            clocks[klokke] = int(m.group(1))
    result["klokker"] = clocks

    # Drueblanding
    druer = re.findall(r'aria-label="([^"]+ \d+ prosent)"', html)
    if druer:
        result["druer"] = ", ".join(druer)

    # Stil – kommer rett før "Drikkeklar"-feltet på produktsiden
    stil_patterns = [
        "Frisk og fruktig", "Fruktig og mild", "Fruktig og rik",
        "Frisk og bærpreget", "Sval og krydret", "Fruktig og fast",
        "Modent og kompleks", "Fyldig og krydret", "Konsentrert og rik",
        "Søte og halvsøte",
        "Frisk og frodig", "Aromatisk", "Rik og fyldig",
        "Frisk og urtepreget", "Sval og mineralsk", "Rik og krydret",
        "Oransje", "Hudkontakt",
    ]
    for stil in stil_patterns:
        if f'aria-label="{stil}"' in html:
            result["stil"] = stil
            break

    # Lukt, Smak, Farge, Metode, Land/distrikt, Produsent, Årgang, Utvalg
    for felt in ["Lukt", "Smak", "Farge", "Metode", "Land, distrikt", "Produsent", "Årgang", "Utvalg"]:
        m = re.search(
            rf'<span>{felt}</span><span[^>]*>([^<]+)',
            html,
        )
        if m:
            result[felt.lower().split(",")[0].strip()] = m.group(1).strip()

    # Alkohol, sukker, syre
    m = re.search(r'<strong>Alkohol</strong>\s*<span[^>]*>([^<]+)', html)
    if m:
        result["alkohol"] = m.group(1).strip()
    m = re.search(r'<strong>Sukker</strong>\s*<span[^>]*>([^<]+)', html)
    if m:
        result["sukker"] = m.group(1).strip()
    m = re.search(r'<strong>Syre</strong>\s*<span[^>]*>([^<]+)', html)
    if m:
        result["syre"] = m.group(1).strip()

    return result


def get_product_details(product_url: str, use_cache: bool = True) -> dict:
    """
    Hent klokker, lukt, smak, drueblanding fra repo-snapshotet (details/<code>.json).

    product_url slutter på `/p/<code>` (relativ eller absolutt). Koden utledes og
    brukes som oppslagsnøkkel mot polet_store.read_details.

    `use_cache` beholdes for bakoverkompat (no-op). Miss (ikke i snapshot, eller
    URL uten utledbar kode) → `PoletRefreshRequired`.
    """
    m = re.search(r"/p/(\d+)", product_url)
    if not m:
        raise PoletRefreshRequired(
            f"Klarte ikke å utlede varenr fra URL '{product_url}'",
            url=product_url,
            hint=(
                "URL mangler /p/<varenr> — refresh produktet fra desktop "
                "(se docs/polet_refresh.md)"
            ),
        )
    code = m.group(1)

    details = polet_store.read_details(code)
    if details is None:
        raise PoletRefreshRequired(
            f"Produktdetaljer for varenr {code} finnes ikke i snapshotet",
            url=product_url,
            hint=(
                "Produktsiden er ikke i repo-snapshotet — refresh den fra "
                "desktop (se docs/polet_refresh.md)"
            ),
        )
    return details


# ─── KLOKKE-PROFIL SIMILARITY ────────────────────────────────────────

CLOCK_DIMS = ("Fylde", "Friskhet", "Garvestoffer")

# Forbeholdet som skal følge ethvert similarity-resultat (ADR-025). Klokkene
# ble målt 2026-08-30 mot brukerens egne ratinger: korrelasjon +0,16 / +0,09 /
# −0,10, og alle seks gruppene med identiske klokker spenner over hele
# ratingskalaen (8/8/8 rommer både 4.1 og 2.0). Å koble på 10 986 katalograder
# gjør funksjonen mer komplett, ikke klokere.
CLOCK_SIMILARITY_CAVEAT = (
    "Klokke-similarity er et GROVFILTER for stil-slektskap, ikke en kvalitets- "
    "eller preferansemodell (ADR-025): klokkene korrelerer ~0 med brukerens "
    "egne ratinger (+0,16 Fylde / +0,09 Friskhet / −0,10 Garvestoffer), og "
    "identiske klokker spenner over hele ratingskalaen. Les treffene som "
    "«smaker i samme retning» — aldri som «noe like godt» eller «noe "
    "kraftigere». Rangering innenfor et treff må skje på appellasjonsnivå, "
    "fat/metode, literpris, årgang og drue."
)


class MissingClockDimension(ValueError):
    """
    En klokke-profil mangler en akse `clock_distance` ble bedt om å regne på.

    Egen type fordi kallere skal kunne skille «denne vinen har ikke tannin-tall»
    fra en programmeringsfeil — og fordi den erstatter en stille degradering:
    fram til 2026-08-30 hoppet `clock_distance` over manglende dimensjoner og
    returnerte en finit, plausibel avstand regnet på 2 av 3 akser.
    """


def clock_distance(
    a: dict,
    b: dict,
    dims: Iterable[str] = CLOCK_DIMS,
    *,
    tolerance: float = 0.0,
) -> float:
    """
    Euklidsk avstand (RMS over aksene) mellom to klokke-profiler.

    a og b er dicts på detalj-navnerommet, som fra `get_product_details()
    ["klokker"]`: `{"Fylde": 8, "Friskhet": 9, "Garvestoffer": 7}`. Bøtte-verdier
    fra en katalograd må oversettes først —
    `polet_facets.clocks_from_buckets(row["clock_buckets"])`.

    `tolerance` er måleusikkerheten på ÉN akse: avstanden på aksen regnes som
    `max(0, |a−b| − tolerance)`. Default 0 gir vanlig euklidsk avstand. Bruk
    `0.5` når den ene profilen er bøtte-utledet, altså kjent som et lukket
    2-intervall og ikke som et tall: da er en målprofil hvor som helst inne i
    bøtta avstand 0, som er det bøtta faktisk sier. Uten dette rangeres de
    10 986 bøtte-vinene systematisk under de 1 668 med eksakte klokker — et
    midtpunkt på 7,5 kan aldri treffe en target på 8 — og hele klokke-sveipen
    fra ADR-024 ville vært påkoblet i navnet, men ikke i rangeringen.

    **Mangler en av `dims` i én av profilene → `MissingClockDimension`.** Den
    forrige versjonen hoppet stille over dimensjonen og regnet videre på
    resten. Det er farlig nettopp fordi svaret ser riktig ut: mater du inn en
    katalograds `clock_buckets` uten oversettelse, heter garvestoff-aksen
    `Tannin` og ikke `Garvestoffer`, og du får en finit avstand som i praksis
    bare måler fylde og friskhet. Samme klokke har tre navn i dette systemet —
    se navnerom-tabellen i `tools/polet_facets.py`.
    """
    dims = tuple(dims)
    if not dims:
        raise ValueError("dims er tom — ingen akser å regne avstand på")
    if tolerance < 0:
        raise ValueError(f"tolerance må være >= 0, fikk {tolerance}")

    diffs = []
    for d in dims:
        for profile, label in ((a, "a"), (b, "b")):
            if d not in profile:
                raise MissingClockDimension(
                    f"Klokke-profil {label} mangler dimensjonen {d!r} "
                    f"(har {sorted(profile)}). Avstanden ville blitt regnet på "
                    f"{len(dims) - 1} av {len(dims)} akser uten at noe sa fra. "
                    "Er dette en katalograds clock_buckets? Da heter "
                    "garvestoffene 'Tannin' og må oversettes med "
                    "polet_facets.clocks_from_buckets() først."
                )
        for profile, label in ((a, "a"), (b, "b")):
            if not isinstance(profile[d], (int, float)) or isinstance(profile[d], bool):
                raise ValueError(
                    f"Klokke-profil {label} har ikke-numerisk verdi for {d!r}: "
                    f"{profile[d]!r}. Ser det ut som en bøtte-kode («7-8»)? Da er "
                    "dette en katalograds clock_buckets — kjør den gjennom "
                    "polet_facets.clocks_from_buckets() først, som både "
                    "oversetter navnene og gjør bøttene om til tall."
                )
        diffs.append(max(0.0, abs(a[d] - b[d]) - tolerance) ** 2)
    return math.sqrt(sum(diffs) / len(diffs))


# Halve bøtte-bredden. Polets klokke-bøtter er lukkede 2-intervaller ("7-8"), så
# en bøtte-verdi er kjent til ±0,5 rundt midtpunktet sitt.
BUCKET_TOLERANCE = 0.5


class ClockMatches(list):
    """
    Resultatet fra `find_similar_by_clocks` — en helt vanlig liste med treff,
    som i tillegg bærer HVOR MANGE kandidater den så på og hvor klokkene kom fra.

    Liste-subklasse med vilje: `len()`, indeksering og iterasjon oppfører seg
    som før, så alle eksisterende kallsteder er urørt, samtidig som dekningen
    er inspiserbar. Motivasjonen er konkret — 2026-08-30 rangerte funksjonen 13
    viner av 753 relevante og sa ikke fra om det. Et resultat som ikke kan
    fortelle hvor stort felt det er valgt fra, ser like overbevisende ut enten
    det har sett 1,7 % eller 100 % av katalogen.
    """

    def __init__(self, treff, *, target_clocks: dict, dims: tuple, stats: dict):
        super().__init__(treff)
        self.target_clocks = dict(target_clocks)
        self.dims = tuple(dims)
        self.stats = dict(stats)

    @property
    def dekning(self) -> Optional[float]:
        """Andel av kandidatene som faktisk hadde brukbare klokker. None ved 0."""
        n = self.stats.get("kandidater", 0)
        return self.stats["med_klokker"] / n if n else None

    def summary(self) -> str:
        """Én tekstblokk å vise sammen med treffene — forbehold FØR tall."""
        s = self.stats
        dekning = f"{self.dekning:.1%}" if self.dekning is not None else "–"
        return (
            f"{CLOCK_SIMILARITY_CAVEAT}\n"
            f"Dekning: {s['med_klokker']} av {s['kandidater']} kandidater hadde "
            f"klokker ({dekning}) — {s['fra_details']} eksakte fra details, "
            f"{s['fra_clock_buckets']} fra katalogens bøtter (±1). "
            f"{s['uten_klokker']} manglet klokkedata helt, "
            f"{s['ufullstendige_klokker']} manglet en akse. "
            f"{len(self)} rangert."
            + (
                f"\nMerk: {s['i_toppsjiktet']} viner ligger like nær målprofilen "
                f"som den nærmeste — de {len(self)} du ser er et vilkårlig utvalg "
                "av dem, ikke en rangering. Skill dem på appellasjon, metode, "
                "literpris, årgang og drue."
                if s.get("i_toppsjiktet", 0) > len(self)
                else ""
            )
        )


def find_similar_by_clocks(
    target_clocks: dict,
    queries: Iterable[str],
    *,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    category: Optional[str] = None,
    country: Optional[str] = None,
    page_size: Optional[int] = None,
    top_k: int = 10,
    dims: Iterable[str] = CLOCK_DIMS,
) -> ClockMatches:
    """
    Finn viner på Polet som ligger nærmest `target_clocks` i STIL.

    > Dette er et grovfilter for stil-slektskap, ikke en kvalitets- eller
    > preferansemodell — se `CLOCK_SIMILARITY_CAVEAT` og ADR-025. Resultatet
    > bærer forbeholdet selv, via `.summary()`.

    target_clocks: `{"Fylde": 8, "Friskhet": 9, "Garvestoffer": 7}` — detalj-
    navnerommet. Mangler en av `dims` → `MissingClockDimension` med én gang,
    i stedet for at hver eneste kandidat blir hoppet over og svaret blir tomt.

    queries: søke-strenger (f.eks. `["Barbera d'Alba", "Dolcetto"]`). Hvert søk
    ser navn + distrikt + underdistrikt, og filtrene under påføres FØR
    avkorting. `page_size=None` (default) betyr ingen avkorting per søk —
    similarity skal se hele feltet, ikke de N første varenumrene.

    **Klokkekilder, i prioritert rekkefølge:**
      1. `details/<code>.json` — eksakte heltall, finnes for ~1 668 viner.
      2. Katalogradens `clock_buckets` — bøtte-oppløsning (±1), finnes for
         10 986 rødviner etter fasett-sveipen i ADR-024. Oversettes gjennom
         `polet_facets.clocks_from_buckets` (`Tannin` → `Garvestoffer`).

    Fram til 2026-08-30 fantes bare vei 1, så hele klokke-sveipen fra ADR-024
    var koblet fra: et typisk søk rangerte 13 viner av 701 mulige.

    Returnerer en `ClockMatches` (liste) med opptil `top_k` dicts:
      - `product`   — katalograden
      - `details`   — detalj-oppslaget, eller None når klokkene kom fra bøttene
      - `clocks`    — profilen avstanden faktisk ble regnet på
      - `clock_source` — `"details"` | `"clock_buckets"`
      - `presisjon` — `"eksakt"` | `"±1 (bøtte)"`
      - `distance`  — RMS over `dims`, med ±0,5 toleranse for bøtte-utledede
        klokker (se `clock_distance`). 0 betyr «innenfor samme bøtte», ikke
        «identisk».
      - `midtpunkt_avstand` — samme uten toleranse; brukes som sekundærnøkkel
    Sortert stigende på `(distance, midtpunkt_avstand)`. Dekningstallene ligger
    på `.stats`, og `.summary()` sier fra når toppsjiktet er større enn
    `top_k` — da er utvalget vilkårlig og må skilles på noe annet enn klokker.
    """
    dims = tuple(dims)
    mangler = [d for d in dims if d not in target_clocks]
    if mangler:
        raise MissingClockDimension(
            f"target_clocks mangler {mangler} (har {sorted(target_clocks)}). "
            "Uten dem ville hver eneste kandidat blitt hoppet over og svaret "
            "blitt tomt eller vilkårlig. Kommer profilen fra en katalograds "
            "clock_buckets? Kjør den gjennom "
            "polet_facets.clocks_from_buckets() først."
        )

    seen: set[str] = set()
    candidates: list[dict] = []
    stats = {
        "kandidater": 0,
        "med_klokker": 0,
        "uten_klokker": 0,
        "ufullstendige_klokker": 0,
        "fra_details": 0,
        "fra_clock_buckets": 0,
        "sokestrenger_uten_treff": 0,
    }

    for q in queries:
        try:
            results = search(
                q,
                page_size=page_size,
                max_price=max_price,
                min_price=min_price,
                category=category,
                country=country,
            )
        except PoletRefreshRequired:
            # Søkestrengen ga ingen snapshot-treff — hopp over, fortsett med
            # resten, men tell det: fem stumme søkestrenger er en annen
            # historie enn fem som traff.
            stats["sokestrenger_uten_treff"] += 1
            continue

        for p in results:
            code = p.get("code")
            if not code or code in seen:
                continue
            seen.add(code)
            stats["kandidater"] += 1

            clocks, source, details = _candidate_clocks(p)
            if not clocks:
                stats["uten_klokker"] += 1
                continue

            tol = 0.0 if source == "details" else BUCKET_TOLERANCE
            try:
                d = clock_distance(target_clocks, clocks, dims=dims, tolerance=tol)
                midt = clock_distance(target_clocks, clocks, dims=dims)
            except MissingClockDimension:
                # Vinen har klokker, men ikke alle aksene vi rangerer på.
                # Å regne på resten ville gitt en avstand som ikke er
                # sammenlignbar med de andre kandidatenes.
                stats["ufullstendige_klokker"] += 1
                continue

            stats["med_klokker"] += 1
            stats["fra_details" if source == "details" else "fra_clock_buckets"] += 1
            candidates.append(
                {
                    "product": p,
                    "details": details,
                    "clocks": clocks,
                    "clock_source": source,
                    "presisjon": "eksakt" if source == "details" else "±1 (bøtte)",
                    "distance": d,
                    "midtpunkt_avstand": midt,
                }
            )

    # Primærnøkkel er den usikkerhetsbevisste avstanden, så en bøtte-vin hvor
    # målprofilen ligger inne i bøtta konkurrerer på like fot med en eksakt
    # treffer. Sekundærnøkkel er midtpunkt-avstanden: den bryter opp de mange
    # 0-ene deterministisk, og gir de vinene vi FAKTISK har målt forrang foran
    # dem vi bare vet ligger i riktig bøtte.
    candidates.sort(key=lambda c: (c["distance"], c["midtpunkt_avstand"]))

    # Hvor mange ligger like nær som den nærmeste? Med bøtte-oppløsning er
    # svaret ofte «flere hundre», og da er `top_k` et vilkårlig utvalg av et
    # stort likt felt — ikke en rangering. Det skal stå i klartekst, ellers har
    # vi byttet den stille avkortingen i B2/B3 mot en ny.
    stats["i_toppsjiktet"] = (
        sum(1 for c in candidates if c["distance"] == candidates[0]["distance"])
        if candidates
        else 0
    )
    return ClockMatches(
        candidates[:top_k], target_clocks=target_clocks, dims=dims, stats=stats
    )


def _candidate_clocks(product: dict) -> tuple[dict, Optional[str], Optional[dict]]:
    """
    Klokke-profilen for én katalograd: `(klokker, kilde, details)`.

    Eksakte klokker fra `details/` foretrekkes; ellers oversettes radens
    `clock_buckets` til detalj-navnerommet med midtpunkt-verdier.
    `({}, None, None)` når vinen ikke har klokker i det hele tatt (~2 750
    rødviner har dem ikke hos Polet — ADR-024).
    """
    url = product.get("url")
    if url:
        try:
            details = get_product_details(url)
        except (PoletRefreshRequired, requests.RequestException):
            details = None
        if details:
            clocks = details.get("klokker") or {}
            if clocks:
                return dict(clocks), "details", details

    buckets = product.get("clock_buckets")
    if buckets:
        return polet_facets.clocks_from_buckets(buckets), "clock_buckets", None
    return {}, None, None


def _format_clock_value(v) -> str:
    """`8` → `8`, `7.5` → `7,5` (bøtte-midtpunkt). Ingen `.0`-haler."""
    if isinstance(v, float) and not v.is_integer():
        return f"{v:.1f}".replace(".", ",")
    return str(int(v)) if isinstance(v, (int, float)) else str(v)


def format_for_recommendation(product: dict, details: Optional[dict] = None) -> str:
    """
    Format ett produkt som menneskelig anbefaling-tekst.

    Uten `details` faller klokkene tilbake på katalogradens `clock_buckets`, og
    da MERKES de `(±1, fra katalog-sveip)` — en bøtte-verdi skal aldri se ut som
    et eksakt måltall i outputen.
    """
    name = product.get("name", "?")
    code = product.get("code", "?")
    price = product.get("price", {}).get("value", "?")
    selection = product.get("product_selection", "?")

    out = f"{name} – {price} kr | Varenummer {code} [{selection}]"

    if details:
        if "klokker" in details:
            k = details["klokker"]
            klokke_str = ", ".join(
                f"{n} {_format_clock_value(v)}/12" for n, v in k.items()
            )
            out += f"\n  Klokker: {klokke_str}"
        if "stil" in details:
            out += f"\n  Stil: {details['stil']}"
        if "druer" in details:
            out += f"\n  Druer: {details['druer']}"
    elif product.get("clock_buckets"):
        k = polet_facets.clocks_from_buckets(product["clock_buckets"])
        klokke_str = ", ".join(f"{n} {_format_clock_value(v)}/12" for n, v in k.items())
        out += f"\n  Klokker: {klokke_str}  (±1, fra katalog-sveip)"

    return out


# ─── EKSEMPLER ───────────────────────────────────────────────────────

if __name__ == "__main__":
    # Eksempel 1: Finn Barbera under 250 kr.
    # Merk at filtrene går INN i search — ikke på resultatet etterpå. Gjør du
    # det motsatte, filtrerer du de 20 første varenumrene, ikke de 20 beste
    # treffene under 250 kr.
    print("=" * 60)
    print("Barbera under 250 kr, kun rødvin")
    print("=" * 60)
    relevant = search("Barbera d'Alba", page_size=None, max_price=250, category="Rødvin")
    print(f"{len(relevant)} treff i snapshotet. De tre første:")
    for p in relevant[:3]:
        print(format_for_recommendation(p))

    # Eksempel 2: Hent klokker for én spesifikk vin
    print()
    print("=" * 60)
    print("Klokke-profil: Fenocchio Barbera d'Alba Superiore")
    print("=" * 60)
    # Søkestrengen må være en delstreng av katalognavnet: vinen heter
    # "Fenocchio Barbera d'Alba Superiore 2023" (varenr 759901), så
    # "Fenocchio Barbera Superiore" ga null treff — og PoletRefreshRequired
    # ba da om en refresh der problemet var søkestrengen (jf. teknisk gjeld #11).
    results = search("Fenocchio Barbera", page_size=3)
    if results:
        p = results[0]
        details = get_product_details(p["url"])
        print(format_for_recommendation(p, details))
        print(f"  Lukt: {details.get('lukt', '?')}")
        print(f"  Smak: {details.get('smak', '?')}")

        # Eksempel 3: stil-slektninger på klokke-profil. Les summary() først —
        # den sier hvor stort felt treffene er valgt fra, og hva de IKKE betyr.
        print()
        print("=" * 60)
        print("Stil-slektninger (grovfilter, ADR-025)")
        print("=" * 60)
        hits = find_similar_by_clocks(
            details["klokker"],
            ["Barbera", "Nebbiolo", "Barbaresco", "Valpolicella Ripasso", "Chianti Classico"],
            max_price=500,
            category="Rødvin",
            top_k=5,
        )
        print(hits.summary())
        print()
        for h in hits:
            print(format_for_recommendation(h["product"], h["details"]))
            print(f"  Avstand: {h['distance']:.2f} ({h['presisjon']})")
