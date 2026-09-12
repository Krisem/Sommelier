"""
Tester for tools/recommend.py — syntetisk katalog, ingen nettverkskall.

Alle tester patcher `polet_store.read_catalog` og `value_score.compute_value_score`.
`user_fit._catalog_index` er `lru_cache`-et og MÅ tømmes, ellers måler testen
den ekte 14k-katalogen i stedet for fixturen.
"""

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools import polet_store, recommend, user_fit

REPO_ROOT = Path(__file__).resolve().parent.parent


def _rad(code, navn, pris, volum=75, land=("italia", "Italia"), kategori=("rødvin", "Rødvin"),
         status="aktiv", klokker=None, distrikt=("italia_piemonte", "Piemonte")):
    return {
        "code": code,
        "name": navn,
        "status": status,
        "price": {"value": pris},
        "volume": {"value": volum},
        "main_country": {"code": land[0], "name": land[1]},
        "main_category": {"code": kategori[0], "name": kategori[1]},
        "district": {"code": distrikt[0], "name": distrikt[1]},
        "sub_District": {},
        "clock_buckets": klokker or {"Fylde": "7-8", "Friskhet": "7-8", "Tannin": "7-8"},
        "product_selection": "Basisutvalget",
        "alcohol": {"value": 13.5},
        "url": f"/p/{code}",
    }


KATALOG = [
    # 3-liters kartong: volum i CENTILITER (300), ikke 3.
    _rad("10037906", "La Huella 2024", 494.9, volum=300, land=("spania", "Spania")),
    _rad("10059006", "Giacosa Fratelli Piemonte Barbera", 544.9, volum=300),
    # Amerikansk → [USA]-flagg, skal ALDRI filtreres bort (ADR-016 / CLAUDE.md steg 8)
    _rad("20000001", "Napa Ridge Cabernet 2021", 399.0, volum=300, land=("usa", "USA"),
         distrikt=("usa_california", "California")),
    _rad("30000001", "Billig Flaske 2023", 99.0, volum=75),
    # Ikke kjøpbar — finnes i snapshotet, men utsolgt
    _rad("40000001", "Utsolgt Vin 2020", 250.0, volum=75, status="utsolgt"),
]


@pytest.fixture
def katalog(monkeypatch):
    monkeypatch.setattr(polet_store, "read_catalog", lambda: list(KATALOG))
    monkeypatch.setattr(polet_store, "catalog_age_days", lambda: 11.0)
    user_fit._catalog_index.cache_clear()
    yield
    user_fit._catalog_index.cache_clear()


@pytest.fixture
def ingen_value(monkeypatch):
    """Enhver value-kjøring teller seg selv — og rører aldri nettet."""
    kall = []

    def fake(produkt, **kw):
        kall.append(produkt.get("code"))
        return {
            "value_verdict": "godt_kjop",
            "quality_tier": "high",
            "summary": "syntetisk",
            "snapshot_age_days": 11,
        }

    monkeypatch.setattr(recommend.value_score, "compute_value_score", fake)
    return kall


@pytest.fixture
def vivino_csv(tmp_path):
    p = tmp_path / "full_wine_list.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "Winery", "Wine name", "Vintage", "Region", "Country",
            "Regional wine style", "Average rating", "Scan date", "Your rating",
        ])
        w.writeheader()
        w.writerow({"Winery": "Giacosa Fratelli", "Wine name": "Piemonte Barbera",
                    "Vintage": "2022", "Region": "Piemonte", "Country": "Italy",
                    "Average rating": "3.8", "Scan date": "2026-01-05 10:00:00",
                    "Your rating": "4.3"})
        w.writerow({"Winery": "Scannet Uten", "Wine name": "Rating Vin",
                    "Region": "Piemonte", "Country": "Italy",
                    "Average rating": "3.5", "Scan date": "2026-02-01 10:00:00",
                    "Your rating": ""})
    return p


# ─── LITERPRIS ───────────────────────────────────────────────────────

def test_literpris_fra_centiliter(katalog, ingen_value):
    """Kjent positiv rad: 494,90 kr / 3,0 l = 164,97 kr/l."""
    rader = recommend.recommend(volum_min=2.9, volum_maks=3.1, antall=10)
    huella = next(r for r in rader if r["varenummer"] == "10037906")
    assert huella["volum_liter"] == 3.0
    assert huella["literpris"] == pytest.approx(164.97, abs=0.01)


