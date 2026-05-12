"""
Vinmonopolet helpers – vmpws (webshop) API

Bruk dette scriptet i prosjektet for å:
- Søke etter viner
- Hente klokker, lukt, smak, drueblanding fra produktsider
- Sammenligne mot brukerens preferanser

Krever ingen API-nøkkel. Vær konservativ med antall kall (~30/sesjon).
"""

import requests
import re
from typing import Optional

BASE = "https://www.vinmonopolet.no"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def search(query: str, page_size: int = 10) -> list[dict]:
    """
    Søk etter produkter på Vinmonopolet.

    Returnerer liste med dicts som inneholder:
    - code (varenummer), name, price.value
    - alcohol.value, volume.value
    - main_category, main_country, district, sub_District
    - product_selection, productAvailability
    - url (relativ sti til produktsiden)
    """
    url = f"{BASE}/vmpws/v2/vmp/products/search"
    r = requests.get(
        url,
        params={"q": query, "pageSize": page_size},
        headers=HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("products", [])


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


def get_product_details(product_url: str) -> dict:
    """
    Hent klokker, lukt, smak, drueblanding fra produktsiden.

    product_url skal være relativ sti (fra search-resultat).
    """
    if not product_url.startswith("http"):
        product_url = BASE + product_url
    r = requests.get(product_url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    r.encoding = "utf-8"
    html = r.text

    result = {}

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
    # Mønster: aria-label="Frisk og fruktig"><div class="icon...
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

    # Lukt, Smak, Farge, Metode
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
