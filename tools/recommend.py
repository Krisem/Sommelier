"""
Én inngang som kjeder de fem kildene bak en vinanbefaling.

Bakgrunn: et vinspørsmål krevde 21 håndskrevne python-snutter mot
`polet_store`, `user_fit`, `value_score`, `aperitif` og Vivino-CSV-en. Denne
modulen samler dem — den **rangerer ikke faglig** og finner ikke opp noen ny
score. Den henter signaler; vurderingen er modellens jobb.

ADR-016 (no-filter-bubble): `no_go` og `risky` er *merker*, aldri filtre. Ingen
rad forsvinner fordi tieren er lav.

## Målte funn som formet koden

**Volum står i CENTILITER.** 3-liters kartong er `volume.value == 300`, ikke 3.
`--volum-min/--volum-maks` tar LITER på CLI-en og konverteres til cl her.
Kontroll: 313 rødviner på 300 cl i katalogen, som matcher tallet i CLAUDE.md.

**Men volum alene skiller IKKE kartong fra storformatflaske.** Av de 284
aktive 3 l-rødvinene er 58 dobbeltmagnum i glass — Ch. Haut-Brion 2021 til
29 412 kr ligger i samme volumtreff som en pappeske til 340. Det finnes ikke
noe emballasjefelt, og navnet sier ingenting. Det som skiller er
**varenummerets to siste siffer**, som koder emballasje, ikke volum:

    …01  standard 75 cl-flaske   (24 621 rader)
    …06  KARTONG / bag-in-box    (150 cl median 270 kr · 300 cl median 500 kr)
    …05  storformatflaske        (150 cl median 1 200 kr)
    …07  storformatflaske        (300 cl median 4 579 kr · 500 cl median 7 634 kr)

Prisbruddet er rent: på 3 l ligger alle …06 mellom 340 og 780 kr, alle …07
mellom 756 kr og 29 412 — 24 kroners overlapp. Derfor `--emballasje kartong`.

**Kritiker-score dekker nesten ingenting.** 21 av 11 956 aktive rødviner har en
rad i `knowledge/scores/` (0 av 284 på 3 l). ADR-016s implementerings-linje
`sorted(wines, key=-critic_score)` gir derfor ingen reell orden i et bredt
katalogsøk. Løsningen her er å ikke lyve om det: sortér på kritiker-score der
den finnes, literpris som tie-break for resten, oppgi sorteringsnøkkelen i
outputen, og alltid vise hvor mange treff som ble kappet bort.

**Årgang har ikke noe felt** — den må hentes ut av navnet. Den er ikke bare
pynt: `value_score` trenger den til Vivino-vintage-match.
"""

from __future__ import annotations

import argparse
import concurrent.futures as _fut
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Iterable, Optional

from tools import polet_store, user_fit, value_score

VIVINO_CSV = Path(__file__).resolve().parent.parent / "data" / "vivino" / "full_wine_list.csv"

# Klokkenøklene katalogen faktisk bruker. Rødvin bærer Tannin (= garvestoffer),
# hvit/musserende/rosé bærer Soedme. Vi normaliserer IKKE — raden får de
# nøklene den har, så en manglende dimensjon er synlig som fravær.
KLOKKE_NØKLER = ("Fylde", "Friskhet", "Tannin", "Soedme")

# Samlet veggklokke-budsjett for value-score på topp-N. aperitif._http_get har
# timeout=15 per kall, så N sekvensielle kall kan ellers bli minutter.
VALUE_TIMEOUT_S = 45.0

REFRESH_DOK = "docs/polet_refresh.md"

# Sorterings-tie-breaks. Kun objektive tallfelt fra raden — ingen ny score.
SORTERINGSNØKLER = ("literpris", "pris")

# Varenummer-suffiks → emballasje. Se modul-docstringen for målingen.
EMBALLASJE_SUFFIKS = {"01": "flaske", "05": "flaske", "06": "kartong", "07": "flaske"}

