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


# ─── query: active_only (B6) ─────────────────────────────────────────
#
# Katalogen bærer `buyable: true` på rader som for lengst er utgått eller
# utsolgt (målt 2026-08-30: 1 264 rødviner). `active_only` skal luke dem bort
# uten å endre default-oppførselen.

# Ett produkt per status-verdi som faktisk forekommer i snapshotet, pluss én
# rad helt uten `status` (kan oppstå i eldre/manuelt seedede rader).
_STATUS_ROWS = {
    "100": "aktiv",
    "200": "utsolgt",
    "300": "utgatt",
    "400": "lanseres",
    "500": "langtidsutsolgt",
    "600": None,  # feltet mangler
}


@pytest.fixture
def _seeded_statuses():
    products = []
    for code, status in _STATUS_ROWS.items():
        prod = _product(
            code, f"Rød {code}", "rødvin", "Rødvin", "italia", "Italia", 200
        )
        # Alle bærer buyable=True — nettopp poenget: flagget er upålitelig.
        prod["buyable"] = True
        if status is not None:
            prod["status"] = status
        products.append(prod)
    polet_store.upsert_products(products, fetched_at="2026-06-08T00:00:00+00:00")


def test_query_default_is_unchanged_by_b6(_seeded_statuses):
    """Default må returnere HELE katalogen — tre andre fikser bygger på den."""
    alle = {p["code"] for p in polet_store.read_catalog()}
    assert {p["code"] for p in polet_store.query()} == alle
    assert {p["code"] for p in polet_store.query(active_only=False)} == alle
    assert len(polet_store.query(category="rødvin")) == len(_STATUS_ROWS)


def test_query_active_only_keeps_exactly_the_active_row(_seeded_statuses):
    """
    Eksakt sett-likhet, ikke «færre enn før»: et filter som stille returnerte
    hele katalogen (jf. fasetten `Garvestoffer`) ville passert en svakere
    assertion.
    """
    res = polet_store.query(active_only=True)
    assert {p["code"] for p in res} == {"100"}
    assert len(res) < len(polet_store.query())


def test_query_active_only_drops_buyable_but_inactive(_seeded_statuses):
    """Hver bortfiltrert rad har buyable=True — det er hele bugen."""
    droppet = [
        p for p in polet_store.query()
        if p["code"] not in {q["code"] for q in polet_store.query(active_only=True)}
    ]
    assert {p["code"] for p in droppet} == {"200", "300", "400", "500", "600"}
    assert all(p.get("buyable") is True for p in droppet)


def test_query_active_only_combines_with_other_filters(_seeded_statuses):
    """active_only skal ikke kortslutte de øvrige filtrene."""
    assert polet_store.query(category="hvitvin", active_only=True) == []
    assert {p["code"] for p in polet_store.query(min_price=300, active_only=True)} == set()
    res = polet_store.query(category="rødvin", max_price=250, active_only=True)
    assert {p["code"] for p in res} == {"100"}


def test_is_active_case_insensitive_and_missing_status():
    assert polet_store.is_active({"status": "aktiv"})
    assert polet_store.is_active({"status": "AKTIV"})
    assert not polet_store.is_active({"status": "utgatt"})
    assert not polet_store.is_active({"status": None})
    assert not polet_store.is_active({})  # ubekreftet ⇒ ikke kjøpbar


def test_query_active_only_against_real_catalog(monkeypatch):
    """
    Mot det EKTE snapshotet: fanger at status-verdiene i produksjonsdata ser ut
    som vi tror. Ingen hardkodede tall (katalogen refreshes), men relasjonene
    må holde — og filteret må faktisk fjerne noe.
    """
    repo_polet = Path(__file__).resolve().parent.parent / "data" / "polet"
    catalog = repo_polet / "catalog.ndjson"
    if not catalog.exists():
        pytest.skip("Ingen repo-katalog å teste mot")
    monkeypatch.setattr(polet_store, "POLET_DIR", repo_polet)
    monkeypatch.setattr(polet_store, "CATALOG", catalog)

    alle = polet_store.query(category="rødvin")
    aktive = polet_store.query(category="rødvin", active_only=True)

    assert aktive, "ingen aktive rødviner — filteret eller dataene er feil"
    assert len(aktive) < len(alle), "filteret fjernet ingenting (no-op?)"
    assert all(p.get("status") == "aktiv" for p in aktive)

    aktive_koder = {p["code"] for p in aktive}
    droppet = [p for p in alle if p["code"] not in aktive_koder]
    assert droppet and all(p.get("status") != "aktiv" for p in droppet)
    # Bugen slik den ble rapportert: inaktive rader som bærer buyable=True.
    assert [p for p in droppet if p.get("buyable") is True]


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


