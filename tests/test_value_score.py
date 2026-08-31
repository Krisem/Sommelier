"""Kontrakt-tester for verdiscoring og peer-percentile.

Kjøres OFFLINE mot repo-snapshotet: polet_store pekes mot en tmp fixture-katalog
(samme mønster som tests/test_vinmonopolet.py sin `snapshot`-fixture), og
Vivino/Aperitif/user-scores monkeypatches. Ingen nettverkskall.
"""

from __future__ import annotations

import json
import time

import pytest


KNOWN_POLET_ID = "15012201"
KNOWN_VINTAGE = 2022


# ─── FIXTURE: liten snapshot-katalog i tmp (≥5 rødvin/italia-peers) ───────

# Egen vin + 5 italienske rødviner som peers + 1 fra annet land/kategori.
_OWN = {
    "code": "15012201",
    "name": "Tornatore Etna Rosso 2022",
    "price": {"value": 289.0, "formattedValue": "Kr 289,00"},
    "main_category": {"code": "rødvin", "name": "Rødvin"},
    "main_country": {"code": "italia", "name": "Italia"},
    "status": "aktiv",
    "url": "/Land/Italia/Sicilia/Etna/Tornatore-Etna-Rosso-2022/p/15012201",
}

_PEERS = [
    {
        "code": f"2000000{i}",
        "name": f"Italiensk Rødvin {i}",
        "price": {"value": price, "formattedValue": f"Kr {price:.0f},00"},
        "main_category": {"code": "rødvin", "name": "Rødvin"},
        "main_country": {"code": "italia", "name": "Italia"},
        "status": "aktiv",
        "url": f"/Land/Italia/X/Y/Vin-{i}/p/2000000{i}",
    }
    for i, price in enumerate([149.0, 199.0, 259.0, 349.0, 599.0], start=1)
]

_OTHER = {
    "code": "30000001",
    "name": "Fransk Hvitvin",
    "price": {"value": 250.0, "formattedValue": "Kr 250,00"},
    "main_category": {"code": "hvitvin", "name": "Hvitvin"},
    "main_country": {"code": "frankrike", "name": "Frankrike"},
    "status": "aktiv",
    "url": "/Land/Frankrike/X/Y/Hvit/p/30000001",
}

_CATALOG = [_OWN, *_PEERS, _OTHER]


def _write_snapshot(monkeypatch, tmp_path, *, generated_at: str | None,
                    catalog=None):
    """Skriv fixture-snapshot til tmp og pek polet_store + value_score dit."""
    from tools import polet_store

    polet_dir = tmp_path / "polet"
    details_dir = polet_dir / "details"
    details_dir.mkdir(parents=True, exist_ok=True)

    catalog_path = polet_dir / "catalog.ndjson"
    catalog_path.write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in (catalog or _CATALOG)) + "\n",
        encoding="utf-8",
    )
    meta_path = polet_dir / "catalog_meta.json"
    if generated_at is not None:
        meta_path.write_text(
            json.dumps({"generated_at": generated_at, "count": len(catalog or _CATALOG)},
                       ensure_ascii=False),
            encoding="utf-8",
        )

    monkeypatch.setattr(polet_store, "POLET_DIR", polet_dir)
    monkeypatch.setattr(polet_store, "CATALOG", catalog_path)
    monkeypatch.setattr(polet_store, "DETAILS_DIR", details_dir)
    monkeypatch.setattr(polet_store, "META", meta_path)
    return polet_store


