"""
Auto-derived øl-statistikk fra Untappd-CSV.

Leser data/untappd/checkins.csv og oppdaterer en managed blokk i
knowledge/smaksprofil.md mellom sentinels:

    <!-- BEGIN AUTO-DERIVED-BEER (untappd_stats.py) -->
    ...
    <!-- END AUTO-DERIVED-BEER -->

Kjør: python3 tools/untappd_stats.py
"""

from __future__ import annotations

import csv
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "untappd" / "checkins.csv"
PROFILE_PATH = ROOT / "knowledge" / "smaksprofil.md"

BEGIN = "<!-- BEGIN AUTO-DERIVED-BEER (untappd_stats.py) -->"
END = "<!-- END AUTO-DERIVED-BEER -->"

RECENT_CUTOFF = datetime(2024, 1, 1)
MIN_N_FOR_PATTERN = 2  # Lower than wine — beer dataset is more exploratory
BLINDSPOT_MAX_N = 1


# Stilfamilie-klassifisering (substring-baseret, første treff vinner)
STYLE_FAMILIES = [
    ("Lambic / Gueuze / Wild", ["lambic", "gueuze", "wild ale", "flanders"]),
    ("Sur (Berliner / Gose / Sour)", ["berliner", "gose", "sour"]),
    ("Belgian Strong / Trappist", ["tripel", "dubbel", "quadrupel", "quad", "belgian strong", "abbey", "trappist"]),
    ("Saison / Farmhouse", ["saison", "farmhouse", "bière de garde"]),
    ("Witbier / Belgian Pale", ["witbier", "wit", "belgian pale", "belgian blonde"]),
    ("Hefeweizen / Weizen", ["hefeweizen", "weizen", "wheat"]),
    ("NEIPA / Hazy IPA", ["new england", "neipa", "hazy"]),
    ("Imperial / Double IPA", ["imperial ipa", "double ipa", "dipa"]),
    ("IPA (standard)", ["ipa"]),
    ("Pale Ale", ["pale ale"]),
    ("Imperial Stout / BA Stout", ["imperial stout", "barrel-aged stout", "barrel aged stout"]),
    ("Stout (standard)", ["stout"]),
    ("Porter / Baltic Porter", ["porter"]),
    ("Brown / Mild / Bitter", ["brown ale", "mild", "bitter", "esb"]),
    ("Barleywine / Old Ale / Wee Heavy", ["barleywine", "old ale", "wee heavy", "scotch ale"]),
    ("Bock / Doppelbock / Eisbock", ["bock", "doppelbock", "eisbock"]),
    ("Schwarzbier / Dunkel", ["schwarz", "dunkel"]),
    ("Märzen / Festbier / Vienna", ["märzen", "marzen", "festbier", "vienna lager"]),
    ("Pilsner", ["pilsner", "pils"]),
    ("Helles / Lager", ["helles", "lager"]),
    ("Kölsch / Altbier", ["kölsch", "kolsch", "altbier"]),
    ("Rauchbier / Smoked", ["rauch", "smoked"]),
    ("Fruit / Spice / Specialty", ["fruit", "spice", "pumpkin", "specialty"]),
    ("Cider / Mead / Other", ["cider", "mead", "perry"]),
]


def classify_style(style: str) -> str:
    s = (style or "").lower()
    for label, needles in STYLE_FAMILIES:
        if any(n in s for n in needles):
            return label
    return "Annet / uklassifisert"


def load_rated() -> list[dict]:
    rows = []
    with CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            yr = r.get("your_rating") or ""
            try:
                rating = float(yr)
            except ValueError:
                continue
            if rating <= 0:
                continue
            scan = r.get("checkin_date") or ""
            try:
                r["_dt"] = datetime.fromisoformat(scan.replace("Z", "+00:00")) if scan else None
            except ValueError:
                r["_dt"] = None
            r["_rating"] = rating
            try:
                r["_abv"] = float(r.get("abv_percent") or 0) or None
            except ValueError:
                r["_abv"] = None
            try:
                r["_ibu"] = float(r.get("ibu") or 0) or None
            except ValueError:
                r["_ibu"] = None
            r["_family"] = classify_style(r.get("style", ""))
            rows.append(r)
    return rows


def agg_by(rows: list[dict], key: str) -> list[tuple[str, int, float, float | None]]:
    """[(label, n, avg, avg_recent_or_None)] sortert på n desc."""
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
        recent = [x["_rating"] for x in items if x.get("_dt") and x["_dt"].replace(tzinfo=None) >= RECENT_CUTOFF]
        avg_recent = statistics.mean(recent) if recent else None
        out.append((label, n, avg, avg_recent))
    out.sort(key=lambda t: (-t[1], -t[2]))
    return out


