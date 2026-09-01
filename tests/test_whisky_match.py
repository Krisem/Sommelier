"""
Tiered join Polet ↔ Meta-Critic.

Testene her handler nesten alle om det samme: at en FEIL join ikke slipper
gjennom som en riktig. En manglende score koster ingenting; en feil score
havner i `value_score` og ser helt normal ut.
"""

import json

import pytest

from tools import whisky_match as wm


def _index(*navn: str):
    """Bygg et Meta-Critic-indeks fra navn alene — resten av feltene er irrelevante."""
    rows = [{"whisky": n, "meta_critic": 8.5, "stdev": 0.3, "n_reviewers": 10} for n in navn]
    return wm._index_metacritic(rows)


# ─── tier-klassifisering ─────────────────────────────────────────────

def test_exact_match_with_agreeing_age_is_tier_a():
    idx = _index("Talisker 10yo")
    m = wm.match_name("Talisker Single Malt 10 Years Old", index=idx)
    assert m["tier"] == "A"
    assert m["kandidat"]["whisky"] == "Talisker 10yo"


def test_age_only_on_one_side_is_demoted_out_of_tier_a():
    """
    «Glenmorangie The Original» ER 10-åringen, så matchen er riktig — men beviset
    er svakere enn to aldre som stemmer, og den skal derfor ikke auto-godtas
    på linje med en eksakt match.
    """
    idx = _index("Glenmorangie 10yo")
    m = wm.match_name("Glenmorangie The Original", index=idx)
    assert m["tier"] in ("B", "C")
    assert m["tier"] != "A"


def test_no_candidate_is_tier_d_not_a_weak_guess():
    idx = _index("Lagavulin 16yo", "Talisker 10yo")
    m = wm.match_name("Inverness Cream", index=idx)
    assert m["tier"] == "D"
    assert m["kandidat"] is None


# ─── de to harde reglene ─────────────────────────────────────────────

def test_contradicting_age_blocks_the_match_entirely():
    """
    Aberlour 12 og Aberlour 18 er to forskjellige flasker uansett hvor likt
    resten av navnet leser. Uten denne regelen ble «Aberlour 12 YO» matchet mot
    «Aberlour A'Bunadh» i den målte kjøringen.
    """
    idx = _index("Aberlour 18yo")
    m = wm.match_name("Aberlour 12 YO Single Malt", index=idx)
    assert m["kandidat"] is None


def test_brand_must_match_even_when_the_rest_is_nearly_identical():
    """
    Uavhengige tappinger deler serienavn og årgang, og skiller seg BARE på hvem
    som tappet. «Glenlivet Connoisseurs Choice 1996» og «Gordon & MacPhail
    Connoisseurs Choice 1996» overlapper på 3 av 6 tokens — nok til tier C uten
    merke-regelen, altså nok til å havne i bunken et menneske må vurdere.

    Første versjon av denne testen brukte «Glenfiddich» mot «Glenlivet», som
    ikke deler ETT token. Den var grønn med og uten regelen — den testet
    ingenting. Mutasjonstest fanget det.
    """
    idx = _index("Gordon & MacPhail Connoisseurs Choice 1996")
    m = wm.match_name("Glenlivet Connoisseurs Choice 1996", index=idx)
    assert m["kandidat"] is None, (
        "en annen tappers flaske ble foreslått som kandidat"
    )
    assert m["tier"] == "D"


def test_different_expressions_of_the_same_brand_do_not_reach_auto_tier():
    """
    «Jack Daniel's Tennessee» → «Gentleman Jack» er en ekte feil fra den målte
    kjøringen. Den kan ikke unngås av matcheren — begge er Jack Daniel's — men
    den skal ALDRI havne i A eller B, der ingen ser på den igjen.
    """
    idx = _index("Jack Daniel's Gentleman Jack")
    m = wm.match_name("Jack Daniel's Tennessee", index=idx)
    assert m["tier"] not in ("A", "B"), (
        "en annen tapping av samme merke ble auto-godtatt — det er nøyaktig "
        "feilen tier C finnes for å fange"
    )


# ─── resolve: ubekreftet tier C er INGEN match ───────────────────────

