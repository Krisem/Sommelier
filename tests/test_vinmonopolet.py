"""Vinmonopolet-helper kontrakt-test.

Tester den nye snapshot-veien: search/search_with_facets/get_product_details
leser repo-snapshotet via tools.polet_store (ingen nettverk). polet_store pekes
mot en liten fixture-katalog i tmp via monkeypatch. Cache-miss → PoletRefreshRequired.

**To testklasser her, med ulikt formål:**

1. *Fixture-tester* (`snapshot`, `snapshot_med_bøtter`) — logikk på små, kjente
   data. Raske, deterministiske.
2. *Skalainvariante tester* (`ekte_katalog`) — kjører mot ekte
   `data/polet/catalog.ndjson` og asserterer at funksjonene har SETT hele
   datagrunnlaget. De finnes fordi suiten var 291 grønne mens `search` filtrerte
   3 av 94 Barbera og `find_similar_by_clocks` rangerte 13 av 701 kandidater:
   begge buggene er usynlige på en fixture med tre rader, og begge returnerte
   plausible svar. Assertene er formulert som ANDELER og som kryss-sjekk mot
   `polet_store`, aldri som hardkodede tall — de skal holde ved 1 849 rader og
   ved 137 750.
"""

from __future__ import annotations

import json

import pytest


# ─── FIXTURE: liten snapshot-katalog i tmp ───────────────────────────
#
# Alle radene bærer `status: "aktiv"`. Det er ikke pynt: `search` og
# `polet_store.query` defaulter til kjøpbare varer siden 2026-08-31, og en
# fixture uten status ville testet fritekst- og prisfiltrene på rader som
# filtreres bort av en helt annen grunn — grønt av feil grunn.

_CATALOG = [
    {
        "code": "10267301",
        "status": "aktiv",
        "name": "Contra Soarda Breganze Vespaiolo 2023",
        "price": {"value": 299.9, "formattedValue": "Kr 299,90"},
        "main_category": {"code": "hvitvin", "name": "Hvitvin"},
        "main_country": {"code": "italia", "name": "Italia"},
        "url": "/Land/Italia/Veneto/Breganze/Contra-Soarda-Breganze-Vespaiolo-2023/p/10267301",
    },
    {
        "code": "11156601",
        "status": "aktiv",
        "name": "Thibault Liger-Belair Bourgogne Rouge Les Grands Chaillots",
        "price": {"value": 495.5, "formattedValue": "Kr 495,50"},
        "main_category": {"code": "rødvin", "name": "Rødvin"},
        "main_country": {"code": "frankrike", "name": "Frankrike"},
        "url": "/Land/Frankrike/Burgund/Bourgogne/Thibault-Liger-Belair/p/11156601",
    },
    {
        "code": "15012201",
        "status": "aktiv",
        "name": "Tornatore Etna Rosso 2022",
        "price": {"value": 289.0, "formattedValue": "Kr 289,00"},
        "main_category": {"code": "rødvin", "name": "Rødvin"},
        "main_country": {"code": "italia", "name": "Italia"},
        # Distriktskoden bærer landprefiks — derfor matcher fritekst-søket kun
        # `.name` på disse objektene, aldri `.code`.
        "district": {"code": "italia_sicilia", "name": "Sicilia"},
        "sub_District": {"code": "italia_sicilia_etna", "name": "Etna"},
        "url": "/Land/Italia/Sicilia/Etna/Tornatore-Etna-Rosso-2022/p/15012201",
    },
]

_DETAILS_15012201 = {
    "code": "15012201",
    "url": "https://www.vinmonopolet.no/Land/Italia/Sicilia/Etna/Tornatore-Etna-Rosso-2022/p/15012201",
    "klokker": {"Fylde": 6, "Friskhet": 8, "Garvestoffer": 6},
    "stil": "Frisk og fruktig",
    "druer": "Nerello Mascalese 95 prosent",
    "fetched_at": "2026-05-12T19:47:09.555981+00:00",
}


@pytest.fixture
def snapshot(monkeypatch, tmp_path):
    """Peker polet_store mot en tmp-katalog fylt med fixture-data."""
    from tools import polet_store

    polet_dir = tmp_path / "polet"
    details_dir = polet_dir / "details"
    details_dir.mkdir(parents=True)

    catalog = polet_dir / "catalog.ndjson"
    catalog.write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in _CATALOG) + "\n",
        encoding="utf-8",
    )
    (details_dir / "15012201.json").write_text(
        json.dumps(_DETAILS_15012201, ensure_ascii=False), encoding="utf-8"
    )

    monkeypatch.setattr(polet_store, "POLET_DIR", polet_dir)
    monkeypatch.setattr(polet_store, "CATALOG", catalog)
    monkeypatch.setattr(polet_store, "DETAILS_DIR", details_dir)
    monkeypatch.setattr(polet_store, "META", polet_dir / "catalog_meta.json")
    return polet_store