# ─── shape-pruning ved ingest ────────────────────────────────────────

def _fat_product(code="100", **overrides):
    """Katalog-shape slik den kommer fra vmpws — med de tunge feltene på."""
    p = _product(code, "Fyldig rød", "rødvin", "Rødvin", "italia", "Italia", 249)
    p.update(
        {
            "productAvailability": {
                "deliveryAvailability": {"availableForPurchase": True},
                "storesAvailability": {"infos": [{"readableValue": "5 stk"}]},
            },
            "images": [
                {"format": "product", "imageType": "PRIMARY", "url": f"…/{code}-1.jpg"},
                {"format": "thumbnail", "imageType": "PRIMARY", "url": f"…/{code}-1.jpg"},
            ],
            "main_sub_category": {},
            "district": {"code": "italia_piemonte", "name": "Piemonte"},
            "sub_District": {"code": "italia_piemonte_barolo", "name": "Barolo"},
            "product_selection": "Basisutvalget",
            "volume": {"formattedValue": "75 cl", "value": 75.0},
        }
    )
    p.update(overrides)
    return p


def test_upsert_prunes_heavy_fields():
    polet_store.upsert_products(
        [_fat_product()], fetched_at="2026-08-29T00:00:00+00:00"
    )
    rad = polet_store.lookup("100")
    for felt in polet_store.PRUNED_CATALOG_FIELDS:
        assert felt not in rad, f"{felt} skulle vært strippet"


def test_upsert_preserves_everything_else():
    fat = _fat_product()
    polet_store.upsert_products([fat], fetched_at="2026-08-29T00:00:00+00:00")
    rad = polet_store.lookup("100")

    forventet = {k: v for k, v in fat.items() if k not in polet_store.PRUNED_CATALOG_FIELDS}
    forventet["fetched_at"] = "2026-08-29T00:00:00+00:00"
    assert rad == forventet
    # Eksplisitt: feltene refresh/value/similarity trenger overlever.
    for felt in ("url", "district", "sub_District", "product_selection", "volume", "price"):
        assert felt in rad


def test_upsert_does_not_mutate_callers_product():
    # Refresh-ritualet leser lagerstatus fra sitt eget LIVE søkesvar
    # (polet_live.store_stock) — pruningen skal ikke tømme kallerens dict.
    fat = _fat_product()
    polet_store.upsert_products([fat], fetched_at="2026-08-29T00:00:00+00:00")
    assert "productAvailability" in fat
    assert "images" in fat


def test_upsert_deterministic_after_pruning():
    produkter = [_fat_product("300"), _fat_product("100"), _fat_product("200")]
    polet_store.upsert_products(produkter, fetched_at="2026-08-29T00:00:00+00:00")
    første = polet_store.CATALOG.read_text(encoding="utf-8")
    polet_store.upsert_products(
        list(reversed(produkter)), fetched_at="2026-08-29T00:00:00+00:00"
    )
    assert polet_store.CATALOG.read_text(encoding="utf-8") == første
    assert [json.loads(l)["code"] for l in første.splitlines()] == ["100", "200", "300"]


# ─── migrate_catalog_shape ───────────────────────────────────────────

@pytest.fixture
def _fat_catalog():
    """Skriv en UPRUNET katalog + meta direkte, som en pre-migrasjons-fil."""
    fete = [_fat_product(c) for c in ("100", "200", "300")]
    for p in fete:
        p["fetched_at"] = "2026-07-02T17:27:00+00:00"
    polet_store._write_catalog(fete)  # serialisering uten prune-steget
    polet_store._write_meta(fete, generated_at="2026-07-02T17:27:00+00:00")
    return fete