def test_literpris_taaler_manglende_volum():
    assert recommend._literpris(100.0, None) is None
    assert recommend._literpris(100.0, 0) is None
    assert recommend._literpris(None, 75) is None
    assert recommend._literpris(150.0, 75) == 200.0


def test_volumfilter_treffer_kartong_ikke_flaske(katalog, ingen_value):
    rader = recommend.recommend(volum_min=2.9, volum_maks=3.1, antall=10)
    koder = {r["varenummer"] for r in rader}
    assert "30000001" not in koder, "75 cl-flaska skal ikke treffe 3 l-filteret"
    # Negativ telling validert mot kjente positive rader:
    assert koder == {"10037906", "10059006", "20000001"}


# ─── ADR-016: TIER ER ET MERKE, IKKE ET FILTER ───────────────────────

def test_no_go_og_risky_overlever_til_output(katalog, ingen_value, monkeypatch):
    """Selv når hver eneste kandidat er no_go/risky skal alle stå igjen."""
    tiere = {"10037906": "no_go", "10059006": "risky", "20000001": "no_go"}
    monkeypatch.setattr(recommend.user_fit, "classify", lambda rad, regler=None: {
        "tier": tiere.get(str(rad.get("code")), "neutral"),
        "reasons": ["syntetisk"], "confidence": "high",
        "rule_fired": "test", "explore": False,
    })
    rader = recommend.recommend(volum_min=2.9, volum_maks=3.1, antall=10)
    assert len(rader) == 3
    assert {r["user_fit"]["tier"] for r in rader} == {"no_go", "risky"}
    assert rader[0]["sok"]["treff_totalt"] == 3


def test_usa_flagges_men_filtreres_ikke(katalog, ingen_value):
    rader = recommend.recommend(volum_min=2.9, volum_maks=3.1, antall=10)
    napa = next(r for r in rader if r["varenummer"] == "20000001")
    assert "[USA]" in napa["flagg"]


def test_user_fit_felter_foelger_med(katalog, ingen_value):
    rader = recommend.recommend(antall=10)
    f = rader[0]["user_fit"]
    assert set(f) >= {"tier", "rule_fired", "confidence", "reasons"}


# ─── VALUE KUN PÅ TOPP-N ─────────────────────────────────────────────

def test_value_kjores_bare_paa_topp_n(katalog, ingen_value):
    rader = recommend.recommend(volum_min=2.9, volum_maks=3.1, antall=2)
    assert len(ingen_value) == 2, f"value kjørt på {len(ingen_value)} rader, ikke 2"
    assert set(ingen_value) == {r["varenummer"] for r in rader}
    assert rader[0]["sok"]["treff_totalt"] == 3, "hele trefflista skal fortsatt telles"
    assert all(r["value"]["snapshot_age_days"] == 11 for r in rader)


def test_ingen_value_flagget_hopper_over_nett(katalog, ingen_value):
    rader = recommend.recommend(antall=5, value=False)
    assert ingen_value == []
    assert all(r["value"] is None and r["value_status"] == "ikke_kjort" for r in rader)
    assert rader[0]["sok"]["value_kjort_paa"] == 0


def test_value_feil_degraderer_raden_men_stopper_ikke_svaret(katalog, monkeypatch):
    def sprenger(produkt, **kw):
        raise RuntimeError("nettverk nede")
    monkeypatch.setattr(recommend.value_score, "compute_value_score", sprenger)
    rader = recommend.recommend(volum_min=2.9, volum_maks=3.1, antall=2)
    assert len(rader) == 2
    assert all(r["value"] is None for r in rader)
    assert all(r["value_status"].startswith("feil:") for r in rader)


# ─── 0 TREFF SIER HVORFOR ────────────────────────────────────────────

def test_for_stramt_filter_forklarer_seg(katalog, ingen_value):
    with pytest.raises(recommend.IngenTreff) as e:
        recommend.recommend(maks_pris=1.0, antall=5)
    m = str(e.value)
    assert "for stramt" in m
    assert "docs/polet_refresh.md" not in m, "feil årsak — dette er ikke et snapshot-hull"


def test_ukjent_varenr_peker_paa_refresh(katalog, ingen_value):
    with pytest.raises(recommend.IngenTreff) as e:
        recommend.recommend(varenr=["99999999"])
    m = str(e.value)
    assert "99999999" in m and "docs/polet_refresh.md" in m