# ─── search ──────────────────────────────────────────────────────────

def test_search_returns_products_with_required_fields(snapshot):
    from tools.vinmonopolet import search

    results = search("Tornatore")
    assert isinstance(results, list)
    assert len(results) >= 1

    p = results[0]
    assert p["name"], "produkt mangler 'name'"
    assert p["code"], "produkt mangler 'code' (varenummer)"
    assert isinstance(p["price"], dict)
    assert isinstance(p["price"]["value"], (int, float))
    assert p["price"]["value"] > 0


def test_search_respects_page_size(snapshot):
    from tools.vinmonopolet import search

    # Tom name_contains matcher alle 3 produktene
    results = search("", page_size=2)
    assert len(results) == 2


def test_search_miss_raises_refresh_required(snapshot):
    from tools.vinmonopolet import search
    from tools.polet_store import PoletRefreshRequired

    with pytest.raises(PoletRefreshRequired) as exc:
        search("FinnesIkkeISnapshot")
    assert exc.value.url is not None


# ─── search_with_facets ──────────────────────────────────────────────

def test_search_with_facets_maps_category_and_country(snapshot):
    from tools.vinmonopolet import search_with_facets

    results = search_with_facets({"mainCategory": "rødvin", "mainCountry": "italia"})
    assert len(results) == 1
    assert results[0]["code"] == "15012201"


def test_search_with_facets_matches_by_name_too(snapshot):
    from tools.vinmonopolet import search_with_facets

    # 'Rødvin' (name) skal matche like godt som 'rødvin' (code)
    results = search_with_facets({"mainCategory": "Rødvin"})
    codes = {p["code"] for p in results}
    assert codes == {"11156601", "15012201"}


def test_search_with_facets_miss_raises_refresh_required(snapshot):
    from tools.vinmonopolet import search_with_facets
    from tools.polet_store import PoletRefreshRequired

    with pytest.raises(PoletRefreshRequired):
        search_with_facets({"mainCategory": "rødvin", "mainCountry": "spania"})


# ─── get_product_details ─────────────────────────────────────────────

def test_get_product_details_derives_code_from_relative_url(snapshot):
    from tools.vinmonopolet import get_product_details

    details = get_product_details(
        "/Land/Italia/Sicilia/Etna/Tornatore-Etna-Rosso-2022/p/15012201"
    )
    assert details["klokker"] == {"Fylde": 6, "Friskhet": 8, "Garvestoffer": 6}
    assert details["stil"] == "Frisk og fruktig"


def test_get_product_details_derives_code_from_absolute_url(snapshot):
    from tools.vinmonopolet import get_product_details

    details = get_product_details(
        "https://www.vinmonopolet.no/Land/X/Y/Z/Foo/p/15012201"
    )
    assert details["code"] == "15012201"


def test_get_product_details_miss_raises_refresh_required(snapshot):
    from tools.vinmonopolet import get_product_details
    from tools.polet_store import PoletRefreshRequired

    with pytest.raises(PoletRefreshRequired) as exc:
        get_product_details("/Land/X/Y/Z/Ukjent/p/99999999")
    assert exc.value.url == "/Land/X/Y/Z/Ukjent/p/99999999"


def test_get_product_details_unparseable_url_raises_refresh_required(snapshot):
    from tools.vinmonopolet import get_product_details
    from tools.polet_store import PoletRefreshRequired

    with pytest.raises(PoletRefreshRequired):
        get_product_details("/noe/uten/produktkode")


# ═══ B2: search filtrerer FØR den avkorter ═══════════════════════════
#
# Repro fra tasks/exploration/scenario_test_2026-08-30.md:
#   filter_results(search("Barbera"), max_price=250)  → 3, mens snapshotet har 94.
# Taket var ikke feil; plasseringen var det.

def test_search_applies_filters_before_truncating(snapshot):
    """Med page_size=1 og et prisfilter skal treffet være det som består
    filteret — ikke det første i katalogen som tilfeldigvis ryker på pris."""
    from tools.vinmonopolet import search

    # Fixturen har to rødviner: 11156601 (495,50) og 15012201 (289,00).
    # Sortert på varenummer kommer den DYRE først, så et etterpå-filter med
    # page_size=1 ville gitt 0 treff.
    results = search("", page_size=1, max_price=300, category="Rødvin")
    assert len(results) == 1, "avkortingen spiste treffet filteret ville beholdt"
    assert results[0]["code"] == "15012201"


def test_search_page_size_none_returns_whole_population(snapshot):
    from tools.vinmonopolet import search

    assert len(search("", page_size=None)) == 3


def test_search_filter_miss_returns_empty_not_refresh_required(snapshot):
    """Fritekst traff, filtrene tømte. Da mangler det ingen data i snapshotet,
    og et refresh-hint ville vært direkte feil råd."""
    from tools.vinmonopolet import search

    assert search("Tornatore", max_price=1) == []


