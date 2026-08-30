"""
Engangs, idempotent rekonstruksjon av data/polet/ fra ~/.cache/sommelier/.

Bakgrunn: details-cachen er nøklet på sha256(full_url)[:24] og har INGEN
code/url inni. Mappingen code→details bygges derfor via search-cachen (som har
både code og url) ved å regne samme sha256(url)[:24] som `_cache_path` i
tools/vinmonopolet.py.

Steg:
1. Les alle search_*.json + search_facets_*.json → {code: product} (union).
2. For hver unike url: sha256(full_url)[:24] → slå opp details_<hash>.json.
3. Skriv catalog via polet_store.upsert_products; skriv details direkte
   (dictene er allerede parset i cachen — ikke re-parse) med code/url/fetched_at
   + "_seed": true. fetched_at = cache-filas mtime (ISO).
4. Details som ikke mappes til en code = orphans → data/polet/_orphan_details.json
   (ikke kast). Kan re-knyttes ved neste desktop-refresh.
5. Print oppsummering.

Idempotent: kjøring to ganger gir samme resultat (deterministisk skriving,
upsert på code, orphans-fil overskrives).
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Gjør fila kjørbar både som modul (`python3 -m tools.vinmonopolet`) og som skript
# (`python3 tools/vinmonopolet.py`) — sistnevnte er kommandoen CLAUDE.md dokumenterer.
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))

from tools import polet_store

CACHE_DIR = Path.home() / ".cache" / "sommelier"
BASE = "https://www.vinmonopolet.no"


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:24]


def _full_url(u: str) -> str:
    return u if u.startswith("http") else BASE + u


def _mtime_iso(path: str) -> str:
    ts = os.stat(path).st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def main() -> None:
    # 1) Bygg {code: product} fra search-cachen.
    by_code: dict[str, dict] = {}
    for pat in ("search_*.json", "search_facets_*.json"):
        for f in glob.glob(str(CACHE_DIR / pat)):
            try:
                data = json.loads(Path(f).read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(data, list):
                continue
            for p in data:
                code = p.get("code")
                if code is not None:
                    by_code[str(code)] = p  # union; senere fil vinner

    # 2) Mapp url-hash → code, for de produktene vi har.
    hash_to_code: dict[str, str] = {}
    code_to_url: dict[str, str] = {}
    for code, p in by_code.items():
        u = p.get("url")
        if not u:
            continue
        full = _full_url(u)
        code_to_url[code] = full
        hash_to_code[_sha(full)] = code

    # 3) Skriv catalog. fetched_at = nyeste search-cache-mtime (proxy for snapshot).
    search_files = glob.glob(str(CACHE_DIR / "search_*.json")) + glob.glob(
        str(CACHE_DIR / "search_facets_*.json")
    )
    if search_files:
        newest_search_mtime = max(os.stat(f).st_mtime for f in search_files)
        catalog_fetched_at = datetime.fromtimestamp(
            newest_search_mtime, tz=timezone.utc
        ).isoformat()
    else:
        catalog_fetched_at = datetime.now(timezone.utc).isoformat()

    products = list(by_code.values())
    n_catalog = polet_store.upsert_products(products, fetched_at=catalog_fetched_at)

    # 4) Gå gjennom alle details-filer; mapp til code eller orphan.
    polet_store.DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    n_details = 0
    orphans: list[dict] = []
    for f in sorted(glob.glob(str(CACHE_DIR / "details_*.json"))):
        h = os.path.basename(f)[len("details_") : -len(".json")]
        try:
            parsed = json.loads(Path(f).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        fetched_at = _mtime_iso(f)
        code = hash_to_code.get(h)
        if code is not None:
            record = dict(parsed)
            record["code"] = code
            record["url"] = code_to_url.get(code, "")
            record["fetched_at"] = fetched_at
            record["_seed"] = True
            out_path = polet_store.DETAILS_DIR / f"{code}.json"
            out_path.write_text(
                json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            n_details += 1
        else:
            orphans.append(
                {
                    "hash": h,
                    "fetched_at": fetched_at,
                    "_seed": True,
                    "parsed": parsed,
                }
            )

    # 5) Skriv orphans deterministisk (sortert på hash).
    orphans.sort(key=lambda o: o["hash"])
    orphan_path = polet_store.POLET_DIR / "_orphan_details.json"
    orphan_path.write_text(
        json.dumps(orphans, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print("=" * 60)
    print("Seed Polet-store — rekonstruksjon fra ~/.cache/sommelier/")
    print("=" * 60)
    print(f"Produkter i katalog:   {n_catalog}")
    print(f"Details mappet:        {n_details}")
    print(f"Orphan details:        {len(orphans)}  → {orphan_path}")
    print(f"Catalog generated_at:  {catalog_fetched_at}")


if __name__ == "__main__":
    main()
