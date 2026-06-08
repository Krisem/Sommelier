"""
Øl-fit classifier v0 — regel-basert tier-klassifisering av BJCP-stilfamilier
mot brukerens Untappd-historikk.

Speiler `tools/user_fit.py` (vin), men med én avgjørende arkitektonisk forskjell:
vin-fit klassifiserer en ekstern katalog (Polet score-DB). Øl har ingen katalog —
så øl-fit klassifiserer selve stilfamiliene (~24 stk fra `untappd_stats.STYLE_FAMILIES`).
Output er en komplett familie→tier-tabell, ikke en projeksjon over produkter.

Kilde: familie-statistikken deriveres DIREKTE fra Untappd-CSV via
`untappd_stats.agg_by_family()` — ikke ved å re-parse den rendrede øl-blokken i
smaksprofil.md (skjørt). Begge er sibling-artefakter fra samme kilde.

Terskler er løsnet ift. vin fordi øl-datasettet er tynnere (~90 check-ins):
`very_fit` krever n≥3 + snitt≥3.85 (brukerbeslutning 2026-06-08).

For batch-spørringer («hvilke av disse vil jeg like») finnes ingen øl-katalog —
lim inn ølene og kjør `classify_beer()` per øl (manuell innliming, v0).

CLI:
    python3 -m tools.beer_fit   # re-genererer data/user_fit/beer_v0.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tools.untappd_stats import (
    STYLE_FAMILIES,
    agg_by_family,
    classify_style,
    load_rated,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BEER_OUTPUT_PATH = REPO_ROOT / "data" / "user_fit" / "beer_v0.json"

# Terskler — eksplisitt navngitt; endring krever bevisst valg.
# Løsnet ift. vin (n≥3/4.0) fordi øl-datasettet er tynnere.
_VERY_FIT_AVG_THRESHOLD = 3.85
_VERY_FIT_MIN_N = 3
_FIT_AVG_THRESHOLD = 3.8      # speiler øl-blokkens "Bekreftede preferanser"
_FIT_MIN_N = 2
_BEKYMRING_AVG_THRESHOLD = 3.2  # speiler øl-blokkens "Bekymringer"
_BEKYMRING_MIN_N = 2
_BLINDSPOT_MAX_N = 1

# Sekkeposter som ikke er ekte BJCP-familier — ekskluderes fra output.
_EXCLUDE_FAMILIES = {"Annet / uklassifisert"}

# Øl-no-go er en eksplisitt brukerbeslutning (feedback-løkke-prinsippet), ikke
# auto-derivert fra lav rating. Tom i v0; regelen ligger klar for fremtiden.
BEER_NO_GO: list[str] = []

# Kanonisk familieliste (fast rekkefølge fra untappd_stats — eneste sannhetskilde).
CANONICAL_FAMILIES = [label for label, _ in STYLE_FAMILIES]


# ---------------------------------------------------------------------------
# Familie-statistikk (derivert fra Untappd-CSV)
# ---------------------------------------------------------------------------


def load_family_stats(rows: Optional[list[dict]] = None) -> dict[str, dict]:
    """
    Bygg {familie: {"n": int, "snitt": float, "snitt_recent": float|None}} fra
    Untappd-historikken. Bruk `rows` for å override i tester (ellers leses CSV).
    """
    if rows is None:
        rows = load_rated()
    out: dict[str, dict] = {}
    for label, n, avg, avg_recent in agg_by_family(rows):
        out[label] = {"n": n, "snitt": avg, "snitt_recent": avg_recent}
    return out


# ---------------------------------------------------------------------------
# Klassifisering
# ---------------------------------------------------------------------------


def classify_family(family: str, family_stats: dict[str, dict]) -> dict:
    """
    Klassifisér én stilfamilie i `very_fit | fit | neutral | risky | no_go`.

    Early-exit (første treff vinner), speiler vin-fit:
        1. no_go     — familie i BEER_NO_GO
        2. bekymring — n≥2 og snitt < 3.2            → risky
        3. bekreftet_snitt — n≥3 og snitt ≥ 3.85     → very_fit
        4. bekreftet_familie — n≥2 og snitt ≥ 3.8    → fit
        5. blindspot — n ≤ 1                          → neutral (low)
        6. default   — alt annet                      → neutral
    """
    stats = family_stats.get(family, {})
    n = stats.get("n", 0)
    snitt = stats.get("snitt")
    snitt_recent = stats.get("snitt_recent")
    base = {"n": n, "snitt": round(snitt, 2) if snitt is not None else None}

    def out(tier, confidence, rule_fired, reason):
        return {
            "tier": tier,
            "reasons": [reason],
            "confidence": confidence,
            "rule_fired": rule_fired,
            **base,
        }

    # 1. no_go
    for ng in BEER_NO_GO:
        if ng and ng.lower() in family.lower():
            return out("no_go", "high", "no_go", f"Familie på øl-no-go-listen: «{ng}».")

    # Ukjent/datapunktløs familie
    if snitt is None or n == 0:
        return out("neutral", "low", "ingen_data", "Ingen check-ins for denne familien.")

    recent_str = f", nyere {snitt_recent:.2f}" if snitt_recent is not None else ""

    # 2. bekymring
    if n >= _BEKYMRING_MIN_N and snitt < _BEKYMRING_AVG_THRESHOLD:
        return out("risky", "high", "bekymring",
                   f"Under bekymrings-terskel: snitt {snitt:.2f} (n={n}).")

    # 3. very_fit
    if n >= _VERY_FIT_MIN_N and snitt >= _VERY_FIT_AVG_THRESHOLD:
        return out("very_fit", "high", "bekreftet_snitt",
                   f"Bekreftet sterk preferanse: snitt {snitt:.2f} (n={n}{recent_str}).")

    # 4. fit
    if n >= _FIT_MIN_N and snitt >= _FIT_AVG_THRESHOLD:
        return out("fit", "medium", "bekreftet_familie",
                   f"Bekreftet preferanse: snitt {snitt:.2f} (n={n}{recent_str}).")

    # 5. blindspot
    if n <= _BLINDSPOT_MAX_N:
        return out("neutral", "low", "blindspot",
                   f"Blindspot: kun n={n} check-in(s) — for tynt for konklusjon.")

    # 6. default
    return out("neutral", "medium", "default",
               f"Mellom terskler: snitt {snitt:.2f} (n={n}) — verken bekreftet eller bekymring.")


def classify_beer(beer: dict, family_stats: Optional[dict[str, dict]] = None) -> dict:
    """
    Bro for batch/inferens-tid: ta et øl-dict, finn stilfamilien via
    `classify_style()`, og klassifisér den.

    `beer` kan ha: style/stil, beer_name/navn, brewery. Familien utledes fra
    style-strengen (samme mapper som genererte øl-blokken — ingen divergens).

    Returnerer classify_family-resultatet pluss `family` (utledet familie).
    """
    if family_stats is None:
        family_stats = load_family_stats()
    style = beer.get("style") or beer.get("stil") or ""
    family = classify_style(style)
    result = classify_family(family, family_stats)
    result["family"] = family
    return result


# ---------------------------------------------------------------------------
# Artefakt-generering
# ---------------------------------------------------------------------------


def build_beer_v0(family_stats: Optional[dict[str, dict]] = None) -> dict:
    """Klassifisér alle observerte familier (unntatt sekkeposter) → payload-dict."""
    if family_stats is None:
        family_stats = load_family_stats()

    families = [
        f for f in family_stats
        if f not in _EXCLUDE_FAMILIES
    ]
    results = {f: classify_family(f, family_stats) for f in families}

    tier_counts: dict[str, int] = {}
    for r in results.values():
        tier_counts[r["tier"]] = tier_counts.get(r["tier"], 0) + 1

    payload: dict = {
        "_meta": {
            "version": "beer_v0",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "data/untappd/checkins.csv (via untappd_stats.agg_by_family)",
            "n_families": len(results),
            "tier_counts": tier_counts,
        },
    }
    for f in sorted(results):
        payload[f] = results[f]
    return payload


def write_beer_v0_json(output_path: Optional[str] = None) -> str:
    """Skriv beer_v0.json til disk. Returnerer absolutt path."""
    out_path = Path(output_path) if output_path else DEFAULT_BEER_OUTPUT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_beer_v0()
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return str(out_path)


if __name__ == "__main__":
    path = write_beer_v0_json()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    meta = data["_meta"]
    print(f"Skrev: {path}")
    print(f"Klassifiserte familier: {meta['n_families']}")
    print("Tier-fordeling:")
    for tier in ("very_fit", "fit", "neutral", "risky", "no_go"):
        n = meta["tier_counts"].get(tier, 0)
        print(f"  {tier:10s} {n:4d}")
