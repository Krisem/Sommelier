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
VALID_RULES = {
    "no_go",
    "bekymring",
    "bekreftet_snitt",
    # Regel 4 var tidligere ett merke (`bekreftet_drue`) for tre ulike treff.
    # De 2 401 rene region-treffene på Polet-basen het også «bekreftet_drue»,
    # som gjorde forklaringen usann. Splittet 2026-08-30 (B4).
    "bekreftet_drue",
    "bekreftet_stil",
    "region_pluss",
    "blindspot",
    # Roadmap-prinsipp 4: en blindspot-vin får aldri `very_fit`, uansett
    # feature-sum. Da nedgraderes den til `fit` med dette merket.
    "blindspot_cap",
    "default",
}
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


# ---------------------------------------------------------------------------
# MÅLT MOT (les dette før du siterer et tall herfra)
#
#   data/polet/catalog.ndjson · 18 546 rader · md5 6f5302e8
#   Rødvin  13 776  fetched_at 2026-08-29T15:52  — komplett etter ADR-024-sveipen
#   Hvitvin  4 616  fetched_at 2026-08-30T15:53  — MIDT I EN SVEIP mot ~9 762
#   Musserende    144  fetched_at 2026-08-30           — sveipet
#   Rosévin        53  fetched_at 2026-06                — FØR SVEIP, mot ~782
#
# Katalogen flyttet seg mens dette ble skrevet: rødvin 1 543 → 13 776, hvitvin
# 152 → 9 765. Rosé har IKKE begynt. Alle assertions under er derfor formulert
# som ANDELER, ikke som tall — de holder ved 1 543 rader og ved 137 750.
# Ser du et absolutt tall om katalogen i en test her, er det en bug.
#
# ROSÉ: reglene for Provence-rosé (Bandol ut av «generisk») er skrevet og har
# regresjonstester, men treffantall for rosé er IKKE MÅLBART før sveipen har
# landet. Et tall målt på 53 juni-rader ville sett ut som et resultat.
# Etterverifisering er ført som egen post i `tasks/todo.md`.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# I — Skalainvariante assertions mot ekte katalogdata (B4/B5)
#
# Disse kjører mot `data/polet/catalog.ndjson`, ikke fixtures. Det er hele
# poenget: de 291 fixture-testene som fantes før fanget ingen av de seks
# buggene i `tasks/exploration/scenario_test_2026-08-30.md`, fordi de tester
# at funksjonene *regner riktig*, aldri at de *har sett hele datagrunnlaget*.
# ---------------------------------------------------------------------------

from collections import Counter  # noqa: E402

from tools.user_fit import (  # noqa: E402
    _KATEGORI_NO_TO_EN,
    _LAND_NO_TO_EN,
    _NO_MATCHERS,
    _UNTRANSLATED,
    _no_matcher_hit,
    _extract_wine_fields,
    classify_catalog,
    classify_code,
)

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "polet" / "catalog.ndjson"

# Regellistene som skal kunne treffe en Polet-rad. `stil_snitt` er en
# oppslags-tabell, ikke en matche-liste, og er derfor ikke med.
NEEDLE_KEYS = [
    "no_go",
    "bekymringer",
    "bommet_druer_regioner",
    "bekreftet_stiler",
    "bekreftede_druer",
    "regioner_pluss",
    "blindspots",
]


def _kan_bygges_generisk(needle: str) -> bool:
    """
    True for auto-deriverte «<Land> <Kategori>»-blindspots («Germany Red Wine»).

    Disse trenger ingen egen matcher: `classify` bygger den engelske strengen
    fra den norske raden via `_LAND_NO_TO_EN` + `_KATEGORI_NO_TO_EN`. Men
    begge halvdelene MÅ finnes i tabellene — mangler landet, fyrer regelen
    aldri, og det var nettopp derfor kun Chile/Portugal/Uruguay traff.
    """
    return any(
        needle == f"{land} {kat}"
        for land in set(_LAND_NO_TO_EN.values())
        for kat in set(_KATEGORI_NO_TO_EN.values())
    )


