"""
Tester for tools/polet_live.py — rene URL-byggere + JSON-parsere for
butikk-spesifikke live-oppslag. Ingen nettverk; nett-hoppet skjer i browseren.
"""

from tools import polet_live


def test_product_search_url_encodes_facets_and_store():
    url = polet_live.product_search_url("geuze", store_id="335")
    # Fasettene skal være URL-encodet inn i query-param (ø → %C3%B8, : → %3A)
    assert "query=geuze%3Arelevance%3AmainCategory%3A%C3%B8l%3AavailableInStores%3A335" in url
    assert url.startswith("https://www.vinmonopolet.no/vmpws/v2/vmp/products/search")


def test_product_search_url_without_store_or_category():
    url = polet_live.product_search_url("stout", category=None)
    assert "availableInStores" not in url
    assert "mainCategory" not in url
    assert "query=stout" in url


def test_find_store_matches_on_name_case_insensitive():
    payload = {
        "stores": [
            {"displayName": "Oslo, Frogner", "name": "111", "address": {"formattedAddress": "Elisenbergveien 37"}},
            {"displayName": "Oslo, Røa", "name": "335", "address": {"formattedAddress": "Tore Hals Mejdells vei 5"}},
        ]
    }
    hit = polet_live.find_store(payload, "røa")
    assert hit == {"name": "Oslo, Røa", "id": "335", "address": "Tore Hals Mejdells vei 5"}
    assert polet_live.find_store(payload, "Bergen") is None


def test_parse_products_extracts_stock():
    payload = {
        "products": [
            {
                "code": "10945401",
                "name": "3 Fonteinen Oude Geuze",
                "mainSubCategory": {"name": "Surøl"},
                "alcohol": {"formattedValue": "6,3%"},
                "volume": {"formattedValue": "75 cl"},
                "price": {"formattedValue": "Kr 199,90"},
                "productAvailability": {
                    "storesAvailability": {"infos": [{"availability": "5 i butikken"}]}
                },
            }
        ]
    }
    rows = polet_live.parse_products(payload)
    assert rows == [
        {
            "code": "10945401",
            "name": "3 Fonteinen Oude Geuze",
            "style": "Surøl",
            "abv": "6,3%",
            "volume": "75 cl",
            "price": "Kr 199,90",
            "stock": "5 i butikken",
        }
    ]


def test_store_stock_none_when_not_store_filtered():
    assert polet_live.store_stock({"productAvailability": {"storesAvailability": {}}}) is None
    assert polet_live.store_stock({}) is None
