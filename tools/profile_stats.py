"""
Auto-derived smaksprofil-statistikk fra Vivino-CSV.

Leser data/vivino/full_wine_list.csv og oppdaterer en managed blokk i
knowledge/smaksprofil.md mellom sentinels:

    <!-- BEGIN AUTO-DERIVED (profile_stats.py) -->
    ...
    <!-- END AUTO-DERIVED -->

Kjør: python3 tools/profile_stats.py
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "vivino" / "full_wine_list.csv"
PROFILE_PATH = ROOT / "knowledge" / "smaksprofil.md"

BEGIN = "<!-- BEGIN AUTO-DERIVED (profile_stats.py) -->"
END = "<!-- END AUTO-DERIVED -->"

RECENT_CUTOFF = datetime(2024, 1, 1)
MIN_N_FOR_PATTERN = 3
BLINDSPOT_MAX_N = 2


def load_rated() -> list[dict]:
    rows = []
    with CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            yr = r.get("Your rating") or ""
            try:
                rating = float(yr)
            except ValueError:
                continue
            if rating <= 0:
                continue
            scan = r.get("Scan date") or ""
            try:
                r["_dt"] = datetime.fromisoformat(scan.split(" ")[0]) if scan else None
            except ValueError:
                r["_dt"] = None
            r["_rating"] = rating
            rows.append(r)
    return rows


def agg_by(rows: list[dict], key: str) -> list[tuple[str, int, float, float | None]]:
    """Return [(label, n, avg, avg_recent_or_None)] sorted by n desc."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        label = (r.get(key) or "").strip()
        if not label:
            continue
        buckets[label].append(r)

    out = []
    for label, items in buckets.items():
        n = len(items)
        avg = statistics.mean(x["_rating"] for x in items)
        recent = [x["_rating"] for x in items if x.get("_dt") and x["_dt"] >= RECENT_CUTOFF]
        avg_recent = statistics.mean(recent) if recent else None
        out.append((label, n, avg, avg_recent))
    out.sort(key=lambda t: (-t[1], -t[2]))
    return out


def fmt_table(rows: list[tuple[str, int, float, float | None]], min_n: int = 1) -> str:
    lines = ["| Kategori | N | Snitt | Snitt 2024+ |", "|---|---|---|---|"]
    for label, n, avg, avg_recent in rows:
        if n < min_n:
            continue
        recent_str = f"{avg_recent:.2f}" if avg_recent is not None else "–"
        lines.append(f"| {label} | {n} | {avg:.2f} | {recent_str} |")
    return "\n".join(lines)


def blindspots(rows: list[dict]) -> list[str]:
    """Kategorier (Country + Wine type) med få datapunkter."""
    buckets: dict[tuple[str, str], int] = defaultdict(int)
    for r in rows:
        country = (r.get("Country") or "").strip()
        wtype = (r.get("Wine type") or "").strip()
        if country and wtype:
            buckets[(country, wtype)] += 1
    return [
        f"{country} {wtype} (n={n})"
        for (country, wtype), n in sorted(buckets.items(), key=lambda x: x[1])
        if n <= BLINDSPOT_MAX_N
    ]


def top_and_bottom(rows: list[dict], k: int = 5) -> tuple[list[dict], list[dict]]:
    s = sorted(rows, key=lambda r: r["_rating"])
    return s[-k:][::-1], s[:k]


def recent_vs_old(rows: list[dict]) -> tuple[float | None, float | None, int, int]:
    recent = [r["_rating"] for r in rows if r.get("_dt") and r["_dt"] >= RECENT_CUTOFF]
    old = [r["_rating"] for r in rows if r.get("_dt") and r["_dt"] < RECENT_CUTOFF]
    avg_r = statistics.mean(recent) if recent else None
    avg_o = statistics.mean(old) if old else None
    return avg_r, avg_o, len(recent), len(old)


def fmt_wine(r: dict) -> str:
    name = f"{r.get('Winery', '')} {r.get('Wine name', '')}".strip()
    vintage = r.get("Vintage") or ""
    year = f" {vintage}" if vintage else ""
    return f"{r['_rating']:.1f} – {name}{year}"