@pytest.fixture
def fresh_snapshot(monkeypatch, tmp_path):
    """Snapshot generert i dag (ferskt) + isolert value_score-cache i tmp."""
    from datetime import datetime, timezone

    from tools import value_score

    now = datetime.now(timezone.utc).isoformat()
    store = _write_snapshot(monkeypatch, tmp_path, generated_at=now)

    # Isolér value_score-cachen til tmp så vi ikke leser/skriver ~/.cache.
    monkeypatch.setattr(value_score, "VALUE_CACHE_DIR", tmp_path / "value_cache")

    # Stub eksterne kilder (offline).
    monkeypatch.setattr(value_score, "get_vivino_rating", lambda *a, **k: None)
    monkeypatch.setattr(value_score, "get_aperitif_score", lambda *a, **k: None)
    monkeypatch.setattr(value_score, "get_user_scores", lambda *a, **k: [])
    return store


@pytest.fixture
def polet_product(fresh_snapshot):
    from tools.vinmonopolet import search

    results = search("Tornatore")
    assert results, "snapshot returnerte 0 treff for 'Tornatore'"
    for r in results:
        if r.get("code") == KNOWN_POLET_ID:
            return r
    return results[0]


@pytest.fixture(scope="module")
def _real_rows():
    """Det ekte repo-snapshotet, lest én gang for hele modulen."""
    from tools import polet_store

    if not polet_store.CATALOG.exists():
        pytest.skip("data/polet/catalog.ndjson mangler")
    rows = polet_store.read_catalog()
    if len(rows) < 100:
        pytest.skip(f"snapshotet er for lite til skala-test ({len(rows)} rader)")
    return rows


@pytest.fixture
def real_catalog(_real_rows, monkeypatch):
    """Kjør mot ekte katalogdata uten å lese 12 MB fra disk per kall.

    Skala-testene MÅ se ekte data — det er hele poenget; en fixture på 6 rader
    er blind for nøyaktig den feilen de finnes for å fange.
    """
    from tools import polet_store

    monkeypatch.setattr(polet_store, "read_catalog", lambda: _real_rows)
    return _real_rows


# ─── peer_percentile (offline) ────────────────────────────────────────

def test_peer_percentile_structure(polet_product):
    from tools.value_score import _peer_percentile

    peer = _peer_percentile(polet_product)

    assert peer is not None, "_peer_percentile returnerte None — for få peers"
    assert set(peer.keys()) >= {
        "percentile", "median_price", "sample_size", "peer_terms",
    }, f"Mangler keys i peer-result: {peer.keys()}"
    assert 0.0 <= peer["percentile"] <= 1.0
    assert peer["median_price"] > 0
    assert peer["sample_size"] >= 5
    assert isinstance(peer["peer_terms"], list) and peer["peer_terms"]


def test_compute_value_score_end_to_end(polet_product):
    from tools.value_score import compute_value_score

    result = compute_value_score(polet_product, vintage=KNOWN_VINTAGE)

    expected_keys = {
        "wine_name", "polet_id", "price", "value_verdict", "summary",
        "quality_tier", "vivino", "aperitif", "peer", "user_scores",
        "snapshot_age_days", "snapshot_generated_at", "peer_status",
    }
    missing = expected_keys - set(result.keys())
    assert not missing, f"compute_value_score mangler keys: {missing}"

    assert isinstance(result["summary"], str) and result["summary"].strip()
    assert result["wine_name"] and result["polet_id"]
    assert result["price"] is not None and result["price"] > 0


def test_compute_value_score_is_cached(polet_product):
    """Andre kall skal være rask (cache hit, < 0.5s)."""
    from tools.value_score import compute_value_score

    compute_value_score(polet_product, vintage=KNOWN_VINTAGE)

    t0 = time.time()
    compute_value_score(polet_product, vintage=KNOWN_VINTAGE)
    elapsed = time.time() - t0

    assert elapsed < 0.5, (
        f"Cached call tok {elapsed:.2f}s — cache treffer ikke. "
        "Sjekk _value_cache_get / LOGIC_VERSION / snapshot-token."
    )


# ─── (a) PoletRefreshRequired svelges ikke stille ─────────────────────

