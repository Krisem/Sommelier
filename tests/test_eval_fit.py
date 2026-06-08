"""Kontrakt-tester for eval-harnessen (`tools.eval_fit`).

Alle offline — ingen HTTP. Tester invarianter og kontrakter, ikke eksakte
flyttall (de avhenger av CSV-innhold og skal kunne endre seg uten å brekke
testene). Rene matematiske funksjoner (spearman/ndcg) testes mot håndregnede
verdier der det er meningsfullt.
"""

from __future__ import annotations

import math

import pytest

from tools import eval_fit


# ---------------------------------------------------------------------------
# Split & lockbox
# ---------------------------------------------------------------------------


def test_split_counts():
    rows = eval_fit.load_eval_rows()
    train, test = eval_fit.split_train_test(rows)
    assert len(train) + len(test) == len(rows)
    # Alle test-rader er nyere enn cutoff
    for r in test:
        assert r["_dt"] is not None and r["_dt"] >= eval_fit.SPLIT_CUTOFF
    # Ingen overlapp på identitet
    assert not ({r["_key"] for r in train} & {r["_key"] for r in test})


def test_lockbox_deterministic():
    rows = eval_fit.load_eval_rows()
    a = eval_fit.select_lockbox(rows)
    b = eval_fit.select_lockbox(rows)
    assert a == b
    assert len(a) == eval_fit.LOCKBOX_K
    # Lockbox er en delmengde av faktiske nøkler
    assert a <= {r["_key"] for r in rows}


def test_lockbox_edge_cases():
    assert eval_fit.select_lockbox([], 15) == set()
    one = [{"_key": "x"}]
    assert eval_fit.select_lockbox(one, 15) == {"x"}


# ---------------------------------------------------------------------------
# Metrikker
# ---------------------------------------------------------------------------


def test_spearman_known_values():
    assert eval_fit.spearman([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0)
    assert eval_fit.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    # Null varians i en vektor → None
    assert eval_fit.spearman([5, 5, 5, 5], [1, 2, 3, 4]) is None
    # n < 3 → None
    assert eval_fit.spearman([1, 2], [1, 2]) is None


def test_spearman_handles_ties():
    # Tunge ties skal ikke kaste og resultatet ligger i [-1, 1]
    val = eval_fit.spearman([1, 1, 2, 2, 3], [4, 4, 4, 4, 5])
    assert val is None or -1.0 <= val <= 1.0


def test_ndcg_bounds():
    # Perfekt rangering → 1.0
    assert eval_fit.ndcg_at_k([5, 4, 3, 2, 1]) == pytest.approx(1.0)
    # Verdi i [0, 1]
    nd = eval_fit.ndcg_at_k([1, 5, 2, 4, 3])
    assert nd is not None and 0.0 <= nd <= 1.0
    # Tom → None
    assert eval_fit.ndcg_at_k([]) is None
    # k > n degraderer grasiøst
    assert eval_fit.ndcg_at_k([3, 1], k=5) is not None


def test_ndcg_manual():
    # DCG = 1/log2(2) + 0/log2(3) = 1.0 ; IDCG = 1.0 → NDCG = 1.0
    assert eval_fit.ndcg_at_k([1, 0], k=2) == pytest.approx(1.0)
    # Omvendt: rel [0, 1]; DCG = 0 + 1/log2(3); IDCG = 1 → NDCG = 1/log2(3)
    assert eval_fit.ndcg_at_k([0, 1], k=2) == pytest.approx(1.0 / math.log2(3))


# ---------------------------------------------------------------------------
# Scorere
# ---------------------------------------------------------------------------


def test_scorer_contract():
    rows = eval_fit.load_eval_rows()
    train, _ = eval_fit.split_train_test(rows)
    scorers = eval_fit.build_scorers(train)
    sample = rows[0]
    for name, fn in scorers.items():
        out = fn(sample)
        assert out is None or isinstance(out, float), f"{name} brøt kontrakt: {out!r}"


def test_random_scorer_deterministic():
    rows = eval_fit.load_eval_rows()
    train, _ = eval_fit.split_train_test(rows)
    s1 = eval_fit.build_scorers(train, seed=7)["random"]
    s2 = eval_fit.build_scorers(train, seed=7)["random"]
    sample = rows[0]
    assert s1(sample) == s2(sample)


def test_style_avg_no_leakage():
    # style_avg bygges KUN på train; en stil som bare finnes i test gir None
    # (eller faller tilbake på land). Vi sjekker at scoreren ikke ser test-rad-ratings.
    rows = eval_fit.load_eval_rows()
    train, test = eval_fit.split_train_test(rows)
    scorer = eval_fit.build_scorers(train)["style_avg"]
    # For hver test-rad: hvis stilen ikke finnes i train (n≥3) og landet ikke finnes,
    # må scoreren returnere None — aldri en verdi avledet fra test-raden selv.
    train_styles = {(r["_wine"]["stil"] or "").strip() for r in train}
    train_lands = {(r["_wine"]["land"] or "").strip() for r in train}
    for r in test:
        stil = (r["_wine"]["stil"] or "").strip()
        land = (r["_wine"]["land"] or "").strip()
        if stil not in train_styles and land not in train_lands:
            assert scorer(r) is None


# ---------------------------------------------------------------------------
# Orkestrering & rapport
# ---------------------------------------------------------------------------


def test_evaluate_scorer_contract():
    rows = eval_fit.load_eval_rows()
    train, test = eval_fit.split_train_test(rows)
    scorer = eval_fit.build_scorers(train)["v0_tier"]
    res = eval_fit.evaluate_scorer("v0_tier", scorer, test)
    assert set(res) >= {"n_scored", "coverage", "spearman", "ndcg5", "n_distinct_scores"}
    assert 0.0 <= res["coverage"] <= 1.0
    assert res["spearman"] is None or -1.0 <= res["spearman"] <= 1.0
    assert res["ndcg5"] is None or 0.0 <= res["ndcg5"] <= 1.0


def test_run_eval_smoke():
    rep = eval_fit.run_eval()
    assert "_meta" in rep and "results" in rep and "warnings" in rep
    # Alle fem scorere, hver med begge test-varianter
    expected = {"random", "vivino_avg", "style_avg", "critic", "v0_tier"}
    assert set(rep["results"]) == expected
    for r in rep["results"].values():
        assert "test_full" in r and "test_ex_lockbox" in r
    m = rep["_meta"]
    assert m["n_train"] + m["n_test"] == m["n_rated_total"]


def test_run_eval_deterministic():
    a = eval_fit.run_eval(seed=42)
    b = eval_fit.run_eval(seed=42)
    for sname in a["results"]:
        assert (
            a["results"][sname]["test_full"]["spearman"]
            == b["results"][sname]["test_full"]["spearman"]
        )


def test_critic_coverage_flagged():
    # Critic-DB ⟂ Vivino-historikk → lav coverage skal produsere en advarsel.
    rep = eval_fit.run_eval()
    cov = rep["results"]["critic"]["test_full"]["coverage"]
    if cov < 0.2:
        assert any("critic" in w for w in rep["warnings"])


def test_render_report_runs():
    rep = eval_fit.run_eval()
    text = eval_fit.render_report(rep)
    assert "eval-harness" in text
    assert "v0_tier" in text
