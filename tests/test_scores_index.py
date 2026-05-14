"""Kontrakt-tester for tools.scores.index().

Disse er fil-agnostiske — de stiller krav til *innhold* og *struktur*, ikke
spesifikke filnavn. Refactors som bytter filnavn eller flytter score-filer
skal fortsatt holde indeksen intakt.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools.scores import index


REPO_ROOT = Path(__file__).resolve().parent.parent
SCORES_DIR = REPO_ROOT / "knowledge" / "scores"


@pytest.fixture(scope="module")
def idx() -> dict:
    return index()


def test_index_returns_dict(idx):
    assert isinstance(idx, dict), "index() skal returnere en dict"
    assert len(idx) > 0, "indeksen er tom"


def test_index_has_minimum_entries(idx):
    total = sum(len(v) for v in idx.values())
    assert total >= 400, (
        f"Forventet minst 400 score-entries totalt; fant {total}. "
        "Enten er filer fjernet eller parseren hopper over headinger."
    )


def test_index_covers_minimum_four_files(idx):
    """Tell unike kilde-test-strenger som proxy for kildefiler — fil-agnostisk."""
    tests_seen: set[str] = set()
    for entries in idx.values():
        for e in entries:
            t = (e.get("test") or "").strip()
            if t:
                tests_seen.add(t)
    assert len(tests_seen) >= 4, (
        f"Forventet entries fra minst 4 distinkte score-kilder; "
        f"fant {len(tests_seen)}: {sorted(tests_seen)}"
    )


def test_index_score_range(idx):
    for varenr, entries in idx.items():
        for e in entries:
            score = e["score"]
            assert 60 <= score <= 100, (
                f"Score utenfor [60,100] for varenr {varenr} "
                f"({e.get('name')}): {score}"
            )


def test_index_entries_have_required_fields(idx):
    """Hver entry skal ha kjernefeltene satt (parseren skal ikke produsere
    halv-parsede entries)."""
    required = {"score", "name", "varenummer"}
    for varenr, entries in idx.items():
        for e in entries:
            missing = required - set(e.keys())
            assert not missing, f"Mangler felter {missing} på entry: {e}"
            assert isinstance(e["score"], float)
            assert e["name"], "name er tom"
            assert e["varenummer"].isdigit(), (
                f"varenummer skal være numerisk: {e['varenummer']!r}"
            )


HEADING_RE = re.compile(
    r"^###\s*\[(\d{1,3}(?:[.,]\d)?)\]\s*(.+?)\s*[—–-]\s*Varenummer\s*(\d+)\s*$",
    re.MULTILINE,
)


def test_every_score_file_fully_parsed(idx):
    """For hver score-fil i knowledge/scores/ (utenom INDEX.md): tell
    headinger i råteksten og sammenlign med indeksen — ingen heading skal
    hoppes over."""
    assert SCORES_DIR.exists(), f"scores-katalogen mangler: {SCORES_DIR}"

    # Bygg lookup fra (test, varenummer) → fant vi entry?
    indexed_by_test_varenr: dict[tuple[str, str], int] = {}
    for varenr, entries in idx.items():
        for e in entries:
            key = ((e.get("test") or "").strip(), varenr)
            indexed_by_test_varenr[key] = indexed_by_test_varenr.get(key, 0) + 1

    files_checked = 0
    for path in sorted(SCORES_DIR.glob("*.md")):
        if path.name == "INDEX.md":
            continue
        files_checked += 1
        text = path.read_text(encoding="utf-8")
        headings = HEADING_RE.findall(text)
        assert headings, f"{path.name}: ingen headinger matchet — fil-format brutt?"

        # Sjekk at filens "test"-frontmatter-verdi finnes i indeksen og at
        # antall entries med den verdien matcher antall headinger i fila.
        # Først: les frontmatter-test ut av råtekst.
        m = re.search(r"^test:\s*(.+)$", text, re.MULTILINE)
        assert m, f"{path.name}: mangler `test:` i frontmatter"
        test_val = m.group(1).strip()

        entries_for_file = sum(
            cnt
            for (t, _vr), cnt in indexed_by_test_varenr.items()
            if t == test_val
        )
        assert entries_for_file == len(headings), (
            f"{path.name}: {len(headings)} headinger i fil, men "
            f"{entries_for_file} entries i indeks for test='{test_val}'. "
            "Parseren hopper over noe."
        )
    assert files_checked >= 4, (
        f"Forventet minst 4 score-filer; fant {files_checked}"
    )
