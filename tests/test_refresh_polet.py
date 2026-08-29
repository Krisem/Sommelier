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
        # 24 er et SERVERTAK målt live 2026-08-29 (24/25/48/50 gir alle
        # `pagination.pageSize: 24`), ikke et valg. Denne assertion sto på 50
        # og grønnvasket avkortingen i hvert eneste sveip — ikke sett den
        # tilbake. Trengs flere enn 24 rader: paginer.
        assert q["pageSize"] == 24
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


# ─── spine_queries ───────────────────────────────────────────────────

def test_spine_queries_covers_measured_total_exactly():
    # Live-målt 2026-08-29: 13 775 røde a 24 = 574 sider, 0-basert.
    pages = list(refresh_polet.spine_queries())
    assert len(pages) == 574
    assert [p["page"] for p in pages] == list(range(574))


def test_spine_queries_all_hit_roedvin_and_page_size_24():
    pages = list(refresh_polet.spine_queries())
    assert {p["query"] for p in pages} == {":relevance:mainCategory:rødvin"}
    assert pages[0]["url"].endswith("&pageSize=24&currentPage=0")
    assert pages[-1]["url"].endswith("&pageSize=24&currentPage=573")


def test_spine_queries_accepts_fresher_total():
    assert len(list(refresh_polet.spine_queries(49))) == 3
    assert list(refresh_polet.spine_queries(0)) == []


def test_spine_queries_is_lazy():
    # Generator, ikke liste — kalleren skal kunne stoppe midtveis.
    gen = refresh_polet.spine_queries()
    assert next(gen)["page"] == 0
    gen.close()


# ─── clock_sweep_queries ─────────────────────────────────────────────

def test_clock_sweep_is_the_full_cartesian_product():
    entries = list(refresh_polet.clock_sweep_queries())
    assert len(entries) == 6 * 6 * 6 == 216


def test_clock_sweep_triples_are_unique_and_cover_all_buckets():
    entries = list(refresh_polet.clock_sweep_queries())
    triples = [(e["fylde"], e["friskhet"], e["tannin"]) for e in entries]
    assert len(set(triples)) == 216
    for i in range(3):
        assert {t[i] for t in triples} == {"1-2", "3-4", "5-6", "7-8", "9-10", "11-12"}


def test_clock_sweep_query_uses_tannin_sulfates_not_garvestoffer():
    entries = list(refresh_polet.clock_sweep_queries())
    for e in entries:
        assert "Tannin(Sulfates):" in e["query"]
        assert "Garvestoffer" not in e["query"]
        assert e["query"].endswith(":mainCategory:rødvin")


def test_clock_sweep_probe_url_is_page_zero():
    first = next(refresh_polet.clock_sweep_queries())
    assert first["probe_url"].endswith("&pageSize=24&currentPage=0")


def test_clock_sweep_is_cheaper_than_three_separate_sweeps():
    # Poenget med det kartesiske sveipet: ~460 sider i én passering mot
    # ~1 370 for tre 1-dim-sveip. Her sjekker vi bare at hver kombinasjon er
    # ETT presist søk som gir alle tre klokkene samtidig.
    entries = list(refresh_polet.clock_sweep_queries())
    assert all({"fylde", "friskhet", "tannin"} <= set(e) for e in entries)


# ─── ingest_clock_sweep ──────────────────────────────────────────────

def _sweep(fylde, friskhet, tannin, codes):
    return {"fylde": fylde, "friskhet": friskhet, "tannin": tannin, "codes": codes}


def test_ingest_clock_sweep_builds_store_mapping():
    report = refresh_polet.ingest_clock_sweep([
        _sweep("7-8", "9-10", "5-6", ["759901", "10267301"]),
        _sweep("1-2", "3-4", "1-2", ["111"]),
    ])
    assert report["mapping"] == {
        "759901": {"Fylde": "7-8", "Friskhet": "9-10", "Tannin": "5-6"},
        "10267301": {"Fylde": "7-8", "Friskhet": "9-10", "Tannin": "5-6"},
        "111": {"Fylde": "1-2", "Friskhet": "3-4", "Tannin": "1-2"},
    }
    assert report["codes"] == 3
    assert report["buckets_seen"] == 2
    assert report["collision_count"] == 0
    assert report["collisions"] == []


