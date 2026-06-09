"""
Tester for tools/polet_store.py — repo-backed Polet lese/skrive-lag.

Bruker monkeypatch for å peke store mot et tmp_path data/polet, slik at ekte
repo-data ikke røres.
"""

import json
from pathlib import Path

import pytest

from tools import polet_store

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "vinmonopolet"
    / "fenocchio_barbera_alba_superiore.html"
)
FIXTURE_CODE = "759901"  # varenr som faktisk står i fixturen


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


def _product(code, name, cat_code, cat_name, country_code, country_name, price):
    return {
        "code": code,
        "name": name,
        "main_category": {"code": cat_code, "name": cat_name},
        "main_country": {"code": country_code, "name": country_name},
        "price": {"value": price},
        "url": f"/p/{code}",
    }


# ─── upsert determinisme ─────────────────────────────────────────────

def test_upsert_deterministic_repeated_runs():
    products = [
        _product("300", "C", "rødvin", "Rødvin", "italia", "Italia", 200),
        _product("100", "A", "rødvin", "Rødvin", "italia", "Italia", 150),
        _product("200", "B", "hvitvin", "Hvitvin", "frankrike", "Frankrike", 180),
    ]
    polet_store.upsert_products(products, fetched_at="2026-06-08T00:00:00+00:00")
    first = polet_store.CATALOG.read_text(encoding="utf-8")
    meta_first = polet_store.META.read_text(encoding="utf-8")

    # Kjør på nytt med samme input → identisk fil.
    polet_store.upsert_products(products, fetched_at="2026-06-08T00:00:00+00:00")
    assert polet_store.CATALOG.read_text(encoding="utf-8") == first
    assert polet_store.META.read_text(encoding="utf-8") == meta_first


def test_upsert_insertion_order_independent(tmp_path, monkeypatch):
    products = [
        _product("100", "A", "rødvin", "Rødvin", "italia", "Italia", 150),
        _product("200", "B", "hvitvin", "Hvitvin", "frankrike", "Frankrike", 180),
        _product("300", "C", "rødvin", "Rødvin", "italia", "Italia", 200),
    ]
    polet_store.upsert_products(products, fetched_at="2026-06-08T00:00:00+00:00")
    out_a = polet_store.CATALOG.read_text(encoding="utf-8")

    # Frisk store (annen tmp), reversert insertion-order → samme output (sortert på code).
    polet_dir2 = tmp_path / "store2" / "data" / "polet"
    monkeypatch.setattr(polet_store, "POLET_DIR", polet_dir2)
    monkeypatch.setattr(polet_store, "CATALOG", polet_dir2 / "catalog.ndjson")
    monkeypatch.setattr(polet_store, "META", polet_dir2 / "catalog_meta.json")
    monkeypatch.setattr(polet_store, "DETAILS_DIR", polet_dir2 / "details")
    polet_store.upsert_products(list(reversed(products)), fetched_at="2026-06-08T00:00:00+00:00")
    out_b = polet_store.CATALOG.read_text(encoding="utf-8")
    assert out_a == out_b
    # Linjene er faktisk sortert på code.
    codes = [json.loads(l)["code"] for l in out_a.splitlines()]
    assert codes == ["100", "200", "300"]


def test_upsert_newest_wins():
    polet_store.upsert_products(
        [_product("100", "Gammel", "rødvin", "Rødvin", "italia", "Italia", 150)],
        fetched_at="2026-01-01T00:00:00+00:00",
    )
    n = polet_store.upsert_products(
        [_product("100", "Ny", "rødvin", "Rødvin", "italia", "Italia", 199)],
        fetched_at="2026-06-08T00:00:00+00:00",
    )
    assert n == 1
    rows = polet_store.read_catalog()
    assert len(rows) == 1
    assert rows[0]["name"] == "Ny"
    assert rows[0]["price"]["value"] == 199


def test_upsert_stamps_fetched_at():
    polet_store.upsert_products(
        [_product("100", "A", "rødvin", "Rødvin", "italia", "Italia", 150)],
        fetched_at="2026-06-08T00:00:00+00:00",
    )
    assert polet_store.lookup("100")["fetched_at"] == "2026-06-08T00:00:00+00:00"


# ─── query ───────────────────────────────────────────────────────────

@pytest.fixture
def _seeded():
    products = [
        _product("100", "Italiensk rød billig", "rødvin", "Rødvin", "italia", "Italia", 150),
        _product("200", "Italiensk rød dyr", "rødvin", "Rødvin", "italia", "Italia", 450),
        _product("300", "Fransk hvit", "hvitvin", "Hvitvin", "frankrike", "Frankrike", 250),
    ]
    polet_store.upsert_products(products, fetched_at="2026-06-08T00:00:00+00:00")


def test_query_category_matches_code_and_name(_seeded):
    assert len(polet_store.query(category="rødvin")) == 2   # via code
    assert len(polet_store.query(category="Rødvin")) == 2   # via name
    assert len(polet_store.query(category="RØDVIN")) == 2   # case-insensitiv


def test_query_country_matches_code_and_name(_seeded):
    assert len(polet_store.query(country="frankrike")) == 1
    assert len(polet_store.query(country="Frankrike")) == 1