_ÅRGANG_RE = re.compile(r"\b(19|20)\d{2}\b")
_STOPPORD = frozenset({"the", "de", "di", "del", "la", "le", "el", "og", "and", "vin", "wine"})


class IngenTreff(Exception):
    """0 treff — bærer alltid årsaken, aldri bare et tomt resultat."""


# ─── SMÅ AVLEDNINGER ─────────────────────────────────────────────────

def _årgang(navn: str) -> Optional[int]:
    m = _ÅRGANG_RE.search(navn or "")
    return int(m.group(0)) if m else None


def _literpris(pris: Optional[float], volum_cl: Optional[float]) -> Optional[float]:
    """Pris per liter. None når pris eller volum mangler — aldri ZeroDivisionError."""
    if pris is None or not volum_cl:
        return None
    return round(pris / (volum_cl / 100.0), 2)


def _emballasje(kode: str) -> Optional[str]:
    """Kartong eller flaske, fra varenummerets to siste siffer. None = ukjent kode."""
    return EMBALLASJE_SUFFIKS.get(str(kode)[-2:])


def _klokker(rad: dict) -> dict:
    cb = rad.get("clock_buckets") or {}
    return {k: cb[k] for k in KLOKKE_NØKLER if k in cb}


def _normaliser(s: str) -> list[str]:
    """Navn → liste med søkbare tokens: uten aksenter, årgang og stoppord."""
    s = _ÅRGANG_RE.sub(" ", s or "").casefold()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    ord_ = re.findall(r"[a-z0-9]+", s)
    return [t for t in ord_ if len(t) >= 2 and t not in _STOPPORD]


# ─── VIVINO-HISTORIKK ────────────────────────────────────────────────

def _les_vivino(path: Optional[Path] = None) -> list[dict]:
    """Brukerens drukne viner. Tom liste hvis CSV-en mangler."""
    p = path or VIVINO_CSV
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as fh:
        rader = list(csv.DictReader(fh))
    for r in rader:
        r["_tokens"] = set(_normaliser(f"{r.get('Winery','')} {r.get('Wine name','')}"))
        r["_produsent"] = set(_normaliser(r.get("Winery", "")))
    return rader


def _historikk(rad: dict, vivino: list[dict]) -> Optional[dict]:
    """
    Har han drukket denne? Krever at det ene navnets tokens er en DELMENGDE av
    det andres — ikke bare produsent pluss ett felles ord.

    Den løsere regelen ble målt og forkastet: 437 «treff», med «Torre dei Beati
    Montepulciano» → «Dei Vino Nobile di Montepulciano» (produsent «Dei») og
    «Girardin Bourgogne Chardonnay» → «Girardin Bourgogne Pinot Noir» blant
    dem. Å fortelle ham at han har drukket en vin han ikke har, er verre enn
    å tie. Delmengde-regelen taper noen ekte treff («Grande Réserve» vs «Grand
    Réserve»); det er den riktige retningen å bomme i.

    `rating` kan være None selv ved treff: mange rader er scannet uten rating.
    «Scannet uten rating» er ikke «aldri prøvd», så de skilles i outputen.
    """
    tokens = set(_normaliser(rad.get("name", "")))
    if len(tokens) < 2:
        return None
    for r in vivino:
        csv_tokens = r["_tokens"]
        # Minst to tokens på BEGGE sider: ett-ords-navn gjorde whiskyen
        # «Jura 12 YO» til et treff på «Côtes du Jura Chardonnay».
        if len(csv_tokens) < 2:
            continue
        if not (csv_tokens <= tokens or tokens <= csv_tokens):
            continue
        rating = (r.get("Your rating") or "").strip()
        return {
            "navn": f"{r.get('Winery','')} {r.get('Wine name','')}".strip(),
            "aargang": (r.get("Vintage") or "").strip() or None,
            "din_rating": float(rating) if rating else None,
            "vivino_snitt": (r.get("Average rating") or "").strip() or None,
            "scan_dato": (r.get("Scan date") or "")[:10] or None,
            "match": "navne-delmengde",
        }
    return None


