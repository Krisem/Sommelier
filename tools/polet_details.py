"""
Struktur-parser for Vinmonopolets produktside — JSON-blob i stedet for regex.

Polets produktside embedder hele produktobjektet som en ferdig JSON-blob:

    <script type="application/json">{"product":{...}}</script>

Det er den samme datastrukturen `vmpws` ville returnert, servert som en del av
siden. `tools.vinmonopolet.parse_product_html` graver de samme feltene ut av
DOM-en med 12 regex (ADR-010) — teknisk gjeld #1, fordi et redesign brekker
regexene *stille*. Denne modulen leser strukturen direkte, og er derfor bare
sårbar for at Polet slutter å embedde blobben (som gir `None`, ikke halve data).

Ingen nettverk, ingen avhengigheter utover stdlib — ren og fixture-testbar
(se `tests/test_polet_details.py`).

- `parse_product_json` returnerer et SUPERSETT av `parse_product_html`-kontrakten:
  identiske nøkkelnavn og verditypene for de feltene begge dekker, pluss felt
  regexene aldri fanget (matparring, lagringspotensial, literpris, emballasje …).
- `parse_product_json` returnerer `None` når blobben ikke finnes — da faller
  kalleren tilbake på regex-veien.
- `compare_parsers` kjører begge parserne på samme HTML og rapporterer avvik
  felt for felt. Det er slik vi beviser at JSON-veien er trygg, og slik vi
  oppdager DOM-drift i regex-veien senere.
"""

from __future__ import annotations

import json
import re

