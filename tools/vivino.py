"""
Vivino rating-helper (uoffisielt explore-API)

Henter average rating + antall ratings for en gitt vin (navn + valgfri årgang).
Brukstilfelle: 2-5 oppslag per anbefaling, ikke bulk. ToS-gråsone — kun ok
for personlig, ikke-kommersiell bruk.

Returnerer både vintage-spesifikk rating og vin-aggregert rating. Caller bør
foretrekke vintage-rating når ratings_count >= 50, ellers fall tilbake til
wine-aggregat.
"""

import hashlib
import json
import time
import urllib.parse
from pathlib import Path
from typing import Optional

import requests

BASE = "https://www.vivino.com/api/explore/explore"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

CACHE_DIR = Path.home() / ".cache" / "sommelier" / "vivino"
CACHE_TTL = 7 * 24 * 60 * 60  # 7 dager


def _cache_path(key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{h}.json"


def _cache_get(key: str):
    p = _cache_path(key)
    if not p.exists():
        return None
    if (time.time() - p.stat().st_mtime) > CACHE_TTL:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _cache_set(key: str, value) -> None:
    p = _cache_path(key)
    try:
        p.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _pick_vintage(matches: list, target_year: Optional[int]) -> dict:
    """Velg matchen som er nærmest target_year, med flest ratings som tiebreak."""
    if target_year is not None:
        exact = [m for m in matches if m["vintage"]["year"] == target_year]
        if exact:
            return max(
                exact,
                key=lambda m: m["vintage"]["statistics"].get("ratings_count", 0),
            )
    return max(
        matches,
        key=lambda m: m["vintage"]["statistics"].get("wine_ratings_count", 0),
    )


def _filter_by_name(matches: list, wine_name: str) -> list:
    """
    Behold kun matches der navne-overlap er maksimalt (mot søketokens).
    Forhindrer at populære feil viner ranker over mindre populære riktige.
    """
    query_tokens = {
        t.lower().strip("'.,")
        for t in wine_name.split()
        if len(t) > 2 and not t.isdigit()
    }
    if not query_tokens:
        return matches

    def overlap(m):
        w = m["vintage"]["wine"]
        full = (
            (w.get("name", "") + " " + w.get("winery", {}).get("name", ""))
            .lower()
        )
        return sum(1 for t in query_tokens if t in full)

    scored = [(overlap(m), m) for m in matches]
    max_score = max(s for s, _ in scored)
    if max_score == 0:
        return matches
    return [m for s, m in scored if s == max_score]


def get_vivino_rating(
    wine_name: str,
    vintage: Optional[int] = None,
    *,
    use_cache: bool = True,
) -> Optional[dict]:
    """
    Søk Vivino på vinnavn, returner rating + lenker.

    Args:
        wine_name: Fritekstsøk, f.eks. "Thymiopoulos Rose Xinomavro"
        vintage: Valgfri årgang. Hvis satt, foretrekkes eksakt match.
        use_cache: Sett False for å tvinge ferskt kall.

    Returns dict med:
        - matched_wine, matched_winery, matched_vintage
        - vintage_rating, vintage_ratings_count   (årgangs-spesifikk)
        - wine_rating, wine_ratings_count         (vin-aggregat, mer stabilt)
        - region, country
        - url (vintage-side), wine_url (aggregat-side)
        - exact_vintage_match (bool)
        - name_match_confidence: "exact" | "partial" | "weak"
        - total_matches

    Returnerer None hvis ingen treff eller blokkert.
    """
    cache_key = f"{wine_name.lower().strip()}|{vintage or ''}"
    if use_cache:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    params = {
        "search_term": wine_name,
        "per_page": 25,
        "order_by": "ratings_count",
        "order": "desc",
    }
    url = f"{BASE}?{urllib.parse.urlencode(params)}"

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
    except requests.RequestException:
        return None

    if r.status_code in (403, 429):
        return None
    if r.status_code != 200:
        return None

    try:
        data = r.json()
    except ValueError:
        return None

    matches = data.get("explore_vintage", {}).get("matches", [])
    if not matches:
        return None

    matches = _filter_by_name(matches, wine_name)
    chosen = _pick_vintage(matches, vintage)
    v = chosen["vintage"]
    w = v["wine"]
    s = v.get("statistics", {})

    # Navne-match-konfidens: alle tokens fra søket må finnes i matched name
    query_tokens = {t.lower() for t in wine_name.split() if len(t) > 2}
    matched_name = (w.get("name", "") + " " + w.get("winery", {}).get("name", "")).lower()
    hits = sum(1 for t in query_tokens if t in matched_name)
    if query_tokens and hits == len(query_tokens):
        confidence = "exact"
    elif query_tokens and hits >= len(query_tokens) * 0.6:
        confidence = "partial"
    else:
        confidence = "weak"

    result = {
        "query": wine_name,
        "requested_vintage": vintage,
        "matched_wine": w.get("name"),
        "matched_winery": w.get("winery", {}).get("name"),
        "matched_vintage": v.get("year"),
        "vintage_rating": s.get("ratings_average"),
        "vintage_ratings_count": s.get("ratings_count"),
        "wine_rating": s.get("wine_ratings_average"),
        "wine_ratings_count": s.get("wine_ratings_count"),
        "region": w.get("region", {}).get("name"),
        "country": w.get("region", {}).get("country", {}).get("code"),
        "url": f"https://www.vivino.com/wines/{v.get('id')}",
        "wine_url": f"https://www.vivino.com/w/{w.get('id')}",
        "exact_vintage_match": vintage is None or v.get("year") == vintage,
        "name_match_confidence": confidence,
        "total_matches": data["explore_vintage"].get("records_matched", 0),
    }
    _cache_set(cache_key, result)
    return result


if __name__ == "__main__":
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else "Thymiopoulos Rose Xinomavro"
    year = int(sys.argv[2]) if len(sys.argv) > 2 else 2024
    r = get_vivino_rating(name, vintage=year)
    if r is None:
        print("Ingen treff (eller blokkert).")
    else:
        print(json.dumps(r, indent=2, ensure_ascii=False))