def test_refresh_required_surfaces_in_peer_and_summary(monkeypatch, tmp_path):
    """Ingen andre viner i kategori+land → peer={status: refresh_required},
    ikke None, og summary nevner det eksplisitt."""
    from tools import value_score
    from tools.value_score import _peer_percentile, compute_value_score

    # Snapshot der egen vin finnes, men INGEN andre i samme kategori+land
    # → peer-populasjonen er tom (bare vinen selv).
    lonely = dict(_OWN)
    lonely["main_category"] = {"code": "musserende_vin", "name": "Musserende vin"}
    lonely["main_country"] = {"code": "ungarn", "name": "Ungarn"}
    _write_snapshot(monkeypatch, tmp_path, generated_at="2026-06-01T00:00:00+00:00",
                    catalog=[lonely, _OTHER])
    monkeypatch.setattr(value_score, "VALUE_CACHE_DIR", tmp_path / "value_cache")
    monkeypatch.setattr(value_score, "get_vivino_rating", lambda *a, **k: None)
    monkeypatch.setattr(value_score, "get_aperitif_score", lambda *a, **k: None)
    monkeypatch.setattr(value_score, "get_user_scores", lambda *a, **k: [])

    peer = _peer_percentile(lonely)
    assert peer == {"status": "refresh_required"}, (
        f"Peer skal signalisere refresh_required, ikke svelges. Fikk: {peer}"
    )

    result = compute_value_score(lonely, vintage=KNOWN_VINTAGE)
    assert result["peer_status"] == "refresh_required"
    assert "peer-data mangler i snapshot" in result["summary"]
    assert "refresh fra desktop" in result["summary"]


# ─── (b) Aldersmerking + degradert språk når > 14 d ───────────────────

def test_verdict_has_snapshot_age(polet_product):
    from tools.value_score import compute_value_score

    result = compute_value_score(polet_product, vintage=KNOWN_VINTAGE)
    assert result["snapshot_age_days"] is not None
    assert result["snapshot_age_days"] >= 0
    assert "snapshot fra" in result["summary"]


def test_stale_snapshot_degrades_language(monkeypatch, tmp_path):
    """catalog_age_days > 14 → summary advarer om at pris/lager kan ha endret seg."""
    from tools import polet_store, value_score
    from tools.value_score import compute_value_score

    _write_snapshot(monkeypatch, tmp_path, generated_at="2026-05-01T00:00:00+00:00")
    monkeypatch.setattr(value_score, "VALUE_CACHE_DIR", tmp_path / "value_cache")
    monkeypatch.setattr(value_score, "get_vivino_rating", lambda *a, **k: None)
    monkeypatch.setattr(value_score, "get_aperitif_score", lambda *a, **k: None)
    monkeypatch.setattr(value_score, "get_user_scores", lambda *a, **k: [])
    # Tving alder til 30 dager uavhengig av dato.
    monkeypatch.setattr(polet_store, "catalog_age_days", lambda: 30.0)

    result = compute_value_score(_OWN, vintage=KNOWN_VINTAGE)
    assert result["snapshot_age_days"] == 30
    assert "30 dager gammelt" in result["summary"]
    assert "verifiser på polet.no før kjøp" in result["summary"]


def test_fresh_snapshot_no_stale_warning(polet_product):
    from tools.value_score import compute_value_score

    result = compute_value_score(polet_product, vintage=KNOWN_VINTAGE)
    assert "verifiser på polet.no før kjøp" not in result["summary"]


# ─── (c) Cache-nøkkel endres når catalog_generated_at endres ──────────

def test_cache_key_includes_snapshot_freshness(monkeypatch, tmp_path):
    from tools import polet_store, value_score

    monkeypatch.setattr(value_score, "VALUE_CACHE_DIR", tmp_path / "value_cache")

    monkeypatch.setattr(polet_store, "catalog_generated_at",
                        lambda: "2026-06-01T00:00:00+00:00")
    p1 = value_score._value_cache_path("15012201", 2022)

    monkeypatch.setattr(polet_store, "catalog_generated_at",
                        lambda: "2026-06-08T00:00:00+00:00")
    p2 = value_score._value_cache_path("15012201", 2022)

    assert p1 != p2, "Cache-nøkkel skal endres når snapshotet refreshes"