def _liknende(rad: dict, vivino: list[dict]) -> Optional[str]:
    """Har han drukket noe fra samme distrikt/underdistrikt? Returnerer regionen."""
    regioner = {
        (r.get("Region") or "").strip().casefold() for r in vivino
    } | {
        (r.get("Regional wine style") or "").strip().casefold() for r in vivino
    }
    for felt in ("sub_District", "district"):
        navn = ((rad.get(felt) or {}).get("name") or "").strip()
        if navn and navn.casefold() in regioner:
            return navn
    return None


def _flagg(rad: dict, hist: Optional[dict], liknende: Optional[str]) -> list[str]:
    """Familiaritet + opprinnelses-advarsel (CLAUDE.md steg 8)."""
    if hist:
        flagg = ["[PRØVD]"]
    elif liknende:
        flagg = ["[LIKNENDE]"]
    else:
        flagg = ["[NYTT]"]
    if str((rad.get("main_country") or {}).get("code", "")).casefold() == "usa":
        flagg.append("[USA]")
    return flagg


# ─── KANDIDATER ──────────────────────────────────────────────────────

def _kandidat(rad: dict, vivino: list[dict], regler: dict) -> dict:
    pris = (rad.get("price") or {}).get("value")
    volum_cl = (rad.get("volume") or {}).get("value")
    hist = _historikk(rad, vivino)
    liknende = _liknende(rad, vivino)
    fit = user_fit.classify(rad, regler)
    return {
        "varenummer": str(rad.get("code", "")),
        "navn": rad.get("name", ""),
        "aargang": _årgang(rad.get("name", "")),
        "pris": pris,
        "volum_liter": round(volum_cl / 100.0, 3) if volum_cl else None,
        "emballasje": _emballasje(rad.get("code", "")),
        "literpris": _literpris(pris, volum_cl),
        "land": (rad.get("main_country") or {}).get("name"),
        "distrikt": (rad.get("district") or {}).get("name"),
        "underdistrikt": (rad.get("sub_District") or {}).get("name") or None,
        "kategori": (rad.get("main_category") or {}).get("name"),
        "utvalg": rad.get("product_selection"),
        "alkohol": (rad.get("alcohol") or {}).get("value"),
        "klokker": _klokker(rad),
        "kommer_snart": bool(rad.get("kommer_snart")),
        "url": rad.get("url"),
        "user_fit": {
            "tier": fit["tier"],
            "rule_fired": fit["rule_fired"],
            "confidence": fit["confidence"],
            "explore": fit["explore"],
            "reasons": fit["reasons"],
        },
        "vivino_historikk": hist,
        "liknende_region": liknende,
        "flagg": _flagg(rad, hist, liknende),
        "value": None,
        "value_status": "ikke_kjort",
    }


def _kritiker(varenr: str) -> Optional[float]:
    from tools import scores
    e = scores.best_score(varenr)
    return e["score"] if e else None