@pytest.fixture(scope="module")
def catalog() -> list[dict]:
    if not CATALOG_PATH.exists():
        pytest.skip(f"Snapshot mangler: {CATALOG_PATH}")
    rows = []
    for line in CATALOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    assert len(rows) > 1000, f"Snapshot ser avkortet ut: {len(rows)} rader"
    return rows


@pytest.fixture(scope="module")
def catalog_tiers() -> dict:
    """Hele katalogen klassifisert én gang (~1 s)."""
    if not CATALOG_PATH.exists():
        pytest.skip(f"Snapshot mangler: {CATALOG_PATH}")
    return classify_catalog()


# --- A4: hver regel er konfrontert med hele katalogen ----------------------


def test_every_needle_is_translated_or_documented(rules):
    """
    Hver needle skal enten ha en norsk katalog-matcher, stå i `_UNTRANSLATED`
    med begrunnelse, eller være et rent navn (no-go-liste, matches direkte).

    Dette er den generelle formen av B4: en regel som aldri kan fyre mot
    katalogen er enten feil eller død, og begge deler skal være et bevisst
    valg. Uten denne testen døde `bekymringer` stille da katalogen ble norsk.
    """
    udekket = []
    for key in NEEDLE_KEYS:
        if key == "no_go":
            continue  # konkrete vin-navn, matches på navn — ingen oversettelse
        for needle in rules[key]:
            if needle in _NO_MATCHERS or needle in _UNTRANSLATED:
                continue
            if key == "blindspots" and _kan_bygges_generisk(needle):
                continue
            udekket.append(f"{key}: {needle!r}")
    assert not udekket, (
        "Needles uten katalog-oversettelse og uten begrunnelse i _UNTRANSLATED:\n  "
        + "\n  ".join(udekket)
    )


def test_no_matchers_table_has_no_stale_entries(rules):
    """
    Motsatt retning: hver nøkkel i `_NO_MATCHERS` skal svare til en needle som
    faktisk står i profilen. Ellers vokser tabellen med oversettelser av regler
    som ikke lenger finnes, og ingen merker det.
    """
    alle = {n for key in NEEDLE_KEYS for n in rules[key]} | set(rules["stil_snitt"])
    foreldet = sorted(set(_NO_MATCHERS) - alle)
    assert not foreldet, f"_NO_MATCHERS har nøkler som ikke finnes i profilen: {foreldet}"


def test_untranslated_entries_have_reasons(rules):
    alle = {n for key in NEEDLE_KEYS for n in rules[key]}
    for needle, grunn in _UNTRANSLATED.items():
        assert needle in alle, f"_UNTRANSLATED: {needle!r} finnes ikke i profilen"
        assert len(grunn) > 20, f"_UNTRANSLATED: {needle!r} mangler reell begrunnelse"


def test_translated_needles_fire_against_catalog(rules, catalog):
    """
    En oversettelse som aldri treffer en eneste katalograd er sannsynligvis
    feil. Unntakene er needles der katalogen bare ikke fører varen — de skal
    stå eksplisitt her, ikke oppdages ved at testen er grønn.
    """
    # UNNTAK: needles der matcheren er riktig, men Polet ikke fører varen.
    # Lista er SELV-UTLØPENDE — en oppføring som faktisk treffer, feiler
    # testen under, så unntaket må fjernes når sortimentet endrer seg.
    # Den sto tom 2026-08-30 etter hvitvin-/musserende-sveipen: alle fire
    # tidligere unntak (Provence Rosé, Generisk Provence-rosé, English
    # Sparkling, Sør-Rhône hvit) fikk varer, og en unntaksliste ingen rydder
    # i er en sjekk som er grønn av feil grunn.
    UTEN_VARER: set[str] = set()
    felter = [_extract_wine_fields(p) for p in catalog]

    def _fyrer(needle: str) -> bool:
        return any(_no_matcher_hit(needle, f) is not None for f in felter)

    foreldet = sorted(n for n in UTEN_VARER if _fyrer(n))
    assert not foreldet, (
        f"Unntak i UTEN_VARER som faktisk treffer katalogen nå — fjern dem, "
        f"ellers undertrykker de sjekken: {foreldet}"
    )
    stille = [n for n in _NO_MATCHERS if n not in UTEN_VARER and not _fyrer(n)]
    assert not stille, (
        "Oversettelser som ikke treffer én eneste katalograd — enten feil "
        f"matcher eller en vare Polet ikke fører (legg i UTEN_VARER): {stille}"
    )