def agg_by_family(rows: list[dict]) -> list[tuple[str, int, float, float | None]]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        buckets[r["_family"]].append(r)
    out = []
    for label, items in buckets.items():
        n = len(items)
        avg = statistics.mean(x["_rating"] for x in items)
        recent = [x["_rating"] for x in items if x.get("_dt") and x["_dt"].replace(tzinfo=None) >= RECENT_CUTOFF]
        avg_recent = statistics.mean(recent) if recent else None
        out.append((label, n, avg, avg_recent))
    out.sort(key=lambda t: (-t[1], -t[2]))
    return out


def agg_by_abv_bucket(rows: list[dict]) -> list[tuple[str, int, float]]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        abv = r.get("_abv")
        if abv is None:
            continue
        if abv < 4.0:
            b = "<4 % (session)"
        elif abv < 5.5:
            b = "4–5,5 % (standard)"
        elif abv < 7.0:
            b = "5,5–7 % (sterkøl)"
        elif abv < 9.0:
            b = "7–9 % (DIPA/Tripel-range)"
        elif abv < 11.0:
            b = "9–11 % (Imperial/Quad)"
        else:
            b = "11+ % (BA / Extreme)"
        buckets[b].append(r["_rating"])
    order = [
        "<4 % (session)",
        "4–5,5 % (standard)",
        "5,5–7 % (sterkøl)",
        "7–9 % (DIPA/Tripel-range)",
        "9–11 % (Imperial/Quad)",
        "11+ % (BA / Extreme)",
    ]
    return [(b, len(buckets[b]), statistics.mean(buckets[b])) for b in order if buckets[b]]


def agg_by_month(rows: list[dict]) -> list[tuple[str, int, float]]:
    buckets: dict[int, list[float]] = defaultdict(list)
    for r in rows:
        dt = r.get("_dt")
        if not dt:
            continue
        buckets[dt.month].append(r["_rating"])
    names = [
        "Jan", "Feb", "Mar", "Apr", "Mai", "Jun",
        "Jul", "Aug", "Sep", "Okt", "Nov", "Des",
    ]
    return [(names[m - 1], len(buckets[m]), statistics.mean(buckets[m])) for m in range(1, 13) if buckets[m]]


def fmt_table(rows: list[tuple], headers: list[str], min_n: int = 1) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows:
        if len(row) >= 2 and isinstance(row[1], int) and row[1] < min_n:
            continue
        cells = []
        for v in row:
            if isinstance(v, float):
                cells.append(f"{v:.2f}")
            elif v is None:
                cells.append("–")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def top_and_bottom(rows: list[dict], k: int = 8) -> tuple[list[dict], list[dict]]:
    s = sorted(rows, key=lambda r: r["_rating"])
    return s[-k:][::-1], s[:k]


def recent_vs_old(rows: list[dict]) -> tuple[float | None, float | None, int, int]:
    recent = [r["_rating"] for r in rows if r.get("_dt") and r["_dt"].replace(tzinfo=None) >= RECENT_CUTOFF]
    old = [r["_rating"] for r in rows if r.get("_dt") and r["_dt"].replace(tzinfo=None) < RECENT_CUTOFF]
    avg_r = statistics.mean(recent) if recent else None
    avg_o = statistics.mean(old) if old else None
    return avg_r, avg_o, len(recent), len(old)


def fmt_beer(r: dict) -> str:
    brewery = r.get("brewery") or ""
    name = r.get("beer_name") or ""
    style = r.get("style") or ""
    abv = r.get("_abv")
    abv_str = f" {abv:.1f}%" if abv else ""
    return f"{r['_rating']:.1f} – {brewery} {name} ({style}){abv_str}"


def adventurousness(rows: list[dict]) -> dict:
    total = len(rows)
    unique_styles = len({r.get("style") for r in rows})
    unique_breweries = len({r.get("brewery") for r in rows})
    unique_families = len({r["_family"] for r in rows})
    return {
        "total": total,
        "unique_styles": unique_styles,
        "unique_breweries": unique_breweries,
        "unique_families": unique_families,
        "style_diversity_ratio": unique_styles / total if total else 0,
        "brewery_diversity_ratio": unique_breweries / total if total else 0,
    }


