"""
Repo-backed lese/skrive-lag for Vinmonopolet-data.

Polets webshop-API er WAF-blokkert (ADR-019), så varig Polet-data ligger nå
git-committet i `data/polet/` (portabelt til Android-Claude-Code uten browser).

- LESE-side (device-agnostisk): `read_catalog`, `lookup`, `query`,
  `read_details` + alders-aksessorer. Returnerer None/[] ved cache-miss.
- SKRIVE-helpers (kun desktop-refresh-ritualet): `upsert_products`,
  `save_details`, `set_clock_buckets`. Deterministisk serialisering for
  konfliktfrie cross-device git-merges, og pruning av felt ingen leser
  (se `PRUNED_CATALOG_FIELDS`) slik at katalogen holder seg lesbar når den
  vokser mot fullt rødvins-sortiment.

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

# ─── KATALOG-SHAPE ───────────────────────────────────────────────────
# Felt som strippes fra hvert produkt før det skrives til catalog.ndjson.
# Målt på snapshotet 2026-07-02 (1 849 rader, 3,0 MB) — ingen kode i repoet
# leser noen av dem FRA katalogen:
#
#   productAvailability  30,5 % av bytene. Lager/leveringsstatus per butikk.
#                        `polet_live.store_stock` leser feltet fra et LIVE
#                        søkesvar, aldri fra snapshotet — og et lagertall som
#                        er uker gammelt er verdiløst uansett.
#   images               15,4 % av bytene. Fem URL-varianter per vin, alle
#                        rent avledbare fra varenummeret
#                        (bilder.vinmonopolet.no/cache/300x300-0/<code>-1.jpg).
#   main_sub_category     1,8 % av bytene, og `{}` for 1 748 av 1 849 rader
#                        (alle 1 543 rødviner). Ren tomvekt.
#
# IKKE prun `url` (dybdehenting), `district`, `sub_District`,
# `product_selection` eller `volume` — de leses av query/similarity/value.
PRUNED_CATALOG_FIELDS = ("productAvailability", "images", "main_sub_category")

# Lovlige fasett-bøtter for klokkene (Polets 1–12-skala i 2-trinns bøtter).
CLOCK_BUCKETS = frozenset({"1-2", "3-4", "5-6", "7-8", "9-10", "11-12"})


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

def _atomic_write_text(path: Path, text: str) -> None:
    """
    Skriv via temp-fil i samme mappe + `os.replace`. Et avbrudd midt i en
    skriving skal aldri etterlate en halv katalog — snapshotet er eneste
    Polet-kilde, og en trunkert NDJSON ville se ut som «vinen finnes ikke».
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _prune_product(product: dict) -> dict:
    """
    Kopi av `product` uten feltene i `PRUNED_CATALOG_FIELDS`. Kopi, ikke
    mutasjon: kalleren (refresh-ritualet) eier sitt eget søkesvar og kan
    fortsatt lese f.eks. lagerstatus fra det live.
    """
    return {k: v for k, v in product.items() if k not in PRUNED_CATALOG_FIELDS}


def _write_catalog(products: list[dict]) -> None:
    """Deterministisk NDJSON: sortert på code, kompakt JSON per linje, trailing newline."""
    ordered = sorted(products, key=lambda p: str(p.get("code", "")))
    lines = [json.dumps(p, ensure_ascii=False, sort_keys=True) for p in ordered]
    _atomic_write_text(CATALOG, "\n".join(lines) + ("\n" if lines else ""))


def _category_coverage(products: list[dict]) -> dict:
    """Antall produkter per main_category.code — sortert for stabil meta."""
    counts: dict[str, int] = {}
    for p in products:
        cat = (p.get("main_category") or {}).get("code")
        if cat:
            counts[cat] = counts.get(cat, 0) + 1
    return dict(sorted(counts.items()))