def test_search_still_raises_when_freetext_misses(snapshot):
    from tools.polet_store import PoletRefreshRequired
    from tools.vinmonopolet import search

    with pytest.raises(PoletRefreshRequired):
        search("FinnesIkkeISnapshot", max_price=1000)


def test_search_matches_district_and_sub_district(snapshot):
    """38 av 74 Etna-rødviner har ikke «Etna» i navnet. Fritekst må se
    distriktsfeltene, ellers er de usynlige."""
    from tools.vinmonopolet import search

    # Fixturens Tornatore har ikke «Sicilia» i navnet.
    assert "Sicilia" not in _CATALOG[2]["name"]
    treff = search("Sicilia", page_size=None)
    assert [p["code"] for p in treff] == ["15012201"]


def test_search_fields_can_be_narrowed_to_name_only(snapshot):
    from tools.vinmonopolet import search
    from tools.polet_store import PoletRefreshRequired

    with pytest.raises(PoletRefreshRequired):
        search("Sicilia", page_size=None, fields=("name",))


def test_search_does_not_match_district_code(snapshot):
    """Distriktskoden bærer landprefiks («italia_sicilia»). Matcher søket på
    .code, returnerer «italia» stille hver eneste italienske vin."""
    from tools.polet_store import PoletRefreshRequired
    from tools.vinmonopolet import search

    assert _CATALOG[2]["district"]["code"].startswith("italia_")
    with pytest.raises(PoletRefreshRequired):
        search("italia_", page_size=None)


def test_filter_results_matches_code_as_well_as_name(snapshot):
    """ADR-009 i miniatyr: «rødvin» (code) og «Rødvin» (name) er samme filter."""
    from tools.vinmonopolet import filter_results, search

    alle = search("", page_size=None)
    assert len(filter_results(alle, category="rødvin")) == len(
        filter_results(alle, category="Rødvin")
    ) == 2


# ═══ B3: klokke-navnerommet — samme klokke, tre navn ═════════════════
#
# `Garvestoffer` (details) · `Tannin` (katalogens clock_buckets) ·
# `Tannin(Sulfates)` (søke-fasett). Tredje utgave av kollisjonen i ADR-009 /
# ADR-024. Den farlige varianten er den som IKKE synes i outputen.

def test_clock_distance_raises_on_missing_dimension():
    """Den stille degraderingen: før 2026-08-30 returnerte dette en finit,
    plausibel avstand regnet på 2 av 3 akser."""
    from tools.vinmonopolet import MissingClockDimension, clock_distance

    a = {"Fylde": 8, "Friskhet": 9, "Garvestoffer": 7}
    b = {"Fylde": 8, "Friskhet": 9}
    with pytest.raises(MissingClockDimension):
        clock_distance(a, b)


def test_clock_distance_rejects_raw_catalog_buckets():
    """DEN testen som ville fanget B3-fiksen gjort feil.

    Mater man en katalograds clock_buckets rett inn — uten å oversette
    `Tannin` → `Garvestoffer` — er garvestoff-aksen borte. Gammel oppførsel:
    et finit, troverdig tall regnet på fylde og friskhet alene.
    """
    from tools.polet_facets import clocks_from_buckets
    from tools.vinmonopolet import MissingClockDimension, clock_distance

    target = {"Fylde": 8, "Friskhet": 9, "Garvestoffer": 7}
    rå_rad = {"Fylde": 7.5, "Friskhet": 9.5, "Tannin": 7.5}  # katalog-navnerom

    with pytest.raises(MissingClockDimension) as exc:
        clock_distance(target, rå_rad)
    assert "Tannin" in str(exc.value), "feilmeldingen må peke på navnerommet"

    # Oversatt går det bra — og aksen er faktisk med.
    oversatt = clocks_from_buckets({"Fylde": "7-8", "Friskhet": "9-10", "Tannin": "7-8"})
    assert "Garvestoffer" in oversatt and "Tannin" not in oversatt
    assert clock_distance(target, oversatt) == pytest.approx(0.5)


def test_clocks_from_buckets_translates_and_midpoints():
    from tools.polet_facets import bucket_midpoint, clocks_from_buckets

    assert bucket_midpoint("7-8") == 7.5
    assert bucket_midpoint("11-12") == 11.5
    with pytest.raises(ValueError):
        bucket_midpoint("7-9")

    assert clocks_from_buckets(
        {"Fylde": "7-8", "Friskhet": "9-10", "Tannin": "5-6"}
    ) == {"Fylde": 7.5, "Friskhet": 9.5, "Garvestoffer": 5.5}


