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

# Vivinos engelske vokabular → norsk, slik Polet-katalogen skriver det.
# Oversettelsen skjer her, ved generering, og ikke ved matching i `user_fit`:
# der var den en oppslags-tabell som stille reduserte blindsone-regelen til
# «land som staves likt på norsk og engelsk» (ADR-027).
LAND_EN_TO_NO: dict[str, str] = {
    "Argentina": "Argentina", "Australia": "Australia", "Austria": "Østerrike",
    "Brazil": "Brasil", "Bulgaria": "Bulgaria", "Canada": "Canada",
    "Chile": "Chile", "China": "Kina", "Croatia": "Kroatia",
    "Cyprus": "Kypros", "Czech Republic": "Tsjekkia", "England": "England",
    "France": "Frankrike", "Georgia": "Georgia", "Germany": "Tyskland",
    "Greece": "Hellas", "Hungary": "Ungarn", "Israel": "Israel",
    "Italy": "Italia", "Japan": "Japan", "Lebanon": "Libanon",
    "Moldova": "Republikken Moldova", "Morocco": "Marokko",
    "New Zealand": "New Zealand", "Portugal": "Portugal", "Romania": "Romania",
    "Serbia": "Serbia", "Slovakia": "Slovakia", "Slovenia": "Slovenia",
    "South Africa": "Sør-Afrika", "Spain": "Spania", "Sweden": "Sverige",
    "Switzerland": "Sveits", "Turkey": "Tyrkia",
    "United Kingdom": "England", "United States": "USA", "Uruguay": "Uruguay",
}

KATEGORI_EN_TO_NO: dict[str, str] = {
    "Red Wine": "Rødvin",
    "White Wine": "Hvitvin",
    "Rosé Wine": "Rosévin",
    "Sparkling": "Musserende vin",
    "Sparkling Wine": "Musserende vin",
    "Dessert Wine": "Dessertvin",
    "Fortified Wine": "Sterkvin",
}

RECENT_CUTOFF = datetime(2024, 1, 1)
MIN_N_FOR_PATTERN = 3
CONFIRM_MIN_SE = 1.0
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


def blindspots(rows: list[dict]) -> list[dict]:
    """
    Land × kategori med få datapunkter, som STRUKTUR — ikke som ferdig streng.

    Vivino skriver på engelsk («Germany», «Red Wine»), Polet-katalogen på norsk
    («Tyskland», «Rødvin»). Så lenge denne funksjonen returnerte
    «Germany Red Wine (n=2)» måtte `user_fit` oversette tilbake ved hver
    matching, og fyrte i praksis bare for land som staves likt på begge språk
    (ADR-027). Oversettelsen hører hjemme HER, én gang, der vokabularet er
    kjent og lukket — ikke i matchingen.
    """
    buckets: dict[tuple[str, str], int] = defaultdict(int)
    for r in rows:
        country = (r.get("Country") or "").strip()
        wtype = (r.get("Wine type") or "").strip()
        if country and wtype:
            buckets[(country, wtype)] += 1
    return [
        {
            "land": LAND_EN_TO_NO.get(country, country),
            "kategori": KATEGORI_EN_TO_NO.get(wtype, wtype),
            "n": n,
            "land_kilde": country,
            "kategori_kilde": wtype,
        }
        for (country, wtype), n in sorted(buckets.items(), key=lambda x: x[1])
        if n <= BLINDSPOT_MAX_N
    ]


def fmt_blindspot(b: dict) -> str:
    """Render-laget: struktur → linja som havner i smaksprofil.md."""
    return f"{b['land']} {b['kategori']} (n={b['n']})"


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


def _csv_row_to_wine(r: dict) -> dict:
    """Map en Vivino-CSV-rad til wine-dict som classify() forstår."""
    navn = f"{(r.get('Winery') or '').strip()} {(r.get('Wine name') or '').strip()}".strip()
    return {
        "navn": navn,
        "produsent": (r.get("Winery") or "").strip(),
        # Vivino har ÉTT regionfelt, og granulariteten varierer: noen ganger er
        # det appellasjonen («Crémant de Bourgogne», «Côtes du Jura»), noen
        # ganger distriktet («Rheingau», «Franken»). Polet skiller de to
        # (`district` mot `sub_District`), så feltet mates inn på begge akser
        # framfor å gjette hvilken det er. Uten `underregion` leste nivåporten
        # i `user_fit` appellasjonen via `region` og `navn` — det virket, men
        # bare tilfeldig.
        "region": (r.get("Region") or "").strip(),
        "underregion": (r.get("Region") or "").strip(),
        # Land og kategori oversettes til Polets norske vokabular HER, ved
        # inngangen. `classify()` har to innganger — Polet-katalogen og denne
        # Vivino-CSV-en — og ADR-027 (beslutning 2b) sier at samme vin må få
        # samme dom uansett hvilken. Da må begge inngangene snakke samme
        # språk før matchingen, ikke oversettes underveis i den.
        # `stil` forblir engelsk: den ER Vivinos taksonomi, og needlene
        # («Burgundy Red») er hentet fra samme sted.
        "land": LAND_EN_TO_NO.get(
            (r.get("Country") or "").strip(), (r.get("Country") or "").strip()
        ),
        "stil": (r.get("Regional wine style") or "").strip(),
        "kategori": KATEGORI_EN_TO_NO.get(
            (r.get("Wine type") or "").strip(), (r.get("Wine type") or "").strip()
        ),
    }