def _write_meta(products: list[dict], *, generated_at: str) -> None:
    meta = {
        "generated_at": generated_at,
        "count": len(products),
        "category_coverage": _category_coverage(products),
    }
    _atomic_write_text(
        META, json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )


def upsert_products(products: list[dict], *, fetched_at: str) -> int:
    """
    Merge `products` inn i katalogen på `code` (nyeste vinner). Stamp hver med
    `fetched_at` hvis ikke allerede satt, og strip `PRUNED_CATALOG_FIELDS`
    før skriving. Skriv tilbake deterministisk (sortert på code) og oppdater
    catalog_meta.json.

    Rader som allerede ligger i katalogen røres ikke av pruningen her — de
    ryddes én gang av `tools/migrate_catalog_shape.py`.

    Returnerer antall opprørte (innkommende, unike) produkter.
    """
    existing = {str(p.get("code")): p for p in read_catalog() if p.get("code") is not None}

    upserted = 0
    for p in products:
        code = p.get("code")
        if code is None:
            continue
        entry = _prune_product(p)
        entry.setdefault("fetched_at", fetched_at)
        existing[str(code)] = entry
        upserted += 1

    merged = list(existing.values())
    _write_catalog(merged)
    _write_meta(merged, generated_at=fetched_at)
    return upserted


def prune_delisted(
    present_codes,
    *,
    category: str,
    generated_at: str,
    max_share: float = 0.10,
    force: bool = False,
) -> dict:
    """
    Fjern rader i ÉN kategori som ikke finnes i en KOMPLETT enumerering av den
    kategorien. Etter en full sveip er fravær informasjon: varen er avregistrert
    hos Polet, og en rad som blir liggende bærer `buyable: true` fra den dagen
    den sist ble hentet — den ser kjøpbar ut i all evighet (ADR-024).

    `present_codes` er varenumrene den komplette sveipen faktisk så. `category`
    avgrenser slettingen til den kategorien som ER sveipet — kall ALDRI dette
    med en delvis sveip, og aldri på tvers av kategorier: fravær betyr ingenting
    for en kategori du ikke har enumerert.

    Sikring: nekter å slette mer enn `max_share` av kategorien uten `force=True`.
    En sveip som stille ble avkortet (jf. `pageSize`-taket, ADR-024) ville ellers
    kunne tømme katalogen. Rapporten forteller hva som ville blitt slettet.

    Details-filer for slettede varenumre fjernes også — de er dødvekt uten en rad.

    Returnerer `{"slettet", "beholdt", "slettede_koder", "details_fjernet"}`.
    """
    present = {str(c) for c in present_codes}
    if not present:
        raise ValueError(
            "present_codes er tom — det ville slettet hele kategorien. "
            "Er sveipen faktisk kjørt?"
        )

    alle = read_catalog()
    i_kat = [p for p in alle if _matches_label(p.get("main_category"), category)]
    if not i_kat:
        raise ValueError(f"Ingen rader i kategori «{category}» — feil kategorinavn?")

    doomed = [p for p in i_kat if str(p.get("code")) not in present]
    share = len(doomed) / len(i_kat)
    if share > max_share and not force:
        raise ValueError(
            f"Ville slettet {len(doomed)} av {len(i_kat)} rader i «{category}» "
            f"({share:.1%}) — over grensen på {max_share:.0%}. Det ser ut som en "
            "avkortet sveip, ikke ekte avregistrering. Sjekk at enumereringen er "
            "komplett (unike koder == totalResults), så kjør med force=True."
        )

    doomed_codes = {str(p.get("code")) for p in doomed}
    beholdt = [p for p in alle if str(p.get("code")) not in doomed_codes]
    _write_catalog(beholdt)
    _write_meta(beholdt, generated_at=generated_at)

    fjernet = 0
    for code in doomed_codes:
        f = DETAILS_DIR / f"{code}.json"
        if f.exists():
            f.unlink()
            fjernet += 1

    return {
        "slettet": len(doomed),
        "beholdt": len(beholdt),
        "slettede_koder": sorted(doomed_codes),
        "details_fjernet": fjernet,
    }