def test_cache_invalidated_across_refresh(monkeypatch, tmp_path):
    """Verdict cachet mot ett snapshot serveres IKKE etter refresh."""
    from tools import polet_store, value_score
    from tools.value_score import compute_value_score

    _write_snapshot(monkeypatch, tmp_path, generated_at="2026-06-01T00:00:00+00:00")
    monkeypatch.setattr(value_score, "VALUE_CACHE_DIR", tmp_path / "value_cache")
    monkeypatch.setattr(value_score, "get_vivino_rating", lambda *a, **k: None)
    monkeypatch.setattr(value_score, "get_aperitif_score", lambda *a, **k: None)
    monkeypatch.setattr(value_score, "get_user_scores", lambda *a, **k: [])

    monkeypatch.setattr(polet_store, "catalog_generated_at",
                        lambda: "2026-06-01T00:00:00+00:00")
    r1 = compute_value_score(_OWN, vintage=KNOWN_VINTAGE)

    # Refresh: nytt generated_at → ny cache-nøkkel → ikke serve gammel.
    monkeypatch.setattr(polet_store, "catalog_generated_at",
                        lambda: "2026-06-08T00:00:00+00:00")
    p_new = value_score._value_cache_path(_OWN["code"], KNOWN_VINTAGE)
    assert not p_new.exists(), "Ny snapshot-nøkkel skal ikke ha en pre-eksisterende cache-fil"
    r2 = compute_value_score(_OWN, vintage=KNOWN_VINTAGE)
    assert r1["value_verdict"] == r2["value_verdict"]  # samme data → samme verdict, men ny fil


# ─── (d) SKALAINVARIANTE TESTER — så peer-poolen ER populasjonen ──────
#
# De øvrige testene i denne fila sjekker at `_peer_percentile` *regner riktig*
# på det den fikk. Testene under sjekker at den *har sett hele datagrunnlaget*.
# Det var nettopp den forskjellen B1 levde i: funksjonen regnet en helt korrekt
# median av `polet_store.query(...)[:50]` — de 50 laveste varenumrene i landet —
# og ingen av de 291 grønne testene merket det da katalogen vokste 1 543 →
# 13 775. Assertion-formen er derfor alltid en *andel av populasjonen*, aldri et
# tall: den holder ved 60 viner og ved 137 750.

def _peer_catalog(n_peers: int, *, status: str = "aktiv", country: str = "italia"):
    """Katalog med `_OWN` + `n_peers` prisvarierte peers i samme kategori+land."""
    peers = [
        {
            "code": f"9{i:07d}",
            "name": f"Peer {i}",
            "price": {"value": 100.0 + i, "formattedValue": f"Kr {100 + i},00"},
            "main_category": {"code": "rødvin", "name": "Rødvin"},
            "main_country": {"code": country, "name": country.capitalize()},
            "status": status,
            "url": f"/x/p/9{i:07d}",
        }
        for i in range(1, n_peers + 1)
    ]
    return [_OWN, *peers]


@pytest.mark.parametrize("n_peers", [12, 60, 500])
def test_peer_pool_is_whole_population_at_any_scale(monkeypatch, tmp_path, n_peers):
    """Vokser katalogen, skal peer-utvalget vokse med den — uten tak.

    Dette er testen B1 ville strøket på i det øyeblikket snapshotet passerte 56
    viner i én kategori×land: `[:50]` ga sample_size 50 for både 60 og 500.
    """
    from tools.value_score import _peer_percentile

    _write_snapshot(monkeypatch, tmp_path, generated_at="2026-08-29T00:00:00+00:00",
                    catalog=_peer_catalog(n_peers))

    peer = _peer_percentile(_OWN)

    assert peer is not None and "percentile" in peer
    assert peer["sample_size"] == n_peers, (
        f"{n_peers} peers i katalogen, men sample_size={peer['sample_size']}. "
        "Et tak er sneket inn i peer-poolen — median/percentil er "
        "populasjonsstatistikk og tåler ikke avkorting."
    )


