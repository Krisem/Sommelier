"""
Sveip av Aperitifs Polliste → repo-committet snapshot i `data/aperitif/`.

Aperitif rangerer hele Polets sortiment etter egne poeng (1-100). Fram til nå
har `tools.aperitif` slått opp ÉN vin av gangen via sitemap + slug-matching —
2-5 oppslag per anbefaling, og et heuristisk navnematch som kan bomme på årgang.
Denne modulen henter i stedet hele den scorede delen av lista i én kjøring og
legger den i repoet, slik at score blir tilgjengelig offline (og på Android)
uten nettverkskall ved spørretid.

Samme mønster som `data/polet/` (ADR-020): snapshot i repo, refresh er et
eksplisitt ritual.

Sondert live 2026-08-31, og verifisert på nytt før sveipen:

- **Pagineringen er stibasert.** `?side=N` returnerer side 1 uansett N. Den
  formen som virker er `/pollisten/pollisten,7,<side>` (side 1 = `/pollisten`).
- **Listeraden har alt vi trenger** — varenummer i `<span class="index">`,
  poeng i nøyaktig samme markup som `_parse_product_page` alt matcher. Ingen
  produktsider hentes.
- **Default-sortering er points_desc.** Poengene faller monotont og tar slutt
  mellom side 545 (poeng 75) og 560 (ingen poeng). Sidene etter det er
  verdiløse for dette formålet; lista fortsetter til side 1 072.
- **Ikke alle scorede rader har varenummer.** Side 520 hadde 30 rader med poeng
  og 18 med `index`-span. Rader uten varenummer telles i metaen, men skrives
  ikke — de kan ikke slås opp.
- **Listeraden har IKKE «godt kjøp»-flagget.** Verifisert på sidene 1, 300,
  520, 545, 560, 575 og 600: null treff på «godt kjøp». Flagget finnes bare på
  produktsiden. Derfor er snapshotet en fallback- og bulk-kilde i
  `get_aperitif_score`, ikke et lag FORAN nettverket — se docstringen der.

`robots.txt` (verifisert 2026-08-31): `/pollisten`-stiene er tillatt;
`?query=`, `/api/*`, `/ajax/*` og `/load` er blokkert. Vi bruker ingen av dem.

Kjør: `python3 -m tools.refresh_aperitif` ✍️  (skriver til data/aperitif/)
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Iterator, Optional

from tools.aperitif import BASE, _http_get

_REPO_ROOT = Path(__file__).resolve().parent.parent
APERITIF_DIR = _REPO_ROOT / "data" / "aperitif"
SCORES = APERITIF_DIR / "scores.ndjson"
META = APERITIF_DIR / "meta.json"

# Stibasert paginering. `?side=N` virker ikke — den returnerer side 1.
PAGE_1 = f"{BASE}/pollisten"
PAGE_N = f"{BASE}/pollisten/pollisten,7,{{page}}"

ROWS_PER_PAGE = 30          # observert konstant på alle sonderte sider
DEFAULT_MAX_PAGES = 700     # taket: poengene tar slutt ~side 555
STOP_AFTER_EMPTY = 3        # sammenhengende sider uten poeng før vi stopper

# Sorterings-vernet sammenligner MEDIAN mot median, med slakk. Første utgave
# sammenlignet sidens høyeste mot forrige sides laveste, og døde på side 133 av
# 560: side 132 hadde én enkelt 89 midt i en blokk med tretti 90-ere, og da så
# den neste siden ut som en oppadgående sortering. Lista er ikke strengt
# monoton på radnivå — den er det på sidenivå. Ekte drift (lista sorterer om,
# eller vi får side 1 tilbake) flytter medianen mange poeng, ikke ett.
SORT_TOLERANCE = 2
REQUEST_DELAY = 0.5         # sekunder mellom kall

# Listesidene er store (~390 kB) og trege: målt 0,4-12 s per side 2026-08-31.
# `_http_get` har 15 s default-timeout, og en side som er marginalt tregere
# enn normalen ble derfor lest som «svarer ikke». Første fullskala-kjøring døde
# på side 222 av den grunn, etter 220 siders arbeid. Timeouten er sveipens
# eget valg, ikke aperitif-modulens.
PAGE_TIMEOUT = 60

# Enkeltsider faller sporadisk (side 3 svarte ikke i første kjøring 2026-08-31,
# men svarte 200 på tre påfølgende forsøk rett etterpå). Et transient fall er
# IKKE drift, og skal ikke drepe en 560-siders sveip — men et vedvarende fall
# er en ekte feil vi ikke skal skrive halv data på toppen av. Stigen er lang
# nok til at en side må være borte i drøyt et minutt før vi gir opp.
RETRY_BACKOFF = (5, 15, 60)  # sekunder mellom forsøk 1→2, 2→3, 3→4


class SweepAborted(RuntimeError):
    """Drift oppdaget. Ingenting skrives — en halv fil er verre enn ingen."""


def page_url(page: int) -> str:
    return PAGE_1 if page == 1 else PAGE_N.format(page=page)


def _default_fetch(url: str) -> Optional[str]:
    return _http_get(url, timeout=PAGE_TIMEOUT)


def cached_fetch(cache_dir: Path):
    """
    Fetch som mellomlagrer hver side på disk.

    En sveip er ~560 sider à ~12 s ≈ to timer. Uten mellomlagring koster ett
    fall på side 222 alt som er hentet før den. Cachen ligger UTENFOR repoet
    og er ren mellomlagring — snapshotet skrives fortsatt atomisk til slutt,
    så «avbryt framfor å skrive halvt» står.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch(url: str) -> Optional[str]:
        side = "1" if url.endswith("/pollisten") else url.rsplit(",", 1)[1]
        p = cache_dir / f"side-{int(side):04d}.html"
        if p.exists():
            return p.read_text(encoding="utf-8")
        html = _default_fetch(url)
        if html is not None:
            p.write_text(html, encoding="utf-8")
        return html

    return fetch


