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
"""

import math
import re
from typing import Iterable, Optional

import requests  # beholdt: find_similar_by_clocks fanger requests.RequestException

from tools import polet_store
from tools.polet_store import PoletRefreshRequired

BASE = "https://www.vinmonopolet.no"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _search_url(query: str) -> str:
    """Bygg vmpws-søke-URL for query — kun til PoletRefreshRequired-hint."""
    return f"{BASE}/vmpws/v2/vmp/products/search?q={query}"


def search(query: str, page_size: int = 10, use_cache: bool = True) -> list[dict]:
    """
    Søk etter produkter i repo-snapshotet (fritekst mot produktnavn).

    Returnerer liste med dicts som inneholder:
    - code (varenummer), name, price.value
    - alcohol.value, volume.value
    - main_category, main_country, district, sub_District
    - product_selection, productAvailability
    - url (relativ sti til produktsiden)

    `use_cache` beholdes for bakoverkompat (no-op — snapshotet ER cachen).
    Tomt resultat → `PoletRefreshRequired` (refresh fra desktop).
    """
    products = polet_store.query(name_contains=query)
    if not products:
        raise PoletRefreshRequired(
            f"Ingen snapshot-treff på '{query}'",
            url=_search_url(query),
            hint=(
                "Søket ga ingen treff i repo-snapshotet — refresh katalogen fra "
                "desktop (se docs/polet_refresh.md)"
            ),
        )
    return products[:page_size]


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
    """Filtrer søkeresultater på pris, kategori og land."""
    out = []
    for p in results:
        price = p.get("price", {}).get("value", 9999)
        if max_price is not None and price > max_price:
            continue
        if min_price is not None and price < min_price:
            continue
        if category and p.get("main_category", {}).get("name") != category:
            continue
        if country and p.get("main_country", {}).get("name") != country:
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


def clock_distance(a: dict, b: dict, dims: Iterable[str] = CLOCK_DIMS) -> float:
    """
    Euklidsk avstand mellom to klokke-profiler.

    a og b er dicts som returnert fra get_product_details()["klokker"],
    e.g. {"Fylde": 8, "Friskhet": 9, "Garvestoffer": 7}.

    Manglende dimensjon i én av profilene = ignoreres (asymmetri tas hensyn til).
    """
    diffs = []
    for d in dims:
        if d in a and d in b:
            diffs.append((a[d] - b[d]) ** 2)
    if not diffs:
        return float("inf")
    return math.sqrt(sum(diffs) / len(diffs))


def find_similar_by_clocks(
    target_clocks: dict,
    queries: Iterable[str],
    *,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    category: Optional[str] = None,
    country: Optional[str] = None,
    page_size: int = 30,
    top_k: int = 10,
) -> list[dict]:
    """
    Finn viner på Polet med nærmest klokke-profil til target_clocks.

    target_clocks: {"Fylde": 8, "Friskhet": 9, "Garvestoffer": 7}
    queries: liste med søke-strenger (f.eks. ["Barbera d'Alba", "Dolcetto"])
    Filtre: pris/kategori/land brukes på søketreff før detaljer hentes.

    Returnerer top_k dicts med felter:
      - product (rådata fra search)
      - details (klokker, stil, etc.)
      - distance (euklidsk)
    Sortert stigende på distance.
    """
    seen: set[str] = set()
    candidates: list[dict] = []

    for q in queries:
        try:
            results = search(q, page_size=page_size)
        except PoletRefreshRequired:
            # Søkestrengen ga ingen snapshot-treff — hopp over, fortsett med resten
            continue
        filtered = filter_results(
            results,
            max_price=max_price,
            min_price=min_price,
            category=category,
            country=country,
        )
        for p in filtered:
            code = p.get("code")
            if not code or code in seen:
                continue
            seen.add(code)
            try:
                details = get_product_details(p["url"])
            except (PoletRefreshRequired, requests.RequestException):
                # Vin ikke i snapshot — hopp over, similarity over det som finnes
                continue
            clocks = details.get("klokker") or {}
            if not clocks:
                continue
            d = clock_distance(target_clocks, clocks)
            if math.isinf(d):
                continue
            candidates.append({"product": p, "details": details, "distance": d})

    candidates.sort(key=lambda c: c["distance"])
    return candidates[:top_k]


def format_for_recommendation(product: dict, details: Optional[dict] = None) -> str:
    """Format ett produkt som menneskelig anbefaling-tekst."""
    name = product.get("name", "?")
    code = product.get("code", "?")
    price = product.get("price", {}).get("value", "?")
    selection = product.get("product_selection", "?")

    out = f"{name} – {price} kr | Varenummer {code} [{selection}]"

    if details:
        if "klokker" in details:
            k = details["klokker"]
            klokke_str = ", ".join(f"{n} {v}/12" for n, v in k.items())
            out += f"\n  Klokker: {klokke_str}"
        if "stil" in details:
            out += f"\n  Stil: {details['stil']}"
        if "druer" in details:
            out += f"\n  Druer: {details['druer']}"

    return out


# ─── EKSEMPLER ───────────────────────────────────────────────────────

if __name__ == "__main__":
    # Eksempel 1: Finn Barbera under 250 kr
    print("=" * 60)
    print("Barbera under 250 kr, kun rødvin")
    print("=" * 60)
    results = search("Barbera d'Alba", page_size=20)
    relevant = filter_results(results, max_price=250, category="Rødvin")
    for p in relevant[:3]:
        print(format_for_recommendation(p))

    # Eksempel 2: Hent klokker for én spesifikk vin
    print()
    print("=" * 60)
    print("Klokke-profil: Fenocchio Barbera d'Alba Superiore")
    print("=" * 60)
    results = search("Fenocchio Barbera Superiore", page_size=3)
    if results:
        p = results[0]
        details = get_product_details(p["url"])
        print(format_for_recommendation(p, details))
        print(f"  Lukt: {details.get('lukt', '?')}")
        print(f"  Smak: {details.get('smak', '?')}")