def test_warning_tiers_actually_fire(catalog_tiers):
    """
    B4 i én linje: 0 `risky` av 13 775 er ikke et gyldig utfall for et
    advarselssystem. Da har ADR-016s vern mot filterboble sluttet å virke,
    og systemet er stille optimistisk uten at noen valgte det.
    """
    counts = Counter(r["tier"] for r in catalog_tiers.values())
    assert counts["risky"] >= 1, "Ingen viner klassifiseres `risky` — advarselen er død"
    assert counts["very_fit"] >= 1, "Ingen viner klassifiseres `very_fit`"
    assert counts["fit"] >= 1
    assert counts["neutral"] >= 1


def test_no_go_rule_fires_on_exact_name(rules):
    """
    `no_go` fyrer 0 ganger på katalogen, og det er *riktig*: oppføringene
    bærer årgang («… Côtes du Rhône 2015») og Polet fører kun gjeldende
    årgang. Regelen testes derfor mot et eksakt navn, ikke mot frekvens.
    Samme vin i annen årgang skal bli `risky`, ikke stillhet — se under.
    """
    assert rules["no_go"], "no-go-listen er tom"
    r = classify({"navn": rules["no_go"][0]}, rules)
    assert r["tier"] == "no_go"
    assert r["rule_fired"] == "no_go"


def test_no_go_wine_in_other_vintage_is_risky(rules):
    """
    «Domaine de la Janasse Côtes du Rhône 2015» (2.0, brukerens laveste
    rødvin) står i katalogen som «Dom. de la Janasse Côtes du Rhône 2024».
    To namespace-forskjeller på én gang: forkortet produsent og ny årgang.
    Den skal advares om, ikke passere som ukjent terreng.
    """
    r = classify_code("3241501", rules)
    if r is None:
        pytest.skip("3241501 ikke i snapshot")
    assert r["tier"] == "risky"
    assert any("annen årgang" in x for x in r["reasons"]), r["reasons"]


def test_tier_distribution_is_not_degenerate(catalog_tiers):
    """
    Vaktpost mot begge ytterlighetene: den gamle fordelingen (83 % `neutral`,
    0 advarsler) og den motsatte overkorreksjonen (alt blir `risky`).
    Formulert som andel, så den holder ved enhver katalogstørrelse.
    """
    n = len(catalog_tiers)
    counts = Counter(r["tier"] for r in catalog_tiers.values())
    for tier, andel in ((t, counts[t] / n) for t in counts):
        assert andel <= 0.80, f"{tier} dekker {andel:.0%} av katalogen — degenerert"
    assert counts["risky"] / n <= 0.25, (
        f"risky dekker {counts['risky'] / n:.0%} — advarselen er blitt bakgrunnsstøy"
    )
    assert counts["very_fit"] / n <= 0.15, "very_fit skal være et sjeldent merke"


# --- B4-regresjoner: de konkrete tilfellene fra scenario-testen -----------


@pytest.mark.parametrize(
    "code,forventet_tier,hva",
    [
        # Repro fra scenario_test_2026-08-30.md § B4 — ga `neutral`/`default`.
        ("1013801", "risky", "Dom. Dupasquier Bourgogne Pinot Noir — «Billig Burgund»"),
        ("10614501", "very_fit", "Casteloro Valpolicella Ripasso — bekreftet stil"),
        ("10064801", "very_fit", "Benanti Etna Rosso — «Southern Italy Red»"),
        ("10100701", "fit", "Luigi Pira Barolo — Nebbiolo + Nord-Italia"),
        # Beaujolais ligger under Polets distrikt «Burgund», men er Gamay og
        # en egen Vivino-stil. Skal IKKE dras med av Burgundy Red-regelen.
        ("11020001", "neutral", "A. Sunier Beaujolais Morgon — ikke Burgundy Red"),
        # Nord-Rhône. Bekymringen gjelder Sør-Rhône; hele Rhône ville vært
        # den motsatte ytterligheten.
        ("10309901", "neutral", "Guy Farge Cornas — nord, ikke sør"),
    ],
)
def test_b4_regression_cases(rules, code, forventet_tier, hva):
    r = classify_code(code, rules)
    if r is None:
        pytest.skip(f"{code} ikke i snapshot")
    assert r["tier"] == forventet_tier, f"{hva}: fikk {r['tier']} ({r['reasons']})"


