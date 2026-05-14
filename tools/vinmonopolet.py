"""
Vinmonopolet helpers – vmpws (webshop) API

Bruk dette scriptet i prosjektet for å:
- Søke etter viner
- Hente klokker, lukt, smak, drueblanding fra produktsider
- Sammenligne mot brukerens preferanser
- Finne nærmeste vin på klokke-profil (find_similar_by_clocks)

Krever ingen API-nøkkel. Diskcache i ~/.cache/sommelier/ unngår rate-limit.
"""

import hashlib
import json
import math
import re
import time
from pathlib import Path
from typing import Iterable, Optional

import requests

BASE = "https://www.vinmonopolet.no"
HEADERS = {"User-Agent": "Mozilla/5.0"}

CACHE_DIR = Path.home() / ".cache" / "sommelier"
SEARCH_TTL = 60 * 60 * 24            # 24 t for søk
DETAILS_TTL = 60 * 60 * 24 * 7       # 7 dager for produktdetaljer (mer stabilt)


def _cache_path(namespace: str, key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{namespace}_{h}.json"


def _cache_get(namespace: str, key: str, ttl: int):
    p = _cache_path(namespace, key)
    if not p.exists():
        return None
    if (time.time() - p.stat().st_mtime) > ttl:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _cache_set(namespace: str, key: str, value) -> None:
    p = _cache_path(namespace, key)
    try:
        p.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def search(query: str, page_size: int = 10, use_cache: bool = True) -> list[dict]:
    """
    Søk etter produkter på Vinmonopolet.

    Returnerer liste med dicts som inneholder:
    - code (varenummer), name, price.value
    - alcohol.value, volume.value
    - main_category, main_country, district, sub_District
    - product_selection, productAvailability
    - url (relativ sti til produktsiden)

    Resultat caches i ~/.cache/sommelier/ i 24 timer. Sett use_cache=False
    for å force ferskt kall.
    """
    cache_key = f"q={query}|n={page_size}"
    if use_cache:
        cached = _cache_get("search", cache_key, SEARCH_TTL)
        if cached is not None:
            return cached

    url = f"{BASE}/vmpws/v2/vmp/products/search"
    r = requests.get(
        url,
        params={"q": query, "pageSize": page_size},
        headers=HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    products = r.json().get("products", [])
    _cache_set("search", cache_key, products)
    return products


def search_with_facets(
    facets: dict,
    page_size: int = 50,
    use_cache: bool = True,
) -> list[dict]:
    """
    Søk Vinmonopolet med Hybris-style fasett-filter (én strukturert spørring).

    Eksempel:
        peers = search_with_facets(
            {"mainCategory": "rødvin", "mainCountry": "italia"},
            page_size=50,
        )

    Argumenter:
        facets: dict med fasett-koder → kode-verdi. Verdier må være `.code`-feltet
                fra Polets fasett-vokabular (lowercase, underscore for mellomrom):
                  - mainCategory: 'rødvin' | 'hvitvin' | 'musserende_vin' | 'rosévin' | ...
                  - mainCountry:  'italia' | 'frankrike' | 'spania' | ...
                  - district:     'italia_sicilia' | 'frankrike_champagne' | ...
                Bruk `.code`-feltet direkte fra et tidligere search()-treff.
        page_size: maks antall produkter (Polets API gir typisk opptil ~100)
        use_cache: bruk 24t diskcache (namespace "search_facets")

    Returnerer samme produkt-struktur som search().
    """
    # Bygg deterministisk query-streng for både cache-key og API
    parts = [f"{k}:{v}" for k, v in sorted(facets.items())]
    query = ":relevance:" + ":".join(parts) if parts else ":relevance"

    cache_key = f"facets={query}|n={page_size}"
    if use_cache:
        cached = _cache_get("search_facets", cache_key, SEARCH_TTL)
        if cached is not None:
            return cached

    url = f"{BASE}/vmpws/v2/vmp/products/search"
    r = requests.get(
        url,
        params={"q": query, "pageSize": page_size},
        headers=HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    products = r.json().get("products", [])
    _cache_set("search_facets", cache_key, products)
    return products


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
    m = re.search(r'aria-label="([^"]+ \d+ prosent)"', html)
    if m:
        result["druer"] = m.group(1)

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
    Hent klokker, lukt, smak, drueblanding fra produktsiden.

    product_url skal være relativ sti (fra search-resultat).
    Caches i 7 dager. Sett use_cache=False for å force ferskt kall.
    """
    if not product_url.startswith("http"):
        product_url = BASE + product_url

    if use_cache:
        cached = _cache_get("details", product_url, DETAILS_TTL)
        if cached is not None:
            return cached

    r = requests.get(product_url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    r.encoding = "utf-8"
    result = parse_product_html(r.text)

    _cache_set("details", product_url, result)
    return result


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
        results = search(q, page_size=page_size)
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
            except requests.RequestException:
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
