"""
Live Vinmonopolet-oppslag (butikk-spesifikt) — URL-byggere + JSON-parsere.

Bakgrunn: repo-snapshotet (`data/polet/`) er vin-only og har BEVISST ikke
butikk-lager (ADR-020) — lager er ferskvare (5 stk i kveld kan være 0 i morgen).
For øl (som ikke er i snapshotet i det hele tatt), og for ethvert
«har butikk X varen på lager?»-spørsmål, må dataen hentes LIVE.

`requests`/`curl` mot `vmpws` gir 403 (WAF gjenkjenner ikke-nettleser-TLS). Den
fungerende veien er `fetch()` fra en ekte browser-fane via Playwright-MCP
`browser_evaluate` (se `docs/polet_refresh.md`). Denne modulen holder den
TESTBARE delen — URL-konstruksjon + respons-normalisering — ren og gjenbrukbar;
selve nettverks-hoppet skjer i browseren:

    browser_navigate("https://www.vinmonopolet.no/")           # sett WAF-cookies
    stores = browser_evaluate(f"() => fetch('{stores_url()}').then(r => r.json())")
    store  = find_store(stores, "Røa")                          # → {'id': '335', ...}
    url    = product_search_url("geuze", store_id=store["id"])
    hits   = browser_evaluate(f"() => fetch('{url}').then(r => r.json())")
    parse_products(hits)   # → kompakte dicts med `stock` per navngitt butikk

VIKTIG (tasks/lessons.md 2026-07-04): butikk-lager er live og volatilt. Nevner
brukeren et spesifikt pol, er lager en HARD forutsetning — aldri anbefal en vare
for et navngitt pol uten bekreftet `stock` der.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import quote

BASE = "https://www.vinmonopolet.no"


def stores_url(page_size: int = 500) -> str:
    """URL for hele butikklista. Filtrer klient-side med `find_store` — `q`-param
    på dette endepunktet filtrerer ikke pålitelig (verifisert 2026-07-04)."""
    return f"{BASE}/vmpws/v2/vmp/stores?fields=FULL&pageSize={page_size}"


def _stores(stores_json: dict | list) -> list[dict]:
    if isinstance(stores_json, list):
        return stores_json
    return stores_json.get("stores") or stores_json.get("data") or []


def find_store(stores_json: dict | list, name: str) -> Optional[dict]:
    """Finn butikk på navn/adresse (case-insensitiv delstreng) i stores-payloaden.

    Returnerer {'name', 'id', 'address'} for første treff, ellers None. `id` er
    Polets `name`-felt (butikknummeret, f.eks. Røa = '335')."""
    needle = name.casefold()
    for s in _stores(stores_json):
        display = str(s.get("displayName") or s.get("name") or "")
        address = str((s.get("address") or {}).get("formattedAddress") or "")
        if needle in display.casefold() or needle in address.casefold():
            return {
                "name": display,
                "id": str(s.get("name") or s.get("storeNumber") or s.get("id") or ""),
                "address": address,
            }
    return None


def product_search_url(
    term: str,
    *,
    category: Optional[str] = "øl",
    store_id: Optional[str] = None,
    page_size: int = 30,
) -> str:
    """Bygg vmpws-søke-URL. `category`/`store_id` legges på som fasetter — begge
    matcher på .code (lowercase). Gi `store_id` for å filtrere til varer som er
    kjøpbare i akkurat den butikken (facet `availableInStores`)."""
    q = term
    if category:
        q += f":relevance:mainCategory:{category}"
    if store_id:
        q += f":availableInStores:{store_id}"
    return f"{BASE}/vmpws/v2/vmp/products/search?fields=FULL&pageSize={page_size}&query={quote(q, safe='')}"


def store_stock(product: dict) -> Optional[str]:
    """Les butikk-lager-teksten (f.eks. '5 i butikken') fra et produkt hentet MED
    `availableInStores`-fasett. None hvis feltet mangler."""
    infos = (
        (product.get("productAvailability") or {})
        .get("storesAvailability", {})
        .get("infos")
    )
    if not infos:
        return None
    return "; ".join(i.get("availability", "") for i in infos if i.get("availability"))


def parse_products(search_json: dict) -> list[dict]:
    """Normaliser en products/search-payload til kompakte dicts:
    code, name, style, abv, volume, price, stock (butikk-lager om filtrert på butikk)."""
    out: list[dict] = []
    for p in search_json.get("products", []):
        out.append(
            {
                "code": p.get("code"),
                "name": p.get("name"),
                "style": (p.get("mainSubCategory") or {}).get("name")
                or (p.get("mainCategory") or {}).get("name"),
                "abv": (p.get("alcohol") or {}).get("formattedValue"),
                "volume": (p.get("volume") or {}).get("formattedValue"),
                "price": (p.get("price") or {}).get("formattedValue"),
                "stock": store_stock(p),
            }
        )
    return out


if __name__ == "__main__":
    # Smoke: vis URL-ene et live-oppslag ville brukt (ingen nettverk her).
    print("stores:", stores_url())
    print("beer@Røa:", product_search_url("geuze", store_id="335"))
    print("all beer:", product_search_url("surøl"))
