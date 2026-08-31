"""Tester for tools.aperitif — varenummer-parsing fra Aperitifs produktside.

Bakgrunn (funnet 2026-08-31): `_parse_product_page` matchet varenummer med
`\\d{7,8}` og bommet derfor på alle 5- og 6-sifrede varenumre. Konsekvensen var
ikke bare «score mangler»: uten `polet_id` feiler både årgangs-verifiseringen i
pass 1 og stale-sjekken på et mapping-treff i `get_aperitif_score`, så de vinene
fikk `vintage_mismatch=True` selv når siden gjaldt akkurat den vinen — altså en
usann påstand videre til brukeren via CLAUDE.md steg 6.

Testene er innholdsbaserte: de går på lengde-klassene i den faktiske katalogen,
ikke på spesifikke varenumre, slik at de overlever nye slipp.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.aperitif import _parse_product_page


REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG = REPO_ROOT / "data" / "polet" / "catalog.ndjson"


def _jsonld_page(sku: str) -> str:
    """Minimal produktside slik Aperitif rendrer den: JSON-LD med sku."""
    return (
        '<html><head><script type="application/ld+json">'
        '{"@type":"Product","name":"Testvin","sku":"' + sku + '",'
        '"aggregateRating":{"ratingValue":"88"}}'
        "</script></head><body>"
        '<h1>Testvin 2022</h1>'
        '<span class="number">88</span> <span class="label">POENG</span>'
        "</body></html>"
    )


def _prose_page(sku: str) -> str:
    """Produktside uten JSON-LD — varenummeret står bare i prosaen."""
    return (
        "<html><body><h1>Testvin 2022</h1>"
        f"<p>Varenummer: {sku}</p>"
        '<span class="number">88</span> <span class="label">POENG</span>'
        "</body></html>"
    )


# ─── Lengde-klassene som fantes i katalogen 2026-08-31 ───────────────
# 5 siffer: 44 varer · 6: 543 · 7: 4 302 · 8: 22 513
@pytest.mark.parametrize("sku", ["63701", "101801", "1002101", "10002501"])
def test_parses_varenummer_of_every_length_from_jsonld(sku):
    assert _parse_product_page(_jsonld_page(sku))["polet_id"] == sku


@pytest.mark.parametrize("sku", ["63701", "101801", "1002101", "10002501"])
def test_parses_varenummer_of_every_length_from_prose(sku):
    assert _parse_product_page(_prose_page(sku))["polet_id"] == sku


def test_every_length_class_in_the_real_catalog_is_parseable():
    """Regresjonsvern: dukker det opp en ny lengde-klasse i katalogen, skal
    denne testen falle — ikke Aperitif-oppslaget, stille."""
    lengths = set()
    with CATALOG.open(encoding="utf-8") as fh:
        for line in fh:
            lengths.add(len(json.loads(line)["code"]))
    assert lengths, "katalogen er tom — testen måler ingenting"
    for length in sorted(lengths):
        sku = "1" + "0" * (length - 1)
        parsed = _parse_product_page(_jsonld_page(sku))
        assert parsed.get("polet_id") == sku, (
            f"varenumre med {length} siffer finnes i katalogen "
            f"({sorted(lengths)}) men parses ikke"
        )


# ─── Grensene skal fortsatt holde ────────────────────────────────────

def test_nine_digit_sku_is_rejected_not_truncated():
    """Uten `(?!\\d)` ville `\\d{5,8}` tatt de åtte første sifrene og levert et
    varenummer som ser gyldig ut, men peker på en annen vin."""
    assert "polet_id" not in _parse_product_page(_jsonld_page("123456789"))


def test_four_digit_sku_is_rejected():
    assert "polet_id" not in _parse_product_page(_jsonld_page("1234"))


def test_score_is_parsed_independently_of_varenummer():
    """Score og varenummer er to uavhengige uttrekk — en side uten sku skal
    fortsatt gi score."""
    page = (
        "<html><body><h1>Testvin</h1>"
        '<span class="number">91</span> <span class="label">POENG</span>'
        "</body></html>"
    )
    parsed = _parse_product_page(page)
    assert parsed["score"] == 91
    assert "polet_id" not in parsed


# ─── Snapshotet i data/aperitif/ ─────────────────────────────────────
# Sveipen (tools/refresh_aperitif.py) gir varenummer → poeng for hele den
# scorede delen av Pollisten. Den listen bærer IKKE «godt kjøp»-flagget, som
# kortslutter `_value_verdict` i value_score. Derfor er snapshotet fallback og
# bulk-kilde, ikke et lag foran nettverket — og disse testene fester nettopp
# det skillet.

import tools.aperitif as ap


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    """Legg et snapshot med én vin på plass, og nullstill modul-cachen."""
    rows = tmp_path / "scores.ndjson"
    rows.write_text(
        json.dumps(
            {
                "polet_id": "12345601",
                "score": 91,
                "wine_name": "Snapshotvin",
                "aperitif_url": "https://www.aperitif.no/pollisten/produkt/x,1",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"generated_at": "2026-08-31T12:00:00"}), encoding="utf-8")
    monkeypatch.setattr(ap, "SNAPSHOT", rows)
    monkeypatch.setattr(ap, "SNAPSHOT_META", meta)
    monkeypatch.setattr(ap, "_SNAPSHOT_CACHE", None)
    return rows


def _no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("skulle ikke gjort HTTP-kall")
    monkeypatch.setattr(ap, "_http_get", boom)


def test_snapshot_score_reads_varenummer_without_network(snapshot, monkeypatch):
    _no_network(monkeypatch)
    r = ap.snapshot_score("12345601")
    assert r["score"] == 91
    assert r["source"] == "snapshot"
    assert r["fetched_at"] == "2026-08-31T12:00:00"


def test_snapshot_never_claims_a_buy_flag(snapshot):
    """Listesiden har ikke flagget — snapshotet skal ikke late som."""
    assert ap.snapshot_score("12345601")["value_flag"] is None


def test_snapshot_miss_is_none(snapshot):
    assert ap.snapshot_score("99999999") is None


def test_offline_uses_snapshot_only(snapshot, monkeypatch):
    _no_network(monkeypatch)
    assert ap.get_aperitif_score("12345601", offline=True)["score"] == 91
    assert ap.get_aperitif_score("11111101", offline=True) is None


def test_lookup_without_a_name_falls_back_to_snapshot(snapshot, monkeypatch):
    """Uten navn finner slug-matchingen ingenting — snapshotet gjør det."""
    monkeypatch.setattr(ap, "_get_score_cache", lambda pid: None)
    monkeypatch.setattr(ap, "_load_mapping", lambda: {})
    r = ap.get_aperitif_score("12345601")
    assert r["score"] == 91 and r["source"] == "snapshot"


def test_exhausted_url_candidates_fall_back_to_snapshot(snapshot, monkeypatch):
    """
    Navnet gir kandidater, men ingen av sidene har verken riktig varenummer
    eller poeng. Før snapshotet var svaret None — nå finnes poenget likevel.
    """
    monkeypatch.setattr(ap, "_get_score_cache", lambda pid: None)
    monkeypatch.setattr(ap, "_load_mapping", lambda: {})
    monkeypatch.setattr(ap, "_save_mapping", lambda m: None)
    monkeypatch.setattr(ap, "_find_url_candidates", lambda name, **k: ["https://x/1"])
    monkeypatch.setattr(
        ap, "_http_get", lambda url, timeout=15: "<html><body><h1>Feil vin</h1></body></html>"
    )
    r = ap.get_aperitif_score("12345601", "Snapshotvin")
    assert r["score"] == 91 and r["source"] == "snapshot"


def test_dead_mapping_url_falls_back_to_snapshot(snapshot, monkeypatch):
    """Kjent URL, men siden svarer ikke (nede/blokkert)."""
    monkeypatch.setattr(ap, "_get_score_cache", lambda pid: None)
    monkeypatch.setattr(ap, "_load_mapping", lambda: {"12345601": "https://x/1"})
    monkeypatch.setattr(ap, "_http_get", lambda url, timeout=15: None)
    r = ap.get_aperitif_score("12345601", "Snapshotvin")
    assert r["score"] == 91 and r["source"] == "snapshot"


def test_wrong_vintage_page_loses_to_the_exact_snapshot_row(snapshot, monkeypatch):
    """
    Pass 2 returnerer en side for en ANNEN årgang. Poeng og flagg der tilhører
    en annen vin, mens snapshotraden er matchet på varenummer.
    """
    other_vintage_page = (
        "<html><body><h1>Snapshotvin 1999</h1>"
        '<span class="number">77</span> <span class="label">POENG'
        "</span><p>Veldig godt kjøp</p></body></html>"
    )
    monkeypatch.setattr(ap, "_get_score_cache", lambda pid: None)
    monkeypatch.setattr(ap, "_set_score_cache", lambda pid, v: None)
    monkeypatch.setattr(ap, "_load_mapping", lambda: {})
    monkeypatch.setattr(ap, "_save_mapping", lambda m: None)
    monkeypatch.setattr(ap, "_find_url_candidates", lambda name, **k: ["https://x/y"])
    monkeypatch.setattr(ap, "_http_get", lambda url, timeout=15: other_vintage_page)

    r = ap.get_aperitif_score("12345601", "Snapshotvin")
    assert r["score"] == 91
    assert r["vintage_mismatch"] is False
    assert r["value_flag"] is None


def test_missing_snapshot_file_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "SNAPSHOT", tmp_path / "finnes-ikke.ndjson")
    monkeypatch.setattr(ap, "_SNAPSHOT_CACHE", None)
    assert ap.snapshot_score("12345601") is None