# ─── Parsing (ren funksjon, fixture-testet) ──────────────────────────

_ROW_SPLIT = re.compile(r'<li class="product-list-element"')

_RE_APERITIF_ID = re.compile(r'data-product-id="(\d+)"')
_RE_LINK = re.compile(
    r'<a href="(/pollisten/produkt/[^"]+)"[^>]*title="([^"]*)"[^>]*>([^<]*)</a>'
)
_RE_AREA = re.compile(r'<span class="country-area">([^<]*)</span>')
_RE_CLASS = re.compile(r'<span class="class">([^<]*)</span>')
_RE_COUNTRY = re.compile(r'<span class="country-name">([^<]*)</span>')
_RE_PRICE = re.compile(r'<span class="price">\s*Pris:\s*([\d.,]+)')
_RE_VOLUME = re.compile(r'<span class="volume">\s*Volum:\s*([\d.,]+)')
_RE_ASSORTMENT = re.compile(r'<span class="assortment">([^<]*)</span>')
_RE_INDEX = re.compile(r'<span class="index">\((\d{5,8})\)</span>')
# Samme markup som tools.aperitif._parse_product_page matcher på produktsiden.
_RE_POINTS = re.compile(
    r'<span class="number">\s*(\d{2,3})\s*</span>\s*<span class="label">\s*POENG'
)
# Årgangen står KUN i lenketeksten («… (2018)»), ikke i title-attributtet.
_RE_VINTAGE_SUFFIX = re.compile(r"\((\d{4})\)\s*$")

# Horeca-rader uten forbrukerpris bærer 99999.00 som sentinel (7 av 210 rader
# på de sonderte sidene). En sentinel som slipper gjennom som «pris» ville
# forgiftet enhver pris-peer-statistikk, så den nulles her.
PRICE_SENTINEL = 99999.0


def _text(m: Optional[re.Match], group: int = 1) -> Optional[str]:
    if not m:
        return None
    s = html_lib.unescape(m.group(group)).strip().rstrip(",").strip()
    return s or None


