"""
Tester for `tools.polet_details` — JSON-blob-parseren for Polets produktside.

Kjører mot den samme pinned fixturen som `test_vinmonopolet_html_fixture.py`
(Fenocchio Barbera d'Alba Superiore, brukerens 4.6-vin, ADR-011). To formål:

1. **Kontrakt:** JSON-veien gir de samme feltene som regex-veien, med samme
   nøkkelnavn og verditype — pluss en del til.
2. **Ekvivalens:** `parse_product_json` og `parse_product_html` er ENIGE om alle
   delte felt. Går den testen i stykker er det et funn om Polet-drift, ikke en
   testfeil å dempe: sjekk hvilken av de to som har rett før du rører asserts.

Fixturen er fra mai 2026 (årgang 2023). Live-siden har rullet videre til 2024 —
testene her låser derfor ikke årgangen, bare at feltet finnes og ser ut som et
årstall.

Refresh av fixturen: se REFRESH_SCRIPT nederst i
`tests/test_vinmonopolet_html_fixture.py`.
"""

import json
from pathlib import Path

import pytest

from tools.polet_details import compare_parsers, parse_product_json
from tools.vinmonopolet import parse_product_html

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "vinmonopolet"
    / "fenocchio_barbera_alba_superiore.html"
)


@pytest.fixture(scope="module")
def fenocchio_html() -> str:
    assert FIXTURE_PATH.exists(), f"Fixture mangler: {FIXTURE_PATH}"
    return FIXTURE_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parsed(fenocchio_html: str) -> dict:
    result = parse_product_json(fenocchio_html)
    assert result is not None, "Fant ingen produkt-blob i fixturen — DOM-drift?"
    return result


# ─── Klokker ─────────────────────────────────────────────────────────

def test_klokker_exact_values(parsed):
    """Samme pinnede profil som regex-testen: 8/9/7."""
    assert parsed["klokker"] == {"Fylde": 8, "Friskhet": 9, "Garvestoffer": 7}


def test_klokker_are_ints_in_range(parsed):
    """Klokker er heltall 1–12 — ikke strenger, slik JSON-blobben lagrer dem."""
    for navn, verdi in parsed["klokker"].items():
        assert isinstance(verdi, int), f"{navn}={verdi!r} er ikke int"
        assert 1 <= verdi <= 12, f"{navn}={verdi} er utenfor 1–12"


def test_klokker_key_always_present_on_valid_blob():
    """`klokker` skal finnes selv når produktet ikke har karakteristikker."""
    html = _blob({"product": {"code": "1", "name": "Uten content"}})
    assert parse_product_json(html)["klokker"] == {}


# ─── Felt delt med regex-parseren ────────────────────────────────────

def test_druer_matches_readable_value(parsed):
    """Druer speiler aria-label-formen regex-parseren leser ('100 prosent'),
    ikke `formattedValue` ('100%')."""
    assert parsed["druer"] == "Barbera 100 prosent"


def test_stil(parsed):
    assert parsed["stil"] == "Frisk og fruktig"


def test_tasting_notes_non_empty(parsed):
    for felt in ("lukt", "smak", "farge", "metode"):
        assert len(parsed.get(felt, "")) > 20, f"{felt} er suspect kort"


def test_traits(parsed):
    assert parsed["alkohol"] == "13,5%"
    assert parsed["sukker"] == "Under 3 g/l"
    assert parsed["syre"] == "6,2 g/l"


def test_utvalg_known_value(parsed):
    valid = {
        "Basisutvalget", "Bestillingsutvalget", "Tilleggsutvalget",
        "Testutvalget", "Partiutvalget",
    }
    assert parsed["utvalg"] in valid


# ─── Felt regexene aldri fanget ──────────────────────────────────────

def test_produsent_and_land_composite(parsed):
    """`land` er DOM-ens 'Land, distrikt'-felt satt sammen av tre JSON-noder.
    Regex-parseren fanger det ikke i det hele tatt (nøstede <a> i cella)."""
    assert parsed["produsent"] == "Fenocchio"
    assert parsed["land"] == "Italia, Piemonte, Barbera d'Alba"
    assert parsed["distrikt"] == "Piemonte"
    assert parsed["underdistrikt"] == "Barbera d'Alba"


