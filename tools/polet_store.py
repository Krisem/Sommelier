"""
Repo-backed lese/skrive-lag for Vinmonopolet-data.

Polets webshop-API er WAF-blokkert (ADR-019), så varig Polet-data ligger nå
git-committet i `data/polet/` (portabelt til Android-Claude-Code uten browser).

- LESE-side (device-agnostisk): `read_catalog`, `lookup`, `query`,
  `read_details` + alders-aksessorer. Returnerer None/[] ved cache-miss.
- SKRIVE-helpers (kun desktop-refresh-ritualet): `upsert_products`,
  `save_details`. Deterministisk serialisering for konfliktfrie cross-device
  git-merges.

`parse_product_html` (ren funksjon, fixture-testet) gjenbrukes uendret fra
`tools.vinmonopolet`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─── STIER (repo-relativt, ikke hardkodet) ───────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
POLET_DIR = _REPO_ROOT / "data" / "polet"
CATALOG = POLET_DIR / "catalog.ndjson"
META = POLET_DIR / "catalog_meta.json"
DETAILS_DIR = POLET_DIR / "details"


class PoletRefreshRequired(Exception):
    """
    Kastes når en etterspurt vin ikke finnes i repo-snapshotet og må hentes
    på nytt fra desktop (Polets WAF blokkerer requests fra Claude).

    `.url` = produkt-/søke-URL som må refreshes (kan være None for søk).
    `.hint` = kort, handlingsrettet veiledning.
    """

    def __init__(self, message: str, *, url: Optional[str] = None, hint: Optional[str] = None):
        self.url = url
        self.hint = hint or (
            "Ikke i snapshot — refresh fra desktop (Polet WAF blokkerer "
            "requests; se docs/polet_refresh.md)"
        )
        super().__init__(f"{message} — {self.hint}")


# ─── LESERE ──────────────────────────────────────────────────────────

def read_catalog() -> list[dict]:
    """Les hele katalogen som en liste produkt-dicts. Tom liste hvis fila mangler."""
    if not CATALOG.exists():
        return []
    out: list[dict] = []
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def lookup(code: str) -> Optional[dict]:
    """Finn ett produkt i katalogen på varenr `code`. None hvis ikke funnet."""
    code = str(code)
    for p in read_catalog():
        if str(p.get("code")) == code:
            return p
    return None


def _matches_label(obj: object, wanted: str) -> bool:
    """
    True hvis fasett-objektet ({code,name}) matcher `wanted` på enten code
    eller name (case-insensitiv). Adresserer ADR-009 kode≠navn-gotcha: både
    "rødvin" (code) og "Rødvin" (name) skal matche.
    """
    if not isinstance(obj, dict):
        return False
    w = wanted.casefold()
    code = str(obj.get("code", "")).casefold()
    name = str(obj.get("name", "")).casefold()
    return w == code or w == name


def query(
    *,
    category: Optional[str] = None,
    country: Optional[str] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    name_contains: Optional[str] = None,
) -> list[dict]:
    """
    Filtrer katalogen. `category`/`country` matcher BÅDE .code og .name
    (case-insensitiv). Pris leses fra `p["price"]["value"]`.
    """
    out: list[dict] = []
    for p in read_catalog():
        if category is not None and not _matches_label(p.get("main_category"), category):
            continue
        if country is not None and not _matches_label(p.get("main_country"), country):
            continue
        price = (p.get("price") or {}).get("value")
        if max_price is not None and (price is None or price > max_price):
            continue
        if min_price is not None and (price is None or price < min_price):
            continue
        if name_contains is not None and name_contains.casefold() not in str(p.get("name", "")).casefold():
            continue
        out.append(p)
    return out


def read_details(code: str) -> Optional[dict]:
    """Les details/<code>.json. None hvis fila mangler."""
    p = DETAILS_DIR / f"{code}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def details_fetched_at(code: str) -> Optional[str]:
    """`fetched_at`-stempel for en details-fil, eller None."""
    d = read_details(code)
    if not d:
        return None
    return d.get("fetched_at")


def _read_meta() -> dict:
    if not META.exists():
        return {}
    try:
        return json.loads(META.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def catalog_generated_at() -> Optional[str]:
    """ISO-tidsstempel for når katalogen sist ble generert (fra meta, ikke mtime)."""
    return _read_meta().get("generated_at")


def catalog_age_days() -> Optional[float]:
    """
    Alder på katalogen i dager, regnet fra meta.generated_at (IKKE fil-mtime —
    git nullstiller mtime ved checkout). None hvis ingen/ugyldig meta.
    """
    gen = catalog_generated_at()
    if not gen:
        return None
    try:
        ts = datetime.fromisoformat(gen)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - ts
    return delta.total_seconds() / 86400.0


# ─── SKRIVE-HELPERS (desktop refresh-ritual) ─────────────────────────

def _write_catalog(products: list[dict]) -> None:
    """Deterministisk NDJSON: sortert på code, kompakt JSON per linje, trailing newline."""
    POLET_DIR.mkdir(parents=True, exist_ok=True)
    ordered = sorted(products, key=lambda p: str(p.get("code", "")))
    lines = [json.dumps(p, ensure_ascii=False, sort_keys=True) for p in ordered]
    CATALOG.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _category_coverage(products: list[dict]) -> dict:
    """Antall produkter per main_category.code — sortert for stabil meta."""
    counts: dict[str, int] = {}
    for p in products:
        cat = (p.get("main_category") or {}).get("code")
        if cat:
            counts[cat] = counts.get(cat, 0) + 1
    return dict(sorted(counts.items()))


def _write_meta(products: list[dict], *, generated_at: str) -> None:
    POLET_DIR.mkdir(parents=True, exist_ok=True)
    meta = {
        "generated_at": generated_at,
        "count": len(products),
        "category_coverage": _category_coverage(products),
    }
    META.write_text(
        json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def upsert_products(products: list[dict], *, fetched_at: str) -> int:
    """
    Merge `products` inn i katalogen på `code` (nyeste vinner). Stamp hver med
    `fetched_at` hvis ikke allerede satt. Skriv tilbake deterministisk
    (sortert på code) og oppdater catalog_meta.json.

    Returnerer antall opprørte (innkommende, unike) produkter.
    """
    existing = {str(p.get("code")): p for p in read_catalog() if p.get("code") is not None}

    upserted = 0
    for p in products:
        code = p.get("code")
        if code is None:
            continue
        entry = dict(p)
        entry.setdefault("fetched_at", fetched_at)
        existing[str(code)] = entry
        upserted += 1

    merged = list(existing.values())
    _write_catalog(merged)
    _write_meta(merged, generated_at=fetched_at)
    return upserted


def save_details(code: str, url: str, html: str, *, fetched_at: str) -> dict:
    """
    Parse produktside-HTML og lagre details/<code>.json med selv-identifiserende
    code/url/fetched_at.

    POSITIV VALIDERING (fanger WAF-challenge-HTML og DOM-drift): varenr `code`
    må forekomme i en PRODUKT-kontekst (strukturert JSON-felt eller bak
    "Varenummer"-etiketten — ikke bare i en canonical/asset-URL) OG HTML må ha
    et produktnavn OG (minst én klokke i parse-resultatet ELLER en strukturert
    pris-blokk). Ellers raise ValueError.
    """
    from tools.vinmonopolet import parse_product_html

    code = str(code)

    # Varenr må forekomme i produkt-kontekst, ikke bare i en canonical/asset-URL
    # (en soft-error/challenge-side kan referere koden i <link rel=canonical>
    # eller et bilde-tag). Ekte produktsider har koden som strukturert JSON-felt
    # eller bak "Varenummer"-etiketten.
    import re
    has_code_context = (
        f'"code":"{code}"' in html
        or bool(re.search(rf"[Vv]arenummer\D{{0,20}}{code}", html))
    )
    if not has_code_context:
        raise ValueError(
            f"HTML inneholder ikke forventet varenr {code} i produkt-kontekst — "
            "sannsynlig WAF-challenge eller feil side. Avviser."
        )

    # Produktnavn: <title>…</title> eller en <h1>. Krev ikke-tom tekst.
    name_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    if not name_match:
        name_match = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.IGNORECASE)
    product_name = name_match.group(1).strip() if name_match else ""
    if not product_name:
        raise ValueError("Fant ikke produktnavn i HTML — avviser (mulig challenge).")

    parsed = parse_product_html(html)

    # Strukturert pris-blokk ('"price"'), ikke en løs "kr <tall>"-regex som også
    # ville matchet f.eks. "kr 0 i frakt" på en feilside.
    has_clock = bool(parsed.get("klokker"))
    has_price = '"price"' in html
    if not (has_clock or has_price):
        raise ValueError(
            "HTML mangler både klokker og strukturert pris — avviser "
            "(mulig challenge/DOM-drift)."
        )

    record = dict(parsed)
    record["code"] = code
    record["url"] = url
    record["fetched_at"] = fetched_at

    DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DETAILS_DIR / f"{code}.json"
    out_path.write_text(
        json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return record