def _number(m: Optional[re.Match]) -> Optional[float]:
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def parse_list_page(html: str) -> list[dict]:
    """
    Parse alle produktrader på én Polliste-side.

    Returnerer én dict per `<li class="product-list-element">`, uansett om
    raden har poeng eller varenummer — filtreringen skjer i sveipen, slik at
    metaen kan telle hva som faktisk fantes.
    """
    rows: list[dict] = []
    for block in _ROW_SPLIT.split(html)[1:]:
        block = block.split("</li>", 1)[0]

        link = _RE_LINK.search(block)
        name = _text(link, 2)
        vintage: Optional[int] = None
        if link:
            m = _RE_VINTAGE_SUFFIX.search(html_lib.unescape(link.group(3)).strip())
            if m:
                vintage = int(m.group(1))

        # `class` bærer noen ganger «Rødvin,  Italia - Toscana» — kategori
        # pluss region, og da mangler `country-area`. Splitt på første komma.
        category = _text(_RE_CLASS.search(block))
        area = _text(_RE_AREA.search(block))
        if category and "," in category:
            category, _, rest = category.partition(",")
            category = category.strip()
            if area is None and rest.strip():
                area = rest.strip()

        price = _number(_RE_PRICE.search(block))
        if price is not None and price >= PRICE_SENTINEL:
            price = None

        points = _RE_POINTS.search(block)

        rows.append(
            {
                "polet_id": _text(_RE_INDEX.search(block)),
                "score": int(points.group(1)) if points else None,
                "wine_name": name,
                "vintage": vintage,
                "country": _text(_RE_COUNTRY.search(block)),
                "area": area,
                "category": category,
                "assortment": _text(_RE_ASSORTMENT.search(block)),
                "price": price,
                "volume": _number(_RE_VOLUME.search(block)),
                "aperitif_id": _text(_RE_APERITIF_ID.search(block)),
                "aperitif_url": BASE + link.group(1) if link else None,
            }
        )
    return rows


# ─── Positiv validering ──────────────────────────────────────────────

_VALID_POLET_ID = re.compile(r"^\d{5,8}$")


def is_writable(row: dict) -> bool:
    """
    Rader vi tør skrive: gyldig varenummer, poeng i lovlig område, navn.

    Positiv validering framfor negativ (lesson 2026-05-14): vi sier hva en
    gyldig rad ER, ikke hva den ikke er, så et markup-skifte gir tomme rader
    i stedet for søppelrader.
    """
    pid = row.get("polet_id")
    score = row.get("score")
    return bool(
        isinstance(pid, str)
        and _VALID_POLET_ID.match(pid)
        and isinstance(score, int)
        and 1 <= score <= 100
        and row.get("wine_name")
    )


# ─── Sveip ───────────────────────────────────────────────────────────

def _fetch_page(fetch, page: int) -> tuple[Optional[str], int]:
    """
    Hent én side med backoff. Returnerer (html, antall omforsøk).
    html er None først når alle forsøk er brukt opp.
    """
    url = page_url(page)
    html = fetch(url)
    retries = 0
    for wait in RETRY_BACKOFF:
        if html is not None:
            break
        time.sleep(wait)
        html = fetch(url)
        retries += 1
    return html, retries