def render(rows: list[dict]) -> str:
    today = datetime.now().date().isoformat()
    n = len(rows)
    overall = statistics.mean(r["_rating"] for r in rows)
    avg_r, avg_o, n_r, n_o = recent_vs_old(rows)

    by_family = agg_by_family(rows)
    by_style = agg_by(rows, "style")
    by_brewery = agg_by(rows, "brewery")
    by_abv = agg_by_abv_bucket(rows)
    by_month = agg_by_month(rows)

    top, bottom = top_and_bottom(rows, k=8)
    adv = adventurousness(rows)

    confirmed = [(l, n_, a, a_r) for l, n_, a, a_r in by_family if n_ >= MIN_N_FOR_PATTERN and a >= 3.8]
    flagged = [(l, n_, a, a_r) for l, n_, a, a_r in by_family if n_ >= MIN_N_FOR_PATTERN and a < 3.2]

    blindspot_families = [l for l, n_, _, _ in by_family if n_ <= BLINDSPOT_MAX_N]

    parts = [
        BEGIN,
        "## Auto-derivert øl-statistikk (Untappd)",
        "",
        f"> Generert {today} av `tools/untappd_stats.py`. Ikke rediger manuelt – kjør på nytt etter ny Untappd-scrape.",
        f"> Grunnlag: {n} ratede check-ins, snitt {overall:.2f}.",
        f"> Mangfold: {adv['unique_breweries']} unike bryggerier, {adv['unique_styles']} unike stiler, {adv['unique_families']} stilfamilier.",
        f"> Stildiversitet: {adv['style_diversity_ratio']:.1%} av check-ins er nye stiler – {'svært utforskende' if adv['style_diversity_ratio'] > 0.6 else 'moderat utforskende' if adv['style_diversity_ratio'] > 0.4 else 'fokusert'}.",
    ]
    if avg_r is not None:
        parts.append(f"> Nyere (2024+): {n_r} check-ins, snitt {avg_r:.2f}.")
    if avg_o is not None:
        parts.append(f"> Eldre (før 2024): {n_o} check-ins, snitt {avg_o:.2f}.")
    parts.append("")

    parts.append("### Per stilfamilie")
    parts.append("")
    parts.append(fmt_table(by_family, ["Stilfamilie", "N", "Snitt", "Snitt 2024+"]))
    parts.append("")

    parts.append("### Per ABV-spenn")
    parts.append("")
    parts.append(fmt_table(by_abv, ["ABV", "N", "Snitt"]))
    parts.append("")

    parts.append("### Bekreftede preferanser (n ≥ 2, snitt ≥ 3.8)")
    parts.append("")
    if confirmed:
        for label, n_, avg, avg_recent in confirmed:
            recent_str = f", nyere {avg_recent:.2f}" if avg_recent else ""
            parts.append(f"- **{label}** – n={n_}, snitt {avg:.2f}{recent_str}")
    else:
        parts.append("_Ingen kategorier med tilstrekkelig datagrunnlag._")
    parts.append("")

    parts.append("### Bekymringer (n ≥ 2, snitt < 3.2)")
    parts.append("")
    if flagged:
        for label, n_, avg, avg_recent in flagged:
            parts.append(f"- **{label}** – n={n_}, snitt {avg:.2f}")
    else:
        parts.append("_Ingen familier under terskelen._")
    parts.append("")

    parts.append("### Blindspots (familier med n ≤ 1)")
    parts.append("")
    if blindspot_families:
        parts.append("\n".join(f"- {b}" for b in blindspot_families))
    else:
        parts.append("_Ingen åpenbare blindspots på familienivå._")
    parts.append("")

    parts.append("### Sesong-mønster (snitt rating per måned)")
    parts.append("")
    parts.append(fmt_table(by_month, ["Måned", "N", "Snitt"]))
    parts.append("")

    parts.append("### Topp 8 ratede ølene")
    parts.append("")
    parts.extend(f"- {fmt_beer(r)}" for r in top)
    parts.append("")

    parts.append("### Bunn 8 ratede ølene")
    parts.append("")
    parts.extend(f"- {fmt_beer(r)}" for r in bottom)
    parts.append("")

    top_breweries = [b for b in by_brewery if b[1] >= 2][:10]
    if top_breweries:
        parts.append("### Mest besøkte bryggerier (n ≥ 2)")
        parts.append("")
        parts.append(fmt_table(top_breweries, ["Bryggeri", "N", "Snitt", "Snitt 2024+"]))
        parts.append("")

    parts.append(END)
    return "\n".join(parts)


def update_profile(block: str) -> None:
    text = PROFILE_PATH.read_text(encoding="utf-8")
    if BEGIN in text and END in text:
        start = text.index(BEGIN)
        end = text.index(END) + len(END)
        new_text = text[:start] + block + text[end:]
    else:
        # Sett inn etter eksisterende vin-auto-derivert blokk hvis mulig
        wine_end = "<!-- END AUTO-DERIVED -->"
        if wine_end in text:
            idx = text.index(wine_end) + len(wine_end)
            new_text = text[:idx] + "\n\n" + block + text[idx:]
        else:
            new_text = text.rstrip() + "\n\n" + block + "\n"
    PROFILE_PATH.write_text(new_text, encoding="utf-8")


def main() -> None:
    rows = load_rated()
    block = render(rows)
    update_profile(block)
    print(f"Oppdaterte {PROFILE_PATH} med {len(rows)} ratede øl-check-ins.")


if __name__ == "__main__":
    main()