def test_migrate_prunes_and_preserves_rows(_fat_catalog):
    from tools import migrate_catalog_shape

    før = polet_store.read_catalog()
    assert all("images" in r for r in før)  # sanity: fila er faktisk fet

    r = migrate_catalog_shape.migrate()
    assert r["rader_før"] == r["rader_etter"] == 3
    assert r["bytes_etter"] < r["bytes_før"]
    assert r["spart_prosent"] > 0

    etter = polet_store.read_catalog()
    assert [x["code"] for x in etter] == ["100", "200", "300"]
    for rad, original in zip(etter, før):
        for felt in polet_store.PRUNED_CATALOG_FIELDS:
            assert felt not in rad
        assert rad == {
            k: v for k, v in original.items() if k not in polet_store.PRUNED_CATALOG_FIELDS
        }


def test_migrate_idempotent(_fat_catalog):
    from tools import migrate_catalog_shape

    migrate_catalog_shape.migrate()
    første = polet_store.CATALOG.read_bytes()
    r2 = migrate_catalog_shape.migrate()
    assert polet_store.CATALOG.read_bytes() == første
    assert r2["bytes_før"] == r2["bytes_etter"]
    assert r2["rader_før"] == r2["rader_etter"] == 3


def test_migrate_preserves_generated_at(_fat_catalog):
    # En shape-migrering er ikke en refresh — den skal ikke friskmelde
    # pris/lager ved å bumpe tidsstempelet value_score alders-merker på.
    from tools import migrate_catalog_shape

    migrate_catalog_shape.migrate()
    assert polet_store.catalog_generated_at() == "2026-07-02T17:27:00+00:00"
    assert json.loads(polet_store.META.read_text(encoding="utf-8"))["count"] == 3


def test_migrate_dry_run_writes_nothing(_fat_catalog):
    from tools import migrate_catalog_shape

    før = polet_store.CATALOG.read_bytes()
    meta_før = polet_store.META.read_bytes()
    r = migrate_catalog_shape.migrate(dry_run=True)

    assert r["dry_run"] is True
    assert r["bytes_etter"] < r["bytes_før"]  # rapporterer gevinsten …
    assert polet_store.CATALOG.read_bytes() == før  # … men rører ikke fila
    assert polet_store.META.read_bytes() == meta_før
    assert all("images" in x for x in polet_store.read_catalog())


def test_migrate_leaves_no_temp_file(_fat_catalog):
    from tools import migrate_catalog_shape

    migrate_catalog_shape.migrate()
    assert list(polet_store.POLET_DIR.glob("*.tmp")) == []


def test_migrate_missing_catalog_raises():
    from tools import migrate_catalog_shape

    with pytest.raises(FileNotFoundError):
        migrate_catalog_shape.migrate()


# ─── set_clock_buckets ───────────────────────────────────────────────

@pytest.fixture
def _seeded_for_buckets():
    polet_store.upsert_products(
        [_fat_product("100"), _fat_product("200")],
        fetched_at="2026-08-29T00:00:00+00:00",
    )


def test_set_clock_buckets_merges(_seeded_for_buckets):
    rapport = polet_store.set_clock_buckets(
        {"100": {"Fylde": "7-8", "Friskhet": "9-10", "Tannin": "5-6"}},
        fetched_at="2026-08-29T12:00:00+00:00",
    )
    assert rapport == {"oppdatert": 1, "ukjent_kode": 0, "uendret": 0}

    rad = polet_store.lookup("100")
    assert rad["clock_buckets"] == {"Fylde": "7-8", "Friskhet": "9-10", "Tannin": "5-6"}
    assert rad["clock_buckets_fetched_at"] == "2026-08-29T12:00:00+00:00"
    # Radens eget fetched_at (når produktet ble hentet) røres ikke.
    assert rad["fetched_at"] == "2026-08-29T00:00:00+00:00"
    # Nabo-raden er urørt.
    assert "clock_buckets" not in polet_store.lookup("200")