def sweep(
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    stop_after_empty: int = STOP_AFTER_EMPTY,
    delay: float = REQUEST_DELAY,
    fetch=None,
    progress=None,
) -> tuple[list[dict], dict]:
    """
    Hent sider til poengene tar slutt. Returnerer (rader, meta).

    Kaster `SweepAborted` ved drift: tom side, uendret side (paginering som
    ikke rykker) eller poeng som stiger på tvers av sider (sortering endret).
    Ingenting skrives før hele sveipen er ferdig.
    """
    fetch = fetch or _default_fetch
    rows: list[dict] = []
    seen_polet_ids: set[str] = set()
    prev_ids: Optional[set] = None
    prev_median: Optional[float] = None

    pages_fetched = 0
    retries_used = 0
    rows_seen = 0
    rows_scored = 0
    rows_scored_without_id = 0
    duplicates = 0
    empty_streak = 0
    last_scored_page = 0

    for page in range(1, max_pages + 1):
        if page > 1 and delay:
            time.sleep(delay)
        html, retries = _fetch_page(fetch, page)
        retries_used += retries
        if html is None:
            raise SweepAborted(
                f"Side {page} svarte ikke på {len(RETRY_BACKOFF) + 1} forsøk — "
                "avbryter uten å skrive."
            )

        page_rows = parse_list_page(html)
        pages_fetched += 1
        if not page_rows:
            raise SweepAborted(
                f"Side {page} ga 0 produktrader. Markup endret, eller vi er ute "
                "av lista — avbryter uten å skrive."
            )

        ids = {r["aperitif_id"] for r in page_rows if r.get("aperitif_id")}
        if prev_ids is not None and ids and ids == prev_ids:
            raise SweepAborted(
                f"Side {page} er identisk med side {page - 1} — pagineringen "
                "rykker ikke. Avbryter uten å skrive."
            )
        prev_ids = ids

        scored = [r for r in page_rows if isinstance(r.get("score"), int)]
        page_scores = [r["score"] for r in scored]
        page_median = statistics.median(page_scores) if page_scores else None
        if page_median is not None and prev_median is not None:
            if page_median > prev_median + SORT_TOLERANCE:
                raise SweepAborted(
                    f"Side {page} har median {page_median} mot forrige sides "
                    f"{prev_median} — sorteringen er ikke lenger points_desc. "
                    "Avbryter uten å skrive."
                )
        if page_median is not None:
            prev_median = page_median

        rows_seen += len(page_rows)
        rows_scored += len(scored)
        for r in scored:
            if not is_writable(r):
                rows_scored_without_id += 1
                continue
            if r["polet_id"] in seen_polet_ids:
                duplicates += 1
                continue
            seen_polet_ids.add(r["polet_id"])
            rows.append(r)

        if progress:
            progress(page, len(page_rows), len(scored), len(rows))

        if scored:
            empty_streak = 0
            last_scored_page = page
        else:
            empty_streak += 1
            if empty_streak >= stop_after_empty:
                break

    meta = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": f"{BASE}/pollisten (listesider, sortert points_desc)",
        "pages_fetched": pages_fetched,
        "page_retries": retries_used,
        "last_page_with_points": last_scored_page,
        "rows_seen": rows_seen,
        "rows_scored": rows_scored,
        "rows_written": len(rows),
        "rows_scored_without_varenummer": rows_scored_without_id,
        "duplicate_varenumre_skipped": duplicates,
        "score_range": (
            [min(r["score"] for r in rows), max(r["score"] for r in rows)]
            if rows else None
        ),
        "forbehold": {
            "prisbias": (
                "Spearman(poeng, pris) = +0,65 for whisky og +0,80 for DN-vin. "
                "«Høyest score» ≈ «dyrest». Prissone-lås er en FORUTSETNING for "
                "å bruke disse poengene til rangering, ikke pynt."
            ),
            "ingen_kjopsflagg": (
                "Listeraden bærer ikke «godt kjøp»/«veldig godt kjøp» — det "
                "flagget finnes bare på produktsiden. Snapshotet er derfor "
                "fallback og bulk-kilde i get_aperitif_score, ikke et lag foran "
                "nettverket."
            ),
            "dekning": (
                "Rader uten varenummer i listeraden er utelatt — de kan ikke "
                "slås opp mot Polet. Se rows_scored_without_varenummer."
            ),
        },
    }
    return rows, meta


def _write_atomic(path: Path, text: str) -> None:
    """Skriv via .tmp i SAMME mappe, så os.replace.

    `sweep()` holder alle radene i minnet og skriver først til slutt, så
    skrivevinduet er det ene sekundet der en to timers sveip kan bli til en
    halv fil. `.tmp` må ligge i samme mappe fordi `os.replace` bare er atomisk
    innenfor ett filsystem.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_snapshot(rows: list[dict], meta: dict, *, directory: Path = APERITIF_DIR) -> None:
    """Deterministisk serialisering, sortert på varenummer (konfliktfrie merges)."""
    directory.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda r: int(r["polet_id"]))
    _write_atomic(
        directory / SCORES.name,
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in ordered),
    )
    _write_atomic(
        directory / META.name, json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
    )


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    ap.add_argument("--delay", type=float, default=REQUEST_DELAY)
    ap.add_argument("--stop-after-empty", type=int, default=STOP_AFTER_EMPTY)
    ap.add_argument("--dry-run", action="store_true", help="ikke skriv til disk")
    ap.add_argument(
        "--cache-dir",
        help="mellomlagre hentede sider her, så en avbrutt sveip kan gjenopptas",
    )
    args = ap.parse_args(argv)

    def progress(page, n_rows, n_scored, total):
        if page % 10 == 0 or n_scored == 0:
            print(
                f"side {page:4d}: {n_rows} rader, {n_scored} med poeng, "
                f"{total} skrivbare totalt",
                flush=True,
            )

    try:
        rows, meta = sweep(
            max_pages=args.max_pages,
            stop_after_empty=args.stop_after_empty,
            delay=args.delay,
            fetch=cached_fetch(Path(args.cache_dir)) if args.cache_dir else None,
            progress=progress,
        )
    except SweepAborted as e:
        print(f"AVBRUTT: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return 0

    write_snapshot(rows, meta)
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
