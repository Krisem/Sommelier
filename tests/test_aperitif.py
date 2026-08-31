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