def test_cote_dor_burgundy_is_blindspot_not_bekymring(rules):
    """
    Brukerens tre Burgundy Red-ratings ligger alle på regionalt
    Bourgogne-nivå. Côte d'Or er derfor ikke en *bekymring* — det er fravær
    av data, og skal merkes som blindsone med lav konfidens, ikke som en
    advarsel profilen ikke har dekning for.
    """
    r = classify_code("10080701", rules)  # Marchand Tawse Gevrey-Chambertin
    if r is None:
        pytest.skip("10080701 ikke i snapshot")
    assert r["tier"] == "neutral"
    assert r["rule_fired"] == "blindspot"
    assert r["confidence"] == "low"


def test_blindspot_never_yields_very_fit(mock_rules):
    """
    Roadmap-prinsipp 4: «Blindspot-viner får aldri very_fit, uansett
    feature-summen.» Regel 3 lå før regel 5, så garantien var ikke
    implementert — den holdt bare fordi ingen kollisjon fantes i dataene.
    """
    r = classify(
        {"navn": "Testvin", "stil": "Italian Ripasso", "land": "Lebanon",
         "kategori": "Red Wine"},
        rules=mock_rules,
    )
    assert r["tier"] == "fit", r
    assert r["rule_fired"] == "blindspot_cap"
    assert r["confidence"] == "low"


def test_region_hit_is_not_labelled_as_grape(rules):
    """
    Et rent region-treff het `bekreftet_drue`. Forklaringen var da usann for
    2 401 av 2 401 `fit`-viner på rødvinsbasen (roadmap-prinsipp 6).
    """
    r = classify({"navn": "Ukjent Rosso", "land": "Italia", "region": "Veneto"}, rules)
    assert r["tier"] == "fit"
    assert r["rule_fired"] == "region_pluss"


# --- A5: oppslagsveien dekker det den slås opp i --------------------------