def test_ingest_clock_sweep_same_triple_twice_is_not_a_collision():
    # Sveiperen dumper per side — samme trippel opptrer i flere batcher.
    report = refresh_polet.ingest_clock_sweep([
        _sweep("7-8", "9-10", "5-6", ["759901"]),
        _sweep("7-8", "9-10", "5-6", ["759901", "222"]),
    ])
    assert report["collision_count"] == 0
    assert report["codes"] == 2
    assert report["buckets_seen"] == 1


def test_ingest_clock_sweep_detects_code_in_two_triples():
    # En vin kan ikke ligge i to bøtter (AND-semantikken, ADR-023) — dette er
    # et datafeil-signal og skal IKKE la siste skriver vinne stille.
    report = refresh_polet.ingest_clock_sweep([
        _sweep("7-8", "9-10", "5-6", ["759901", "ok1"]),
        _sweep("1-2", "1-2", "1-2", ["759901"]),
    ])
    assert report["collision_count"] == 1
    assert report["collisions"][0]["code"] == "759901"
    assert report["collisions"][0]["buckets"] == [
        {"Fylde": "7-8", "Friskhet": "9-10", "Tannin": "5-6"},
        {"Fylde": "1-2", "Friskhet": "1-2", "Tannin": "1-2"},
    ]
    # Første trippel vinner, koden går ikke tapt, og naboen er urørt.
    assert report["mapping"]["759901"] == {
        "Fylde": "7-8", "Friskhet": "9-10", "Tannin": "5-6"
    }
    assert report["mapping"]["ok1"]["Fylde"] == "7-8"


def test_ingest_clock_sweep_reports_three_way_collision_once():
    report = refresh_polet.ingest_clock_sweep([
        _sweep("7-8", "7-8", "7-8", ["x"]),
        _sweep("1-2", "1-2", "1-2", ["x"]),
        _sweep("3-4", "3-4", "3-4", ["x"]),
    ])
    assert report["collision_count"] == 1
    assert len(report["collisions"][0]["buckets"]) == 3


def test_ingest_clock_sweep_empty_input():
    report = refresh_polet.ingest_clock_sweep([])
    assert report == {
        "mapping": {},
        "codes": 0,
        "buckets_seen": 0,
        "collisions": [],
        "collision_count": 0,
    }


def test_ingest_clock_sweep_zero_hit_combo_is_normal():
    # ~2 750 av de 13 775 røde har ingen klokker — tomme kombinasjoner er
    # forventet, ikke en feil.
    report = refresh_polet.ingest_clock_sweep([_sweep("1-2", "1-2", "1-2", [])])
    assert report["mapping"] == {}
    assert report["buckets_seen"] == 0


def test_ingest_clock_sweep_coerces_numeric_codes_to_str():
    report = refresh_polet.ingest_clock_sweep([_sweep("7-8", "7-8", "7-8", [759901])])
    assert list(report["mapping"]) == ["759901"]


def test_ingest_clock_sweep_rejects_missing_dimension():
    entry = _sweep("7-8", "9-10", "5-6", ["1"])
    del entry["tannin"]
    with pytest.raises(ValueError):
        refresh_polet.ingest_clock_sweep([entry])


def test_ingest_clock_sweep_rejects_invalid_bucket_code():
    with pytest.raises(ValueError):
        refresh_polet.ingest_clock_sweep([_sweep("7-12", "9-10", "5-6", ["1"])])


def test_ingest_clock_sweep_rejects_non_list_codes():
    with pytest.raises(ValueError):
        refresh_polet.ingest_clock_sweep([_sweep("7-8", "9-10", "5-6", "759901")])


def test_ingest_clock_sweep_mapping_keys_match_store_contract():
    # Signaturen polet_store.set_clock_buckets konsumerer er avtalt — nøklene
    # er Fylde/Friskhet/Tannin (ikke fasett-koden «Tannin(Sulfates)»).
    report = refresh_polet.ingest_clock_sweep([_sweep("7-8", "9-10", "5-6", ["1"])])
    assert set(report["mapping"]["1"]) == {"Fylde", "Friskhet", "Tannin"}
