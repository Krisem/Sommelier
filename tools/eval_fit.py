"""
Modell-agnostisk evaluerings-harness for user-fit-score.

Måler hvor godt en «scorer» rangerer brukerens egne viner mot hans faktiske
`Your rating` (ground truth fra Vivino-CSV). En scorer er en funksjon
`Callable[[dict], float | None]` der høyere = bedre fit, og None = «kan ikke
score denne» (manglende data).

Harnessen evaluerer dagens v0-tier-modell side om side med fire baselines
(random, Vivino-snitt, stil-snitt, kritiker-score), slik at spørsmålet
«bør vi bygge v1?» blir empirisk i stedet for subjektivt.

Tidsbasert split: `Scan date < 2024-01-01` = train, ellers test. 15 viner
holdes som lockbox. Metrikker rapporteres BÅDE på hele test-settet og på
test minus lockbox (lockbox koster signal på dagens statiske v0, men disiplinen
holdes for fremtidig v1-tuning).

Ingen eksterne avhengigheter (scipy finnes ikke i repoet) — ren stdlib.

Se `roadmap.md` § "Evaluerings-harness" og § "User-fit-score" for design.

CLI:
    python3 -m tools.eval_fit               # skriv data/user_fit/eval_v0.json + rapport
    python3 -m tools.eval_fit --stdout-only # bare rapport, ingen fil
"""

from __future__ import annotations

import math
import random
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from tools.profile_stats import load_rated
from tools.user_fit import classify, load_profile_rules

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_PATH = ROOT / "data" / "user_fit" / "eval_v0.json"

SPLIT_CUTOFF = datetime(2024, 1, 1)
LOCKBOX_K = 15
DEFAULT_SEED = 42
NDCG_K = 5

# Ordinal tier → kontinuerlig score (midt-i-bøtte). Bevisst grov: poenget er å
# vise at v0's få distinkte verdier gir lav rangerings-oppløsning.
_TIER_SCORE = {
    "no_go": 0.0,
    "risky": 1.0,
    "neutral": 2.0,
    "fit": 3.0,
    "very_fit": 4.0,
}


# ---------------------------------------------------------------------------
# Datalasting & split
# ---------------------------------------------------------------------------


def _csv_row_to_wine(r: dict) -> dict:
    """Map en Vivino-CSV-rad til wine-dict som classify() forstår."""
    navn = f"{(r.get('Winery') or '').strip()} {(r.get('Wine name') or '').strip()}".strip()
    return {
        "navn": navn,
        "produsent": (r.get("Winery") or "").strip(),
        "region": (r.get("Region") or "").strip(),
        "land": (r.get("Country") or "").strip(),
        "stil": (r.get("Regional wine style") or "").strip(),
        "kategori": (r.get("Wine type") or "").strip(),
    }


def load_eval_rows() -> list[dict]:
    """
    Last ratede viner og berik hver rad for evaluering.

    Gjenbruker `profile_stats.load_rated()` (setter `_rating`, `_dt`) og legger til:
      - `_wine`: dict til classify()
      - `_avg_rating`: Vivino-crowd-snitt (float | None)
      - `_key`: stabil identitets-nøkkel for deterministisk sortering/RNG
    """
    rows = load_rated()
    for r in rows:
        r["_wine"] = _csv_row_to_wine(r)
        try:
            r["_avg_rating"] = float((r.get("Average rating") or "").replace(",", "."))
        except ValueError:
            r["_avg_rating"] = None
        scan = (r.get("Scan date") or "").strip()
        r["_key"] = f"{r['_wine']['navn']}|{(r.get('Vintage') or '').strip()}|{scan}"
    return rows


