"""Kontrakt-tester for øl-fit (`tools.beer_fit`).

Alle offline. Regel-tester bruker en konstruert `mock_stats`-dict (deterministisk,
uavhengig av CSV-innhold). Smoke-tester kjører mot ekte Untappd-data og sjekker
invarianter, ikke eksakte verdier.
"""

from __future__ import annotations

import pytest

from tools import beer_fit


VALID_TIERS = {"very_fit", "fit", "neutral", "risky", "no_go"}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_RULES = {
    "no_go", "bekymring", "bekreftet_snitt", "bekreftet_familie",
    "blindspot", "default", "ingen_data",
}
REQUIRED_KEYS = {"tier", "reasons", "confidence", "rule_fired", "n", "snitt"}


@pytest.fixture
def mock_stats() -> dict[str, dict]:
    return {
        "Lambic / Gueuze / Wild": {"n": 4, "snitt": 3.88, "snitt_recent": 4.25},  # very_fit
        "Sur (Berliner / Gose / Sour)": {"n": 2, "snitt": 4.0, "snitt_recent": None},  # fit (n<3)
        "Pilsner": {"n": 8, "snitt": 2.97, "snitt_recent": None},  # risky
        "Stout (standard)": {"n": 9, "snitt": 3.61, "snitt_recent": None},  # default
        "Rauchbier / Smoked": {"n": 1, "snitt": 4.5, "snitt_recent": None},  # blindspot (low!)
    }


# ---------------------------------------------------------------------------
# Regel-korrekthet (én regel per test)
# ---------------------------------------------------------------------------


def test_very_fit_loosened_threshold(mock_stats):
    r = beer_fit.classify_family("Lambic / Gueuze / Wild", mock_stats)
    assert r["tier"] == "very_fit"
    assert r["rule_fired"] == "bekreftet_snitt"
    assert r["confidence"] == "high"


def test_fit_when_n_below_very_fit(mock_stats):
    # snitt 4.0 men n=2 < 3 → fit, ikke very_fit
    r = beer_fit.classify_family("Sur (Berliner / Gose / Sour)", mock_stats)
    assert r["tier"] == "fit"
    assert r["rule_fired"] == "bekreftet_familie"


def test_bekymring(mock_stats):
    r = beer_fit.classify_family("Pilsner", mock_stats)
    assert r["tier"] == "risky"
    assert r["rule_fired"] == "bekymring"
    assert r["confidence"] == "high"


def test_default(mock_stats):
    r = beer_fit.classify_family("Stout (standard)", mock_stats)
    assert r["tier"] == "neutral"
    assert r["rule_fired"] == "default"


def test_blindspot_never_very_fit_despite_high_avg(mock_stats):
    # n=1 snitt 4.5 → blindspot/neutral/low, ALDRI very_fit (anti-falsk-presisjon)
    r = beer_fit.classify_family("Rauchbier / Smoked", mock_stats)
    assert r["tier"] == "neutral"
    assert r["rule_fired"] == "blindspot"
    assert r["confidence"] == "low"


def test_unknown_family(mock_stats):
    r = beer_fit.classify_family("Ikke-eksisterende familie", mock_stats)
    assert r["tier"] == "neutral"
    assert r["rule_fired"] == "ingen_data"
    assert r["n"] == 0


# ---------------------------------------------------------------------------
# Returstruktur
# ---------------------------------------------------------------------------


def test_result_contract(mock_stats):
    for fam in mock_stats:
        r = beer_fit.classify_family(fam, mock_stats)
        assert REQUIRED_KEYS <= set(r)
        assert r["tier"] in VALID_TIERS
        assert r["confidence"] in VALID_CONFIDENCE
        assert r["rule_fired"] in VALID_RULES
        assert isinstance(r["reasons"], list) and r["reasons"]


def test_threshold_constants():
    # Løsnet very_fit-terskel (brukerbeslutning 2026-06-08)
    assert beer_fit._VERY_FIT_AVG_THRESHOLD == 3.85
    assert beer_fit._VERY_FIT_MIN_N == 3


# ---------------------------------------------------------------------------
# classify_beer-bro (Untappd-stil → familie)
# ---------------------------------------------------------------------------


def test_classify_beer_maps_style(mock_stats):
    r = beer_fit.classify_beer({"style": "Lambic - Gueuze"}, mock_stats)
    assert r["family"] == "Lambic / Gueuze / Wild"
    assert r["tier"] == "very_fit"


def test_classify_beer_empty_no_crash(mock_stats):
    r = beer_fit.classify_beer({}, mock_stats)
    assert r["tier"] in VALID_TIERS
    assert "family" in r


# ---------------------------------------------------------------------------
# Taksonomi-kontrakt
# ---------------------------------------------------------------------------


def test_canonical_families_unique_nonempty():
    assert beer_fit.CANONICAL_FAMILIES
    assert all(isinstance(f, str) and f for f in beer_fit.CANONICAL_FAMILIES)
    assert len(beer_fit.CANONICAL_FAMILIES) == len(set(beer_fit.CANONICAL_FAMILIES))


def test_classify_style_bridge_consistent():
    from tools.untappd_stats import classify_style
    assert classify_style("Belgian Tripel") == "Belgian Strong / Trappist"


# ---------------------------------------------------------------------------
# Artefakt-generering (mot ekte data + tmp_path)
# ---------------------------------------------------------------------------


def test_build_beer_v0_real_data():
    payload = beer_fit.build_beer_v0()
    assert payload["_meta"]["version"] == "beer_v0"
    n_fam = payload["_meta"]["n_families"]
    assert n_fam == sum(payload["_meta"]["tier_counts"].values())
    # Sekkepost ekskludert
    assert "Annet / uklassifisert" not in payload
    # Hver entry har n + snitt
    for k, v in payload.items():
        if k == "_meta":
            continue
        assert "n" in v and "snitt" in v
        assert v["tier"] in VALID_TIERS


def test_write_beer_v0_json_tmp(tmp_path):
    import json
    p = beer_fit.write_beer_v0_json(str(tmp_path / "beer_v0.json"))
    data = json.loads(open(p, encoding="utf-8").read())
    assert "_meta" in data and data["_meta"]["version"] == "beer_v0"


def test_load_family_stats_with_mock_rows():
    # Deterministisk: gi egne rader, sjekk at agg fungerer uten å lese disk
    rows = [
        {"_family": "Pilsner", "_rating": 3.0, "_dt": None},
        {"_family": "Pilsner", "_rating": 3.0, "_dt": None},
        {"_family": "Stout (standard)", "_rating": 4.0, "_dt": None},
    ]
    stats = beer_fit.load_family_stats(rows)
    assert stats["Pilsner"]["n"] == 2
    assert stats["Stout (standard)"]["snitt"] == 4.0