def test_finnes_men_ikke_kjopbar_peker_ikke_paa_refresh(katalog, ingen_value):
    """Tredje årsak: raden finnes, men er utsolgt. Refresh er feil råd der."""
    with pytest.raises(recommend.IngenTreff) as e:
        recommend.recommend(varenr=["40000001"])
    m = str(e.value)
    assert "ikke kjøpbar" in m
    assert "Ingen refresh hjelper" in m


def test_delvis_bom_paa_varenr_er_synlig(katalog, ingen_value):
    """Ett gyldig + ett ukjent + ett utsolgt: de to tapte skal stå i outputen."""
    rader = recommend.recommend(varenr=["10037906", "99999999", "40000001"])
    assert len(rader) == 1
    assert rader[0]["sok"]["mangler_i_snapshot"] == ["99999999"]
    assert rader[0]["sok"]["ikke_kjopbar"] == ["40000001"]


# ─── ÅRGANG, KLOKKER, VIVINO ─────────────────────────────────────────

def test_aargang_hentes_fra_navnet(katalog, ingen_value):
    rader = recommend.recommend(volum_min=2.9, volum_maks=3.1, antall=10)
    by = {r["varenummer"]: r for r in rader}
    assert by["10037906"]["aargang"] == 2024
    assert by["10059006"]["aargang"] is None, "årgangsløs vin skal ikke få en oppdiktet årgang"


def test_aargang_sendes_til_value_score(katalog, monkeypatch):
    sett = {}
    monkeypatch.setattr(recommend.value_score, "compute_value_score",
                        lambda p, **kw: sett.update({p["code"]: kw.get("vintage")}) or
                        {"value_verdict": "x", "quality_tier": "y", "summary": "z",
                         "snapshot_age_days": 1})
    recommend.recommend(varenr=["10037906"])
    assert sett == {"10037906": 2024}


def test_klokker_beholder_katalogens_egne_nokler(katalog, ingen_value):
    rader = recommend.recommend(varenr=["10037906"], value=False)
    assert rader[0]["klokker"] == {"Fylde": "7-8", "Friskhet": "7-8", "Tannin": "7-8"}


def test_vivino_treff_gir_provd_med_rating(katalog, ingen_value, vivino_csv):
    rader = recommend.recommend(varenr=["10059006"], value=False, vivino_csv=vivino_csv)
    h = rader[0]["vivino_historikk"]
    assert h is not None and h["din_rating"] == 4.3
    assert "[PRØVD]" in rader[0]["flagg"]


def test_kjent_region_gir_liknende_ikke_nytt(katalog, ingen_value, vivino_csv):
    rader = recommend.recommend(varenr=["30000001"], value=False, vivino_csv=vivino_csv)
    assert rader[0]["liknende_region"] == "Piemonte"
    assert rader[0]["flagg"] == ["[LIKNENDE]"]


def test_ukjent_terreng_gir_nytt(katalog, ingen_value, vivino_csv):
    rader = recommend.recommend(varenr=["20000001"], value=False, vivino_csv=vivino_csv)
    assert rader[0]["vivino_historikk"] is None
    assert rader[0]["flagg"] == ["[NYTT]", "[USA]"]


def test_navnematch_avviser_ulik_vin_med_samme_produsent():
    """Målt falsk positiv fra den løsere regelen — skal forbli avvist."""
    viv = [{"_tokens": set(recommend._normaliser("Dei Vino Nobile di Montepulciano Riserva")),
            "Winery": "Dei", "Wine name": "Vino Nobile", "Your rating": "4.0",
            "Vintage": "", "Average rating": "", "Scan date": ""}]
    rad = {"name": "Torre dei Beati Montepulciano d'Abruzzo Mazzamurello 2015"}
    assert recommend._historikk(rad, viv) is None


def test_scannet_uten_rating_er_ikke_aldri_provd(katalog, ingen_value, tmp_path, monkeypatch):
    p = tmp_path / "v.csv"
    p.write_text(
        "Winery,Wine name,Vintage,Region,Country,Regional wine style,"
        "Average rating,Scan date,Your rating\n"
        "Giacosa Fratelli,Piemonte Barbera,,Piemonte,Italy,,3.8,2026-01-05 10:00:00,\n",
        encoding="utf-8")
    rader = recommend.recommend(varenr=["10059006"], value=False, vivino_csv=p)
    h = rader[0]["vivino_historikk"]
    assert h is not None and h["din_rating"] is None
    assert "[PRØVD]" in rader[0]["flagg"]


# ─── SØKE-META OG CLI ────────────────────────────────────────────────