def test_peer_sample_equals_declared_population_for_every_pool(real_catalog):
    """For HVER kategori×land i det ekte snapshotet: sample_size == populasjonen.

    Ikke et utvalg pools — alle. `peer_terms` erklærer hvilket grunnlag som ble
    brukt (`status:aktiv` eller `status:alle`), og testen holder funksjonen til
    sin egen erklæring.
    """
    from tools import polet_store
    from tools.value_score import _peer_percentile

    pools: dict = {}
    for p in real_catalog:
        key = ((p.get("main_category") or {}).get("code"),
               (p.get("main_country") or {}).get("code"))
        pools.setdefault(key, []).append(p)

    checked = 0
    for (category, country), rows in pools.items():
        if not category:
            continue
        wine = next((r for r in rows if (r.get("price") or {}).get("value")), None)
        if wine is None:
            continue

        peer = _peer_percentile(wine)
        if peer is None or "percentile" not in peer:
            continue  # tynn pool — egen test dekker den grenen

        # `active_only=False` med vilje: peer-populasjonen i `_peer_percentile`
        # er hele katalogen, og statusfilteret legges på ETTERPÅ, kun når
        # `peer_terms` sier `status:aktiv`. Testen må speile den rekkefølgen,
        # ellers måler den mot en annen nevner enn funksjonen erklærer.
        population = polet_store.query(
            category=category, country=country or None, active_only=False
        )
        if "status:aktiv" in peer["peer_terms"]:
            population = [r for r in population if polet_store.is_active(r)]
        expected = len([
            r for r in population
            if r.get("code") != wine.get("code") and (r.get("price") or {}).get("value")
        ])

        assert peer["sample_size"] == expected, (
            f"{category}/{country}: sample_size={peer['sample_size']} av {expected} "
            f"i den erklærte populasjonen ({peer['peer_terms']}). "
            "Peer-gruppen er avkortet."
        )
        # A1, ordrett: sample_size >= 0.9 * (len(populasjonen) - 1). Andel, ikke
        # tall — den holder ved 1 543 viner og ved 137 750. NB: nevneren må
        # filtreres likt som telleren. Måler man mot den ufiltrerte katalogen
        # mens peer-gruppen er aktiv-filtrert, feiler testen på ~16 % og ser ut
        # som en bug i fiksen; den 16 %-en er 2 196 utgåtte rødviner.
        assert peer["sample_size"] >= 0.9 * expected
        checked += 1

    assert checked >= 10, f"Bare {checked} pools testet — snapshotet ser feil ut"


def test_peer_percentile_matches_independent_ground_truth():
    """Pinnet repro av B1, mot ekte `data/polet/` og en uavhengig fasit.

    Før fiksen: 72. percentil av 50 peers, median 362,4 kr.
    Fasit for fransk rødvin: median ~705 kr (aktive), percentil ~0,50.
    """
    from statistics import median

    from tools import polet_store
    from tools.value_score import _peer_percentile, compute_value_score

    wine = polet_store.lookup("15690101")  # Les Griffons de Pichon Baron 2020
    if wine is None:
        pytest.skip("15690101 finnes ikke i snapshotet")
    price = wine["price"]["value"]

    prices = sorted(
        (r["price"]["value"]
         for r in polet_store.query(category="rødvin", country="frankrike")
         if polet_store.is_active(r) and (r.get("price") or {}).get("value")
         and r.get("code") != wine["code"])
    )
    peer = _peer_percentile(wine)

    assert peer["sample_size"] == len(prices) > 1000
    assert peer["median_price"] == round(median(prices), 1)
    assert peer["percentile"] == round(sum(1 for v in prices if v < price) / len(prices), 2)
    # Den samlede fasiten: en helt gjennomsnittlig priset vin skal ligge på medianen.
    assert abs(peer["percentile"] - 0.5) < 0.1, (
        f"percentil {peer['percentile']} — B1 ga 0.72 for denne vinen"
    )

    # Tallet brukeren faktisk leser skal være populasjonen, ikke et utvalg av den.
    summary = compute_value_score(
        wine, fetch_vivino=False, fetch_aperitif=False, use_cache=False
    )["summary"]
    assert f"av {peer['sample_size']} peers" in summary