def set_clock_buckets(mapping: dict, *, fetched_at: str) -> dict:
    """
    Merge klokke-bøtter fra et fasett-sveip inn på EKSISTERENDE katalograder.

    `mapping` er `{"<varenr>": {"Fylde": "7-8", "Friskhet": "9-10", ...}}` —
    bøtte-verdiene må ligge i `CLOCK_BUCKETS`, ellers `ValueError`. Hele
    mappingen valideres FØR første skriving, så en ugyldig bøtte midt i
    sveipet ikke etterlater en halvmerget katalog.

    Bøttene legges på raden under `clock_buckets`, med sveipe-tidspunktet
    under `clock_buckets_fetched_at`. Radens eget `fetched_at` (når produktet
    ble hentet) og katalogens `generated_at` røres IKKE — et klokke-sveip
    friskmelder ikke pris og lager.

    Koder som ikke finnes i katalogen telles og ignoreres — en bøtte uten en
    katalograd er meningsløs, og en syntetisk rad uten navn/pris/land ville
    forurenset `query`. Rader med identiske bøtter fra før røres ikke i det
    hele tatt (heller ikke tidsstempelet), så gjentatte sveip gir tom git-diff.

    Returnerer `{"oppdatert": n, "ukjent_kode": n, "uendret": n}`.
    """
    for code, buckets in mapping.items():
        if not isinstance(buckets, dict):
            raise ValueError(
                f"Klokke-bøtter for {code} må være en dict, fikk {type(buckets).__name__}"
            )
        for dim, value in buckets.items():
            if value not in CLOCK_BUCKETS:
                raise ValueError(
                    f"Ugyldig klokke-bøtte for {code}/{dim}: {value!r} — "
                    f"lovlige verdier er {sorted(CLOCK_BUCKETS)}"
                )

    rows = read_catalog()
    by_code = {str(r.get("code")): r for r in rows if r.get("code") is not None}

    rapport = {"oppdatert": 0, "ukjent_kode": 0, "uendret": 0}
    for code, buckets in mapping.items():
        row = by_code.get(str(code))
        if row is None:
            rapport["ukjent_kode"] += 1
            continue
        if row.get("clock_buckets") == buckets:
            rapport["uendret"] += 1
            continue
        row["clock_buckets"] = dict(buckets)
        row["clock_buckets_fetched_at"] = fetched_at
        rapport["oppdatert"] += 1

    if rapport["oppdatert"]:
        _write_catalog(rows)
    return rapport


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
    from tools.polet_details import parse_product_json
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

    # Foretrekk den innebygde JSON-blobben på produktsiden (ADR-024): den er
    # Polets egen strukturerte representasjon, mens regex-veien tolker DOM-en.
    # Regex beholdes som fallback for sider uten blobb — og som drift-varsel:
    # forsvinner blobben en dag, degraderer vi i stedet for å krasje.
    parsed = parse_product_json(html)
    parser_used = "json"
    if parsed is None:
        parsed = parse_product_html(html)
        parser_used = "html"
    elif parsed.get("varenummer") not in (None, code):
        # Blobben tilhører et ANNET produkt enn vi ba om. Varenr-sjekken over
        # ser bare at koden forekommer et sted i HTML-en; her ser vi at selve
        # produktobjektet er feil. Ikke skriv det til snapshotet.
        raise ValueError(
            f"JSON-blobben har varenr {parsed.get('varenummer')}, forventet "
            f"{code} — feil produktside. Avviser."
        )

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
    # Proveniens: gjør det mulig å finne igjen de details-filene som ble skrevet
    # av den tynnere regex-veien (de mangler bl.a. land/produsent/årgang) uten å
    # måtte gjette ut fra hvilke nøkler som finnes.
    record["parser"] = parser_used

    DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DETAILS_DIR / f"{code}.json"
    out_path.write_text(
        json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return record
