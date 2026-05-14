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