def test_inactive_peers_are_excluded_and_declared(monkeypatch, tmp_path):
    """Utgåtte varer er ikke en hylle — de skal ut av prissammenligningen."""
    from tools.value_score import _peer_percentile

    catalog = _peer_catalog(10) + [
        dict(row, code=f"8{i:07d}", status="utgatt", price={"value": 1.0})
        for i, row in enumerate(_peer_catalog(20)[1:], start=1)
    ]
    _write_snapshot(monkeypatch, tmp_path, generated_at="2026-08-29T00:00:00+00:00",
                    catalog=catalog)

    peer = _peer_percentile(_OWN)

    assert peer["sample_size"] == 10, "utgåtte/utsolgte varer skal ikke telle som peers"
    assert "status:aktiv" in peer["peer_terms"]
    assert peer["median_price"] > 1.0, "1-krones utgåtte rader dro medianen ned"


def test_thin_active_pool_falls_back_to_full_population(monkeypatch, tmp_path):
    """Færre enn 5 aktive peers: bruk hele populasjonen, og si fra at du gjorde det."""
    from tools.value_score import _peer_percentile

    catalog = _peer_catalog(3) + [
        dict(row, code=f"8{i:07d}", status="utgatt")
        for i, row in enumerate(_peer_catalog(6)[1:], start=1)
    ]
    _write_snapshot(monkeypatch, tmp_path, generated_at="2026-08-29T00:00:00+00:00",
                    catalog=catalog)

    peer = _peer_percentile(_OWN)

    assert peer["sample_size"] == 9, "tynn aktiv-pool skal falle tilbake til hele populasjonen"
    assert "status:alle" in peer["peer_terms"], "grunnlaget skal alltid være erklært"


def test_tiny_pool_gives_no_percentile(monkeypatch, tmp_path):
    """3 peers er ikke en median. Da skal funksjonen tie, ikke gjette."""
    from tools.value_score import _peer_percentile

    _write_snapshot(monkeypatch, tmp_path, generated_at="2026-08-29T00:00:00+00:00",
                    catalog=_peer_catalog(3))

    assert _peer_percentile(_OWN) is None


