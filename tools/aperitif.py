"""
Aperitif.no Polliste-helper

Henter Aperitif sin poengscore (1-100) og "godt kjøp"-flagg for en gitt vin
på Vinmonopolet, basert på Polets varenummer + vinens navn.

Strategi:
1. Lokal varenr → Aperitif-URL mapping i ~/.cache/sommelier/aperitif/mapping.json
2. Ved cache-miss: slå opp slug i Aperitif sitemap (cached 30 d), match mot navn
3. Verifisér at varenummeret faktisk står på siden før vi cacher
4. Cache score-resultat per varenummer i 14 dager
5. Snapshot i `data/aperitif/scores.ndjson` som fallback (se under)

Brukstilfelle: 2-5 oppslag per anbefaling. Per-vin on-demand, ikke bulk.

**Snapshotet er fallback og bulk-kilde, ikke et lag FORAN nettverket.**
`tools.refresh_aperitif` sveiper Pollistens listesider, og der står poengene —
men ikke «godt kjøp»-flagget, som bare finnes på produktsiden (verifisert på
sju listesider 2026-08-31, null treff). Flagget er ikke pynt: det kortslutter
`_value_verdict` i `value_score.py`, og 5 av 9 cachede oppslag hadde det satt.
Å lese snapshotet først ville derfor stille senket en `godt_kjop`-dom til
peer-logikk. Snapshotet brukes i stedet der det er strengt bedre enn nettet:
når nettoppslaget ikke fant vinen, når det bare fant en ANNEN årgang, og når
kalleren eksplisitt ber om offline (bulk).
"""

import html as html_lib
import json
import re
import time
from pathlib import Path
from typing import Optional

import requests

BASE = "https://www.aperitif.no"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en;q=0.7",
}

_REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = _REPO_ROOT / "data" / "aperitif" / "scores.ndjson"
SNAPSHOT_META = _REPO_ROOT / "data" / "aperitif" / "meta.json"

CACHE_DIR = Path.home() / ".cache" / "sommelier" / "aperitif"
SCORE_TTL = 14 * 24 * 60 * 60       # 14 d for score
SITEMAP_TTL = 30 * 24 * 60 * 60     # 30 d for sitemap
REQUEST_DELAY = 0.25                 # min sekunder mellom HTTP-kall (ikke før første)
_LAST_HTTP_AT = 0.0                  # global throttle-state


def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name


def _cache_fresh(path: Path, ttl: int) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) < ttl


def _load_mapping() -> dict:
    p = _cache_path("mapping.json")
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_mapping(m: dict) -> None:
    p = _cache_path("mapping.json")
    try:
        p.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _get_score_cache(polet_id: str):
    p = _cache_path(f"score_{polet_id}.json")
    if not _cache_fresh(p, SCORE_TTL):
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _set_score_cache(polet_id: str, value) -> None:
    p = _cache_path(f"score_{polet_id}.json")
    try:
        p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


# ─── Snapshot (repo-committet, se tools/refresh_aperitif.py) ─────────

_SNAPSHOT_CACHE: Optional[dict] = None


def _load_snapshot() -> dict:
    """Varenummer → rad. Tom dict hvis snapshotet ikke finnes ennå."""
    global _SNAPSHOT_CACHE
    if _SNAPSHOT_CACHE is not None:
        return _SNAPSHOT_CACHE
    rows: dict = {}
    try:
        with SNAPSHOT.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                pid = row.get("polet_id")
                if pid:
                    rows[str(pid)] = row
    except OSError:
        pass
    _SNAPSHOT_CACHE = rows
    return rows


def snapshot_score(polet_id: str) -> Optional[dict]:
    """
    Aperitif-poeng fra snapshotet, uten nettverk. None ved bom.

    `value_flag` er alltid None her — listesiden bærer ikke flagget. Feltet er
    med for at formen skal være lik nettverkssvaret, ikke fordi det er målt.
    """
    row = _load_snapshot().get(str(polet_id).strip())
    if not row:
        return None
    return {
        "polet_id": row["polet_id"],
        "score": row.get("score"),
        "wine_name": row.get("wine_name"),
        "aperitif_url": row.get("aperitif_url"),
        "value_flag": None,
        "vintage_mismatch": False,
        "source": "snapshot",
        "fetched_at": snapshot_meta().get("generated_at"),
    }


