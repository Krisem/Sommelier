"""
Parsing og drift-vern for whiskyanalysis.com Meta-Critic.

Kilden er én HTML-tabell på ett nettsted vi ikke kontrollerer. Endrer den seg,
skal sveipen STOPPE — ikke skrive et snapshot som ser gyldig ut. Disse testene
finnes for at den stoppen faktisk skal inntreffe.
"""

import json
from pathlib import Path

import pytest

from tools import whiskyanalysis as wa

FIXTURE = Path(__file__).parent / "fixtures" / "whiskyanalysis_database.html"


@pytest.fixture
def side() -> str:
    return FIXTURE.read_text(encoding="utf-8")


# ─── parsing ─────────────────────────────────────────────────────────

def test_parses_the_pinned_fixture(side):
    rows = wa.parse_database_page(side, min_rows=5)
    assert len(rows) == 20
    for r in rows:
        assert r["whisky"]
        assert isinstance(r["meta_critic"], float)


def test_first_row_is_read_field_for_field(side):
    """Kolonnerekkefølgen er posisjonsbasert — en forskyvning må fanges her."""
    rad = wa.parse_database_page(side, min_rows=5)[0]
    assert rad["whisky"] == "2 Gingers Irish Whiskey"
    assert rad["meta_critic"] == 7.76
    assert rad["stdev"] == 0.54
    assert rad["n_reviewers"] == 4
    assert rad["cost_band"] == "$$"
    assert rad["cost_rank"] == 2
    assert rad["country"] == "Ireland"
    assert rad["type"] == "Blend"


# ─── drift-vern ──────────────────────────────────────────────────────

def test_changed_header_raises(side):
    """
    Den viktigste testen i fila. Bytter kilden ut en kolonne, blir hver rad
    parset feltforskjøvet — score havner i STDEV-kolonnen — og alt ser
    fortsatt ut som gyldige tall. Stille er nettopp det den ikke får være.
    """
    endret = side.replace("Meta Critic", "MetaCritic Score", 1)
    # Uten denne ville testen bli stille vakuøs den dagen markupen endrer form:
    # replace() ville ikke truffet, `endret` ville vært identisk med `side`, og
    # parse ville reist ValueError av en HELT annen grunn — eller ingen.
    assert endret != side, "mutasjonen traff ingenting — testen tester ikke drift"
    with pytest.raises(ValueError, match="[Kk]olonneheader"):
        wa.parse_database_page(endret, min_rows=5)


def test_too_few_rows_raises(side):
    with pytest.raises(ValueError, match="gulvet"):
        wa.parse_database_page(side, min_rows=100)


def test_no_table_raises():
    with pytest.raises(ValueError, match="[Ff]ant ingen"):
        wa.parse_database_page("<html><body><p>ingen tabell</p></body></html>")


def test_source_updated_is_read_from_the_page(side):
    """
    `generated_at` sier når VI hentet. `source_updated` sier hvor gamle tallene
    er. Databasen har stått stille siden januar 2023 — leses alderen av feil
    felt, presenteres 3,5 år gamle tall som ferske.
    """
    assert wa.extract_source_updated(side) == "January 20, 2023"


def test_source_updated_returns_none_rather_than_guessing():
    assert wa.extract_source_updated("<html><body>ingen dato her</body></html>") is None


# ─── normalisering ───────────────────────────────────────────────────

def test_age_is_extracted_not_tokenised():
    for navn in ("Talisker 10yo", "Talisker Single Malt 10 Years Old", "Talisker 10 YO"):
        tokens, age = wa.normalise(navn)
        assert age == 10, navn
        assert tokens == ["talisker"], navn


def test_generic_words_do_not_identify_a_bottle():
    """«single malt scotch whisky» skiller ingenting når alt er whisky."""
    tokens, age = wa.normalise("Glenfiddich Single Malt Scotch Whisky")
    assert tokens == ["glenfiddich"]
    assert age is None


def test_parenthetical_suffix_is_dropped():
    tokens, age = wa.normalise("Lagavulin 16yo (all reviews)")
    assert tokens == ["lagavulin"]
    assert age == 16


def test_region_words_are_stripped_from_brand_names_too():
    """
    «highland», «islay» og «speyside» står i GENERIC_TOKENS fordi de opptrer som
    regionsangivelse i begge kilder. Bivirkningen er at «Highland Park» blir
    ["park"] — overraskende, men riktig for formålet: BEGGE sider normaliseres
    likt, så joinen holder, og «park» skiller fortsatt Highland Park fra
    Highland Queen.

    Testen står her for at bivirkningen skal være dokumentert og ikke oppdages
    på nytt som en antatt bug.
    """
    assert wa.normalise("Highland Park 12 YO")[0] == ["park"]
    assert wa.normalise("Highland Park 12yo (all reviews)")[0] == ["park"]
    assert wa.normalise("Highland Queen")[0] == ["queen"]


def test_normalise_survives_empty_input():
    assert wa.normalise("") == ([], None)
    assert wa.normalise(None) == ([], None)


# ─── persentil ───────────────────────────────────────────────────────

def test_percentile_rank_orders_within_the_source():
    rows = [{"meta_critic": v} for v in (7.0, 8.0, 9.0, 9.5)]
    assert wa.percentile_rank(7.0, rows) < wa.percentile_rank(9.0, rows)
    assert wa.percentile_rank(9.5, rows) > 0.8


def test_percentile_rank_handles_empty_source():
    assert wa.percentile_rank(8.0, []) is None


# ─── snapshotet i repoet ─────────────────────────────────────────────

def test_committed_snapshot_carries_its_caveats():
    """
    Prisbias og «ikke uavhengig av Aperitif» er de to påstandene som avgjør at
    Meta-Critic IKKE får styre value_verdict. Forsvinner de fra metaen, er
    begrunnelsen for designet borte selv om koden står.
    """
    meta = wa.read_meta()
    if not meta:
        pytest.skip("snapshot ikke bygget i dette miljøet")
    forbehold = meta.get("forbehold", {})
    assert "prisbias" in forbehold
    assert "ikke_uavhengig" in forbehold
    assert meta.get("source_updated"), "kildens egen alder må stå i metaen"
    # Prisbiasen er selve grunnen til at kilden ikke vektes — den skal måles,
    # ikke huskes.
    assert meta["prisbias_spearman"] > 0.5, (
        "prisbiasen er borte — det ville vært en ny og bedre kilde, og "
        "beslutningen om å ikke vekte den må da tas på nytt"
    )