def test_set_clock_buckets_ignores_unknown_codes(_seeded_for_buckets):
    rapport = polet_store.set_clock_buckets(
        {"100": {"Fylde": "7-8"}, "99999": {"Fylde": "1-2"}},
        fetched_at="2026-08-29T12:00:00+00:00",
    )
    assert rapport == {"oppdatert": 1, "ukjent_kode": 1, "uendret": 0}
    # Ukjent kode teller — men skal IKKE opprette en syntetisk rad.
    assert polet_store.lookup("99999") is None
    assert {p["code"] for p in polet_store.read_catalog()} == {"100", "200"}


def test_set_clock_buckets_unchanged_leaves_file_byte_identical(_seeded_for_buckets):
    buckets = {"100": {"Fylde": "7-8"}}
    polet_store.set_clock_buckets(buckets, fetched_at="2026-08-29T12:00:00+00:00")
    første = polet_store.CATALOG.read_bytes()

    # Samme bøtter, nytt tidsstempel → uendret, og ingen git-diff.
    rapport = polet_store.set_clock_buckets(
        buckets, fetched_at="2026-08-30T12:00:00+00:00"
    )
    assert rapport == {"oppdatert": 0, "ukjent_kode": 0, "uendret": 1}
    assert polet_store.CATALOG.read_bytes() == første


def test_set_clock_buckets_rejects_invalid_bucket(_seeded_for_buckets):
    with pytest.raises(ValueError, match="Ugyldig klokke-bøtte"):
        polet_store.set_clock_buckets(
            {"100": {"Fylde": "8"}}, fetched_at="2026-08-29T12:00:00+00:00"
        )
    with pytest.raises(ValueError):
        polet_store.set_clock_buckets(
            {"100": {"Fylde": "7-9"}}, fetched_at="2026-08-29T12:00:00+00:00"
        )


def test_set_clock_buckets_validates_before_writing(_seeded_for_buckets):
    # Gyldig kode først, ugyldig bøtte etterpå: ingenting skal være skrevet.
    før = polet_store.CATALOG.read_bytes()
    with pytest.raises(ValueError):
        polet_store.set_clock_buckets(
            {"100": {"Fylde": "7-8"}, "200": {"Fylde": "ugyldig"}},
            fetched_at="2026-08-29T12:00:00+00:00",
        )
    assert polet_store.CATALOG.read_bytes() == før
    assert "clock_buckets" not in polet_store.lookup("100")


def test_set_clock_buckets_rejects_non_dict_value(_seeded_for_buckets):
    with pytest.raises(ValueError):
        polet_store.set_clock_buckets(
            {"100": "7-8"}, fetched_at="2026-08-29T12:00:00+00:00"
        )


def test_set_clock_buckets_deterministic_and_sorted(_seeded_for_buckets):
    polet_store.set_clock_buckets(
        {"200": {"Fylde": "11-12"}, "100": {"Fylde": "1-2"}},
        fetched_at="2026-08-29T12:00:00+00:00",
    )
    linjer = polet_store.CATALOG.read_text(encoding="utf-8").splitlines()
    assert [json.loads(l)["code"] for l in linjer] == ["100", "200"]
    # Nøklene er fortsatt sortert innenfor hver linje.
    for linje in linjer:
        rad = json.loads(linje)
        assert linje == json.dumps(rad, ensure_ascii=False, sort_keys=True)


def test_set_clock_buckets_empty_mapping_is_noop(_seeded_for_buckets):
    før = polet_store.CATALOG.read_bytes()
    assert polet_store.set_clock_buckets({}, fetched_at="2026-08-29T12:00:00+00:00") == {
        "oppdatert": 0,
        "ukjent_kode": 0,
        "uendret": 0,
    }
    assert polet_store.CATALOG.read_bytes() == før


# ─── WIRING: JSON-blobb foretrekkes, regex er fallback (ADR-024) ─────

_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures" / "vinmonopolet" / "fenocchio_barbera_alba_superiore.html"
)