def snapshot_meta() -> dict:
    try:
        return json.loads(SNAPSHOT_META.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _http_get(url: str, timeout: int = 15) -> Optional[str]:
    global _LAST_HTTP_AT
    delta = time.time() - _LAST_HTTP_AT
    if delta < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - delta)
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
    except requests.RequestException:
        _LAST_HTTP_AT = time.time()
        return None
    _LAST_HTTP_AT = time.time()
    if r.status_code != 200:
        return None
    return r.text


# ─── Sitemap-indeks (cached 30 d) ────────────────────────────────────

def _load_sitemap_index() -> list[tuple[str, str]]:
    """
    Returnerer liste av (slug, aperitif_url) for alle Polliste-produkter.
    Cached på disk i 30 dager. Første kall: ~34 HTTP-kall.
    """
    cache_file = _cache_path("sitemap_index.json")
    if _cache_fresh(cache_file, SITEMAP_TTL):
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # Hent sitemap-indeksen
    idx_text = _http_get(f"{BASE}/sitemap.xml")
    if not idx_text:
        return []

    sitemap_urls = re.findall(
        r"<loc>([^<]+catalogproduct[^<]+)</loc>", idx_text
    )

    entries: list[tuple[str, str]] = []
    for sm_url in sitemap_urls:
        text = _http_get(sm_url)
        if not text:
            continue
        for m in re.finditer(
            r"<loc>([^<]*?/pollisten/produkt/([^<,]+),(\d+))</loc>", text
        ):
            full_url, slug, _aperitif_id = m.group(1), m.group(2), m.group(3)
            entries.append((slug, full_url))

    try:
        cache_file.write_text(
            json.dumps(entries, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass
    return entries


def _slugify(name: str) -> str:
    """Tilnærmet samme slug-regel som Aperitif bruker."""
    s = name.lower()
    s = re.sub(r"[éèê]", "e", s)
    s = re.sub(r"[áàâ]", "a", s)
    s = re.sub(r"[óòô]", "o", s)
    s = re.sub(r"[üû]", "u", s)
    s = re.sub(r"[íì]", "i", s)
    s = re.sub(r"[ñ]", "n", s)
    s = re.sub(r"[ø]", "o", s)
    s = re.sub(r"[æ]", "ae", s)
    s = re.sub(r"[å]", "a", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


def _find_url_candidates(wine_name: str, max_candidates: int = 5) -> list[str]:
    """
    Finn sannsynlige Aperitif-URLer for en gitt vin basert på slug-overlapp.
    Returnerer topp N sortert etter token-overlapp.
    """
    target_slug = _slugify(wine_name)
    target_tokens = set(t for t in target_slug.split("-") if len(t) > 2)
    if not target_tokens:
        return []

    entries = _load_sitemap_index()
    scored: list[tuple[int, str]] = []
    for slug, url in entries:
        slug_tokens = set(t for t in slug.split("-") if len(t) > 2)
        overlap = len(target_tokens & slug_tokens)
        if overlap >= max(2, len(target_tokens) // 2):
            scored.append((overlap, url))

    scored.sort(key=lambda t: -t[0])
    return [url for _, url in scored[:max_candidates]]


# ─── Parsing av produktsiden ────────────────────────────────────────

def _parse_product_page(html: str) -> dict:
    """
    Parse score, verdi-flagg, vurdering, varenr fra produktside-HTML.
    """
    result: dict = {}

    m = re.search(
        r'<span class="number">\s*(\d{2,3})\s*</span>\s*<span class="label">\s*POENG',
        html,
    )
    if m:
        result["score"] = int(m.group(1))

    # Varenumre er 5-8 siffer (målt 2026-08-31 mot catalog.ndjson: 44 stk med 5,
    # 543 med 6, 4 302 med 7, 22 513 med 8). Den gamle `\d{7,8}` bommet på de
    # 587 korte — de fikk aldri `polet_id`, og da slår BÅDE årgangs-
    # verifiseringen i pass 1 og stale-sjekken på mapping-treffet feil ut.
    # `(?!\d)` hindrer at et 9-sifret tall trunkeres til et gyldig-utseende
    # varenummer.
    m = re.search(r'"sku"\s*:\s*"?(\d{5,8})(?!\d)', html)
    if not m:
        m = re.search(r'[Vv]arenummer[^\d]{0,30}(\d{5,8})(?!\d)', html)
    if m:
        result["polet_id"] = m.group(1)

    if re.search(r"[Vv]eldig godt kj[øo]p", html):
        result["value_flag"] = "veldig_godt_kjop"
    elif re.search(r"[Gg]odt kj[øo]p", html):
        result["value_flag"] = "godt_kjop"
    else:
        result["value_flag"] = None

    m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    if m:
        result["wine_name"] = html_lib.unescape(m.group(1).strip())

    # Smaket-dato
    m = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4})", html)
    if m:
        result["tasted_date"] = m.group(1)

    return result


# ─── Hovedfunksjon ──────────────────────────────────────────────────

def get_aperitif_score(
    polet_id: str,
    wine_name: Optional[str] = None,
    *,
    use_cache: bool = True,
    offline: bool = False,
) -> Optional[dict]:
    """
    Slå opp Aperitif-score for en vin på Polet.

    Args:
        polet_id: Polets varenummer (f.eks. "13015901")
        wine_name: Vinens navn — trengs for å finne URL første gang.
                   Ignoreres om vi allerede har URL i mapping.
        use_cache: Sett False for å tvinge ferskt kall.
        offline: Bruk kun snapshotet — ingen HTTP. For bulk over katalogen.

    Returnerer dict med:
        - score (1-100), value_flag, wine_name, polet_id, aperitif_url,
          tasted_date, fetched_at

    Snapshotet i `data/aperitif/` brukes der det er strengt bedre enn nettet:
    når nettoppslaget ikke fant vinen, og når det bare fant en ANNEN årgang
    (snapshotraden er matchet på varenummer, ikke på slug-likhet). Se
    modul-docstringen for hvorfor det ikke leses FØRST.

    Returnerer None hvis ingen treff eller blokkert.
    """
    polet_id = str(polet_id).strip()

    if offline:
        return snapshot_score(polet_id)

    if use_cache:
        cached = _get_score_cache(polet_id)
        if cached is not None:
            return cached

    mapping = _load_mapping()
    url = mapping.get(polet_id)

    vintage_mismatch = False
    parsed: dict = {}
    if url is None:
        if not wine_name:
            return snapshot_score(polet_id)
        candidates = _find_url_candidates(wine_name)
        # Pass 1: eksakt varenr-match (samme årgang)
        for candidate in candidates:
            html = _http_get(candidate)
            if not html:
                continue
            parsed = _parse_product_page(html)
            if parsed.get("polet_id") == polet_id:
                url = candidate
                mapping[polet_id] = url
                _save_mapping(mapping)
                break
        # Pass 2: ingen eksakt varenr — bruk top-kandidat med flagg
        # (Aperitifs side er ofte for en annen årgang av samme vin)
        if url is None and candidates:
            html = _http_get(candidates[0])
            if html:
                parsed = _parse_product_page(html)
                if parsed.get("score"):
                    url = candidates[0]
                    vintage_mismatch = True
        if url is None:
            return snapshot_score(polet_id)
    else:
        html = _http_get(url)
        if not html:
            return snapshot_score(polet_id)
        parsed = _parse_product_page(html)
        if parsed.get("polet_id") != polet_id:
            # Mapping stale — fjern og fall tilbake
            mapping.pop(polet_id, None)
            _save_mapping(mapping)
            return get_aperitif_score(polet_id, wine_name, use_cache=False)

    if vintage_mismatch:
        # Siden gjelder en annen årgang, så både poenget og «godt kjøp»-flagget
        # der tilhører en annen vin. Har snapshotet raden, er den matchet på
        # varenummer og dermed strengt bedre — bruk den i stedet for å sende en
        # usann påstand videre (samme feilklasse som 5-sifret-varenummer-bommen).
        exact = snapshot_score(polet_id)
        if exact and exact.get("score"):
            return exact

    result = {
        **parsed,
        "polet_id": polet_id,
        "aperitif_url": url,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "vintage_mismatch": vintage_mismatch,
    }
    _set_score_cache(polet_id, result)
    return result


if __name__ == "__main__":
    import sys

    polet_id = sys.argv[1] if len(sys.argv) > 1 else "13015901"
    name = sys.argv[2] if len(sys.argv) > 2 else "Thymiopoulos Rose de Xinomavro"
    r = get_aperitif_score(polet_id, name)
    if r is None:
        print("Ingen treff på Aperitif.")
    else:
        print(json.dumps(r, indent=2, ensure_ascii=False))