def test_query_price_range(_seeded):
    assert {p["code"] for p in polet_store.query(max_price=200)} == {"100"}
    assert {p["code"] for p in polet_store.query(min_price=300)} == {"200"}
    assert {p["code"] for p in polet_store.query(min_price=200, max_price=400)} == {"300"}


def test_query_name_contains(_seeded):
    assert {p["code"] for p in polet_store.query(name_contains="fransk")} == {"300"}


def test_query_combined(_seeded):
    res = polet_store.query(category="rødvin", max_price=200)
    assert {p["code"] for p in res} == {"100"}


# ─── lookup ──────────────────────────────────────────────────────────

def test_lookup_found_and_miss(_seeded):
    assert polet_store.lookup("100")["name"] == "Italiensk rød billig"
    assert polet_store.lookup("999") is None


# ─── read_details / save_details round-trip ──────────────────────────

def test_read_details_miss_returns_none():
    assert polet_store.read_details("759901") is None


def test_save_details_valid_html_roundtrip():
    html = FIXTURE.read_text(encoding="utf-8")
    url = "/p/759901"
    rec = polet_store.save_details(
        FIXTURE_CODE, url, html, fetched_at="2026-06-08T00:00:00+00:00"
    )
    assert rec["code"] == FIXTURE_CODE
    assert rec["url"] == url
    assert rec["fetched_at"] == "2026-06-08T00:00:00+00:00"
    assert rec["klokker"]  # parse fanget klokker

    back = polet_store.read_details(FIXTURE_CODE)
    assert back == rec
    assert polet_store.details_fetched_at(FIXTURE_CODE) == "2026-06-08T00:00:00+00:00"


def test_save_details_deterministic():
    html = FIXTURE.read_text(encoding="utf-8")
    polet_store.save_details(FIXTURE_CODE, "/p/759901", html, fetched_at="2026-06-08T00:00:00+00:00")
    first = (polet_store.DETAILS_DIR / f"{FIXTURE_CODE}.json").read_text(encoding="utf-8")
    polet_store.save_details(FIXTURE_CODE, "/p/759901", html, fetched_at="2026-06-08T00:00:00+00:00")
    second = (polet_store.DETAILS_DIR / f"{FIXTURE_CODE}.json").read_text(encoding="utf-8")
    assert first == second


def test_save_details_rejects_challenge_html():
    # Challenge-aktig: mangler riktig varenr (og produktdata).
    challenge = (
        "<html><head><title>Just a moment...</title></head>"
        "<body>Checking your browser before accessing.</body></html>"
    )
    with pytest.raises(ValueError):
        polet_store.save_details(
            FIXTURE_CODE, "/p/759901", challenge, fetched_at="2026-06-08T00:00:00+00:00"
        )


def test_save_details_rejects_wrong_varenr():
    # Gyldig produktside, men for FEIL varenr → varenr ikke i HTML → avvist.
    html = FIXTURE.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        polet_store.save_details(
            "00000000", "/p/00000000", html, fetched_at="2026-06-08T00:00:00+00:00"
        )


def test_save_details_rejects_soft_error_with_code_only_in_url():
    # Regresjon: en soft-error/feilside kan referere varenr i canonical/asset-URL
    # og ha en løs "kr 0 i frakt"-tekst, men mangler produktdata (klokker/strukturert
    # pris) og varenr i produkt-kontekst. Skal avvises (ikke falsk positiv).
    soft = (
        "<html><head><title>Vinmonopolet</title>"
        '<link rel="canonical" href="https://www.vinmonopolet.no/p/759901"></head>'
        '<body><img src="https://bilder.vinmonopolet.no/cache/300x300-0/759901-1.jpg">'
        "Beklager, en feil oppstod. kr 0 i frakt</body></html>"
    )
    with pytest.raises(ValueError):
        polet_store.save_details(
            FIXTURE_CODE, "/p/759901", soft, fetched_at="2026-06-08T00:00:00+00:00"
        )


# ─── catalog_age_days / generated_at ─────────────────────────────────

def test_catalog_age_days_from_meta():
    from datetime import datetime, timedelta, timezone

    five_days_ago = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    polet_store.upsert_products(
        [_product("100", "A", "rødvin", "Rødvin", "italia", "Italia", 150)],
        fetched_at=five_days_ago,
    )
    age = polet_store.catalog_age_days()
    assert age is not None
    assert 4.9 < age < 5.1
    assert polet_store.catalog_generated_at() == five_days_ago


def test_catalog_age_days_none_without_meta():
    assert polet_store.catalog_age_days() is None
    assert polet_store.catalog_generated_at() is None


# ─── cache-miss-semantikk (lesere returnerer None/[], kaster ikke) ───

def test_readers_empty_when_no_snapshot():
    assert polet_store.read_catalog() == []
    assert polet_store.lookup("100") is None
    assert polet_store.query(category="rødvin") == []
    assert polet_store.read_details("100") is None
    assert polet_store.details_fetched_at("100") is None


def test_refresh_required_carries_url_and_hint():
    exc = polet_store.PoletRefreshRequired("Vin 100 mangler", url="/p/100")
    assert exc.url == "/p/100"
    assert "refresh fra desktop" in exc.hint.lower()
    assert "snapshot" in str(exc).lower()