def test_classify_code_covers_the_catalog(catalog):
    """
    B5: `data/user_fit/v0.json` dekker 110 av 23 740 varenumre (0,59 %).
    Den foreskrevne oppslagsveien må dekke katalogen, ikke 0,6 % av den.
    `classify_code` går rett på katalog-raden og dekker den per konstruksjon —
    testen holder konstruksjonen i hevd.

    AVVIK FRA OPPRINNELIG FORMULERING (A5(a), besluttet av hovedtråden
    2026-08-30). Assertionen var opprinnelig formulert som
    `len(set(v0.json) & katalog) / len(katalog) >= 0.9` — altså et krav til
    FILA. Den formen kan bare oppfylles ved å generere en rad per varenummer,
    en derivert artefakt som måtte regenereres ved hver snapshot-refresh og
    som vokste med 4 465 rader mens dette ble skrevet. Å bygge den for å
    tilfredsstille bokstaven i assertionen ville skapt nøyaktig den gjelden
    assertionen skulle avdekke. Testen måler derfor OPPSLAGSVEIEN i stedet:
    samme hensikt — «et oppslag som brukes må dekke det den slås opp i» —
    uten fila i mellom. `v0.json` beholdes som det den faktisk er, score-DB-
    ens fit-indeks, og `_meta.scope` sier det (se testen under).
    """
    prøve = [catalog[i]["code"] for i in range(0, len(catalog), max(1, len(catalog) // 200))]
    bom = [c for c in prøve if classify_code(c) is None]
    assert not bom, f"{len(bom)} av {len(prøve)} varenumre ga ingen klassifisering: {bom[:5]}"


def test_classify_code_returns_none_outside_snapshot():
    assert classify_code("00000000") is None


def test_v0_json_declares_its_scope():
    """
    Fila er derivert fra `knowledge/scores/`, ikke fra katalogen. Uten et
    eksplisitt omfang i `_meta` leses den som en katalog-indeks — det er
    nettopp den feilen CLAUDE.md steg 6b gjorde.
    """
    if not DEFAULT_OUTPUT_PATH.exists():
        pytest.skip("v0.json ikke generert")
    meta = json.loads(DEFAULT_OUTPUT_PATH.read_text(encoding="utf-8"))["_meta"]
    assert meta.get("source") == "knowledge/scores/"
    assert "classify_code" in meta.get("scope", ""), (
        "_meta.scope må peke på den faktiske oppslagsveien"
    )


# --- Parse-regresjoner ----------------------------------------------------


def test_no_prose_leaked_into_needles(rules):
    """
    «Sauvignon Blanc: Bare én i hele dataene (Cloudy Bay 4.5 fra 2015).
    Ukjent om…» hadde lekket inn som ett matche-mønster.
    """
    for key in NEEDLE_KEYS:
        for needle in rules[key]:
            assert len(needle) <= 60, f"{key}: brødtekst som needle: {needle!r}"
            assert "." not in needle.rstrip("."), f"{key}: setning som needle: {needle!r}"


def test_region_needles_have_balanced_parens(rules):
    """«Tyskland (Mosel, Rheingau» — uparet parentes fra en dash-kutting."""
    for needle in rules["regioner_pluss"]:
        assert needle.count("(") == needle.count(")"), f"Uparet parentes: {needle!r}"
    assert "Tyskland" in rules["regioner_pluss"]


def test_both_blindspot_sections_are_read(rules):
    """
    `smaksprofil.md` har to Blindspots-seksjoner. Parseren leste bare den
    første, så halvparten av blindsonene var stille døde — inkludert «Pinot
    Noir generelt», den som dekker Côte d'Or.
    """
    bs = rules["blindspots"]
    assert any("Red Wine" in x or "White Wine" in x for x in bs), "auto-derivert mangler"
    assert "Pinot Noir generelt" in bs, "kuratert prosa-blindsone mangler"


def test_beer_rules_do_not_leak_into_wine(rules):
    """Øl-blokka i smaksprofil.md har egne Blindspots/Bekymringer — beer_fit eier dem."""
    ØL = ("Kölsch", "Altbier", "Rauchbier", "Barleywine", "Schwarzbier", "Märzen")
    for key in NEEDLE_KEYS:
        for needle in rules[key]:
            assert not any(x in needle for x in ØL), f"{key}: øl-regel lekket inn: {needle!r}"


# ---------------------------------------------------------------------------
# K — Fordelings-helsesjekker (ikke treffantall)
#
# «422 treff» så ut som en regel i drift. Fordelingen avslørte at de kom fra
# tre land av femten — Portugal, Chile og Uruguay — som alle staves likt på
# norsk og engelsk. Regelen matchet på stavelsessammenfall, ikke semantikk.
# Et treffantall kan derfor ikke brukes som helsesjekk. Disse testene måler
# SPREDNING i stedet, og de er behavioural: de leser ikke oversettelses-
# tabellene, de leser utfallet.
# ---------------------------------------------------------------------------


def test_blindspot_fires_across_many_countries(catalog):
    """
    Fanger stavelsessammenfall-feilen direkte: blindsonene dekker 15
    land-/kategori-kombinasjoner, men traff bare de tre landene som heter det
    samme på begge språk. En strukturell test på `_LAND_NO_TO_EN` ville ikke
    sett det — bruksstedet kan ha sluttet å lese tabellen.
    """
    rules = load_profile_rules()
    land = Counter()
    for p in catalog:
        if classify(p, rules)["rule_fired"] == "blindspot":
            navn = (p.get("main_country") or {}).get("name")
            if navn:
                land[navn] += 1
    assert len(land) >= 10, (
        f"Blindspot fyrer bare for {len(land)} land: {sorted(land)}. "
        "Det er signaturen på matching via stavelsessammenfall."
    )
    # Land der norsk og engelsk navn er ULIKE — de er hele poenget.
    for navn in ("Tyskland", "Spania", "Frankrike"):
        assert land.get(navn, 0) > 0, (
            f"Ingen blindspot-treff for {navn}. Norsk↔engelsk landnavn er "
            "sannsynligvis ikke oversatt på bruksstedet."
        )


def test_composite_blindspot_needs_country_translation(rules):
    """
    Den ENE veien som *bare* kan gå via norsk→engelsk landnavn.

    `1005301` er en libanesisk rødvin. «Lebanon Red Wine» har ingen egen
    matcher og ingen kuratert prosa-blindsone bak seg — treffet krever at
    `Libanon` oversettes til `Lebanon` på bruksstedet. Testen asserterer på
    hvilken needle som står i begrunnelsen, ikke på at *en eller annen*
    blindsone traff: uten det maskerer «Pinot Noir generelt» feilen.
    """
    r = classify_code("1005301", rules)
    if r is None:
        pytest.skip("1005301 ikke i snapshot")
    assert r["rule_fired"] == "blindspot", r["reasons"]
    assert any("Lebanon Red Wine" in x for x in r["reasons"]), (
        f"Forventet at «Lebanon Red Wine» navngis. Fikk: {r['reasons']}"
    )


def test_german_red_is_blindspot_not_fit(rules):
    """
    Profilen har «Germany Red Wine (n=2)» som blindsone OG «Tyskland (Mosel,
    Rheingau – Riesling)» som region-preferanse. Region-treffet alene gjorde
    alle 368 tyske rødviner `fit` — en positiv dom bygget på evidens om en
    annen kategori. Spesifisitet skal slå generalitet.
    """
    r = classify_code("17227001", rules)  # United Winemakers of Germany Pinot Noir
    if r is None:
        pytest.skip("17227001 ikke i snapshot")
    assert r["tier"] == "neutral", r["reasons"]
    assert r["rule_fired"] == "blindspot"


@pytest.mark.parametrize("code", ["16908505", "10876701", "12591006"])
def test_provence_rose_fires_on_every_varenummer(rules, code):
    """
    Samme vin — Studio by Miraval Rosé 2025 — ligger på tre varenumre, to av
    dem under IGP «Méditerranée» framfor «Provence». En matcher bundet til
    distriktsnavnet «Provence» fanget ett av tre.

    Provence-rosé er brukerens verst dokumenterte område (snitt 2.38, hans
    eneste 1.0). Dette er kategorien der stillhet koster mest.
    """
    r = classify_code(code, rules)
    if r is None:
        pytest.skip(f"{code} ikke i snapshot")
    assert r["tier"] == "risky", r["reasons"]


def test_bullet_parser_drops_prose_without_colon():
    """
    Lengdetaket er egen forsvarslinje, ikke bare et biprodukt av kolon-kuttet.
    Uten denne testen overlever en mutasjon som fjerner taket, fordi dagens
    ene brødtekst-lekkasje tilfeldigvis har et kolon i seg.
    """
    from tools.user_fit import _bullet_items

    seksjon = (
        "- **Barbera**\n"
        "- Dette er en hel setning uten kolon som forklarer at brukeren har "
        "prøvd noe en gang og ikke helt vet hva han synes om det ennå\n"
    )
    items = _bullet_items(seksjon)
    assert items == ["Barbera"], f"Brødtekst slapp gjennom: {items}"


# ---------------------------------------------------------------------------
# L — Nivå-innsnevrede bekymringer (overprøvd av hovedtråden 2026-08-30)
#
# En bekymring avledet fra instegsviner skal ikke matche hele regionen uansett
# prisnivå. Men den bredere regionen er heller ikke frikjent — den er
# udokumentert, og skal bære `blindspot` med lav konfidens.
# ---------------------------------------------------------------------------

from tools.user_fit import _NIVA_INNSNEVRET  # noqa: E402


@pytest.mark.parametrize(
    "code,forventet_tier,hva",
    [
        # Basis Côtes-du-Rhône: 2 av 3 ratinger ligger her (3.0 og 2.0).
        ("3241501", "risky", "Janasse Côtes du Rhône — instegsnivå, dokumentert lavt"),
        # Cru: ingen rating dekker nivået. Den ene ratingen over instegsnivå
        # (Lirac 4.0) er den HØYESTE av de tre — ingen støtte for `risky`.
        ("10506201", "neutral", "Daumen Châteauneuf-du-Pape — cru, udokumentert"),
        # Regionalt Bourgogne vs Côte d'Or: samme skille, samme begrunnelse.
        ("1013801", "risky", "Dupasquier Bourgogne — regionalt nivå"),
        ("10080701", "neutral", "Marchand Tawse Gevrey-Chambertin — cru"),
    ],
)
def test_level_narrowed_concerns(rules, code, forventet_tier, hva):
    r = classify_code(code, rules)
    if r is None:
        pytest.skip(f"{code} ikke i snapshot")
    assert r["tier"] == forventet_tier, f"{hva}: fikk {r['tier']} ({r['reasons']})"


@pytest.mark.parametrize("code", ["10506201", "10080701"])
def test_narrowed_region_is_flagged_not_silently_cleared(rules, code):
    """
    Innsnevringen skal ikke lese som frikjennelse. Under ADR-016 må en
    Châteauneuf fortsatt bære merket om at brukeren har tynn og blandet
    erfaring i Sør-Rhône — bare ikke som `risky`, som er en påstand dataene
    ikke bærer. Begrunnelsen må navngi nivået historikken FAKTISK dekker.
    """
    r = classify_code(code, rules)
    if r is None:
        pytest.skip(f"{code} ikke i snapshot")
    assert r["rule_fired"] == "blindspot"
    assert r["confidence"] == "low"
    assert any("dokumentert på" in x for x in r["reasons"]), r["reasons"]


def test_level_narrowing_holds_on_the_vivino_path(rules):
    """
    `classify()` har to innganger: Polet-katalograder (norsk) og Vivino-CSV-
    rader (engelsk, via `tools/eval_fit.py`). Nivå-innsnevringen bodde først
    bare i den norske matcheren, så en Lirac fra CSV-en ble `risky` mens en
    Lirac fra katalogen ble blindsone — samme vin, ulik dom, avhengig av kilde.

    Det er ikke bare stygt: eval-harnessen fra ADR-017 leser CSV-stien, og er
    beslutningsgrunnlaget for om user-fit v1 skal bygges i det hele tatt.
    """
    basis = {"stil": "Southern Rhône Red", "land": "France", "region": "Côtes-du-Rhône"}
    cru = {"stil": "Southern Rhône Red", "land": "France", "region": "Lirac"}
    assert classify(basis, rules)["tier"] == "risky"
    assert classify(cru, rules)["tier"] == "neutral"
    assert classify(cru, rules)["rule_fired"] == "blindspot"


def test_same_wine_same_tier_across_sources(rules):
    """Polet-rad og Vivino-rad for samme vin skal gi samme tier."""
    polet = classify_code("3241501", rules)  # Dom. de la Janasse Côtes du Rhône
    if polet is None:
        pytest.skip("3241501 ikke i snapshot")
    vivino = classify(
        {"navn": "Domaine de la Janasse Côtes du Rhône Rouge",
         "stil": "Southern Rhône Red", "land": "France", "region": "Côtes-du-Rhône"},
        rules,
    )
    assert polet["tier"] == vivino["tier"] == "risky"


# --- De tre resterende parene (fikset på bestilling 2026-08-30) -------------


def test_sor_rhone_hvit_bound_to_lirac(rules):
    """
    Evidensen er «to lave på Lirac Blanc» — som viste seg å være SAMME vin i
    to årganger (Ch. de Ségriés 3.2 og 3.0). Lirac ligger over basisnivå, så
    generaliseringen gikk både nedover til Côtes-du-Rhône blanc og sidelengs
    til Châteauneuf-du-Pape blanc, et helt annet produkt.
    """
    lirac = {"land": "Frankrike", "kategori": "Hvitvin",
             "region": "Rhône", "underregion": "Lirac"}
    cdp = {"land": "Frankrike", "kategori": "Hvitvin",
           "region": "Rhône", "underregion": "Châteauneuf-du-Pape"}
    assert classify(lirac, rules)["tier"] == "risky"
    r = classify(cdp, rules)
    assert r["tier"] == "neutral" and r["rule_fired"] == "blindspot"


def test_southern_italy_very_fit_bound_to_sicilia(rules):
    """
    Plussiden. 3 av 4 ratede er sicilianske, men matcheren ga `very_fit` til
    hele Syd-Italia. En falsk `very_fit` er like mye en filterboble som en
    manglende `risky` (ADR-016) — den sender brukeren mot Taurasi på
    grunnlag av Etna. Resten av Syd-Italia skal ha positivt merke ett hakk
    ned, ikke stillhet.
    """
    etna = {"land": "Italia", "kategori": "Rødvin",
            "region": "Sicilia", "underregion": "Etna"}
    campania = {"land": "Italia", "kategori": "Rødvin", "region": "Campania"}
    assert classify(etna, rules)["tier"] == "very_fit"
    r = classify(campania, rules)
    assert r["tier"] == "fit", r["reasons"]
    assert r["confidence"] == "low"
    assert any("dokumentert på Sicilia" in x for x in r["reasons"]), r["reasons"]


def test_bandol_rose_is_not_generic_provence(rules):
    """
    Evidensen er fire kommersielle Côtes de Provence / Coteaux d'Aix — to av
    dem samme vin i to årganger, med 2,0 poengs spenn. Bandol er Provences
    seriøse hjørne og finnes ikke i historikken.
    """
    generisk = {"land": "Frankrike", "kategori": "Rosévin",
                "region": "Provence", "underregion": "Côtes de Provence"}
    bandol = {"land": "Frankrike", "kategori": "Rosévin",
              "region": "Provence", "underregion": "Bandol"}
    assert classify(generisk, rules)["tier"] == "risky"
    r = classify(bandol, rules)
    assert r["tier"] == "neutral" and r["rule_fired"] == "blindspot"


def test_narrowing_applies_on_both_paths(rules):
    """
    Hver innsnevring skal gjelde begge innganger. Vivino-rader har engelske
    land- og stilnavn og treffer aldri `_NO_MATCHERS`; uten den kryss-
    språklige porten ville de beholdt den brede regelen.
    """
    par = [
        ({"land": "Italia", "kategori": "Rødvin", "region": "Campania"},
         {"stil": "Southern Italy Red", "land": "Italy", "region": "Taurasi"}),
        ({"land": "Frankrike", "kategori": "Rosévin", "region": "Provence",
          "underregion": "Bandol"},
         {"stil": "Provence Rosé", "land": "France", "region": "Bandol",
          "kategori": "Rosé Wine"}),
        ({"land": "Frankrike", "kategori": "Rødvin", "region": "Rhône",
          "underregion": "Châteauneuf-du-Pape"},
         {"stil": "Southern Rhône Red", "land": "France",
          "region": "Châteauneuf-du-Pape"}),
    ]
    for polet, vivino in par:
        assert classify(polet, rules)["tier"] == classify(vivino, rules)["tier"], (
            f"Ulik dom på de to inngangene: {polet} vs {vivino}"
        )


def test_niva_innsnevret_is_wellformed(rules):
    """Hver innsnevring må være en levende regel med begrunnelse og utfall."""
    for needle, spec in _NIVA_INNSNEVRET.items():
        assert spec["kilde"] in NEEDLE_KEYS, f"{needle!r}: ukjent kilde"
        assert needle in rules[spec["kilde"]], (
            f"{needle!r} er innsnevret, men står ikke i {spec['kilde']!r} lenger"
        )
        assert needle in _NO_MATCHERS, f"{needle!r} mangler den smale matcheren"
        assert spec["utenfor"] in {"blindspot", "fit"}, f"{needle!r}: ugyldig utfall"
        assert spec["smal"] and spec["bredere"], f"{needle!r}: ufullstendig"
        assert spec["nivå"] and spec["evidens"], f"{needle!r}: mangler begrunnelse"