def test_clocks_from_buckets_keeps_unknown_dim_name():
    """En framtidig klokke vi ikke kjenner skal ikke krasje en
    similarity-kjøring — sikringen mot en tapt AKSE ligger i clock_distance."""
    from tools.polet_facets import clocks_from_buckets

    ut = clocks_from_buckets({"Fylde": "7-8", "Krydder": "1-2"})
    assert ut == {"Fylde": 7.5, "Krydder": 1.5}


@pytest.mark.parametrize("katalognavn", ["Soedme", "Sødme"])
def test_clocks_from_buckets_translates_sweetness_both_spellings(katalognavn):
    """Sødme-klokka er den fjerde stavemåten i denne kollisjonen: `Soedme` uten
    ø i søket og på katalograden, `Sødme` med ø i details (290 filer målt
    2026-08-30). Uten oversettelse mister hvitvins-similarity sødme-aksen
    stille — nøyaktig samme feil som `Tannin` / `Garvestoffer`."""
    from tools.polet_facets import clocks_from_buckets

    ut = clocks_from_buckets({"Fylde": "5-6", "Friskhet": "9-10", katalognavn: "1-2"})
    assert ut == {"Fylde": 5.5, "Friskhet": 9.5, "Sødme": 1.5}
    assert "Soedme" not in ut


def test_white_wine_similarity_axis_is_not_silently_lost():
    """Ende-til-ende av samme felle, på hvitvinsaksen: en katalograds bøtter
    matet rått inn mangler `Sødme` og må krasje, ikke regne på 2 av 3."""
    from tools.polet_facets import clocks_from_buckets
    from tools.vinmonopolet import MissingClockDimension, clock_distance

    hvit_dims = ("Fylde", "Friskhet", "Sødme")
    target = {"Fylde": 6, "Friskhet": 9, "Sødme": 2}
    # Tallene er allerede midtpunkter; det ENESTE som er galt er navnet.
    utranslatert = {"Fylde": 5.5, "Friskhet": 9.5, "Soedme": 1.5}

    with pytest.raises(MissingClockDimension) as exc:
        clock_distance(target, utranslatert, dims=hvit_dims)
    assert "Sødme" in str(exc.value)

    rå = {"Fylde": "5-6", "Friskhet": "9-10", "Soedme": "1-2"}
    assert clock_distance(target, clocks_from_buckets(rå), dims=hvit_dims) == pytest.approx(0.5)


def test_clock_distance_rejects_bucket_strings_with_a_useful_message():
    """Rå bøtte-koder ga TypeError før — teknisk sant, praktisk ubrukelig.
    Feilmeldingen skal peke på clocks_from_buckets."""
    from tools.vinmonopolet import clock_distance

    with pytest.raises(ValueError) as exc:
        clock_distance(
            {"Fylde": 8, "Friskhet": 9, "Garvestoffer": 7},
            {"Fylde": "7-8", "Friskhet": "9-10", "Garvestoffer": "7-8"},
        )
    assert "clocks_from_buckets" in str(exc.value)


def test_clock_distance_tolerance_treats_bucket_as_interval():
    """En bøtte er et 2-intervall, ikke et tall. Uten toleranse kan en
    bøtte-vin aldri nå avstand 0, og de 10 986 bøtte-vinene rangeres
    systematisk under de 1 668 med eksakte klokker."""
    from tools.vinmonopolet import BUCKET_TOLERANCE, clock_distance

    target = {"Fylde": 8, "Friskhet": 9, "Garvestoffer": 7}
    bøtte = {"Fylde": 7.5, "Friskhet": 9.5, "Garvestoffer": 7.5}  # bøttene 7-8/9-10/7-8

    assert clock_distance(target, bøtte) == pytest.approx(0.5)
    assert clock_distance(target, bøtte, tolerance=BUCKET_TOLERANCE) == 0.0
    # Toleransen forskyver, den nullstiller ikke: en vin to hakk unna er unna.
    fjern = {"Fylde": 3.5, "Friskhet": 9.5, "Garvestoffer": 7.5}
    assert clock_distance(target, fjern, tolerance=BUCKET_TOLERANCE) > 1.0


def test_clock_distance_rejects_negative_tolerance():
    from tools.vinmonopolet import clock_distance

    with pytest.raises(ValueError):
        clock_distance({"Fylde": 8}, {"Fylde": 8}, dims=("Fylde",), tolerance=-1)


# ═══ B3: find_similar_by_clocks leser clock_buckets ══════════════════