def test_sok_meta_viser_hva_som_ble_kappet(katalog, ingen_value):
    rader = recommend.recommend(volum_min=2.9, volum_maks=3.1, antall=1)
    sok = rader[0]["sok"]
    assert sok["treff_totalt"] == 3 and sok["viser"] == 1
    assert "literpris" in sok["sortering"]
    assert sok["snapshot_alder_dager"] == 11.0


def test_cli_json_er_gyldig_json():
    r = subprocess.run(
        [sys.executable, "-m", "tools.recommend", "--kategori", "rødvin",
         "--volum-min", "2.9", "--volum-maks", "3.1", "--antall", "2",
         "--ingen-value", "--json"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    rader = json.loads(r.stdout)
    assert len(rader) == 2
    assert all(r_["volum_liter"] == 3.0 for r_ in rader)


def test_cli_0_treff_gir_exit_1_og_forklaring():
    r = subprocess.run(
        [sys.executable, "-m", "tools.recommend", "--varenr", "99999999", "--ingen-value"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 1
    assert "0 treff" in r.stderr and "polet_refresh" in r.stderr


# ─── SORTERINGS-RETNING ──────────────────────────────────────────────

def test_default_sortering_er_uendret_literpris_stigende(katalog, ingen_value):
    rader = recommend.recommend(volum_min=2.9, volum_maks=3.1, antall=10)
    assert [r["varenummer"] for r in rader] == ["20000001", "10037906", "10059006"]


def test_synkende_snur_utsnittet(katalog, ingen_value):
    """`--antall` må kunne treffe den DYRE enden — ellers lyver kappingen."""
    rader = recommend.recommend(volum_min=2.9, volum_maks=3.1, antall=2, synkende=True)
    assert [r["varenummer"] for r in rader] == ["10059006", "10037906"]
    assert "literpris desc" in rader[0]["sok"]["sortering"]


def test_sorter_paa_pris(katalog, ingen_value):
    rader = recommend.recommend(volum_min=2.9, volum_maks=3.1, antall=3, sorter="pris")
    assert [r["pris"] for r in rader] == [399.0, 494.9, 544.9]


def test_rad_uten_literpris_sorteres_sist_i_begge_retninger(katalog, ingen_value, monkeypatch):
    katalog_uten = list(KATALOG) + [_rad("50000001", "Uten Volum", 200.0, volum=None)]
    monkeypatch.setattr(polet_store, "read_catalog", lambda: katalog_uten)
    for synkende in (False, True):
        rader = recommend.recommend(antall=10, synkende=synkende, value=False)
        assert rader[-1]["varenummer"] == "50000001", f"synkende={synkende}"


def test_ukjent_sorteringsnokkel_avvises(katalog, ingen_value):
    with pytest.raises(ValueError, match="Ukjent sorteringsnøkkel"):
        recommend.recommend(antall=3, sorter="tier")


# ─── EMBALLASJE: VOLUM ALENE SKILLER IKKE KARTONG FRA STORFORMAT ─────

def test_emballasje_leses_av_varenummer_suffiks():
    assert recommend._emballasje("10037906") == "kartong"
    assert recommend._emballasje("18853707") == "flaske"   # Haut-Brion dobbeltmagnum
    assert recommend._emballasje("10002601") == "flaske"   # standard 75 cl
    assert recommend._emballasje("99999999") is None


def test_emballasjefilter_skiller_kartong_fra_dobbeltmagnum(katalog, ingen_value, monkeypatch):
    """Samme volum (3 l), ulik emballasje — bare suffikset skiller dem."""
    magnum = _rad("18853707", "Ch. Haut-Brion 2021", 29412.5, volum=300,
                  land=("frankrike", "Frankrike"))
    monkeypatch.setattr(polet_store, "read_catalog", lambda: list(KATALOG) + [magnum])

    alle = recommend.recommend(volum_min=2.9, volum_maks=3.1, antall=10)
    assert "18853707" in {r["varenummer"] for r in alle}, "volumfilteret alene tar med flaska"

    kartong = recommend.recommend(volum_min=2.9, volum_maks=3.1, antall=10,
                                  emballasje="kartong")
    koder = {r["varenummer"] for r in kartong}
    assert "18853707" not in koder
    # 20000001 faller også bort: suffikset …01 er flaske, uansett at volumet er 3 l.
    # Filteret leser emballasje, ikke størrelse — det er hele poenget.
    assert koder == {"10037906", "10059006"}
    assert all(r["emballasje"] == "kartong" for r in kartong)