def test_peer_median_does_not_drift_from_population_median(real_catalog):
    """A1 fanger at *for få* ble sett. Denne fanger at *de gale* ble sett.

    B1 tok de 50 laveste varenumrene, og de er systematisk billigere enn
    gruppen de skulle representere: peer-medianen for fransk rødvin var 362 kr
    mot 720 kr sant — halvparten. Et utvalg kan være stort nok og likevel
    skjevt, så sample_size alene er ikke nok.

    Terskelen er 15 %, målt og ikke gjettet. På pools ≥ 100 viner:
      · med B1: frankrike −49,7 %, usa −31,6 %, italia −11,7 %
      · med fiksen: største avvik 4,2 % (italia), fransk rødvin −2,1 %
    Restavviket er aktiv-filteret — utgåtte varer er marginalt dyrere enn
    aktive, så medianen faller litt når de tas ut. Det er en forklart,
    ensifret forskyvning, ikke et artefakt.

    Merk: en assertion på *fortegn* ville feilet på riktig kode. 9 av 11 store
    pools peker samme vei etter fiksen (aktiv-filteret er ensrettet); det er
    magnituden, ikke retningen, som skiller 2 % fra 50 %.
    """
    from statistics import median

    from tools import polet_store
    from tools.value_score import _peer_percentile

    pools: dict = {}
    for p in real_catalog:
        key = ((p.get("main_category") or {}).get("code"),
               (p.get("main_country") or {}).get("code"))
        pools.setdefault(key, []).append(p)

    checked = 0
    for (category, country), rows in pools.items():
        if not category:
            continue
        wine = next((r for r in rows if (r.get("price") or {}).get("value")), None)
        if wine is None:
            continue
        full = [
            r["price"]["value"] for r in rows
            if r.get("code") != wine.get("code") and (r.get("price") or {}).get("value")
        ]
        if len(full) < 100:
            continue  # under dette er utvalgsstøy større enn signalet vi ser etter
        peer = _peer_percentile(wine)
        if peer is None or "percentile" not in peer:
            continue

        drift = abs(peer["median_price"] / median(full) - 1)
        assert drift < 0.15, (
            f"{category}/{country}: peer-median {peer['median_price']} kr mot "
            f"populasjonens {round(median(full), 1)} kr ({drift:.0%} avvik) — "
            "utvalget er skjevt, ikke bare lite."
        )
        checked += 1

    assert checked >= 5, f"Bare {checked} store pools testet — snapshotet ser feil ut"


# ─── B7: samme vin på flere varenumre til ulik pris (2026-08-31) ──────

def _rad(code, navn, pris, vol=75.0, utvalg="Bestillingsutvalget", status="aktiv"):
    return {
        "code": code, "name": navn, "status": status,
        "price": {"value": pris}, "volume": {"value": vol},
        "product_selection": utvalg,
        "main_category": {"name": "Rødvin", "code": "rodvin"},
        "main_country": {"name": "Frankrike", "code": "frankrike"},
    }


def test_billigere_duplikat_finner_samme_vin_til_lavere_pris(monkeypatch):
    """Beychevelle 2019 lå 2026-08-31 på 1 199,90 OG 2 188,90 samtidig."""
    from tools import value_score

    katalog = [_rad("A", "Ch. Beychevelle 2019", 2188.9),
               _rad("B", "Ch. Beychevelle 2019", 1199.9)]
    monkeypatch.setattr(value_score.polet_store, "query", lambda **k: katalog)

    funn = value_score.billigere_duplikat(katalog[0])
    assert funn["varenummer"] == "B"
    assert funn["du_sparer"] == 989.0
    # Asymmetrisk: den billigste raden har ingenting billigere å peke på.
    assert value_score.billigere_duplikat(katalog[1]) is None


def test_ulikt_volum_er_ikke_samme_flaske(monkeypatch):
    """Uten volum-porten sammenlignes 375 ml med 750 ml."""
    from tools import value_score

    katalog = [_rad("A", "Ch. Beychevelle 2019", 2188.9, vol=75.0),
               _rad("B", "Ch. Beychevelle 2019", 1199.9, vol=37.5)]
    monkeypatch.setattr(value_score.polet_store, "query", lambda **k: katalog)
    assert value_score.billigere_duplikat(katalog[0]) is None


def test_spesialutvalget_er_ikke_en_prisfeil(monkeypatch):
    """Polets auksjonskanal — separate partier til ulik pris er forventet.

    468 av 792 duplikatrader lå der 2026-08-31; uten porten ville de dominert
    funnene med noe som ikke er en feil.
    """
    from tools import value_score

    katalog = [_rad("A", "Ch. Beychevelle 2019", 2188.9),
               _rad("B", "Ch. Beychevelle 2019", 1199.9, utvalg="Spesialutvalget")]
    monkeypatch.setattr(value_score.polet_store, "query", lambda **k: katalog)
    assert value_score.billigere_duplikat(katalog[0]) is None