def test_årgang_looks_like_a_year(parsed):
    """Ikke lås årgangen — fixturen er 2023, live er 2024."""
    årgang = parsed["årgang"]
    assert årgang.isdigit() and 1900 <= int(årgang) <= 2100, f"Rar årgang: {årgang!r}"


def test_matparring(parsed):
    assert parsed["matparring"] == ["Storfe", "Småvilt", "Svin"]


def test_lagringspotensial(parsed):
    assert parsed["lagringspotensial"] == "Drikkeklar nå, men kan også lagres"


def test_identity_and_numbers(parsed):
    assert parsed["varenummer"] == "759901"
    assert parsed["navn"].startswith("Fenocchio Barbera d'Alba Superiore")
    assert parsed["kategori"] == "Rødvin"
    assert parsed["emballasje"] == "Glass"
    assert parsed["grossist"] == "Excellars AS"
    assert parsed["volum"] == 75
    assert parsed["pris"] == pytest.approx(204.9)
    assert parsed["literpris"] == pytest.approx(273.2)


def test_stil_beskrivelse_present(parsed):
    assert len(parsed["stil_beskrivelse"]) > 50


# ─── Ekvivalens mot regex-parseren ───────────────────────────────────

def test_json_is_superset_of_regex(fenocchio_html):
    """Alt regex-veien finner, finner JSON-veien også. Feiler denne, er
    JSON-veien en REGRESJON for de feltene — ikke bytt før den er grønn."""
    diff = compare_parsers(fenocchio_html)
    assert diff["kun_html"] == {}, (
        f"Regex-parseren fanger felt JSON-parseren mister: {diff['kun_html']}"
    )


def test_parsers_agree_on_every_shared_field(fenocchio_html):
    """Ekvivalenstest. Uenighet her er et FUNN: én av parserne har feil, eller
    Polet har endret DOM-en uten å endre JSON-blobben (eller omvendt)."""
    diff = compare_parsers(fenocchio_html)
    assert diff["uenige"] == {}, f"Parserne er uenige: {diff['uenige']}"


def test_shared_field_set_is_the_documented_eleven(fenocchio_html):
    """Pinner hvilke felt de to veiene faktisk deler i dag. Endres dette settet,
    skal noen ta stilling til hvorfor."""
    diff = compare_parsers(fenocchio_html)
    assert set(diff["enige"]) == {
        "klokker", "druer", "stil", "lukt", "smak", "farge", "metode",
        "utvalg", "alkohol", "sukker", "syre",
    }


def test_compare_reports_the_new_fields(fenocchio_html):
    """De nye feltene skal dukke opp som `kun_json` i diagnosen."""
    kun_json = compare_parsers(fenocchio_html)["kun_json"]
    for felt in (
        "matparring", "lagringspotensial", "literpris", "emballasje",
        "produsent", "land", "årgang", "varenummer", "pris",
    ):
        assert felt in kun_json, f"{felt} mangler i kun_json"


def test_shared_fields_have_identical_types(fenocchio_html):
    """Samme nøkkel skal ha samme TYPE i begge veier, ikke bare lik verdi."""
    fra_json = parse_product_json(fenocchio_html)
    fra_html = parse_product_html(fenocchio_html)
    for key in set(fra_json) & set(fra_html):
        assert type(fra_json[key]) is type(fra_html[key]), (
            f"{key}: {type(fra_json[key])} vs {type(fra_html[key])}"
        )


# ─── Degenerert input ────────────────────────────────────────────────

def _blob(payload: dict) -> str:
    """Minimal produktside med én JSON-blob."""
    return (
        "<html><body><script type=\"application/json\">"
        + json.dumps(payload, ensure_ascii=False)
        + "</script></body></html>"
    )


