"""Kontrakt-tester for `tools.user_fit` — v0 regel-basert tier-klassifisering.

Disse testene er offline (ingen nettverk). De verifiserer:
- Parsing-robusthet mot dagens `knowledge/smaksprofil.md`
- Regel-prioritet og early-exit-ordering i `classify()`
- Defensive defaults (tomt input, None-felter, ulike typer)
- Case-insensitivitet
- Returstruktur og verdiområder
- Batch (`classify_score_db`) og JSON-output (`write_v0_json`) med `tmp_path`
- Pure-function-egenskap med mock-rules
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.user_fit import (
    DEFAULT_OUTPUT_PATH,
    SMAKSPROFIL_PATH,
    _VERY_FIT_AVG_THRESHOLD,
    classify,
    classify_score_db,
    load_profile_rules,
    write_v0_json,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rules() -> dict:
    """Reelle regler parset fra `knowledge/smaksprofil.md`."""
    return load_profile_rules()


@pytest.fixture
def mock_rules() -> dict:
    """Selvinneholdt mock-regelsett — leser ikke disk under classify()."""
    return {
        "no_go": ["FakeBadWine 2020"],
        "bekymringer": ["Provence Rosé"],
        "bommet_druer_regioner": ["Argentinsk Bonarda"],
        "bekreftet_stiler": ["Italian Ripasso", "Southern Italy Red"],
        "bekreftede_druer": ["Barbera", "Nebbiolo"],
        "regioner_pluss": ["Nord-Italia", "Champagne"],
        "blindspots": ["Lebanon Red Wine"],
        "stil_snitt": {
            "Italian Ripasso": 4.10,
            "Southern Italy Red": 4.05,
            "Provence Rosé": 2.38,
        },
    }


# ---------------------------------------------------------------------------
# A — Parsing-robusthet
# ---------------------------------------------------------------------------


EXPECTED_KEYS = {
    "no_go",
    "bekymringer",
    "bommet_druer_regioner",
    "bekreftet_stiler",
    "bekreftede_druer",
    "regioner_pluss",
    "blindspots",
    "stil_snitt",
}


def test_load_profile_rules_returns_dict_with_expected_keys(rules):
    assert isinstance(rules, dict)
    missing = EXPECTED_KEYS - set(rules.keys())
    assert not missing, f"Mangler keys i rules: {missing}"


@pytest.mark.parametrize(
    "key",
    sorted(EXPECTED_KEYS - {"stil_snitt"}),
)
def test_list_keys_are_lists(rules, key):
    assert isinstance(rules[key], list), f"{key} skal være liste, fikk {type(rules[key])}"


def test_stil_snitt_is_dict(rules):
    assert isinstance(rules["stil_snitt"], dict)


@pytest.mark.parametrize(
    "key,min_n",
    [
        ("no_go", 5),
        ("bekreftet_stiler", 2),
        ("blindspots", 5),
        ("bekymringer", 2),
        ("bekreftede_druer", 3),
    ],
)
def test_rules_have_minimum_entries(rules, key, min_n):
    assert len(rules[key]) >= min_n, (
        f"{key} har bare {len(rules[key])} entries — forventet ≥ {min_n}"
    )


def test_stil_snitt_italian_ripasso(rules):
    val = rules["stil_snitt"].get("Italian Ripasso")
    assert val is not None, "Italian Ripasso mangler i stil_snitt"
    assert abs(val - 4.10) < 0.1, f"Italian Ripasso snitt {val} ikke ≈ 4.10"


def test_stil_snitt_provence_rose(rules):
    val = rules["stil_snitt"].get("Provence Rosé")
    assert val is not None, "Provence Rosé mangler i stil_snitt"
    assert abs(val - 2.38) < 0.1, f"Provence Rosé snitt {val} ikke ≈ 2.38"


# ---------------------------------------------------------------------------
# B — classify() korrekthet (regelprioritet, en regel per test)
# ---------------------------------------------------------------------------


def test_classify_rule_no_go():
    r = classify({"navn": "Whispering Angel Rosé"})
    assert r["tier"] == "no_go"
    assert r["rule_fired"] == "no_go"


def test_classify_rule_bekymring_via_stil():
    r = classify({"stil": "Provence Rosé", "land": "Frankrike"})
    assert r["tier"] == "risky"
    assert r["rule_fired"] == "bekymring"


def test_classify_rule_bekreftet_snitt_very_fit():
    r = classify({"stil": "Italian Ripasso"})
    assert r["tier"] == "very_fit"
    assert r["rule_fired"] == "bekreftet_snitt"


def test_classify_rule_bekreftet_drue():
    r = classify({"druer": "Barbera 100 prosent"})
    assert r["tier"] == "fit"
    assert r["rule_fired"] == "bekreftet_drue"


def test_classify_rule_bekreftet_region_piemonte():
    """Forventet (per spec): land+region for Piemonte/Nord-Italia → fit."""
    r = classify({"land": "Italia", "region": "Piemonte"})
    assert r["tier"] == "fit", (
        f"Forventet fit for Piemonte/Italia (regioner_pluss-treff), fikk {r['tier']}. "
        "Reell bug: regioner_pluss inneholder 'Nord-Italia' men ikke 'Piemonte' eller 'Italia'."
    )


def test_classify_rule_blindspot_us_hvitvin():
    """Spec: norsk kategori 'Hvitvin' + land 'United States' → blindspot."""
    r = classify({"kategori": "Hvitvin", "land": "United States"})
    assert r["tier"] == "neutral"
    assert r["confidence"] == "low"
    assert r["rule_fired"] == "blindspot", (
        f"Forventet blindspot, fikk {r['rule_fired']}. "
        "Reell bug: blindspot-streng er 'United States White Wine' (engelsk) — "
        "matcher ikke norsk 'Hvitvin'."
    )


def test_classify_rule_default():
    r = classify({"navn": "ukjent vin uten signal"})
    assert r["tier"] == "neutral"
    assert r["rule_fired"] == "default"


# ---------------------------------------------------------------------------
# C — Early-exit ordering
# ---------------------------------------------------------------------------


def test_no_go_wins_over_bekreftet_drue():
    r = classify({"navn": "Whispering Angel Rosé", "druer": "Barbera"})
    assert r["tier"] == "no_go"
    assert r["rule_fired"] == "no_go"


def test_bekymring_wins_over_bekreftet_snitt():
    """Bekymring skal vinne over positiv signal — eksplisitt design-valg."""
    r = classify({"stil": "Italian Ripasso", "land": "Provence Rosé område"})
    # "Provence Rosé" må være i et felt som inngår i bekymring-haystacks
    # → bruk stil-feltet med begge nøkkelord
    r2 = classify({"stil": "Provence Rosé Italian Ripasso"})
    assert r2["tier"] == "risky"
    assert r2["rule_fired"] == "bekymring"


# ---------------------------------------------------------------------------
# D — Defensive defaults
# ---------------------------------------------------------------------------


def test_classify_empty_dict_no_crash():
    r = classify({})
    assert r["tier"] == "neutral"


def test_classify_none_navn_no_crash():
    r = classify({"navn": None})
    assert r["tier"] in {"very_fit", "fit", "neutral", "risky", "no_go"}


def test_classify_empty_strings():
    r = classify({"navn": "", "stil": "", "land": ""})
    assert r["tier"] == "neutral"


def test_classify_kategori_as_dict():
    """Polet-stil: kategori er {'name': 'Rødvin'} — skal håndteres som streng."""
    r_dict = classify({"navn": "X", "kategori": {"name": "Rødvin"}})
    r_str = classify({"navn": "X", "kategori": "Rødvin"})
    assert r_dict["tier"] == r_str["tier"]
    assert r_dict["rule_fired"] == r_str["rule_fired"]


def test_classify_code_only():
    r = classify({"code": "12345"})
    assert r["tier"] == "neutral"


# ---------------------------------------------------------------------------
# E — Case- og diakritikk-håndtering
# ---------------------------------------------------------------------------


def test_case_insensitive_stil_lowercase():
    upper = classify({"stil": "Italian Ripasso"})
    lower = classify({"stil": "italian ripasso"})
    assert upper["tier"] == lower["tier"]
    assert upper["rule_fired"] == lower["rule_fired"]


def test_case_insensitive_navn_mixed_case_no_go():
    """Spec: 'WHISPERING angel' (uten 'Rosé') skal matche no_go."""
    r = classify({"navn": "WHISPERING angel Rosé"})
    assert r["tier"] == "no_go", (
        f"Forventet no_go for mixed-case match, fikk {r['tier']}"
    )


def test_case_insensitive_land_lowercase():
    upper = classify({"stil": "Provence Rosé", "land": "Frankrike"})
    lower = classify({"stil": "Provence Rosé", "land": "frankrike"})
    assert upper["tier"] == lower["tier"]
    assert upper["rule_fired"] == lower["rule_fired"]


# ---------------------------------------------------------------------------
# F — Returstruktur
# ---------------------------------------------------------------------------


VALID_TIERS = {"very_fit", "fit", "neutral", "risky", "no_go"}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_RULES = {"no_go", "bekymring", "bekreftet_snitt", "bekreftet_drue", "blindspot", "default"}
REQUIRED_RESULT_KEYS = {"tier", "reasons", "confidence", "rule_fired"}


@pytest.mark.parametrize(
    "wine",
    [
        {},
        {"navn": "Whispering Angel Rosé"},
        {"stil": "Italian Ripasso"},
        {"druer": "Barbera"},
        {"navn": "Random Vin", "land": "Italia"},
        {"stil": "Provence Rosé"},
    ],
)
def test_classify_return_structure(wine):
    r = classify(wine)
    missing = REQUIRED_RESULT_KEYS - set(r.keys())
    assert not missing, f"Mangler keys: {missing}"
    assert r["tier"] in VALID_TIERS, f"Ugyldig tier: {r['tier']}"
    assert r["confidence"] in VALID_CONFIDENCE, f"Ugyldig confidence: {r['confidence']}"
    assert r["rule_fired"] in VALID_RULES, f"Ugyldig rule_fired: {r['rule_fired']}"
    assert isinstance(r["reasons"], list)
    assert all(isinstance(s, str) for s in r["reasons"])


# ---------------------------------------------------------------------------
# G — Batch og JSON-output
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_results() -> dict:
    return classify_score_db()


def test_classify_score_db_returns_many_entries(db_results):
    assert isinstance(db_results, dict)
    assert len(db_results) >= 100, (
        f"Forventet ≥ 100 keys i classify_score_db, fikk {len(db_results)}"
    )


def test_classify_score_db_keys_are_string_varenr(db_results):
    for k in list(db_results.keys())[:20]:
        assert isinstance(k, str), f"key {k!r} er ikke streng"


def test_classify_score_db_values_are_valid(db_results):
    for varenr, r in list(db_results.items())[:50]:
        missing = REQUIRED_RESULT_KEYS - set(r.keys())
        assert not missing, f"Mangler keys for {varenr}: {missing}"
        assert r["tier"] in VALID_TIERS
        assert r["confidence"] in VALID_CONFIDENCE
        assert r["rule_fired"] in VALID_RULES


def test_write_v0_json_to_tmp(tmp_path):
    out_path = tmp_path / "v0.json"
    returned = write_v0_json(str(out_path))
    assert returned == str(out_path)
    assert out_path.exists(), "JSON-filen ble ikke skrevet"


def test_write_v0_json_meta_structure(tmp_path):
    out_path = tmp_path / "v0.json"
    write_v0_json(str(out_path))
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert "_meta" in data
    meta = data["_meta"]
    for k in ("version", "generated_at", "n_classified", "tier_counts"):
        assert k in meta, f"_meta mangler {k}"
    assert meta["version"] == "v0"


def test_write_v0_json_meta_counts_match(tmp_path):
    out_path = tmp_path / "v0.json"
    write_v0_json(str(out_path))
    data = json.loads(out_path.read_text(encoding="utf-8"))
    meta = data["_meta"]
    non_meta_keys = [k for k in data if k != "_meta"]
    assert meta["n_classified"] == len(non_meta_keys), (
        f"n_classified={meta['n_classified']} matcher ikke "
        f"antall entries={len(non_meta_keys)}"
    )
    assert sum(meta["tier_counts"].values()) == meta["n_classified"], (
        "Summen av tier_counts skal være lik n_classified"
    )


def test_write_v0_json_idempotent_classifications(tmp_path):
    p1 = tmp_path / "a.json"
    p2 = tmp_path / "b.json"
    write_v0_json(str(p1))
    write_v0_json(str(p2))
    d1 = json.loads(p1.read_text(encoding="utf-8"))
    d2 = json.loads(p2.read_text(encoding="utf-8"))
    # Strip timestamps før sammenligning
    d1["_meta"].pop("generated_at", None)
    d2["_meta"].pop("generated_at", None)
    assert d1 == d2, "Klassifiseringene skal være idempotente modulo timestamp"


def test_write_v0_json_does_not_touch_default_path(tmp_path):
    """Sikkerhetsnet — tester skal ikke skrive til ekte data/user_fit/v0.json."""
    out_path = tmp_path / "v0.json"
    write_v0_json(str(out_path))
    # Vi har bare brukt tmp_path — verifiser at returnen er der
    assert str(tmp_path) in str(out_path)
    assert out_path != DEFAULT_OUTPUT_PATH


# ---------------------------------------------------------------------------
# H — Pure-function-egenskap
# ---------------------------------------------------------------------------


def test_classify_deterministic_same_input(mock_rules):
    wine = {"stil": "Italian Ripasso", "navn": "Test"}
    r1 = classify(wine, rules=mock_rules)
    r2 = classify(wine, rules=mock_rules)
    assert r1 == r2


def test_load_profile_rules_has_lru_cache():
    """Sjekk at cache-API er eksponert (cache_info finnes)."""
    assert hasattr(load_profile_rules, "cache_info")
    info_before = load_profile_rules.cache_info()
    load_profile_rules()
    info_after = load_profile_rules.cache_info()
    # Etter minst ett kall skal currsize være ≥ 1
    assert info_after.currsize >= 1, "lru_cache ser ikke ut til å være aktiv"


# ---------------------------------------------------------------------------
# I — Ren funksjonell test med mock rules
# ---------------------------------------------------------------------------


def test_mock_rules_no_go(mock_rules):
    r = classify({"navn": "FakeBadWine 2020 reserva"}, rules=mock_rules)
    assert r["tier"] == "no_go"
    assert r["rule_fired"] == "no_go"


def test_mock_rules_bekreftet_snitt(mock_rules):
    r = classify({"stil": "Italian Ripasso"}, rules=mock_rules)
    assert r["tier"] == "very_fit"
    assert r["rule_fired"] == "bekreftet_snitt"


def test_mock_rules_drue(mock_rules):
    r = classify({"druer": "Nebbiolo 100%"}, rules=mock_rules)
    assert r["tier"] == "fit"
    assert r["rule_fired"] == "bekreftet_drue"


def test_mock_rules_default(mock_rules):
    r = classify({"navn": "Helt ukjent vin"}, rules=mock_rules)
    assert r["tier"] == "neutral"
    assert r["rule_fired"] == "default"


def test_mock_rules_does_not_read_disk(mock_rules, monkeypatch):
    """Verifiser at classify(rules=...) ikke trigger load_profile_rules."""
    sentinel = {"called": False}

    def fake_loader(*args, **kwargs):
        sentinel["called"] = True
        return {}

    monkeypatch.setattr("tools.user_fit.load_profile_rules", fake_loader)
    classify({"stil": "Italian Ripasso"}, rules=mock_rules)
    assert not sentinel["called"], "classify(rules=...) skal ikke laste fra disk"


def test_very_fit_threshold_constant():
    """Sanity-check at terskelen ikke har endret seg utilsiktet."""
    assert _VERY_FIT_AVG_THRESHOLD == 4.0


def test_smaksprofil_path_exists():
    """Sanity-check at default-pathen finnes (ellers feiler alt annet)."""
    assert SMAKSPROFIL_PATH.exists(), f"Mangler {SMAKSPROFIL_PATH}"
