"""Vinmonopolet-helper kontrakt-test.

Tester den nye snapshot-veien: search/search_with_facets/get_product_details
leser repo-snapshotet via tools.polet_store (ingen nettverk). polet_store pekes
mot en liten fixture-katalog i tmp via monkeypatch. Cache-miss → PoletRefreshRequired.
"""

from __future__ import annotations

import json

import pytest


# ─── FIXTURE: liten snapshot-katalog i tmp ───────────────────────────

_CATALOG = [
    {
        "code": "10267301",
        "name": "Contra Soarda Breganze Vespaiolo 2023",
        "price": {"value": 299.9, "formattedValue": "Kr 299,90"},
        "main_category": {"code": "hvitvin", "name": "Hvitvin"},
        "main_country": {"code": "italia", "name": "Italia"},
        "url": "/Land/Italia/Veneto/Breganze/Contra-Soarda-Breganze-Vespaiolo-2023/p/10267301",
    },
    {
        "code": "11156601",
        "name": "Thibault Liger-Belair Bourgogne Rouge Les Grands Chaillots",
        "price": {"value": 495.5, "formattedValue": "Kr 495,50"},
        "main_category": {"code": "rødvin", "name": "Rødvin"},
        "main_country": {"code": "frankrike", "name": "Frankrike"},
        "url": "/Land/Frankrike/Burgund/Bourgogne/Thibault-Liger-Belair/p/11156601",
    },
    {
        "code": "15012201",
        "name": "Tornatore Etna Rosso 2022",
        "price": {"value": 289.0, "formattedValue": "Kr 289,00"},
        "main_category": {"code": "rødvin", "name": "Rødvin"},
        "main_country": {"code": "italia", "name": "Italia"},
        "url": "/Land/Italia/Sicilia/Etna/Tornatore-Etna-Rosso-2022/p/15012201",
    },
]

_DETAILS_15012201 = {
    "code": "15012201",
    "url": "https://www.vinmonopolet.no/Land/Italia/Sicilia/Etna/Tornatore-Etna-Rosso-2022/p/15012201",
    "klokker": {"Fylde": 6, "Friskhet": 8, "Garvestoffer": 6},
    "stil": "Frisk og fruktig",
    "druer": "Nerello Mascalese 95 prosent",
    "fetched_at": "2026-05-12T19:47:09.555981+00:00",
}


@pytest.fixture
def snapshot(monkeypatch, tmp_path):
    """Peker polet_store mot en tmp-katalog fylt med fixture-data."""
    from tools import polet_store

    polet_dir = tmp_path / "polet"
    details_dir = polet_dir / "details"
    details_dir.mkdir(parents=True)

    catalog = polet_dir / "catalog.ndjson"
    catalog.write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in _CATALOG) + "\n",
        encoding="utf-8",
    )
    (details_dir / "15012201.json").write_text(
        json.dumps(_DETAILS_15012201, ensure_ascii=False), encoding="utf-8"
    )

    monkeypatch.setattr(polet_store, "POLET_DIR", polet_dir)
    monkeypatch.setattr(polet_store, "CATALOG", catalog)
    monkeypatch.setattr(polet_store, "DETAILS_DIR", details_dir)
    monkeypatch.setattr(polet_store, "META", polet_dir / "catalog_meta.json")
    return polet_store


# ─── search ──────────────────────────────────────────────────────────

def test_search_returns_products_with_required_fields(snapshot):
    from tools.vinmonopolet import search

    results = search("Tornatore")
    assert isinstance(results, list)
    assert len(results) >= 1

    p = results[0]
    assert p["name"], "produkt mangler 'name'"
    assert p["code"], "produkt mangler 'code' (varenummer)"
    assert isinstance(p["price"], dict)
    assert isinstance(p["price"]["value"], (int, float))
    assert p["price"]["value"] > 0


def test_search_respects_page_size(snapshot):
    from tools.vinmonopolet import search

    # Tom name_contains matcher alle 3 produktene
    results = search("", page_size=2)
    assert len(results) == 2


def test_search_miss_raises_refresh_required(snapshot):
    from tools.vinmonopolet import search
    from tools.polet_store import PoletRefreshRequired

    with pytest.raises(PoletRefreshRequired) as exc:
        search("FinnesIkkeISnapshot")
    assert exc.value.url is not None


# ─── search_with_facets ──────────────────────────────────────────────

def test_search_with_facets_maps_category_and_country(snapshot):
    from tools.vinmonopolet import search_with_facets

    results = search_with_facets({"mainCategory": "rødvin", "mainCountry": "italia"})
    assert len(results) == 1
    assert results[0]["code"] == "15012201"


def test_search_with_facets_matches_by_name_too(snapshot):
    from tools.vinmonopolet import search_with_facets

    # 'Rødvin' (name) skal matche like godt som 'rødvin' (code)
    results = search_with_facets({"mainCategory": "Rødvin"})
    codes = {p["code"] for p in results}
    assert codes == {"11156601", "15012201"}


def test_search_with_facets_miss_raises_refresh_required(snapshot):
    from tools.vinmonopolet import search_with_facets
    from tools.polet_store import PoletRefreshRequired

    with pytest.raises(PoletRefreshRequired):
        search_with_facets({"mainCategory": "rødvin", "mainCountry": "spania"})


# ─── get_product_details ─────────────────────────────────────────────

def test_get_product_details_derives_code_from_relative_url(snapshot):
    from tools.vinmonopolet import get_product_details

    details = get_product_details(
        "/Land/Italia/Sicilia/Etna/Tornatore-Etna-Rosso-2022/p/15012201"
    )
    assert details["klokker"] == {"Fylde": 6, "Friskhet": 8, "Garvestoffer": 6}
    assert details["stil"] == "Frisk og fruktig"


def test_get_product_details_derives_code_from_absolute_url(snapshot):
    from tools.vinmonopolet import get_product_details

    details = get_product_details(
        "https://www.vinmonopolet.no/Land/X/Y/Z/Foo/p/15012201"
    )
    assert details["code"] == "15012201"


def test_get_product_details_miss_raises_refresh_required(snapshot):
    from tools.vinmonopolet import get_product_details
    from tools.polet_store import PoletRefreshRequired

    with pytest.raises(PoletRefreshRequired) as exc:
        get_product_details("/Land/X/Y/Z/Ukjent/p/99999999")
    assert exc.value.url == "/Land/X/Y/Z/Ukjent/p/99999999"


def test_get_product_details_unparseable_url_raises_refresh_required(snapshot):
    from tools.vinmonopolet import get_product_details
    from tools.polet_store import PoletRefreshRequired

    with pytest.raises(PoletRefreshRequired):
        get_product_details("/noe/uten/produktkode")