def confirmed_styles(rows: list[dict]) -> list[tuple[str, int, float, float | None]]:
    """Stiler som er bekreftet RELATIVT til hvordan brukeren rater kategorien.

    Den gamle regelen var absolutt: n>=3 og snitt >= 4,0. Den var ikke
    kategorinoytral. Brukeren rater ros\u00e9 3,30 og musserende 4,03 i snitt, sa en
    fast 4,0-grense stengte ros\u00e9 og hvitvin ute uansett hvor godt en stil gjorde
    det innenfor sin egen kategori — «Northern Italy Ros\u00e9» ligger +0,58 over
    brukerens eget ros\u00e9sitt pa tre distinkte viner og falt likevel.

    Ny regel, tre krav:

    1. `n >= MIN_N_FOR_PATTERN` — uendret.
    2. Stilsnittet ligger minst `CONFIRM_MIN_SE` standardfeil over snittet for
       SIN EGEN kategori. Standardfeilen skalerer med n, sa fa observasjoner ma
       sla kraftigere ut for a telle.
    3. Gulv pa brukerens totalsnitt, sa en svak kategori ikke kan kron\u00e9 middelmadighet:
       +1 SE over et lavt kategorisnitt er ikke nok alene.

    `CONFIRM_MIN_SE` er 1,0 og ikke 0,9 med vilje. 0,9 ville bevart dagens fire
    stiler uendret — det er kurvetilpasning til svaret man allerede har.
    Ved 1,0 faller «Southern Italy Red» ut pa +0,91 SE (fire viner, 0,26 over
    rodvinssnittet), og det er riktig: det er innenfor stoyen.
    """
    if not rows:
        return []
    overall = statistics.mean(r["_rating"] for r in rows)

    per_type: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        t = (r.get("Wine type") or "").strip()
        if t:
            per_type[t].append(r["_rating"])

    out = []
    for label, n_, avg, avg_recent in agg_by(rows, "Regional wine style"):
        if n_ < MIN_N_FOR_PATTERN:
            continue
        kat = next(
            ((r.get("Wine type") or "").strip() for r in rows
             if (r.get("Regional wine style") or "").strip() == label), ""
        )
        basis = per_type.get(kat, [])
        if len(basis) < MIN_N_FOR_PATTERN:
            continue
        se = statistics.stdev(basis) / (n_ ** 0.5)
        if se <= 0:
            continue
        if (avg - statistics.mean(basis)) / se < CONFIRM_MIN_SE:
            continue
        if avg < overall:
            continue
        out.append((label, n_, avg, avg_recent))
    out.sort(key=lambda t: (-t[2], -t[1]))
    return out


def positive_styles(rows: list[dict]) -> list[tuple[str, int, float, float | None]]:
    """Stiler med reell positiv evidens som likevel ikke naar toppkarakter.

    Uten dette nivaaet er profilen binaer: en stil er enten bekreftet eller
    usynlig. Da regelen ble kategori-relativ falt «Southern Italy Red» ut paa
    +0,91 SE — og 186 sicilianske rodviner gikk fra `very_fit` rett til
    «ingen regler traff», enda brukeren har ratet fire av dem 4,1 · 4,1 ·
    4,0 · 4,0. Fire ratinger over eget snitt skal ikke gi null signal.

    Krav: `n >= MIN_N_FOR_PATTERN`, snitt over brukerens totalsnitt, og IKKE
    allerede bekreftet. Disse gir `fit`, aldri `very_fit` — toppkarakteren
    forblir like streng.
    """
    if not rows:
        return []
    overall = statistics.mean(r["_rating"] for r in rows)
    bekreftet = {label for label, _, _, _ in confirmed_styles(rows)}
    out = [
        (label, n_, avg, avg_recent)
        for label, n_, avg, avg_recent in agg_by(rows, "Regional wine style")
        if n_ >= MIN_N_FOR_PATTERN and avg >= overall and label not in bekreftet
    ]
    out.sort(key=lambda t: (-t[2], -t[1]))
    return out