def test_unconfirmed_tier_c_resolves_to_nothing(tmp_path, monkeypatch):
    join = tmp_path / "join.ndjson"
    join.write_text(
        json.dumps({"polet_id": "1", "tier": "C", "bekreftet": None,
                    "wa_whisky": "Noe", "meta_critic": 8.0}) + "\n"
        + json.dumps({"polet_id": "2", "tier": "C", "bekreftet": "ja",
                      "wa_whisky": "Noe annet", "meta_critic": 8.1}) + "\n"
        + json.dumps({"polet_id": "3", "tier": "A", "bekreftet": "n/a",
                      "wa_whisky": "Eksakt", "meta_critic": 9.0}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(wm, "JOIN", join)

    assert wm.resolve("1") is None, "ubekreftet tier C er ingen match, ikke en svak match"
    assert wm.resolve("2")["wa_whisky"] == "Noe annet"
    assert wm.resolve("3")["wa_whisky"] == "Eksakt"
    assert wm.resolve("finnes-ikke") is None


def test_pending_lists_only_unanswered_tier_c(tmp_path, monkeypatch):
    join = tmp_path / "join.ndjson"
    join.write_text(
        json.dumps({"polet_id": "1", "tier": "C", "bekreftet": None, "wa_whisky": "A"}) + "\n"
        + json.dumps({"polet_id": "2", "tier": "C", "bekreftet": "nei", "wa_whisky": "B"}) + "\n"
        + json.dumps({"polet_id": "3", "tier": "A", "bekreftet": "n/a", "wa_whisky": "C"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(wm, "JOIN", join)
    assert [r["polet_id"] for r in wm.pending()] == ["1"]


# ─── regenerering må ikke kaste menneskets arbeid ────────────────────

def test_rewriting_the_join_preserves_confirmations(tmp_path, monkeypatch):
    """
    Bekreftelsene er det eneste i denne pipelinen som koster menneskelig tid.
    En regenerering som nullstiller dem ville tapt arbeidet STILLE — det
    oppdages først når noen leter etter et svar de husker å ha gitt.
    """
    join = tmp_path / "join.ndjson"
    monkeypatch.setattr(wm, "JOIN", join)

    wm.write_join([{"polet_id": "1", "tier": "C", "wa_whisky": "Kandidat X",
                    "polet_navn": "Noe", "score": 0.5}])
    rader = wm.read_join()
    rader["1"]["bekreftet"] = "ja"
    join.write_text(json.dumps(rader["1"], sort_keys=True) + "\n", encoding="utf-8")

    # Regenerer med SAMME kandidat → svaret skal overleve.
    wm.write_join([{"polet_id": "1", "tier": "C", "wa_whisky": "Kandidat X",
                    "polet_navn": "Noe", "score": 0.5}])
    assert wm.read_join()["1"]["bekreftet"] == "ja"


def test_a_changed_candidate_invalidates_the_old_confirmation(tmp_path, monkeypatch):
    """
    Motstykket: peker matcheren på en NY kandidat, gjaldt ikke det gamle ja-et
    den. Å arve bekreftelsen ville vært å bekrefte noe ingen har sett på.
    """
    join = tmp_path / "join.ndjson"
    monkeypatch.setattr(wm, "JOIN", join)

    wm.write_join([{"polet_id": "1", "tier": "C", "wa_whisky": "Kandidat X",
                    "polet_navn": "Noe", "score": 0.5}])
    rader = wm.read_join()
    rader["1"]["bekreftet"] = "ja"
    join.write_text(json.dumps(rader["1"], sort_keys=True) + "\n", encoding="utf-8")

    wm.write_join([{"polet_id": "1", "tier": "C", "wa_whisky": "Kandidat Y",
                    "polet_navn": "Noe", "score": 0.5}])
    assert wm.read_join()["1"]["bekreftet"] is None


# ─── kalibrering mot det målte ───────────────────────────────────────

def test_his_seven_bottles_all_join():
    """
    De sju han faktisk har ratet er den ene delmengden der en manglende join
    merkes med en gang. Alle sju skal treffe, og ingen av dem på tier C.
    """
    join = wm.read_join()
    if not join:
        pytest.skip("join.ndjson ikke bygget i dette miljøet")
    for kode in ("464401", "1975701", "11356801", "12701", "3021801", "468001", "579401"):
        rad = join.get(kode)
        assert rad is not None, f"{kode} mangler i join-fila"
        assert rad["tier"] in ("A", "B"), f"{kode} landet på tier {rad['tier']}"
        assert rad["meta_critic"] is not None
