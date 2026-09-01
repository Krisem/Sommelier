"""
Join mellom Polets whisky-katalog og whiskyanalysis.com Meta-Critic — på navn.

Det finnes ingen felles nøkkel. Polet har varenummer, Meta-Critic har et
flaskenavn skrevet av en kanadisk anmelder. Alt som binder dem er strenger som
«Talisker Single Malt 10 Years Old» og «Talisker 10yo».

**Derfor er dette ikke en boolsk match, men en tier.** En feil join er verre enn
ingen join: den ser riktig ut, den havner i `value_score`, og ingenting varsler
om den. Målt mot Aperitifs 316 whiskyer (2026-09-01) fordeler kandidatene seg:

    A  eksakt (j=1,0, alder enig)     82   26 %   auto-godtas
    B  sterk  (score ≥ 0,75)          12    4 %   auto-godtas, logges
    C  svak   (0,30–0,75)             61   19 %   MÅ BEKREFTES av mennesket
    D  ingen                         161   51 %   ingen score

Tier C kan ikke løses med en bedre terskel, og det er verdt å se hvorfor:

    FEIL:    Jack Daniel's Tennessee     → Jack Daniel's Gentleman Jack
    FEIL:    Aberlour 12 YO              → Aberlour A'Bunadh
    RIKTIG:  Glenmorangie The Original   → Glenmorangie 10yo
    RIKTIG:  Michter's US 1 Bourbon      → Michter's Small Batch US*1 Bourbon

Alle fire ligger i samme score-intervall. Skillet er kunnskap om hva flaskene
er, ikke en tallgrense — så tier C går til mennesket, i chat, samme kanal som
whisky-ratingene (ADR-033). Se ADR-035.

Tier D er i stor grad norske hyllevare-blends (Inverness Cream, Lord Elcho,
Glen Scanlan) som ingen kritiker har vurdert. Det er et tak på kilden, ikke en
feil i matchingen.

Kjør:  python3 -m tools.whisky_match --report
       python3 -m tools.whisky_match --pending      (tier C som venter på svar)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterator, Optional

from tools import polet_store, whiskyanalysis
from tools.whiskyanalysis import normalise

JOIN = whiskyanalysis.WA_DIR / "join.ndjson"

# Straff når ÉN av navnene har aldersangivelse og den andre ikke. Ikke en
# diskvalifikasjon: «Glenmorangie The Original» ER 10-åringen, og «Johnnie
# Walker Black Label» ER 12-åringen. Men det er svakere bevis enn to som
# stemmer, og straffen holder dem ute av auto-tieren.
AGE_ASYMMETRY_PENALTY = 0.15

TIER_B_FLOOR = 0.75
TIER_C_FLOOR = 0.30

WHISKY_SUB_CATEGORY = "brennevin_whisky"


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _index_metacritic(rows: Optional[list[dict]] = None) -> list[tuple[list[str], Optional[int], dict]]:
    rows = whiskyanalysis.read_snapshot() if rows is None else rows
    out = []
    for r in rows:
        tokens, age = normalise(r["whisky"])
        if tokens:
            out.append((tokens, age, r))
    return out


def match_name(name: str, index=None) -> dict:
    """
    Finn beste Meta-Critic-kandidat for `name`.

    Returnerer alltid en dict med `tier` (A/B/C/D), `score`, `kandidat` og
    `begrunnelse` — aldri bare en boolsk. Kalleren skal kunne se HVORFOR, fordi
    tier C skal leses av et menneske.

    To harde regler før noe scores:
      - Merket (første identifiserende token) må stemme. «Glenfiddich» og
        «Glenlivet» deler tokens uten å være samme destilleri.
      - Alder må ikke MOTSI. Er begge oppgitt og ulike, er det to forskjellige
        flasker uansett hvor likt resten leser.
    """
    index = _index_metacritic() if index is None else index
    tokens, age = normalise(name)
    if not tokens:
        return {"tier": "D", "score": 0.0, "kandidat": None,
                "begrunnelse": "navnet ga ingen identifiserende tokens"}

    beste, beste_score, beste_j, beste_alder = None, -1.0, 0.0, None
    for wt, wage, rad in index:
        if tokens[0] != wt[0]:
            continue
        if age is not None and wage is not None and age != wage:
            continue
        straff = AGE_ASYMMETRY_PENALTY if (age is None) != (wage is None) else 0.0
        j = _jaccard(set(tokens), set(wt))
        score = j - straff
        if score > beste_score:
            beste, beste_score, beste_j, beste_alder = rad, score, j, wage

    if beste is None:
        return {"tier": "D", "score": 0.0, "kandidat": None,
                "begrunnelse": f"ingen kandidat med merket «{tokens[0]}»"}

    if beste_j == 1.0 and age == beste_alder:
        tier = "A"
    elif beste_score >= TIER_B_FLOOR:
        tier = "B"
    elif beste_score >= TIER_C_FLOOR:
        tier = "C"
    else:
        tier = "D"

    return {
        "tier": tier,
        "score": round(beste_score, 3),
        "kandidat": beste if tier != "D" else None,
        "begrunnelse": f"jaccard={beste_j:.2f} alder={age}/{beste_alder}",
    }


# ─── KATALOG-SIDEN ───────────────────────────────────────────────────

def catalog_whiskies() -> list[dict]:
    """Alle whiskyrader i Polet-snapshotet."""
    return [
        r for r in polet_store.read_catalog()
        if (r.get("main_sub_category") or {}).get("code") == WHISKY_SUB_CATEGORY
    ]


def match_catalog(rows: Optional[list[dict]] = None) -> list[dict]:
    """Join hele whisky-katalogen. Én dict per varenummer."""
    index = _index_metacritic()
    out = []
    for r in (catalog_whiskies() if rows is None else rows):
        m = match_name(r.get("name", ""), index=index)
        out.append({
            "polet_id": r.get("code"),
            "polet_navn": r.get("name"),
            "tier": m["tier"],
            "score": m["score"],
            "wa_whisky": (m["kandidat"] or {}).get("whisky"),
            "meta_critic": (m["kandidat"] or {}).get("meta_critic"),
            "stdev": (m["kandidat"] or {}).get("stdev"),
            "n_reviewers": (m["kandidat"] or {}).get("n_reviewers"),
            "begrunnelse": m["begrunnelse"],
        })
    return out


# ─── BEKREFTELSER ────────────────────────────────────────────────────

def read_join() -> dict[str, dict]:
    """Committet join-fil, indeksert på varenummer. Mangler → {}."""
    if not JOIN.exists():
        return {}
    out = {}
    for line in JOIN.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rad = json.loads(line)
            out[rad["polet_id"]] = rad
    return out


def resolve(polet_id: str) -> Optional[dict]:
    """
    Meta-Critic-raden som GJELDER for et varenummer, eller None.

    Tier A og B gjelder direkte. Tier C gjelder KUN når `bekreftet == "ja"` —
    en ubekreftet tier C er ikke en svak match, den er ingen match.
    """
    rad = read_join().get(str(polet_id))
    if not rad:
        return None
    if rad["tier"] in ("A", "B"):
        return rad
    if rad["tier"] == "C" and rad.get("bekreftet") == "ja":
        return rad
    return None


def write_join(rows: list[dict]) -> None:
    """
    Skriv join-fila, men BEVAR eksisterende `bekreftet`-svar.

    En regenerering som glemmer dette ville kastet menneskets arbeid stille —
    og det er nettopp den sorten tap som ikke oppdages før noen leter etter en
    bekreftelse de husker å ha gitt.
    """
    tidligere = read_join()
    ut = []
    for r in rows:
        rad = dict(r)
        gammel = tidligere.get(rad["polet_id"])
        if gammel and gammel.get("wa_whisky") == rad.get("wa_whisky"):
            rad["bekreftet"] = gammel.get("bekreftet")
        else:
            rad["bekreftet"] = None if rad["tier"] == "C" else "n/a"
        ut.append(rad)

    JOIN.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True)
        for r in sorted(ut, key=lambda r: r["polet_id"])
    )
    JOIN.write_text(body + "\n", encoding="utf-8")


def pending() -> list[dict]:
    """Tier C som venter på ja/nei fra mennesket."""
    return [r for r in read_join().values()
            if r["tier"] == "C" and r.get("bekreftet") is None]


# ─── RAPPORT ─────────────────────────────────────────────────────────

def tier_distribution(rows: list[dict]) -> dict[str, int]:
    d = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in rows:
        d[r["tier"]] += 1
    return d


def _aperitif_whiskies() -> Iterator[dict]:
    path = whiskyanalysis._REPO_ROOT / "data" / "aperitif" / "scores.ndjson"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            if d.get("category") == "Whisky":
                yield d


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Join Polet-whisky mot Meta-Critic")
    ap.add_argument("--report", action="store_true", help="tier-fordeling")
    ap.add_argument("--write", action="store_true", help="skriv data/whiskyanalysis/join.ndjson")
    ap.add_argument("--pending", action="store_true", help="tier C som venter på bekreftelse")
    ap.add_argument("--limit", type=int, default=15)
    args = ap.parse_args(argv)

    if args.pending:
        p = pending()
        print(f"{len(p)} tier C venter på bekreftelse\n")
        for r in p[: args.limit]:
            print(f"  {r['score']:.2f}  {r['polet_navn'][:46]:46s} → {r['wa_whisky']}")
        return 0

    rows = match_catalog()
    if args.write:
        write_join(rows)
        print(f"Skrev {len(rows)} rader til {JOIN}")

    if args.report or not args.write:
        tot = len(rows)
        print(f"KATALOG — {tot} whiskyer i data/polet/")
        for tier, n in tier_distribution(rows).items():
            print(f"  {tier}  {n:5d}  ({n / tot:5.1%})")

        # Kalibreringssettet: tallene i docstringen og i ADR-035 er målt her.
        ap_rows = list(_aperitif_whiskies())
        if ap_rows:
            index = _index_metacritic()
            ap_m = [match_name(d["wine_name"], index=index) for d in ap_rows]
            n = len(ap_m)
            print(f"\nKALIBRERING — Aperitifs {n} whiskyer (sammenlign mot ADR-035)")
            d = {"A": 0, "B": 0, "C": 0, "D": 0}
            for m in ap_m:
                d[m["tier"]] += 1
            for tier, k in d.items():
                print(f"  {tier}  {k:5d}  ({k / n:5.1%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