def _sorter(kandidater: list[dict], nokkel: str = "literpris",
            synkende: bool = False) -> list[dict]:
    """
    Kritiker-score synkende der den finnes, så `nokkel` som tie-break.

    Dette er IKKE en kvalitetsrangering — literpris og pris er objektive fakta
    på raden, ikke dommer. Se modul-docstringen om critic-dekningen.

    Retningen er et valg fordi `--antall` ellers lyver: målt på spørsmålet
    verktøyet ble bygget for («kraftigere rødvin, 3 l») ga default-stigende
    literpris de seks BILLIGSTE av 284 treff (113–127 kr/l) — feil ende av
    hylla for «kraftig», som per CLAUDE.md oversettes til appellasjonsnivå og
    literpris. `--min-pris` flytter gulvet, men ordner ikke, så modellen får
    fortsatt et vilkårlig utsnitt. Default er uendret.

    Rader uten verdi sorteres sist i BEGGE retninger — «ukjent» er ikke «høy».
    """
    if nokkel not in SORTERINGSNØKLER:
        raise ValueError(f"Ukjent sorteringsnøkkel {nokkel!r} — lovlige: {SORTERINGSNØKLER}")
    retning = -1.0 if synkende else 1.0
    return sorted(
        kandidater,
        key=lambda k: (
            -(_kritiker(k["varenummer"]) or -1e9),
            retning * k[nokkel] if k[nokkel] is not None else float("inf"),
            k["varenummer"],
        ),
    )


# ─── VALUE PÅ TOPP-N ─────────────────────────────────────────────────

def _value_topp_n(kandidater: list[dict], rader: dict, timeout: float) -> None:
    """
    Kjør `compute_value_score` på de kandidatene som faktisk vises — aldri på
    hele trefflista. Samlet veggklokke-budsjett; en rad som ikke rekker fram
    degraderes til `value_status="timeout"`, den stopper ikke svaret.
    """
    if not kandidater:
        return
    with _fut.ThreadPoolExecutor(max_workers=min(4, len(kandidater))) as ex:
        jobber = {
            ex.submit(
                value_score.compute_value_score,
                rader[k["varenummer"]],
                vintage=k["aargang"],
            ): k
            for k in kandidater
        }
        ferdige, _ = _fut.wait(jobber, timeout=timeout)
        for job, k in jobber.items():
            if job not in ferdige:
                k["value_status"] = "timeout"
                continue
            try:
                v = job.result()
            except Exception as e:  # nettverk/parse — en rad uten value er ikke en feil
                k["value_status"] = f"feil: {type(e).__name__}"
                continue
            k["value"] = {
                "verdict": v.get("value_verdict"),
                "quality_tier": v.get("quality_tier"),
                "summary": v.get("summary"),
                "snapshot_age_days": v.get("snapshot_age_days"),
            }
            k["value_status"] = "ok"


# ─── HOVEDINNGANG ────────────────────────────────────────────────────

