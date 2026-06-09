"""
Tester for tools/refresh_polet.py — refresh-plumbingen (ingest + planlegging).

Offline: monkeypatcher polet_store mot en tmp-katalog (samme mønster som
tests/test_polet_store.py / tests/test_vinmonopolet.py). Ingen nettverk.
"""

import json
from pathlib import Path

import pytest

from tools import polet_store, refresh_polet

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "vinmonopolet"
    / "fenocchio_barbera_alba_superiore.html"
)
FIXTURE_CODE = "759901"  # varenr som faktisk står i fixturen

FETCHED_AT = "2026-06-08T00:00:00+00:00"


@pytest.fixture(autouse=True)
def _tmp_store(tmp_path, monkeypatch):
    """Pek alle store-stier mot tmp_path/data/polet for hver test."""
    polet_dir = tmp_path / "data" / "polet"
    details_dir = polet_dir / "details"
    monkeypatch.setattr(polet_store, "POLET_DIR", polet_dir)
    monkeypatch.setattr(polet_store, "CATALOG", polet_dir / "catalog.ndjson")
    monkeypatch.setattr(polet_store, "META", polet_dir / "catalog_meta.json")
    monkeypatch.setattr(polet_store, "DETAILS_DIR", details_dir)
    return polet_dir


def _product(code, name="Vin", cat="rødvin", country="italia", price=200):
    return {
        "code": code,
        "name": name,
        "main_category": {"code": cat, "name": cat.capitalize()},
        "main_country": {"code": country, "name": country.capitalize()},
        "price": {"value": price},
        "url": f"/p/{code}",
    }


# ─── ingest_search_payload ───────────────────────────────────────────

def test_ingest_search_payload_accepts_dict():
    payload = {"products": [_product("100"), _product("200")]}
    n = refresh_polet.ingest_search_payload(payload, fetched_at=FETCHED_AT)
    assert n == 2
    assert {p["code"] for p in polet_store.read_catalog()} == {"100", "200"}


def test_ingest_search_payload_accepts_json_string():
    payload = json.dumps({"products": [_product("100"), _product("200"), _product("300")]})
    n = refresh_polet.ingest_search_payload(payload, fetched_at=FETCHED_AT)
    assert n == 3
    assert {p["code"] for p in polet_store.read_catalog()} == {"100", "200", "300"}


def test_ingest_search_payload_stamps_fetched_at():
    refresh_polet.ingest_search_payload({"products": [_product("100")]}, fetched_at=FETCHED_AT)
    assert polet_store.lookup("100")["fetched_at"] == FETCHED_AT


def test_ingest_search_payload_empty_products_returns_zero():
    assert refresh_polet.ingest_search_payload({"products": []}, fetched_at=FETCHED_AT) == 0
    assert polet_store.read_catalog() == []


def test_ingest_search_payload_missing_products_key_returns_zero():
    assert refresh_polet.ingest_search_payload({"foo": "bar"}, fetched_at=FETCHED_AT) == 0


def test_ingest_search_payload_invalid_json_string_returns_zero():
    assert refresh_polet.ingest_search_payload("<html>not json</html>", fetched_at=FETCHED_AT) == 0


# ─── ingest_details_html ─────────────────────────────────────────────

def test_ingest_details_html_writes_valid():
    html = FIXTURE.read_text(encoding="utf-8")
    url = "/p/759901"
    rec = refresh_polet.ingest_details_html(FIXTURE_CODE, url, html, fetched_at=FETCHED_AT)
    assert rec["code"] == FIXTURE_CODE
    assert rec["url"] == url
    assert rec["fetched_at"] == FETCHED_AT
    assert rec["klokker"]
    # Faktisk skrevet til snapshot og lesbar igjen.
    assert polet_store.read_details(FIXTURE_CODE) == rec


def test_ingest_details_html_rejects_challenge_html():
    challenge = (
        "<html><head><title>Just a moment...</title></head>"
        "<body>Checking your browser before accessing.</body></html>"
    )
    with pytest.raises(ValueError):
        refresh_polet.ingest_details_html(
            FIXTURE_CODE, "/p/759901", challenge, fetched_at=FETCHED_AT
        )


def test_ingest_details_html_rejects_wrong_varenr():
    html = FIXTURE.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        refresh_polet.ingest_details_html(
            "00000000", "/p/00000000", html, fetched_at=FETCHED_AT
        )


# ─── peer_pool_queries ───────────────────────────────────────────────

def test_peer_pool_queries_shape_and_lowercase():
    queries = refresh_polet.peer_pool_queries()
    assert isinstance(queries, list)
    assert 6 <= len(queries) <= 10
    for q in queries:
        assert set(q.keys()) == {"mainCategory", "mainCountry", "pageSize"}
        assert q["pageSize"] == 50
        assert q["mainCategory"] == q["mainCategory"].lower()
        assert q["mainCountry"] == q["mainCountry"].lower()


def test_peer_pool_queries_no_duplicates():
    queries = refresh_polet.peer_pool_queries()
    combos = [(q["mainCategory"], q["mainCountry"]) for q in queries]
    assert len(combos) == len(set(combos))


def test_peer_pool_queries_static_fallback_when_no_csv(monkeypatch, tmp_path):
    # Pek CSV-stien mot en ikke-eksisterende fil → ren statisk fallback.
    monkeypatch.setattr(refresh_polet, "_VIVINO_CSV", tmp_path / "missing.csv")
    queries = refresh_polet.peer_pool_queries()
    assert 6 <= len(queries) <= 10
    combos = {(q["mainCategory"], q["mainCountry"]) for q in queries}
    # Kjerne-dekningen (rødvin dominerer) skal være med.
    assert ("rødvin", "italia") in combos
    assert ("rødvin", "frankrike") in combos
    assert ("musserende_vin", "frankrike") in combos