_KATALOG_MED_BØTTER = [
    # Eksakte klokker via details/ — 8/9/7, blink på målprofilen.
    {
        "code": "20000001",
        "name": "Eksakt Barbera",
        "price": {"value": 200.0},
        "main_category": {"code": "rødvin", "name": "Rødvin"},
        "main_country": {"code": "italia", "name": "Italia"},
        "url": "/Land/Italia/Piemonte/Eksakt-Barbera/p/20000001",
    },
    # Kun bøtter — samme stilsone, men ingen details-fil.
    {
        "code": "20000002",
        "name": "Bøtte Barbera",
        "price": {"value": 210.0},
        "main_category": {"code": "rødvin", "name": "Rødvin"},
        "main_country": {"code": "italia", "name": "Italia"},
        "url": "/Land/Italia/Piemonte/Botte-Barbera/p/20000002",
        "clock_buckets": {"Fylde": "7-8", "Friskhet": "9-10", "Tannin": "7-8"},
    },
    # Bøtter, men langt unna på fylde.
    {
        "code": "20000003",
        "name": "Fjern Barbera",
        "price": {"value": 220.0},
        "main_category": {"code": "rødvin", "name": "Rødvin"},
        "main_country": {"code": "italia", "name": "Italia"},
        "url": "/Land/Italia/Piemonte/Fjern-Barbera/p/20000003",
        "clock_buckets": {"Fylde": "1-2", "Friskhet": "9-10", "Tannin": "7-8"},
    },
    # Bøtter uten garvestoff-akse — skal telles som ufullstendig, ikke rangeres.
    {
        "code": "20000004",
        "name": "Halv Barbera",
        "price": {"value": 230.0},
        "main_category": {"code": "rødvin", "name": "Rødvin"},
        "main_country": {"code": "italia", "name": "Italia"},
        "url": "/Land/Italia/Piemonte/Halv-Barbera/p/20000004",
        "clock_buckets": {"Fylde": "7-8", "Friskhet": "9-10"},
    },
    # Ingen klokker i det hele tatt (~2 750 rødviner har dem ikke — ADR-024).
    {
        "code": "20000005",
        "name": "Blind Barbera",
        "price": {"value": 240.0},
        "main_category": {"code": "rødvin", "name": "Rødvin"},
        "main_country": {"code": "italia", "name": "Italia"},
        "url": "/Land/Italia/Piemonte/Blind-Barbera/p/20000005",
    },
]