@pytest.mark.parametrize(
    "html",
    [
        pytest.param("", id="tom-streng"),
        pytest.param("<html><body>ingenting</body></html>", id="ingen-blob"),
        pytest.param(
            '<script type="application/json">{"product": ikke-json}</script>',
            id="ødelagt-json",
        ),
        pytest.param(
            '<script type="application/json">{"data":{"_id":"footer"}}</script>',
            id="blob-uten-product",
        ),
        pytest.param(
            '<script type="application/json">{}</script>'
            '<script type="application/json">{}</script>',
            id="tomme-blobber",
        ),
        pytest.param(
            '<script type="application/json">{"product": null}</script>',
            id="product-er-null",
        ),
        pytest.param(
            '<script type="application/json">["product"]</script>',
            id="blob-er-liste",
        ),
    ],
)
def test_degenerate_input_returns_none(html):
    """Ingen brukbar produkt-blob → `None`, aldri exception og aldri halv dict."""
    assert parse_product_json(html) is None


def test_none_input_returns_none():
    assert parse_product_json(None) is None


def test_waf_challenge_returns_none():
    """Cloudflare-challenge er den vanligste ikke-produktsiden vi får (ADR-019).
    Den skal gi `None` slik at kalleren faller tilbake, ikke en tom dict som
    later som parsingen gikk bra."""
    waf = (
        "<!DOCTYPE html><html><head><title>Just a moment...</title></head>"
        "<body><div id='cf-wrapper'><h1>Checking your browser before accessing "
        "vinmonopolet.no</h1></div>"
        "<script src='/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1'>"
        "</script></body></html>"
    )
    assert parse_product_json(waf) is None
    diff = compare_parsers(waf)
    assert diff["json_funnet"] is False
    assert diff["enige"] == [] and diff["uenige"] == {}


def test_product_blob_is_picked_among_several():
    """Header og footer har hver sin JSON-blob — produktblobben ligger i midten
    og skal plukkes på toppnøkkelen, ikke på posisjon."""
    html = (
        '<script type="application/json">{}</script>'
        '<script type="application/json">{"data":{"_id":"header"}}</script>'
        + _blob({"product": {"code": "12345", "name": "Testvin"}})
        + '<script type="application/json">{"data":{"_id":"footer"}}</script>'
    )
    assert parse_product_json(html)["varenummer"] == "12345"


def test_broken_blob_does_not_hide_a_later_good_one():
    """En ødelagt blob tidlig på siden skal hoppes over, ikke avbryte søket."""
    html = (
        '<script type="application/json">{oops</script>'
        + _blob({"product": {"code": "999", "name": "Bakerst"}})
    )
    assert parse_product_json(html)["varenummer"] == "999"


def test_missing_content_gives_bare_dict():
    """Produkt uten `content` → dict med de feltene som finnes, ikke None."""
    result = parse_product_json(
        _blob({"product": {"code": "1", "name": "N", "smell": "Lukt av noe"}})
    )
    assert result["klokker"] == {}
    assert result["lukt"] == "Lukt av noe"
    assert "stil" not in result and "alkohol" not in result


def test_empty_lists_and_blank_strings_are_omitted():
    """Tomme lister og tomme strenger skal ikke gi nøkler — samme kontrakt som
    regex-parseren, der en nøkkel bare finnes hvis regexen matchet."""
    result = parse_product_json(_blob({"product": {
        "code": "1",
        "smell": "",
        "taste": "   ",
        "packageType": None,
        "content": {"ingredients": [], "isGoodFor": [], "traits": [],
                    "characteristics": [], "style": {}},
    }}))
    assert set(result) == {"klokker", "varenummer"}


def test_garbage_shapes_inside_content_do_not_crash():
    """Feil TYPER inne i blobben (lister der vi venter dict osv.) skal hoppes
    over, ikke kaste."""
    result = parse_product_json(_blob({"product": {
        "code": "1",
        "content": {
            "characteristics": ["ikke en dict", {"name": "Fylde"}, {"value": "5"}],
            "ingredients": "ikke en liste",
            "style": "ikke en dict",
            "traits": [None, {"name": "Alkohol", "formattedValue": "12%"}],
            "storagePotential": [],
            "isGoodFor": [{"name": "Storfe"}, "søppel"],
        },
        "price": {"value": "ikke et tall"},
        "volume": {"value": True},
        "main_producer": "ikke en dict",
    }}))
    assert result["klokker"] == {}          # begge entries mangler navn ELLER verdi
    assert result["alkohol"] == "12%"
    assert result["matparring"] == ["Storfe"]
    assert "pris" not in result             # streng er ikke et tall
    assert "volum" not in result            # bool er ikke et tall
    assert "produsent" not in result


