#!/usr/bin/env python3
"""
Engangs-migrering av katalog-shapen i `data/polet/catalog.ndjson`.

Strippper `polet_store.PRUNED_CATALOG_FIELDS` fra hver eksisterende rad
(`productAvailability`, `images`, `main_sub_category` — se konstanten for
byte-andeler og hvorfor ingen leser dem) og skriver katalogen tilbake med
`polet_store`s egen deterministiske serialisering, via temp-fil + atomisk
rename. `catalog_meta.json` re-deriveres fra de prunede radene, men
`generated_at` BEVARES: dette er en shape-endring, ikke en refresh — å bumpe
tidsstempelet ville falskt friskmeldt pris og lager.

Idempotent: kjør to ganger → identisk fil. Ingen rader forsvinner (antall før
== antall etter er en hard assert, ikke bare en rapport).

    python3 tools/migrate_catalog_shape.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import polet_store  # noqa: E402


def _serialize(products: list[dict]) -> str:
    """Samme serialisering som `polet_store._write_catalog` — uten å skrive."""
    ordered = sorted(products, key=lambda p: str(p.get("code", "")))
    lines = [json.dumps(p, ensure_ascii=False, sort_keys=True) for p in ordered]
    return "\n".join(lines) + ("\n" if lines else "")


def migrate(*, dry_run: bool = False) -> dict:
    """
    Prune katalogen. Returnerer en rapport-dict med rader/bytes før og etter.
    Skriver ingenting når `dry_run`.
    """
    if not polet_store.CATALOG.exists():
        raise FileNotFoundError(f"Fant ingen katalog å migrere: {polet_store.CATALOG}")

    bytes_før = polet_store.CATALOG.stat().st_size
    rader = polet_store.read_catalog()
    prunet = [polet_store._prune_product(p) for p in rader]

    # Radbevaring er en invariant, ikke et måltall: en migrering som mister
    # viner er verre enn en som ikke sparer bytes.
    assert len(prunet) == len(rader), "Migreringen mistet rader — avbryter"

    tekst = _serialize(prunet)
    bytes_etter = len(tekst.encode("utf-8"))

    fjernet = {felt: 0 for felt in polet_store.PRUNED_CATALOG_FIELDS}
    for rad in rader:
        for felt in fjernet:
            if felt in rad:
                fjernet[felt] += 1

    if not dry_run:
        polet_store._atomic_write_text(polet_store.CATALOG, tekst)
        generated_at = polet_store.catalog_generated_at()
        if generated_at:
            polet_store._write_meta(prunet, generated_at=generated_at)

    return {
        "rader_før": len(rader),
        "rader_etter": len(prunet),
        "bytes_før": bytes_før,
        "bytes_etter": bytes_etter,
        "spart_prosent": (
            100.0 * (bytes_før - bytes_etter) / bytes_før if bytes_før else 0.0
        ),
        "felt_fjernet_fra": fjernet,
        "dry_run": dry_run,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Prune shape i data/polet/catalog.ndjson")
    ap.add_argument(
        "--dry-run", action="store_true", help="rapportér uten å skrive noe"
    )
    args = ap.parse_args()

    r = migrate(dry_run=args.dry_run)

    print(f"Katalog: {polet_store.CATALOG}")
    print(f"  rader:  {r['rader_før']} → {r['rader_etter']}"
          f"{'  ✓ bevart' if r['rader_før'] == r['rader_etter'] else '  ✗ AVVIK'}")
    print(f"  bytes:  {r['bytes_før']:,} → {r['bytes_etter']:,}"
          .replace(",", " "))
    print(f"  spart:  {r['spart_prosent']:.1f} %"
          f" ({(r['bytes_før'] - r['bytes_etter']) / 1_048_576:.2f} MiB)")
    for felt, n in r["felt_fjernet_fra"].items():
        print(f"  fjernet {felt} fra {n} rader")
    print("  (dry-run — ingenting skrevet)" if r["dry_run"] else "  skrevet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