@pytest.fixture
def snapshot_med_bøtter(monkeypatch, tmp_path):
    """Katalog hvor bare ÉN av fem viner har details — resten har clock_buckets
    eller ingenting. Speiler forholdet i ekte snapshot (1 668 details mot
    10 986 bøtter)."""
    from tools import polet_store

    polet_dir = tmp_path / "polet"
    details_dir = polet_dir / "details"
    details_dir.mkdir(parents=True)

    catalog = polet_dir / "catalog.ndjson"
    catalog.write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in _KATALOG_MED_BØTTER) + "\n",
        encoding="utf-8",
    )
    (details_dir / "20000001.json").write_text(
        json.dumps(
            {
                "code": "20000001",
                "klokker": {"Fylde": 8, "Friskhet": 9, "Garvestoffer": 7},
                "stil": "Frisk og fruktig",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(polet_store, "POLET_DIR", polet_dir)
    monkeypatch.setattr(polet_store, "CATALOG", catalog)
    monkeypatch.setattr(polet_store, "DETAILS_DIR", details_dir)
    monkeypatch.setattr(polet_store, "META", polet_dir / "catalog_meta.json")
    return polet_store


_TARGET = {"Fylde": 8, "Friskhet": 9, "Garvestoffer": 7}


def test_find_similar_ranks_bucket_only_wines(snapshot_med_bøtter):
    """Kjernen i B3: en vin uten details-fil skal kunne rangeres på
    katalogradens clock_buckets. Før fiksen var den usynlig."""
    from tools.vinmonopolet import find_similar_by_clocks

    hits = find_similar_by_clocks(_TARGET, ["Barbera"], top_k=10)
    koder = [h["product"]["code"] for h in hits]

    assert "20000002" in koder, "bøtte-vinen ble ikke vurdert i det hele tatt"
    assert koder[:2] == ["20000001", "20000002"], (
        "eksakt treff skal rangere først, bøtte-vin i samme stilsone rett etter"
    )
    assert "20000003" in koder and koder.index("20000003") > 1


def test_find_similar_marks_clock_source_and_precision(snapshot_med_bøtter):
    """En bøtte-verdi skal aldri se ut som et eksakt måltall."""
    from tools.vinmonopolet import find_similar_by_clocks

    hits = find_similar_by_clocks(_TARGET, ["Barbera"], top_k=10)
    per_kode = {h["product"]["code"]: h for h in hits}

    assert per_kode["20000001"]["clock_source"] == "details"
    assert per_kode["20000001"]["presisjon"] == "eksakt"
    assert per_kode["20000002"]["clock_source"] == "clock_buckets"
    assert per_kode["20000002"]["presisjon"] == "±1 (bøtte)"
    # Oversettelsen har skjedd: profilen står i detalj-navnerommet.
    assert "Garvestoffer" in per_kode["20000002"]["clocks"]
    assert "Tannin" not in per_kode["20000002"]["clocks"]


def test_find_similar_counts_every_candidate(snapshot_med_bøtter):
    """Kandidater KAN hoppes over. At de hoppes over stille, kan de ikke."""
    from tools.vinmonopolet import find_similar_by_clocks

    hits = find_similar_by_clocks(_TARGET, ["Barbera"], top_k=10)
    s = hits.stats

    assert s["kandidater"] == 5
    assert s["med_klokker"] == 3
    assert s["fra_details"] == 1
    assert s["fra_clock_buckets"] == 2
    assert s["ufullstendige_klokker"] == 1   # 20000004, mangler garvestoff-aksen
    assert s["uten_klokker"] == 1            # 20000005
    assert s["med_klokker"] + s["uten_klokker"] + s["ufullstendige_klokker"] == s["kandidater"]
    assert len(hits) == s["med_klokker"]


def test_find_similar_summary_carries_adr025_caveat(snapshot_med_bøtter):
    """ADR-025: resultatet skal ikke invitere til å leses som «noe like godt»."""
    from tools.vinmonopolet import find_similar_by_clocks

    tekst = find_similar_by_clocks(_TARGET, ["Barbera"], top_k=10).summary()

    assert "GROVFILTER" in tekst
    assert "samme retning" in tekst
    assert "ADR-025" in tekst
    assert "Dekning:" in tekst and "3 av 5" in tekst


def test_find_similar_rejects_target_missing_a_dimension(snapshot_med_bøtter):
    """Et target uten garvestoff-akse ville fått HVER kandidat hoppet over og
    gitt et tomt svar uten forklaring. Kast med én gang i stedet."""
    from tools.vinmonopolet import MissingClockDimension, find_similar_by_clocks

    with pytest.raises(MissingClockDimension):
        find_similar_by_clocks({"Fylde": 8, "Friskhet": 9}, ["Barbera"])


def test_find_similar_rejects_raw_catalog_buckets_as_target(snapshot_med_bøtter):
    """Samme felle fra andre kanten: target hentet rett fra en katalograd."""
    from tools.vinmonopolet import MissingClockDimension, find_similar_by_clocks

    rå = _KATALOG_MED_BØTTER[1]["clock_buckets"]
    with pytest.raises(MissingClockDimension):
        find_similar_by_clocks(rå, ["Barbera"])


def test_find_similar_counts_queries_that_missed(snapshot_med_bøtter):
    from tools.vinmonopolet import find_similar_by_clocks

    hits = find_similar_by_clocks(_TARGET, ["Barbera", "FinnesIkke"], top_k=10)
    assert hits.stats["sokestrenger_uten_treff"] == 1


def test_format_for_recommendation_marks_bucket_clocks(snapshot_med_bøtter):
    from tools.vinmonopolet import format_for_recommendation

    tekst = format_for_recommendation(_KATALOG_MED_BØTTER[1])
    assert "Garvestoffer 7,5/12" in tekst
    assert "±1" in tekst, "bøtte-verdi må merkes, ikke presenteres som måling"


# ═══ SKALAINVARIANTE TESTER — mot ekte data/polet/catalog.ndjson ═════
#
# Suiten var 291 grønne mens `search` filtrerte 3 av 94 og
# `find_similar_by_clocks` rangerte 13 av 701. Ingen av delene er synlig på en
# fixture med fem rader — begge funksjonene RETURNERTE et plausibelt svar.
# Testene under asserterer derfor ikke at logikken regner riktig, men at
# funksjonene har SETT hele datagrunnlaget. Ingen hardkodede tall: alt utledes
# fra katalogen ved kjøretid, så de holder når snapshotet vokser eller krymper.

@pytest.fixture
def ekte_katalog():
    """Det repo-committede snapshotet, ufiltrert. Skipper kun hvis fila mangler
    (fersk klone uten data/) — ALDRI på størrelse: en liten katalog er nettopp
    når disse assertene er billige å tilfredsstille og verdiløse."""
    from tools import polet_store

    if not polet_store.CATALOG.exists():
        pytest.skip("data/polet/catalog.ndjson mangler i denne klonen")
    rows = polet_store.read_catalog()
    if not rows:
        pytest.skip("katalogen er tom")
    return rows


def _navnetreff(rows, q):
    return [p for p in rows if q.casefold() in str(p.get("name", "")).casefold()]


def test_search_returns_same_count_as_filtering_whole_snapshot(ekte_katalog):
    """A2, kjernen: å søke-og-filtrere skal gi nøyaktig like mange som å
    filtrere hele snapshotet direkte.

    Kryss-sjekket går mot `polet_store.query`, altså en uavhengig
    implementasjon av det samme filteret — ikke mot en kopi av logikken i
    denne fila.
    """
    from tools import polet_store
    from tools.vinmonopolet import search

    for q, maks in (("Barbera", 250), ("Nebbiolo", 500), ("Ripasso", 300)):
        fasit = polet_store.query(
            name_contains=q, category="rødvin", max_price=maks
        )
        if not fasit:
            continue
        via_search = search(
            q, page_size=None, max_price=maks, category="Rødvin", fields=("name",)
        )
        assert len(via_search) == len(fasit), (
            f"'{q}' ≤{maks}: search ga {len(via_search)}, snapshotet har {len(fasit)}"
        )


def test_filter_results_after_search_sees_whole_population(ekte_katalog):
    """Den eksakte repro-linjen fra rapporten. Ga 3 av 94 før 2026-08-30."""
    from tools import polet_store
    from tools.vinmonopolet import filter_results, search

    fasit = polet_store.query(name_contains="Barbera", category="rødvin", max_price=250)
    if not fasit:
        pytest.skip("ingen Barbera under 250 i dette snapshotet")

    truffet = filter_results(
        search("Barbera", page_size=None, fields=("name",)),
        max_price=250,
        category="Rødvin",
    )
    assert len(truffet) == len(fasit)


def test_search_page_size_n_returns_n_when_n_matches_exist(ekte_katalog):
    """Ber du om N som oppfyller predikatet, får du N — hvis N finnes.
    Sier ingenting om HVILKE N; bare at avkortingen ikke spiste treff
    filteret ville beholdt."""
    from tools import polet_store
    from tools.vinmonopolet import search

    fasit = polet_store.query(name_contains="Barbera", category="rødvin", max_price=250)
    n = min(25, len(fasit))
    if n < 2:
        pytest.skip("for få Barbera under 250 til å teste avkortingen")

    treff = search("Barbera", page_size=n, max_price=250, category="Rødvin")
    assert len(treff) == n
    for p in treff:
        assert p["price"]["value"] <= 250
        assert p["main_category"]["name"] == "Rødvin"


def test_search_sees_wines_that_have_the_term_only_in_the_district(ekte_katalog):
    """38 av 74 Etna-rødviner har ikke «Etna» i navnet. Et navne-bare-søk gjør
    dem usynlige; assertionen er formulert som dekning, ikke som et tall.

    Målt mot HELE katalogen (`active_only=False`) med vilje: testen handler om
    hvilke FELTER fritekst leser, og skal ikke kunne bli grønn fordi de
    savnede radene tilfeldigvis er utgått. Statusfilteret har sin egen test
    rett under.
    """
    from tools.vinmonopolet import search

    i_distrikt = [
        p
        for p in ekte_katalog
        if "etna" in str((p.get("sub_District") or {}).get("name") or "").casefold()
        or "etna" in str((p.get("district") or {}).get("name") or "").casefold()
    ]
    if not i_distrikt:
        pytest.skip("ingen Etna-distriktsrader i dette snapshotet")

    funnet = {p["code"] for p in search("Etna", page_size=None, active_only=False)}
    mangler = [p["code"] for p in i_distrikt if p["code"] not in funnet]
    assert not mangler, f"{len(mangler)} Etna-viner er usynlige for fritekstsøket"

    kun_navn = {p["code"] for p in _navnetreff(ekte_katalog, "Etna")}
    assert len(funnet) > len(kun_navn), "bredden ga ingenting — er fields riktig?"


def test_search_and_query_agree_on_what_is_buyable(ekte_katalog):
    """
    To veier til samme spørsmål skal svare likt. `search` filtrerte ikke på
    status mens `polet_store.query` gjorde det — samme klasse feil som
    ADR-009 (kode ≠ navn), bare på en annen akse.
    """
    from tools import polet_store
    from tools.vinmonopolet import search

    via_search = {p["code"] for p in search("Etna", page_size=None)}
    hele = {p["code"] for p in search("Etna", page_size=None, active_only=False)}
    assert via_search < hele, "statusfilteret fjernet ingenting (no-op?)"

    kjopbare = {
        p["code"]
        for p in ekte_katalog
        if p["code"] in hele
        and (polet_store.is_active(p) or polet_store.is_kommer_snart(p))
    }
    assert via_search == kjopbare


def test_catalog_clock_namespace_has_not_drifted(ekte_katalog):
    """Drift-vern på selve navnerommet.

    Hvis Polet eller ingest-siden en dag skriver garvestoff-bøtta under et
    annet navn enn `Tannin`, slutter oversettelsen å treffe — og similarity
    ville mistet aksen stille for hele katalogen. Da skal DENNE testen fyre,
    ikke rangeringen degradere i det stille.
    """
    from tools.polet_facets import CLOCK_DIM_BY_CATALOG_DIM

    sett = set()
    for p in ekte_katalog:
        sett.update(p.get("clock_buckets") or {})
    if not sett:
        pytest.skip("ingen clock_buckets i dette snapshotet")

    ukjente = sett - set(CLOCK_DIM_BY_CATALOG_DIM)
    assert not ukjente, (
        f"katalogen har klokke-dimensjon(er) {sorted(ukjente)} som ikke finnes i "
        "CLOCK_DIM_BY_CATALOG_DIM — de blir IKKE oversatt til detalj-navnerommet"
    )
    assert "Tannin" in sett, (
        "ingen rad bruker 'Tannin' lenger — garvestoff-bøtta har byttet navn, og "
        "clocks_from_buckets oversetter nå ingenting"
    )


def test_find_similar_considers_the_whole_clock_population(ekte_katalog):
    """A3a: kandidatmengden skal stå i rimelig forhold til hva snapshotet
    faktisk inneholder. Rangerte 13 av 701 før 2026-08-30 — 98,3 % kastet,
    uten et ord i outputen."""
    from tools import polet_store
    from tools.vinmonopolet import find_similar_by_clocks

    queries = ["Barbera", "Nebbiolo", "Barbaresco", "Valpolicella Ripasso", "Chianti Classico"]

    # Hva FINNES: rødviner ≤500 som matcher minst én søkestreng på navn.
    relevante = [
        p
        for p in ekte_katalog
        if (p.get("main_category") or {}).get("name") == "Rødvin"
        and (p.get("price") or {}).get("value", 1e9) <= 500
        and any(q.casefold() in str(p.get("name", "")).casefold() for q in queries)
    ]
    # «Klokkedata» = details ELLER clock_buckets, slik A3(a) er formulert.
    med_klokkedata = [
        p
        for p in relevante
        if p.get("clock_buckets") or polet_store.read_details(p["code"])
    ]
    top_k = 8
    if len(med_klokkedata) < 10 * top_k:
        pytest.skip("for få klokke-bærende kandidater til å teste dekningen")

    hits = find_similar_by_clocks(
        {"Fylde": 8, "Friskhet": 9, "Garvestoffer": 7},
        queries,
        max_price=500,
        category="Rødvin",
        top_k=top_k,
    )

    assert len(hits) == top_k, "kandidatpoolen ble kastet før rangeringen"
    # Bredden på søket gjør at `kandidater` kan være STØRRE enn navnetreffene
    # (distrikt teller også med) — men aldri mindre.
    assert hits.stats["kandidater"] >= len(relevante), (
        f"vurderte {hits.stats['kandidater']} av minst {len(relevante)} relevante"
    )
    assert hits.stats["med_klokker"] >= 0.9 * len(med_klokkedata), (
        f"kun {hits.stats['med_klokker']} av {len(med_klokkedata)} klokke-bærende "
        "kandidater ble vurdert"
    )
    # Hovedleveransen i ADR-024 skal faktisk være påkoblet, ikke bare importert.
    assert hits.stats["fra_clock_buckets"] > hits.stats["fra_details"], (
        "similarity henter fortsatt nesten alt fra details/ — clock_buckets "
        "er ikke reelt i bruk"
    )


def test_find_similar_lets_bucket_wines_reach_the_top(ekte_katalog):
    """Det holder ikke å VURDERE bøtte-vinene hvis de er strukturelt utestengt
    fra toppen. Uten ±0,5-toleransen kan et midtpunkt på 7,5 aldri treffe en
    target på 8, og de 10 986 taper alltid mot de 1 668."""
    from tools.vinmonopolet import find_similar_by_clocks

    hits = find_similar_by_clocks(
        {"Fylde": 8, "Friskhet": 9, "Garvestoffer": 7},
        ["Barbera", "Nebbiolo", "Barbaresco", "Valpolicella Ripasso", "Chianti Classico"],
        max_price=500,
        category="Rødvin",
        top_k=200,
    )
    if hits.stats["fra_clock_buckets"] == 0:
        pytest.skip("ingen bøtte-viner i dette snapshotet")

    beste = hits[0]["distance"]
    i_toppsjiktet = [h for h in hits if h["distance"] == beste]
    assert any(h["clock_source"] == "clock_buckets" for h in i_toppsjiktet), (
        "ingen bøtte-vin nådde toppsjiktet — toleransen virker ikke"
    )


def test_find_similar_summary_discloses_a_tied_top_tier(ekte_katalog):
    """Bøtte-oppløsning gir mange helt like treff. Å vise 8 av 50 uten å si det
    ville vært den samme stille avkortingen i ny drakt."""
    from tools.vinmonopolet import find_similar_by_clocks

    hits = find_similar_by_clocks(
        {"Fylde": 8, "Friskhet": 9, "Garvestoffer": 7},
        ["Barbera", "Nebbiolo", "Barbaresco", "Valpolicella Ripasso", "Chianti Classico"],
        max_price=500,
        category="Rødvin",
        top_k=3,
    )
    if hits.stats["i_toppsjiktet"] <= len(hits):
        pytest.skip("ingen uavgjort i toppen i dette snapshotet")
    assert "vilkårlig utvalg" in hits.summary()
    assert str(hits.stats["i_toppsjiktet"]) in hits.summary()