# Alle `<script type="application/json">`-blokker på siden. Det er FLERE (header
# og footer har hver sin Sanity-blob) — vi plukker den som har "product" som
# toppnøkkel, ikke den første.
_JSON_BLOB_RE = re.compile(
    r'<script[^>]*\btype=["\']application/json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)

# Klokke-verdi som fallback fra `readableValue` ("Fylde, 8 av 12") når `value`
# ikke lar seg tolke som heltall.
_READABLE_CLOCK_RE = re.compile(r"(\d+)\s*av\s*\d+")

# Traits Polet legger på alle produkter — samme nøkkelnavn som regex-parseren.
_TRAIT_KEYS = {"Alkohol": "alkohol", "Sukker": "sukker", "Syre": "syre"}


# ─── SMÅ HJELPERE ────────────────────────────────────────────────────

def _text(value) -> str | None:
    """Trimmet ikke-tom streng, ellers `None` (nøkkelen skal da utelates)."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _name_of(node) -> str | None:
    """`{"name": "Piemonte", …}` → `"Piemonte"`. Alt annet → `None`."""
    return _text(node.get("name")) if isinstance(node, dict) else None


def _number(node, key: str = "value") -> float | int | None:
    """Tall-feltet i en `{value, formattedValue, readableValue}`-node."""
    if not isinstance(node, dict):
        return None
    value = node.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _clock_value(entry: dict) -> int | None:
    """Klokke-verdi som heltall — `value` først, `readableValue` som fallback."""
    try:
        return int(str(entry.get("value")).strip())
    except (TypeError, ValueError):
        pass
    m = _READABLE_CLOCK_RE.search(str(entry.get("readableValue") or ""))
    return int(m.group(1)) if m else None


def _put(result: dict, key: str, value) -> None:
    """Sett nøkkelen kun når verdien er meningsfull — speiler regex-parseren,
    som bare setter en nøkkel når regexen faktisk matchet."""
    if value is not None and value != "" and value != []:
        result[key] = value


# ─── BLOB-UTTREKK ────────────────────────────────────────────────────

def _find_product_blob(html: str) -> dict | None:
    """
    Produkt-objektet fra den JSON-blobben som faktisk har `"product"` som
    toppnøkkel. Blobber som ikke er gyldig JSON, eller som er andre ting
    (header/footer-innhold), hoppes over uten å kaste.
    """
    if not isinstance(html, str) or not html:
        return None
    for raw in _JSON_BLOB_RE.findall(html):
        try:
            blob = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if not isinstance(blob, dict):
            continue
        product = blob.get("product")
        if isinstance(product, dict):
            return product
    return None


# ─── PARSER ──────────────────────────────────────────────────────────

def parse_product_json(html: str) -> dict | None:
    """
    Trekk produktdetaljer ut av JSON-blobben på en Polet-produktside.

    Ren funksjon — ingen I/O. Returnerer `None` (ikke exception) når siden ikke
    har en produkt-blob (WAF-challenge, feilside, gammel DOM); kalleren faller
    da tilbake på `parse_product_html`.

    Nøkler DELT med `parse_product_html` (samme navn, samme verditype):
      klokker      dict[str, int]  alltid til stede, kan være tom
      druer        str             "Barbera 100 prosent" (readableValue, komma-separert)
      stil         str             "Frisk og fruktig"
      lukt         str
      smak         str
      farge        str
      metode       str
      land         str             "Italia, Piemonte, Barbera d'Alba"
      produsent    str
      årgang       str
      utvalg       str
      alkohol      str             "13,5%"
      sukker       str             "Under 3 g/l"
      syre         str             "6,2 g/l"

    Nøkler regexene ALDRI fanget:
      varenummer        str          navn              str
      kategori          str          pris              tall
      volum             tall         literpris         tall
      emballasje        str          grossist          str
      distrikt          str          underdistrikt     str
      matparring        list[str]    lagringspotensial str
      stil_beskrivelse  str

    Alle nøkler unntatt `klokker` utelates når feltet mangler eller er tomt —
    samme kontrakt som regex-parseren, der en nøkkel bare finnes hvis regexen
    matchet.
    """
    product = _find_product_blob(html)
    if product is None:
        return None

    content = product.get("content")
    if not isinstance(content, dict):
        content = {}

    result: dict = {}

    # Klokker (Fylde/Friskhet/Garvestoffer/Sødme/Bitterhet/…) på skala 1–12.
    # Vi tar ALLE dimensjonene Polet oppgir, ikke bare de seks regexen kjenner —
    # øl og musserende har andre dimensjoner enn stillevin.
    klokker: dict[str, int] = {}
    for entry in content.get("characteristics") or []:
        if not isinstance(entry, dict):
            continue
        navn = _text(entry.get("name"))
        verdi = _clock_value(entry)
        if navn and verdi is not None:
            klokker[navn] = verdi
    result["klokker"] = klokker

    # Drueblanding. `readableValue` ("Barbera 100 prosent") — ikke
    # `formattedValue` ("Barbera 100%") — fordi regex-parseren leser
    # aria-label-en, som er readableValue.
    druer = [
        _text(i.get("readableValue"))
        for i in content.get("ingredients") or []
        if isinstance(i, dict)
    ]
    _put(result, "druer", ", ".join(d for d in druer if d))

    style = content.get("style") if isinstance(content.get("style"), dict) else {}
    _put(result, "stil", _text(style.get("name")))
    _put(result, "stil_beskrivelse", _text(style.get("description")))

    _put(result, "lukt", _text(product.get("smell")))
    _put(result, "smak", _text(product.get("taste")))
    _put(result, "farge", _text(product.get("color")))
    _put(result, "metode", _text(product.get("method")))
    _put(result, "utvalg", _text(product.get("product_selection")))
    _put(result, "årgang", _text(product.get("year")))
    _put(result, "produsent", _name_of(product.get("main_producer")))

    # "Land, distrikt" er ett felt i DOM-en — tre noder i JSON-en.
    distrikt = _name_of(product.get("district"))
    underdistrikt = _name_of(product.get("sub_District"))
    land_deler = [_name_of(product.get("main_country")), distrikt, underdistrikt]
    _put(result, "land", ", ".join(d for d in land_deler if d))

    # Alkohol/Sukker/Syre ligger som traits med samme visningsstreng som DOM-en.
    for trait in content.get("traits") or []:
        if not isinstance(trait, dict):
            continue
        key = _TRAIT_KEYS.get(_text(trait.get("name")) or "")
        if key:
            _put(result, key, _text(trait.get("formattedValue")))

    # ─── Felt regexene aldri fanget ──────────────────────────────────

    _put(result, "varenummer", _text(product.get("code")))
    _put(result, "navn", _text(product.get("name")))
    _put(result, "kategori", _name_of(product.get("main_category")))
    _put(result, "distrikt", distrikt)
    _put(result, "underdistrikt", underdistrikt)
    _put(result, "emballasje", _text(product.get("packageType")))
    _put(result, "korktype", _text(product.get("cork")))
    _put(result, "grossist", _text(product.get("wholeSaler")))

    # Sertifiseringsflagg. `eco` er den eneste med reell spredning (13 % av
    # 1 187 målte produktsider) og finnes ikke noe annet sted i snapshotet —
    # katalograden bærer `sustainable`, som er noe annet og bredere.
    # Bare True lagres: fraværet av nøkkelen betyr «ikke merket», og det holder
    # filene små. bioDynamic (10) og fairTrade (5) er sjeldne, men gratis å ta
    # med når vi først står i blobben.
    for nøkkel, felt in (("eco", "økologisk"), ("bioDynamic", "biodynamisk"),
                         ("fairTrade", "fairtrade")):
        if product.get(nøkkel) is True:
            result[felt] = True
    _put(result, "pris", _number(product.get("price")))
    _put(result, "volum", _number(product.get("volume")))
    _put(result, "literpris", _number(product.get("litrePrice")))

    storage = content.get("storagePotential")
    if isinstance(storage, dict):
        _put(result, "lagringspotensial", _text(storage.get("formattedValue")))

    matparring = [
        _name_of(m) for m in content.get("isGoodFor") or [] if isinstance(m, dict)
    ]
    _put(result, "matparring", [m for m in matparring if m])

    return result


# ─── DIAGNOSE ────────────────────────────────────────────────────────

def compare_parsers(html: str) -> dict:
    """
    Kjør begge parserne på samme HTML og rapporter avvik felt for felt.

    Diagnoseverktøy, ikke produksjonsvei: dette er hvordan vi beviser at
    JSON-veien er trygg å bytte til, og hvordan vi oppdager at regex-veien har
    drevet fra hverandre etter et Polet-redesign.

    Returnerer:
      json_funnet  bool                 fant vi en produkt-blob i det hele tatt
      enige        list[str]            delte nøkler med identisk verdi (sortert)
      uenige       dict[str, dict]      delt nøkkel → {"json": …, "html": …}
      kun_json     dict[str, object]    felt bare JSON-veien fant
      kun_html     dict[str, object]    felt bare regex-veien fant (regresjons-signal)

    `kun_html` er den viktigste linja: er den ikke-tom, dekker JSON-veien mindre
    enn regex-veien, og byttet er ikke trygt for de feltene.
    """
    # Lokal import med vilje: `tools.vinmonopolet` drar inn `requests`, og
    # `parse_product_json` skal kunne kjøre på ren stdlib (ADR-020 —
    # snapshot-lesing må være portabel til enheter uten requests). Bare
    # diagnose-funksjonen betaler for regex-veien.
    from tools.vinmonopolet import parse_product_html

    fra_html = parse_product_html(html)
    fra_json = parse_product_json(html)

    if fra_json is None:
        return {
            "json_funnet": False,
            "enige": [],
            "uenige": {},
            "kun_json": {},
            "kun_html": dict(fra_html),
        }

    delte = set(fra_json) & set(fra_html)
    enige = sorted(k for k in delte if fra_json[k] == fra_html[k])
    uenige = {
        k: {"json": fra_json[k], "html": fra_html[k]}
        for k in sorted(delte)
        if fra_json[k] != fra_html[k]
    }
    return {
        "json_funnet": True,
        "enige": enige,
        "uenige": uenige,
        "kun_json": {k: fra_json[k] for k in sorted(set(fra_json) - delte)},
        "kun_html": {k: fra_html[k] for k in sorted(set(fra_html) - delte)},
    }