def render(rows: list[dict]) -> str:
    today = datetime.now().date().isoformat()
    n = len(rows)
    overall = statistics.mean(r["_rating"] for r in rows)
    avg_r, avg_o, n_r, n_o = recent_vs_old(rows)

    by_type = agg_by(rows, "Wine type")
    by_country = agg_by(rows, "Country")
    by_style = agg_by(rows, "Regional wine style")
    by_region = agg_by(rows, "Region")

    top, bottom = top_and_bottom(rows, k=5)

    confirmed = [(l, n_, a, a_r) for l, n_, a, a_r in by_style if n_ >= MIN_N_FOR_PATTERN and a >= 4.0]
    flagged = [(l, n_, a, a_r) for l, n_, a, a_r in by_style if n_ >= MIN_N_FOR_PATTERN and a < 3.3]

    bs = blindspots(rows)

    parts = [
        BEGIN,
        f"## Auto-derivert statistikk",
        "",
        f"> Generert {today} av `tools/profile_stats.py`. Ikke rediger manuelt – kjør scriptet på nytt etter Vivino-eksport.",
        f"> Grunnlag: {n} ratede viner, snitt {overall:.2f}.",
        f"> Nyere ratings (2024-01-01+): {n_r} viner, snitt {avg_r:.2f}." if avg_r else "",
        f"> Eldre ratings (før 2024): {n_o} viner, snitt {avg_o:.2f}." if avg_o else "",
        "",
        "### Per vintype",
        "",
        fmt_table(by_type),
        "",
        "### Per land (topp etter N)",
        "",
        fmt_table([r for r in by_country if r[1] >= 2][:15]),
        "",
        "### Per regional stil (n ≥ 2)",
        "",
        fmt_table([r for r in by_style if r[1] >= 2][:20]),
        "",
        "### Bekreftede mønstre (n ≥ 3, snitt ≥ 4.0)",
        "",
    ]
    if confirmed:
        for label, n_, avg, avg_recent in confirmed:
            recent_str = f", nyere {avg_recent:.2f}" if avg_recent else ""
            parts.append(f"- **{label}** – n={n_}, snitt {avg:.2f}{recent_str}")
    else:
        parts.append("_Ingen kategorier med tilstrekkelig datagrunnlag._")
    parts.append("")
    parts.append("### Bekymringer (n ≥ 3, snitt < 3.3)")
    parts.append("")
    if flagged:
        for label, n_, avg, avg_recent in flagged:
            parts.append(f"- **{label}** – n={n_}, snitt {avg:.2f}")
    else:
        parts.append("_Ingen stiler under terskelen._")
    parts.append("")
    parts.append("### Blindspots (kategori-kombinasjoner med n ≤ 2)")
    parts.append("")
    parts.append("\n".join(f"- {b}" for b in bs[:15]) or "_Ingen._")
    parts.append("")
    parts.append("### Topp 5 ratede viner")
    parts.append("")
    parts.extend(f"- {fmt_wine(r)}" for r in top)
    parts.append("")
    parts.append("### Bunn 5 ratede viner")
    parts.append("")
    parts.extend(f"- {fmt_wine(r)}" for r in bottom)
    parts.append("")
    parts.append(END)

    return "\n".join(p for p in parts if p is not None)


def update_profile(block: str) -> None:
    text = PROFILE_PATH.read_text(encoding="utf-8")
    if BEGIN in text and END in text:
        start = text.index(BEGIN)
        end = text.index(END) + len(END)
        new_text = text[:start] + block + text[end:]
    else:
        marker = "## Datagrunnlag (kort)"
        if marker in text:
            idx = text.index(marker)
            new_text = text[:idx] + block + "\n\n" + text[idx:]
        else:
            new_text = text.rstrip() + "\n\n" + block + "\n"
    PROFILE_PATH.write_text(new_text, encoding="utf-8")


def main() -> None:
    rows = load_rated()
    block = render(rows)
    update_profile(block)
    print(f"Oppdaterte {PROFILE_PATH} med {len(rows)} ratede viner.")

    # Etter at smaksprofil-blokken er regenerert, regenerér user-fit
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from tools.user_fit import write_v0_json
        path = write_v0_json()
        print(f"User-fit v0 regenerert: {path}")
    except Exception as e:
        print(f"User-fit-regenerering hoppet over: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