def test_save_details_prefers_json_blob(tmp_path, monkeypatch):
    """Ekte produktside har blobb → parser=json og de felt regexen bommer på."""
    monkeypatch.setattr(polet_store, "DETAILS_DIR", tmp_path / "details")
    rec = polet_store.save_details(
        "759901", "/p/759901", _FIXTURE.read_text(encoding="utf-8"),
        fetched_at="2026-08-29T00:00:00+00:00",
    )
    assert rec["parser"] == "json"
    assert rec["klokker"] == {"Fylde": 8, "Friskhet": 9, "Garvestoffer": 7}
    # Nøyaktig de tre feltene regex-veien dropper stille:
    assert rec["produsent"] == "Fenocchio" and rec["årgang"] == "2023"
    assert rec["land"].startswith("Italia")
    assert rec["matparring"] == ["Storfe", "Småvilt", "Svin"]


def test_save_details_falls_back_to_html_without_blob(tmp_path, monkeypatch):
    """Blobben strippet → regex-veien tar over, og proveniensen sier fra."""
    monkeypatch.setattr(polet_store, "DETAILS_DIR", tmp_path / "details")
    html = _FIXTURE.read_text(encoding="utf-8").replace(
        '<script type="application/json">{"product"',
        '<script type="application/json">{"ikkeprodukt"', 1,
    )
    rec = polet_store.save_details(
        "759901", "/p/759901", html, fetched_at="2026-08-29T00:00:00+00:00",
    )
    assert rec["parser"] == "html"
    assert rec["klokker"]  # regex finner fortsatt klokkene


def test_save_details_rejects_blob_for_wrong_product(tmp_path, monkeypatch):
    """Riktig varenr i HTML, men blobben beskriver et annet produkt → avvis."""
    monkeypatch.setattr(polet_store, "DETAILS_DIR", tmp_path / "details")
    html = _FIXTURE.read_text(encoding="utf-8").replace('"code":"759901"', '"code":"111111"')
    html = html.replace("<title>", "<title>Varenummer 759901 ", 1)
    with pytest.raises(ValueError, match="feil produktside"):
        polet_store.save_details(
            "759901", "/p/759901", html, fetched_at="2026-08-29T00:00:00+00:00",
        )


# ─── prune_delisted: fravær etter komplett sveip er informasjon ──────

def _cat_row(code, category="Rødvin", cat_code="rødvin"):
    return {"code": code, "name": f"Vin {code}", "buyable": True,
            "main_category": {"code": cat_code, "name": category},
            "price": {"value": 200}, "volume": {"value": 75}}


@pytest.fixture
def _mixed_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr(polet_store, "POLET_DIR", tmp_path)
    monkeypatch.setattr(polet_store, "CATALOG", tmp_path / "catalog.ndjson")
    monkeypatch.setattr(polet_store, "META", tmp_path / "catalog_meta.json")
    monkeypatch.setattr(polet_store, "DETAILS_DIR", tmp_path / "details")
    rows = [_cat_row(f"r{i}") for i in range(10)]
    rows += [_cat_row(f"h{i}", "Hvitvin", "hvitvin") for i in range(4)]
    polet_store._write_catalog(rows)
    polet_store._write_meta(rows, generated_at="2026-01-01T00:00:00+00:00")
    return tmp_path


def test_prune_delisted_removes_only_absent_in_that_category(_mixed_catalog):
    present = {f"r{i}" for i in range(10)} - {"r3"}
    r = polet_store.prune_delisted(
        present, category="rødvin", generated_at="2026-08-29T00:00:00+00:00")
    assert r["slettet"] == 1 and r["slettede_koder"] == ["r3"]
    koder = {p["code"] for p in polet_store.read_catalog()}
    assert "r3" not in koder
    # Hvitvin er IKKE sveipet — ingen av dem må røres selv om de mangler i present.
    assert {f"h{i}" for i in range(4)} <= koder


