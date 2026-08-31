"""Innholds-baserte tester for `knowledge/` og `deep-knowledge/`.

Ingen tester sjekker bestemte filer for bestemte ord — istedet stiller vi
krav som "et sted i knowledge/ finnes 'Fylde'" og "en fil som heter
sommelier finnes". Slik tåler vi refactors som flytter innhold mellom filer.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = REPO_ROOT / "knowledge"
DEEP = REPO_ROOT / "deep-knowledge"


def _md_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.md") if "_archive" not in p.parts]


def _content_contains(root: Path, needle: str, case_sensitive: bool = False) -> bool:
    files = _md_files(root)
    needle_cmp = needle if case_sensitive else needle.lower()
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        haystack = text if case_sensitive else text.lower()
        if needle_cmp in haystack:
            return True
    return False


def _has_file_with_stem(root: Path, stem_substring: str) -> bool:
    target = stem_substring.lower()
    for p in _md_files(root):
        if target in p.stem.lower():
            return True
    return False


def test_knowledge_dir_exists():
    assert KNOWLEDGE.is_dir(), f"mangler {KNOWLEDGE}"


def test_knowledge_mentions_fylde():
    """Klokke-rammeverket må være dokumentert et eller annet sted."""
    assert _content_contains(KNOWLEDGE, "Fylde"), (
        "Ingen knowledge/-fil nevner 'Fylde' (klokke-rammeverket)"
    )


def test_knowledge_mentions_bjcp():
    """Øl-stilrammeverket må være dokumentert."""
    assert _content_contains(KNOWLEDGE, "BJCP"), (
        "Ingen knowledge/-fil nevner 'BJCP' (øl-rammeverket)"
    )


def test_knowledge_has_smaksprofil_file():
    assert _has_file_with_stem(KNOWLEDGE, "smaksprofil"), (
        "Mangler smaksprofil-fil i knowledge/"
    )


def test_knowledge_has_sommelier_file():
    """Kjernefil for vin må finnes som markdown i knowledge/."""
    assert _has_file_with_stem(KNOWLEDGE, "sommelier"), (
        "Mangler kjernefil for vin (sommelier*.md) i knowledge/"
    )


def test_knowledge_has_cicerone_file():
    """Kjernefil for øl må finnes som markdown i knowledge/."""
    assert _has_file_with_stem(KNOWLEDGE, "cicerone"), (
        "Mangler kjernefil for øl (cicerone*.md) i knowledge/"
    )


def test_deep_knowledge_index_exists_and_lists_italia():
    index = DEEP / "INDEX.md"
    assert index.exists(), f"mangler {index}"
    text = index.read_text(encoding="utf-8").lower()
    assert "italia.md" in text, (
        "deep-knowledge/INDEX.md viser ikke til italia.md"
    )


# ---------------------------------------------------------------------------
# Prosaen i smaksprofil.md mot de auto-deriverte tallene (teknisk gjeld #10)
#
# Seks tallpåstander i prosaen vedlikeholdes for hånd mens den managed blokka
# over dem regenereres av `profile_stats.py`. Avviket var 13 viner før
# Vivino-synken 2026-08-30 og 18 etter — det vokser hver gang noen synker, og
# feilen er stille: påstandene er fortsatt *formulert* som sannhet.
#
# Fri prosa («41 av 122 ratede viner er italienske») holdes bevisst utenfor —
# der tipper det over i regex-arkeologi.
#
# Flyttet hit fra `test_user_fit.py` § J 2026-08-31. Den lå der bare fordi
# agenten som skrev den ikke eide denne fila; testen sjekker innhold i
# `knowledge/`, ikke oppførselen til `user_fit`.
#
# KRITISK: hver assertion sjekker ANTALL TREFF før den sammenligner tall.
# Uten det ville en omformulert overskrift gi null treff, og testen bli grønn
# mens den hadde sluttet å sjekke noe som helst.
# ---------------------------------------------------------------------------

import re  # noqa: E402
import statistics  # noqa: E402

from tools.profile_stats import agg_by, load_rated  # noqa: E402
from tools.user_fit import SMAKSPROFIL_PATH  # noqa: E402

# Prosaens norske kategorinavn → Vivinos `Wine type`
KATEGORI_TIL_WINE_TYPE = {
    "Rødvin": "Red Wine",
    "Hvitvin": "White Wine",
    "Musserende": "Sparkling",
    "Rosé": "Rosé Wine",
}


@pytest.fixture(scope="module")
def profil_tekst() -> str:
    return SMAKSPROFIL_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def vivino_stats() -> dict:
    rows = load_rated()
    per_type = {label: (n, avg) for label, n, avg, _ in agg_by(rows, "Wine type")}
    return {
        "n": len(rows),
        "snitt": statistics.mean(r["_rating"] for r in rows),
        "per_type": per_type,
    }


def test_prosa_kategorioverskrifter_matcher_tallene(profil_tekst, vivino_stats):
    """«### Rødvin (klart hovedkategorien – 67 viner, snitt 3.79)»"""
    treff = re.findall(
        r"^### ([A-Za-zÀ-ÿ]+) \(.*?(\d+) viner, snitt (\d+\.\d+)",
        profil_tekst,
        re.MULTILINE,
    )
    assert len(treff) == 4, (
        f"Forventet 4 kategorioverskrifter med tall, fant {len(treff)}: {treff}. "
        "Er en overskrift omformulert, har testen sluttet å sjekke — ikke gjør "
        "den grønn ved å senke tallet."
    )
    for kategori, n_str, snitt_str in treff:
        wine_type = KATEGORI_TIL_WINE_TYPE.get(kategori)
        assert wine_type, f"Ukjent kategori i prosaen: {kategori!r}"
        n_fasit, snitt_fasit = vivino_stats["per_type"][wine_type]
        assert int(n_str) == n_fasit, (
            f"«### {kategori}» sier {n_str} viner, profile_stats sier {n_fasit}"
        )
        assert abs(float(snitt_str) - snitt_fasit) < 0.005, (
            f"«### {kategori}» sier snitt {snitt_str}, "
            f"profile_stats sier {snitt_fasit:.2f}"
        )