def recommend(
    *,
    kategori: Optional[str] = "rødvin",
    land: Optional[str] = None,
    maks_pris: Optional[float] = None,
    min_pris: Optional[float] = None,
    volum_min: Optional[float] = None,
    volum_maks: Optional[float] = None,
    emballasje: Optional[str] = None,
    navn_inneholder: Optional[str] = None,
    varenr: Optional[Iterable[str]] = None,
    antall: int = 8,
    sorter: str = "literpris",
    synkende: bool = False,
    value: bool = True,
    value_timeout: float = VALUE_TIMEOUT_S,
    vivino_csv: Optional[Path] = None,
) -> list[dict]:
    """
    Samle kandidater fra Polet-snapshotet og berik dem med de andre kildene.

    `volum_min`/`volum_maks` er i LITER (katalogen lagrer centiliter).
    `emballasje` er "kartong" eller "flaske" — volum alene skiller dem ikke.
    `sorter`/`synkende` velger tie-break-retningen over et objektivt tallfelt —
    ikke en kvalitetsrangering, se `_sorter`.
    `varenr` går utenom filtrene og slår opp eksakte varenumre.

    Hver rad bærer et delt `sok`-objekt: totalt antall treff, hvor mange som
    vises, sorteringsnøkkel, og hvilke varenumre som manglet eller ikke var
    kjøpbare. Ingenting kappes i stillhet.

    Reiser `IngenTreff` med årsak når resultatet er tomt.
    """
    mangler: list[str] = []
    ikke_kjopbar: list[str] = []

    if varenr:
        rader = []
        for kode in varenr:
            kode = str(kode).strip()
            # lookup() filtrerer IKKE på status, i motsetning til query() —
            # derfor skiller vi «finnes ikke» fra «finnes, men ikke kjøpbar».
            p = polet_store.lookup(kode)
            if p is None:
                mangler.append(kode)
            elif polet_store.is_active(p) or polet_store.is_kommer_snart(p):
                rader.append({**p, "kommer_snart": True} if polet_store.is_kommer_snart(p) else p)
            else:
                ikke_kjopbar.append(kode)
    else:
        rader = polet_store.query(
            category=kategori,
            country=land,
            max_price=maks_pris,
            min_price=min_pris,
            name_contains=navn_inneholder,
        )
        if emballasje is not None:
            rader = [r for r in rader if _emballasje(r.get("code", "")) == emballasje]
        if volum_min is not None or volum_maks is not None:
            lo = volum_min * 100 if volum_min is not None else None
            hi = volum_maks * 100 if volum_maks is not None else None
            rader = [
                r for r in rader
                if (v := (r.get("volume") or {}).get("value")) is not None
                and (lo is None or v >= lo) and (hi is None or v <= hi)
            ]

    if not rader:
        if mangler and not ikke_kjopbar:
            raise IngenTreff(
                f"Varenummer {', '.join(mangler)} finnes ikke i Polet-snapshotet. "
                f"Snapshotet kan være for gammelt — se {REFRESH_DOK}."
            )
        if ikke_kjopbar and not mangler:
            raise IngenTreff(
                f"Varenummer {', '.join(ikke_kjopbar)} finnes i snapshotet, men er "
                f"ikke kjøpbar (utsolgt/utgått). Ingen refresh hjelper på det."
            )
        if mangler or ikke_kjopbar:
            raise IngenTreff(
                f"Ingen kjøpbare treff. Mangler i snapshot: {', '.join(mangler) or '–'}. "
                f"Finnes, men ikke kjøpbar: {', '.join(ikke_kjopbar) or '–'}. Se {REFRESH_DOK}."
            )
        raise IngenTreff(
            "Ingen treff på filteret — det er for stramt, ikke et hull i snapshotet. "
            f"Filter: kategori={kategori!r} land={land!r} pris={min_pris}–{maks_pris} "
            f"volum={volum_min}–{volum_maks} l emballasje={emballasje!r} "
            f"navn~{navn_inneholder!r}. "
            "Løsne ett kriterium om gangen (prisen og volumet snevrer mest)."
        )

    vivino = _les_vivino(vivino_csv)
    regler = user_fit.load_profile_rules()
    kandidater = _sorter([_kandidat(r, vivino, regler) for r in rader], sorter, synkende)
    vist = kandidater[: max(0, antall)]

    if value and vist:
        _value_topp_n(vist, {str(r.get("code")): r for r in rader}, value_timeout)

    sok = {
        "treff_totalt": len(kandidater),
        "viser": len(vist),
        "sortering": (
            f"kritiker-score desc (21/11956 dekning), "
            f"{sorter} {'desc' if synkende else 'asc'} som tie-break"
        ),
        "mangler_i_snapshot": mangler,
        "ikke_kjopbar": ikke_kjopbar,
        "snapshot_alder_dager": polet_store.catalog_age_days(),
        "value_kjort_paa": len(vist) if value else 0,
    }
    for k in vist:
        k["sok"] = sok
    return vist


# ─── CLI ─────────────────────────────────────────────────────────────