def test_prune_delisted_also_removes_orphaned_details(_mixed_catalog):
    polet_store.DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    (polet_store.DETAILS_DIR / "r3.json").write_text("{}", encoding="utf-8")
    (polet_store.DETAILS_DIR / "r4.json").write_text("{}", encoding="utf-8")
    r = polet_store.prune_delisted(
        {f"r{i}" for i in range(10)} - {"r3"}, category="rødvin",
        generated_at="2026-08-29T00:00:00+00:00")
    assert r["details_fjernet"] == 1
    assert not (polet_store.DETAILS_DIR / "r3.json").exists()
    assert (polet_store.DETAILS_DIR / "r4.json").exists()


def test_prune_delisted_refuses_mass_deletion_from_truncated_sweep(_mixed_catalog):
    """En avkortet sveip ser ut som massedød. Nekt, ikke tøm katalogen."""
    with pytest.raises(ValueError, match="avkortet sveip"):
        polet_store.prune_delisted(
            {"r0", "r1"}, category="rødvin",
            generated_at="2026-08-29T00:00:00+00:00")
    assert len(polet_store.read_catalog()) == 14  # ingenting slettet


def test_prune_delisted_force_overrides_guard(_mixed_catalog):
    r = polet_store.prune_delisted(
        {"r0", "r1"}, category="rødvin",
        generated_at="2026-08-29T00:00:00+00:00", force=True)
    assert r["slettet"] == 8


def test_prune_delisted_rejects_empty_and_unknown_category(_mixed_catalog):
    with pytest.raises(ValueError, match="tom"):
        polet_store.prune_delisted(
            set(), category="rødvin", generated_at="2026-08-29T00:00:00+00:00")
    with pytest.raises(ValueError, match="feil kategorinavn"):
        polet_store.prune_delisted(
            {"r0"}, category="sider", generated_at="2026-08-29T00:00:00+00:00")


# ─── _write_meta bevarer felter den ikke kjenner ──────────────────────────


def test_write_meta_preserves_unknown_keys():
    """
    En skrivefunksjon som bygger en fersk struktur fra en fast mal, sletter alt
    utenfor malen i stillhet. `category_completeness` er kompletthets-beviset
    bak teknisk gjeld #11 og kan ikke rekonstrueres uten å betale timeskvoten
    om igjen — det skal overleve enhver katalogskriving.
    """
    products = [
        {"code": "1", "name": "A", "main_category": {"code": "rødvin"}},
        {"code": "2", "name": "B", "main_category": {"code": "hvitvin"}},
    ]
    polet_store.upsert_products(products, fetched_at="2026-06-08T00:00:00+00:00")

    meta = json.loads(polet_store.META.read_text(encoding="utf-8"))
    meta["category_completeness"] = {"hvitvin": {"total_results": 9762, "unique_codes": 9762}}
    meta["completeness_schema_note"] = "fravær betyr «ikke målt», ikke «ufullstendig»"
    polet_store.META.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    # En helt vanlig katalogskriving etterpå
    polet_store.upsert_products(
        [{"code": "3", "name": "C", "main_category": {"code": "rosévin"}}],
        fetched_at="2026-06-09T00:00:00+00:00",
    )

    etter = json.loads(polet_store.META.read_text(encoding="utf-8"))
    assert etter["category_completeness"]["hvitvin"]["total_results"] == 9762
    assert etter["completeness_schema_note"].startswith("fravær")
    # …og de avledede nøklene er faktisk oppdatert, ikke frosset med de bevarte
    assert etter["count"] == 3
    assert etter["category_coverage"]["rosévin"] == 1


def test_write_meta_survives_corrupt_existing_meta():
    """Uleselig meta skal ikke velte en katalogskriving — den skal bygges på nytt."""
    polet_store.META.parent.mkdir(parents=True, exist_ok=True)
    polet_store.META.write_text("{ ikke gyldig json", encoding="utf-8")
    polet_store.upsert_products(
        [{"code": "1", "name": "A", "main_category": {"code": "rødvin"}}],
        fetched_at="2026-06-08T00:00:00+00:00",
    )
    meta = json.loads(polet_store.META.read_text(encoding="utf-8"))
    assert meta["count"] == 1