def test_prosa_datagrunnlag_matcher_tallene(profil_tekst, vivino_stats):
    """«- 122 ratede viner, snitt 3.82»"""
    treff = re.findall(
        r"^- (\d+) ratede viner, snitt (\d+\.\d+)", profil_tekst, re.MULTILINE
    )
    assert len(treff) == 1, (
        f"Forventet nøyaktig én datagrunnlag-linje, fant {len(treff)}: {treff}"
    )
    n_str, snitt_str = treff[0]
    assert int(n_str) == vivino_stats["n"], (
        f"Prosaen sier {n_str} ratede viner, CSV-en har {vivino_stats['n']}"
    )
    assert abs(float(snitt_str) - vivino_stats["snitt"]) < 0.005, (
        f"Prosaen sier snitt {snitt_str}, faktisk {vivino_stats['snitt']:.2f}"
    )


def test_prosa_tyngdepunkt_matcher_tallene(profil_tekst, vivino_stats):
    """«- Tyngdepunkt: rødvin (67), musserende (23), hvitvin (20), rosé (10)»"""
    linjer = re.findall(r"^- Tyngdepunkt: (.+)$", profil_tekst, re.MULTILINE)
    assert len(linjer) == 1, f"Forventet én Tyngdepunkt-linje, fant {len(linjer)}"
    par = re.findall(r"([A-Za-zÀ-ÿ]+)\s*\((\d+)\)", linjer[0])
    assert len(par) == 4, f"Forventet 4 kategorier på Tyngdepunkt-linja, fant {par}"
    for kategori, n_str in par:
        wine_type = KATEGORI_TIL_WINE_TYPE.get(kategori.capitalize())
        assert wine_type, f"Ukjent kategori på Tyngdepunkt-linja: {kategori!r}"
        n_fasit = vivino_stats["per_type"][wine_type][0]
        assert int(n_str) == n_fasit, (
            f"Tyngdepunkt sier {kategori} ({n_str}), profile_stats sier {n_fasit}"
        )


# ─── whisky.md ───────────────────────────────────────────────────────
# Fagfilen er skrevet før brukeren har ratet én eneste whisky. Testene her
# bevokter derfor ikke fagkunnskapen, men de tre påstandene som er FARLIGE å
# miste: at n=0, at klokkene ikke er en preferanse-påstand, og at det som ikke
# er verifisert ikke står der som fakta.

WHISKY = KNOWLEDGE / "whisky.md"


@pytest.fixture
def whisky_tekst() -> str:
    if not WHISKY.exists():
        pytest.skip("knowledge/whisky.md finnes ikke ennå")
    return WHISKY.read_text(encoding="utf-8")


def test_whisky_states_that_there_are_no_ratings_yet(whisky_tekst):
    """
    Uten denne setningen er filen et fundament som ser ut som en
    preferanse-modell. Whisky står på n=0, og det må stå i filen selv — ikke
    bare i en planfil ingen leser under en anbefaling.
    """
    assert "n=0" in whisky_tekst
    assert "84" in whisky_tekst, "terskelen for når en modell kan si noe mangler"


def test_whisky_carries_the_adr025_caveat_on_the_clocks(whisky_tekst):
    """Fylde/Fat/Røyk er stil-slektskap, aldri «du vil like denne»."""
    lav = whisky_tekst.lower()
    assert "adr-025" in lav
    assert "grovfilter" in lav


def test_whisky_does_not_present_wset_sat_content_as_fact(whisky_tekst):
    """
    Begge PDF-URL-ene ga 403. Presedensen er `bjcp_2021.pdf`-referansen i
    cicerone.md, som viste seg hallusinert. Nevnes SAT-en, skal den nevnes
    som noe vi IKKE har.
    """
    lav = whisky_tekst.lower()
    if "systematic approach to tasting" in lav or "wset" in lav:
        assert "403" in whisky_tekst, (
            "WSETs SAT nevnes uten forbeholdet om at kilden ikke er hentet"
        )


def test_whisky_flags_the_empty_spirits_catalog(whisky_tekst):
    """
    Katalogen har to brennevinsrader, begge grappa. Et tomt whisky-søk betyr
    «ikke enumerert», ikke «Polet fører den ikke» — og brukeren skal ikke
    sendes på et refresh-ritual for det (gjeld #11).
    """
    lav = whisky_tekst.lower()
    assert "grappa" in lav
    assert "refresh" in lav


def test_whisky_names_the_legal_sources_it_rests_on(whisky_tekst):
    """Juridisk kategori er ankeret — da må hjemlene stå der."""
    for kilde in ("2009", "27 CFR", "2019/787", "JSLMA", "Technical File"):
        assert kilde in whisky_tekst, f"mangler hjemmel: {kilde}"


def test_whisky_marks_the_japanese_rules_as_non_binding(whisky_tekst):
    """
    JSLMA er en bransjestandard uten lovhjemmel. Skrives den som lov, blir
    «japansk whisky» presentert som en garanti den ikke er.
    """
    assert "uten lovhjemmel" in whisky_tekst.lower()
