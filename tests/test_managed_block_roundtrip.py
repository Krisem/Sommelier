"""Round-trip-vern for de to managed blokkene i `knowledge/smaksprofil.md`.

Fila er for det meste håndskrevet prosa med to maskin-eide blokker klemt inn i
midten. Lærdommen fra 2026-08-30 er at «skrivefunksjoner som bygger fra en mal
sletter alt utenfor malen» — og her ville tapet vært hele den kuraterte
profilen. Derfor: regenerér blokka og assertér at ALT utenfor sentinelene er
bit-identisk, tegn for tegn.

Testen kjøres FØR prosaen i fila endres (Fase 3.1), slik at den fanger et tap
mens vi redigerer, ikke etterpå.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import tools.profile_stats as profile_stats
import tools.untappd_stats as untappd_stats


PROFILE = Path(__file__).resolve().parent.parent / "knowledge" / "smaksprofil.md"


def _outside(text: str, begin: str, end: str) -> tuple[str, str]:
    """Teksten før og etter en managed blokk."""
    assert begin in text and end in text, f"sentinel mangler: {begin}"
    return text[: text.index(begin)], text[text.index(end) + len(end) :]


@pytest.mark.parametrize(
    "module",
    [profile_stats, untappd_stats],
    ids=["vin", "øl"],
)
def test_regenerating_a_managed_block_leaves_all_other_prose_bit_identical(module):
    original = PROFILE.read_text(encoding="utf-8")
    regenerated = module.splice(original, module.BEGIN + "\nNY BLOKK\n" + module.END)

    assert _outside(original, module.BEGIN, module.END) == _outside(
        regenerated, module.BEGIN, module.END
    )


@pytest.mark.parametrize(
    "module",
    [profile_stats, untappd_stats],
    ids=["vin", "øl"],
)
def test_the_other_managed_block_survives_a_regeneration(module):
    """Vin-blokka skal ikke røre øl-blokka, og omvendt."""
    other = untappd_stats if module is profile_stats else profile_stats
    original = PROFILE.read_text(encoding="utf-8")
    regenerated = module.splice(original, module.BEGIN + "\nNY BLOKK\n" + module.END)

    o_start = original.index(other.BEGIN)
    o_end = original.index(other.END) + len(other.END)
    r_start = regenerated.index(other.BEGIN)
    r_end = regenerated.index(other.END) + len(other.END)
    assert regenerated[r_start:r_end] == original[o_start:o_end]


def test_splice_is_idempotent():
    original = PROFILE.read_text(encoding="utf-8")
    block = profile_stats.BEGIN + "\nNY BLOKK\n" + profile_stats.END
    once = profile_stats.splice(original, block)
    assert profile_stats.splice(once, block) == once


def test_real_render_preserves_the_curated_profile():
    """
    Ikke en attrapp-blokk, men den ekte render-stien fra Vivino-CSV-en.
    Den er den som faktisk kjøres av `python3 tools/profile_stats.py`.
    """
    original = PROFILE.read_text(encoding="utf-8")
    block = profile_stats.render(profile_stats.load_rated())
    regenerated = profile_stats.splice(original, block)

    assert _outside(original, profile_stats.BEGIN, profile_stats.END) == _outside(
        regenerated, profile_stats.BEGIN, profile_stats.END
    )
    # Og den kuraterte prosaen finnes fortsatt i sin helhet
    for anchor in ("## No-go-liste", "## Druer du vet du liker", "## Notater til Claude"):
        assert anchor in regenerated