def _skriv_tekst(rader: list[dict]) -> None:
    sok = rader[0]["sok"]
    alder = sok["snapshot_alder_dager"]
    alder_str = f"snapshot {alder:.0f} dager gammelt" if alder is not None else "snapshot: ukjent alder"
    print(f"{sok['viser']} av {sok['treff_totalt']} treff  ·  sortert: {sok['sortering']}")
    print(alder_str)
    if sok["mangler_i_snapshot"]:
        print(f"  mangler i snapshot: {', '.join(sok['mangler_i_snapshot'])} → {REFRESH_DOK}")
    if sok["ikke_kjopbar"]:
        print(f"  finnes, men ikke kjøpbar: {', '.join(sok['ikke_kjopbar'])}")
    print()
    for i, k in enumerate(rader, 1):
        lp = f"{k['literpris']:.0f} kr/l" if k["literpris"] is not None else "literpris ukjent"
        print(f"{i:2d}. {k['navn']}  [{k['varenummer']}]  {' '.join(k['flagg'])}")
        print(f"    {k['pris']:.0f} kr · {k['volum_liter']} l {k['emballasje'] or '?'} · {lp} · "
              f"{k['land'] or '–'} / {k['distrikt'] or '–'}"
              + (f" / {k['underdistrikt']}" if k["underdistrikt"] else ""))
        if k["klokker"]:
            print("    klokker: " + "  ".join(f"{d} {v}" for d, v in k["klokker"].items()))
        f = k["user_fit"]
        print(f"    fit: {f['tier']} ({f['rule_fired']}, {f['confidence']}"
              + (", explore" if f["explore"] else "") + ")")
        if f["reasons"]:
            print(f"      – {f['reasons'][0]}")
        if k["vivino_historikk"]:
            h = k["vivino_historikk"]
            r = f"din rating {h['din_rating']}" if h["din_rating"] else "scannet uten rating"
            print(f"    drukket: {h['navn']} ({h['scan_dato']}) — {r}")
        elif k["liknende_region"]:
            print(f"    kjent region: {k['liknende_region']}")
        if k["value"]:
            v = k["value"]
            print(f"    value: {v['verdict']} — {v['summary']}")
        elif k["value_status"] != "ikke_kjort":
            print(f"    value: {k['value_status']}")
        print()


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python3 -m tools.recommend",
        description="Samler Polet-katalog, klokker, user-fit, Vivino-historikk og value-score.",
    )
    ap.add_argument("--kategori", default="rødvin")
    ap.add_argument("--land")
    ap.add_argument("--maks-pris", type=float)
    ap.add_argument("--min-pris", type=float)
    ap.add_argument("--volum-min", type=float, help="liter (katalogen lagrer cl)")
    ap.add_argument("--volum-maks", type=float, help="liter")
    ap.add_argument("--emballasje", choices=("kartong", "flaske"),
                    help="varenummer-suffiks: …06 = kartong, …01/05/07 = flaske")
    ap.add_argument("--navn-inneholder")
    ap.add_argument("--varenr", help="komma-separert; går utenom filtrene")
    ap.add_argument("--antall", type=int, default=8)
    ap.add_argument("--sorter", choices=SORTERINGSNØKLER, default="literpris",
                    help="tie-break-felt (ingen kvalitetsrangering)")
    ap.add_argument("--synkende", action="store_true", help="dyreste/høyeste først")
    ap.add_argument("--ingen-value", action="store_true", help="hopp over value-score")
    ap.add_argument("--value-timeout", type=float, default=VALUE_TIMEOUT_S)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    try:
        rader = recommend(
            kategori=a.kategori, land=a.land,
            maks_pris=a.maks_pris, min_pris=a.min_pris,
            volum_min=a.volum_min, volum_maks=a.volum_maks, emballasje=a.emballasje,
            navn_inneholder=a.navn_inneholder,
            varenr=[c for c in a.varenr.split(",") if c.strip()] if a.varenr else None,
            antall=a.antall, sorter=a.sorter, synkende=a.synkende,
            value=not a.ingen_value, value_timeout=a.value_timeout,
        )
    except IngenTreff as e:
        print(f"0 treff — {e}", file=sys.stderr)
        return 1

    if a.json:
        print(json.dumps(rader, ensure_ascii=False, indent=2))
    else:
        _skriv_tekst(rader)
    return 0


if __name__ == "__main__":
    sys.exit(main())
