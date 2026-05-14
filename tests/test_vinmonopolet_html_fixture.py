"""
Drift-vern for `tools.vinmonopolet.parse_product_html`.

Pinner én Polet-produktside (Fenocchio Barbera d'Alba Superiore — brukerens
4.6-rated vin) som lokal HTML-fixture. Når Polet redesigner sjekkout/
produktsider, vil regex-baserte parsere ofte feile *stille* og returnere
halve data. Testene her skal feile *synlig* så vi oppdager driften.

Når Polet faktisk endrer HTML:
1. Sjekk om endringen er regresjon (regex må fikses) eller bare ny info
2. Hvis fixed/akseptert: re-fetch fixture med scriptet i docstring nederst
3. Oppdater asserts hvis nye felt er lagt til
"""

from pathlib import Path

import pytest

from tools.vinmonopolet import parse_product_html

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "vinmonopolet"
    / "fenocchio_barbera_alba_superiore.html"
)


@pytest.fixture(scope="module")
def fenocchio_html() -> str:
    assert FIXTURE_PATH.exists(), (
        f"Fixture mangler: {FIXTURE_PATH}. Re-fetch via scriptet i denne fila."
    )
    return FIXTURE_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parsed(fenocchio_html: str) -> dict:
    return parse_product_html(fenocchio_html)


# ─── Klokker (kvantitative, stabile for denne produsent+stil) ─────────

def test_klokker_all_three_present(parsed):
    """Fylde, Friskhet, Garvestoffer skal alltid være satt for rødvin."""
    klokker = parsed.get("klokker", {})
    assert "Fylde" in klokker, "Fylde-klokke mangler — DOM-drift?"
    assert "Friskhet" in klokker, "Friskhet-klokke mangler — DOM-drift?"
    assert "Garvestoffer" in klokker, "Garvestoffer-klokke mangler — DOM-drift?"


def test_klokker_exact_values(parsed):
    """Brukerens 4.6-vin har kjent klokke-profil 8/9/7 — pinned."""
    klokker = parsed["klokker"]
    assert klokker["Fylde"] == 8
    assert klokker["Friskhet"] == 9
    assert klokker["Garvestoffer"] == 7


def test_klokker_in_valid_range(parsed):
    """Klokker er alltid 1–12. Hvis vi ser tall utenfor: regex matcher feil."""
    for navn, verdi in parsed["klokker"].items():
        assert 1 <= verdi <= 12, f"{navn}={verdi} er utenfor 1–12"


# ─── Drueblanding ─────────────────────────────────────────────────────

def test_druer_contains_barbera(parsed):
    """Fenocchio er 100% Barbera — hvis vi ikke ser drue-navnet, regex feiler."""
    druer = parsed.get("druer", "")
    assert "Barbera" in druer, f"Forventet 'Barbera' i druer, fikk: {druer!r}"
    assert "prosent" in druer or "%" in druer, (
        f"Forventet prosent-angivelse i druer, fikk: {druer!r}"
    )


# ─── Stil (kategorisk, stabil) ────────────────────────────────────────

def test_stil_matches_known_category(parsed):
    """Fenocchio Barbera er kategorisert som 'Frisk og fruktig' av Polet."""
    assert parsed.get("stil") == "Frisk og fruktig"


# ─── Tasting-notater (semi-stabilt — kun lengde-sjekk) ────────────────

def test_lukt_non_empty(parsed):
    """Lukt-feltet kan variere mellom årganger, men skal alltid være >20 tegn."""
    lukt = parsed.get("lukt", "")
    assert len(lukt) > 20, f"Lukt-feltet er suspect kort: {lukt!r}"


def test_smak_non_empty(parsed):
    smak = parsed.get("smak", "")
    assert len(smak) > 20, f"Smak-feltet er suspect kort: {smak!r}"


def test_farge_present(parsed):
    farge = parsed.get("farge", "")
    assert len(farge) > 3, f"Farge-feltet mangler: {farge!r}"


# ─── Numeriske felt ───────────────────────────────────────────────────

def test_alkohol_around_13_percent(parsed):
    """Barbera d'Alba Superiore ligger typisk 13–14,5 %. Hvis vi ser <10
    eller >18 har regex grepet feil felt."""
    alkohol = parsed.get("alkohol", "")
    assert alkohol, "Alkohol-feltet mangler"
    assert "%" in alkohol or "vol" in alkohol.lower(), (
        f"Forventet %-tegn i alkohol-streng: {alkohol!r}"
    )
    # Trekk ut tall (kan være '13,5%' eller '13.5%' osv)
    digits = "".join(c if c.isdigit() else "." for c in alkohol.replace(",", "."))
    digits = digits.replace("..", ".").strip(".")
    try:
        pct = float(digits.split("%")[0].strip("."))
    except (ValueError, IndexError):
        pytest.fail(f"Klarte ikke parse alkohol-tall fra {alkohol!r}")
    assert 10 <= pct <= 18, f"Alkohol {pct}% er utenfor sannsynlig spenn for Barbera"


def test_sukker_present(parsed):
    """Sukker kan være 'Under 3 g/l' eller et tall — bare sjekk at det er satt."""
    assert parsed.get("sukker"), "Sukker-felt mangler"


def test_syre_present(parsed):
    assert parsed.get("syre"), "Syre-felt mangler"


# ─── Metadata-felt ────────────────────────────────────────────────────

def test_utvalg_known_value(parsed):
    """Utvalg er begrenset til Polets kategorier."""
    utvalg = parsed.get("utvalg", "")
    valid = {
        "Basisutvalget", "Bestillingsutvalget", "Tilleggsutvalget",
        "Testutvalget", "Partiutvalget",
    }
    assert utvalg in valid, f"Ukjent utvalg: {utvalg!r} (mulig at Polet har endret)"


# ─── Robusthet ────────────────────────────────────────────────────────

def test_parse_empty_html_returns_empty_clocks():
    """Garbage input skal ikke krasje — returnerer dict med tom klokker-key."""
    result = parse_product_html("<html><body>nothing here</body></html>")
    assert result["klokker"] == {}
    assert "druer" not in result or not result["druer"]


def test_parse_returns_dict_with_klokker_key():
    """Selv på tomt input skal `klokker`-key alltid eksistere."""
    result = parse_product_html("")
    assert "klokker" in result


# ─── Refresh-instruks (kjøres manuelt når Polet endrer DOM) ───────────

REFRESH_SCRIPT = """
import requests
from tools.vinmonopolet import search, parse_product_html

results = search("Fenocchio Barbera Superiore", page_size=3)
target = next((p for p in results if "Fenocchio" in p["name"]
               and "Superiore" in p["name"]), results[0])
url = "https://www.vinmonopolet.no" + target["url"]
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
r.raise_for_status(); r.encoding = "utf-8"
with open("tests/fixtures/vinmonopolet/fenocchio_barbera_alba_superiore.html",
          "w", encoding="utf-8") as f:
    f.write(r.text)
print(parse_product_html(r.text))  # verifiser at parsing fortsatt fungerer
"""
