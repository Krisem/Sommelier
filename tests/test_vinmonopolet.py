"""Vinmonopolet-helper kontrakt-test.

Krever live HTTP (Polet) — markert `network`.
"""

from __future__ import annotations

import pytest


@pytest.mark.network
def test_search_barbera_returns_products_with_required_fields():
    from tools.vinmonopolet import search

    results = search("Barbera")
    assert isinstance(results, list), "search() skal returnere liste"
    assert len(results) >= 1, "Forventet minst 1 treff på 'Barbera'"

    p = results[0]
    assert "name" in p and p["name"], "produkt mangler 'name'"
    assert "code" in p and p["code"], "produkt mangler 'code' (varenummer)"
    assert "price" in p, "produkt mangler 'price'-dict"
    assert isinstance(p["price"], dict), "price skal være dict"
    assert "value" in p["price"], "price.value mangler"
    assert isinstance(p["price"]["value"], (int, float)), (
        f"price.value skal være tall: {type(p['price']['value'])}"
    )
    assert p["price"]["value"] > 0, "price.value skal være positiv"