def test_clock_value_falls_back_to_readable_value():
    """Er `value` ubrukelig, skal `readableValue` ('Fylde, 8 av 12') redde oss —
    samme streng regex-parseren leser."""
    result = parse_product_json(_blob({"product": {"content": {"characteristics": [
        {"name": "Fylde", "value": "8.0", "readableValue": "Fylde, 8 av 12"},
        {"name": "Friskhet", "value": None, "readableValue": "Friskhet, 9 av 12"},
        {"name": "Bitterhet", "value": "søppel", "readableValue": "uleselig"},
    ]}}}))
    assert result["klokker"] == {"Fylde": 8, "Friskhet": 9}


def test_all_characteristics_are_kept_not_just_the_six_known():
    """Øl og musserende har andre klokke-dimensjoner enn stillevin. JSON-veien
    tar alle Polet oppgir — regex-veien kjenner bare seks navn."""
    result = parse_product_json(_blob({"product": {"content": {"characteristics": [
        {"name": "Bitterhet", "value": "4"},
        {"name": "Sødme", "value": "2"},
        {"name": "En helt ny dimensjon", "value": "11"},
    ]}}}))
    assert result["klokker"] == {
        "Bitterhet": 4, "Sødme": 2, "En helt ny dimensjon": 11,
    }


# ─── compare_parsers ─────────────────────────────────────────────────

def test_compare_shape_is_stable(fenocchio_html):
    diff = compare_parsers(fenocchio_html)
    assert set(diff) == {"json_funnet", "enige", "uenige", "kun_json", "kun_html"}
    assert isinstance(diff["enige"], list)
    assert diff["enige"] == sorted(diff["enige"]), "enige skal være sortert"


def test_compare_on_html_without_blob_reports_regex_only_fields():
    """Uten blob skal diagnosen vise hva regex-veien fortsatt klarer — her
    ingenting utover den tomme klokke-dicten."""
    diff = compare_parsers("<html><body>ingen blob</body></html>")
    assert diff["json_funnet"] is False
    assert diff["kun_html"] == {"klokker": {}}


# ─── Sertifisering og korktype (lagt til 2026-08-30) ─────────────────

def _sert_blob(**over):
    p = {"code": "1", "name": "X", "content": {}, "price": {"value": 1}}
    p.update(over)
    return '<script type="application/json">' + json.dumps({"product": p}) + "</script>"


def test_eco_flag_only_present_when_true():
    """Fraværet av nøkkelen betyr «ikke merket» — holder filene små."""
    assert parse_product_json(_sert_blob(eco=True))["økologisk"] is True
    assert "økologisk" not in parse_product_json(_sert_blob(eco=False))
    assert "økologisk" not in parse_product_json(_sert_blob())


def test_biodynamic_and_fairtrade_flags():
    r = parse_product_json(_sert_blob(bioDynamic=True, fairTrade=True))
    assert r["biodynamisk"] is True and r["fairtrade"] is True
    assert "biodynamisk" not in parse_product_json(_sert_blob(bioDynamic=False))


def test_cork_type_parsed_and_omitted_when_missing():
    assert parse_product_json(_sert_blob(cork="Skrukapsel"))["korktype"] == "Skrukapsel"
    assert "korktype" not in parse_product_json(_sert_blob())


def test_truthy_but_not_true_is_not_treated_as_certified():
    """Kun ekte True — en streng eller 1 skal ikke gi sertifiseringsmerke."""
    assert "økologisk" not in parse_product_json(_sert_blob(eco="nei"))
    assert "økologisk" not in parse_product_json(_sert_blob(eco=1))