def split_train_test(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Tidsbasert split. Rader uten dato → train (gamle nok til å mangle metadata)."""
    train, test = [], []
    for r in rows:
        dt = r.get("_dt")
        if dt is not None and dt >= SPLIT_CUTOFF:
            test.append(r)
        else:
            train.append(r)
    return train, test


def select_lockbox(rows: list[dict], k: int = LOCKBOX_K) -> set[str]:
    """
    Velg k lockbox-viner deterministisk (ingen RNG): sorter alle rader stabilt
    på `_key`, plukk k jevnt fordelte indekser. Returnerer settet av `_key`.
    """
    ordered = sorted(rows, key=lambda r: r["_key"])
    n = len(ordered)
    if n == 0 or k <= 0:
        return set()
    if k >= n:
        return {r["_key"] for r in ordered}
    idxs = sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})
    return {ordered[i]["_key"] for i in idxs}


# ---------------------------------------------------------------------------
# Metrikker (ren-Python — scipy finnes ikke)
# ---------------------------------------------------------------------------


def _average_ranks(values: list[float]) -> list[float]:
    """Tildel gjennomsnittsrang ved ties (1-basert)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # 1-basert snitt av posisjoner i..j
        for t in range(i, j + 1):
            ranks[order[t]] = avg_rank
        i = j + 1
    return ranks


def spearman(pred: list[float], truth: list[float]) -> Optional[float]:
    """Spearman rang-korrelasjon. None ved n<3 eller null varians i en vektor."""
    if len(pred) != len(truth) or len(pred) < 3:
        return None
    rp, rt = _average_ranks(pred), _average_ranks(truth)
    mp, mt = statistics.mean(rp), statistics.mean(rt)
    num = sum((a - mp) * (b - mt) for a, b in zip(rp, rt))
    den_p = sum((a - mp) ** 2 for a in rp)
    den_t = sum((b - mt) ** 2 for b in rt)
    if den_p == 0 or den_t == 0:
        return None
    return num / math.sqrt(den_p * den_t)


def ndcg_at_k(ranked_relevance: list[float], k: int = NDCG_K) -> Optional[float]:
    """
    NDCG@k. `ranked_relevance` = ground-truth-relevans i prediktert rekkefølge.
    Lineær gain (rå rating) — ikke 2^rel-1: ratings er allerede en jevn 1–5-skala
    og n er lite, så eksponentiell gain ville overvekte toppen urimelig.
    """
    if not ranked_relevance:
        return None

    def dcg(rels: list[float]) -> float:
        return sum(rel / math.log2(i + 2) for i, rel in enumerate(rels[:k]))

    ideal = sorted(ranked_relevance, reverse=True)
    idcg = dcg(ideal)
    if idcg == 0:
        return None
    return dcg(ranked_relevance) / idcg


# ---------------------------------------------------------------------------
# Scorere (modell-agnostisk kontrakt: dict -> float | None)
# ---------------------------------------------------------------------------


def build_scorers(
    train_rows: list[dict], seed: int = DEFAULT_SEED
) -> dict[str, Callable[[dict], Optional[float]]]:
    """Bygg de fem scorerne. Baselines som trenger train-kontekst lukkes over den."""
    rules = load_profile_rules()

    # style_avg / country_avg fra KUN train (unngå leakage)
    def _means(key: str) -> dict[str, tuple[int, float]]:
        buckets: dict[str, list[float]] = {}
        for r in train_rows:
            label = (r["_wine"].get(key) or "").strip()
            if label:
                buckets.setdefault(label, []).append(r["_rating"])
        return {k: (len(v), statistics.mean(v)) for k, v in buckets.items()}

    style_means = _means("stil")
    country_means = _means("land")

    # critic-DB navn-indeks (normalisert navn → maks score)
    from tools.scores import index

    critic_by_name: list[tuple[str, float]] = []
    for entries in index().values():
        for e in entries:
            nm = (e.get("name") or "").strip().lower()
            if nm:
                critic_by_name.append((nm, float(e.get("score", 0.0))))

    def score_random(wine_row: dict) -> Optional[float]:
        # Deterministisk per vin (order-uavhengig): seed på identitet.
        return random.Random(f"{seed}-{wine_row['_key']}").random()

    def score_vivino_avg(wine_row: dict) -> Optional[float]:
        return wine_row.get("_avg_rating")

    def score_style_avg(wine_row: dict) -> Optional[float]:
        stil = (wine_row["_wine"].get("stil") or "").strip()
        if stil in style_means and style_means[stil][0] >= 3:
            return style_means[stil][1]
        land = (wine_row["_wine"].get("land") or "").strip()
        if land in country_means:
            return country_means[land][1]
        return None

    def score_critic(wine_row: dict) -> Optional[float]:
        navn = wine_row["_wine"]["navn"].lower()
        if not navn:
            return None
        best: Optional[float] = None
        for nm, sc in critic_by_name:
            if nm and (nm in navn or navn in nm):
                best = sc if best is None else max(best, sc)
        return best

    def score_v0_tier(wine_row: dict) -> Optional[float]:
        tier = classify(wine_row["_wine"], rules)["tier"]
        return _TIER_SCORE.get(tier)

    return {
        "random": score_random,
        "vivino_avg": score_vivino_avg,
        "style_avg": score_style_avg,
        "critic": score_critic,
        "v0_tier": score_v0_tier,
    }


# ---------------------------------------------------------------------------
# Evaluering
# ---------------------------------------------------------------------------


def evaluate_scorer(
    name: str, scorer: Callable[[dict], Optional[float]], test_rows: list[dict]
) -> dict:
    """Kjør én scorer over test-settet og beregn metrikker over de scorede radene."""
    scored: list[tuple[float, float]] = []  # (pred, truth)
    for r in test_rows:
        s = scorer(r)
        if s is not None:
            scored.append((float(s), r["_rating"]))

    n_test = len(test_rows)
    n_scored = len(scored)
    coverage = (n_scored / n_test) if n_test else 0.0

    if n_scored < 3:
        return {
            "n_scored": n_scored,
            "coverage": round(coverage, 3),
            "spearman": None,
            "ndcg5": None,
            "n_distinct_scores": len({p for p, _ in scored}),
            "note": "for få scorede viner for metrikk",
        }

    preds = [p for p, _ in scored]
    truths = [t for _, t in scored]
    sp = spearman(preds, truths)
    # NDCG: sorter scorede rader synkende på pred (stabil tie-bryting), bruk truth som relevans
    ranked = [t for _, t in sorted(scored, key=lambda x: (-x[0], x[1]))]
    nd = ndcg_at_k(ranked, NDCG_K)

    return {
        "n_scored": n_scored,
        "coverage": round(coverage, 3),
        "spearman": round(sp, 3) if sp is not None else None,
        "ndcg5": round(nd, 3) if nd is not None else None,
        "n_distinct_scores": len(set(preds)),
        "note": None,
    }


def run_eval(seed: int = DEFAULT_SEED) -> dict:
    """Full evaluering. Rapporterer hver scorer på BÅDE hele test-settet og test∖lockbox."""
    rows = load_eval_rows()
    train, test = split_train_test(rows)
    lockbox_keys = select_lockbox(rows, LOCKBOX_K)
    test_ex = [r for r in test if r["_key"] not in lockbox_keys]
    lockbox_wines = sorted(r["_key"] for r in rows if r["_key"] in lockbox_keys)

    scorers = build_scorers(train, seed)

    results: dict[str, dict] = {}
    for sname in sorted(scorers):
        results[sname] = {
            "test_full": evaluate_scorer(sname, scorers[sname], test),
            "test_ex_lockbox": evaluate_scorer(sname, scorers[sname], test_ex),
        }

    # Datagrunnlag-statistikk for ærlig kontekst
    ratings = [r["_rating"] for r in rows]
    warnings: list[str] = []
    if len(test) < 30:
        warnings.append(
            f"Test-sett n={len(test)} er for lite for stabil Spearman — "
            f"behandle metrikker som indikative, ikke konklusive."
        )
    if results.get("critic", {}).get("test_full", {}).get("coverage", 0) < 0.2:
        cov = results["critic"]["test_full"]["coverage"]
        warnings.append(
            f"critic-baseline coverage {cov} — kritiker-DB dekker nær null av brukerens "
            f"drukne viner (varenr-DB ⟂ Vivino-historikk)."
        )
    v0_distinct = results.get("v0_tier", {}).get("test_full", {}).get("n_distinct_scores")
    if v0_distinct is not None and v0_distinct <= 3:
        warnings.append(
            f"v0_tier ga kun {v0_distinct} distinkte score-verdier på test-settet — "
            f"grov rangerings-oppløsning (støtter v1-trigger)."
        )

    return {
        "_meta": {
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "seed": seed,
            "split_cutoff": SPLIT_CUTOFF.date().isoformat(),
            "ground_truth_field": "Your rating",
            "n_rated_total": len(rows),
            "n_train": len(train),
            "n_test": len(test),
            "n_test_ex_lockbox": len(test_ex),
            "lockbox_k": LOCKBOX_K,
            "lockbox_wines": lockbox_wines,
            "rating_min": min(ratings) if ratings else None,
            "rating_max": max(ratings) if ratings else None,
            "rating_std": round(statistics.pstdev(ratings), 3) if len(ratings) > 1 else None,
        },
        "results": results,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Rapport & I/O
# ---------------------------------------------------------------------------


def render_report(report: dict) -> str:
    m = report["_meta"]
    lines = [
        f"=== User-fit eval-harness (seed {m['seed']}, cutoff {m['split_cutoff']}) ===",
        f"Datagrunnlag: {m['n_rated_total']} ratede | train {m['n_train']} | "
        f"test {m['n_test']} | lockbox {m['lockbox_k']} (test∖lockbox = {m['n_test_ex_lockbox']})",
        f"Ground truth: «{m['ground_truth_field']}» "
        f"(min {m['rating_min']}, max {m['rating_max']}, std {m['rating_std']})",
        "",
        f"{'Scorer':14}{'Cov':>6}{'Spearman':>10}{'NDCG@5':>9}{'Distinkt':>10}",
        "-" * 49,
    ]
    for sname in sorted(report["results"]):
        full = report["results"][sname]["test_full"]
        sp = "–" if full["spearman"] is None else f"{full['spearman']:+.2f}"
        nd = "–" if full["ndcg5"] is None else f"{full['ndcg5']:.2f}"
        lines.append(
            f"{sname:14}{full['coverage']:>6.2f}{sp:>10}{nd:>9}{full['n_distinct_scores']:>10}"
        )
    if report["warnings"]:
        lines.append("")
        lines.append("Advarsler:")
        for w in report["warnings"]:
            lines.append(f"  • {w}")
    return "\n".join(lines)


def write_eval_json(report: dict, output_path: Optional[str] = None) -> str:
    import json

    out_path = Path(output_path) if output_path else DEFAULT_OUTPUT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return str(out_path)


if __name__ == "__main__":
    stdout_only = "--stdout-only" in sys.argv
    rep = run_eval()
    print(render_report(rep))
    if not stdout_only:
        path = write_eval_json(rep)
        print(f"\nSkrev: {path}")