def region_evidence(rows: list[dict]) -> list[tuple[str, int, float, int]]:
    """Hvor mange ratede viner staar faktisk bak hver «region du dras mot»?

    Regionene er KURATERT prosa, ikke auto-derivert, saa de har aldri baaret
    tall. Det lot «Jura (Chardonnay)» staa som et moenster paa linje med
    «Nord-Italia» — enda Jura hviler paa \u00e9n vin i to aargangor og Nord-Italia
    paa titalls. Uten n kan ikke leseren skille de to.

    Tellingen gaar gjennom `user_fit._needle_hits` — den EKTE matcheren, med
    samme haystacks som `classify` bruker for regioner. En egen
    gjenimplementering her ville kunnet gi et annet svar enn regelen den skal
    beskrive, og da er tallet verre enn ingen tall.

    Returnerer [(region, n_rader, snitt, n_distinkte_viner)].
    """
    from tools.user_fit import _extract_wine_fields, _needle_hits, load_profile_rules

    regioner = load_profile_rules().get("regioner_pluss", [])
    out = []
    for needle in regioner:
        treff = []
        for r in rows:
            f = _extract_wine_fields(_csv_row_to_wine(r))
            hays = [f["region"], f["underregion"], f["produsent"], f["land"], f["navn"]]
            if _needle_hits([needle], hays, f):
                treff.append(r)
        if not treff:
            out.append((needle, 0, 0.0, 0))
            continue
        distinkte = {
            ((r.get("Winery") or "").strip(), (r.get("Wine name") or "").strip())
            for r in treff
        }
        out.append((
            needle,
            len(treff),
            statistics.mean(r["_rating"] for r in treff),
            len(distinkte),
        ))
    out.sort(key=lambda t: -t[1])
    return out


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

    confirmed = confirmed_styles(rows)
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
        "### Bekreftede mønstre (n ≥ 3, minst 1 SE over eget kategorisnitt)",
        "",
    ]
    if confirmed:
        for label, n_, avg, avg_recent in confirmed:
            recent_str = f", nyere {avg_recent:.2f}" if avg_recent else ""
            parts.append(f"- **{label}** – n={n_}, snitt {avg:.2f}{recent_str}")
    else:
        parts.append("_Ingen kategorier med tilstrekkelig datagrunnlag._")
    parts.append("")
    parts.append("### Evidens bak regionene")
    parts.append("")
    parts.append("| Region | N | Snitt | Distinkte viner |")
    parts.append("|---|---|---|---|")
    for navn_, n_, avg, dist in region_evidence(rows):
        parts.append(f"| {navn_} | {n_} | {avg:.2f} | {dist} |")
    parts.append("")
    parts.append("### Positive mønstre (n ≥ 3, over totalsnitt, under 1 SE)")
    parts.append("")
    positive = positive_styles(rows)
    if positive:
        for label, n_, avg, _ in positive:
            parts.append(f"- **{label}** – n={n_}, snitt {avg:.2f}")
    else:
        parts.append("_Ingen._")
    parts.append("")
    parts.append("### Bekymringer (n ≥ 3, snitt < 3.3)")
    parts.append("")
    if flagged:
        for label, n_, avg, avg_recent in flagged:
            parts.append(f"- **{label}** – n={n_}, snitt {avg:.2f}")
    else:
        parts.append("_Ingen stiler under terskelen._")
    parts.append("")
    parts.append("### Blindsoner, auto-derivert (land × kategori, n ≤ 2)")
    parts.append("")
    parts.append("\n".join(f"- {fmt_blindspot(b)}" for b in bs[:15]) or "_Ingen._")
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


def splice(text: str, block: str) -> str:
    """
    Sett `block` inn mellom sentinelene og la ALT annet stå urørt.

    Ren funksjon med vilje: dette er skrivestien inn i en fil som for
    det meste er håndskrevet prosa, og round-trip-testen kan bare feste
    «resten er bit-identisk» hvis spleisingen kan kjøres uten disk.
    """
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
    return new_text



def update_profile(block: str) -> None:
    PROFILE_PATH.write_text(
        splice(PROFILE_PATH.read_text(encoding="utf-8"), block), encoding="utf-8"
    )


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
