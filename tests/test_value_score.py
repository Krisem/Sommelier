"""Kontrakt-tester for verdiscoring og peer-percentile.

Disse krever live HTTP (Polet/Aperitif/Vivino) — markert `network`. Skip dem
med `pytest -m 'not network'` ved offline-kjøring.

Vi bruker en stabil, kjent vin (Tornatore Etna Rosso, varenr 15012201) som
fixture. Hvis Polet endrer fritekst-søk drastisk vil testen falle — det er
en *reell* regression vi vil oppdage, ikke noe vi skal pakke inn.
"""

from __future__ import annotations

import time

import pytest


KNOWN_QUERY = "Tornatore Etna Rosso"
KNOWN_POLET_ID = "15012201"
KNOWN_VINTAGE = 2022


@pytest.fixture(scope="module")
def polet_product():
    from tools.vinmonopolet import search

    results = search(KNOWN_QUERY)
    assert results, f"Polet returnerte 0 treff for '{KNOWN_QUERY}'"
    # Foretrekk eksakt varenr om mulig, ellers første treff.
    for r in results:
        if r.get("code") == KNOWN_POLET_ID:
            return r
    return results[0]


@pytest.mark.network
def test_peer_percentile_structure(polet_product):
    from tools.value_score import _peer_percentile

    t0 = time.time()
    peer = _peer_percentile(polet_product)
    elapsed = time.time() - t0

    assert peer is not None, (
        "_peer_percentile returnerte None — for få peers eller manglende "
        "kategori/pris. Sjekk Polet-respons."
    )
    assert elapsed < 10, f"_peer_percentile tok {elapsed:.1f}s (> 10s)"

    assert set(peer.keys()) >= {
        "percentile", "median_price", "sample_size", "peer_terms",
    }, f"Mangler keys i peer-result: {peer.keys()}"

    assert 0.0 <= peer["percentile"] <= 1.0, (
        f"percentile utenfor [0,1]: {peer['percentile']}"
    )
    assert peer["median_price"] > 0, (
        f"median_price skal være positiv: {peer['median_price']}"
    )
    assert peer["sample_size"] >= 5, (
        f"sample_size skal være ≥5: {peer['sample_size']}"
    )
    assert isinstance(peer["peer_terms"], list), (
        f"peer_terms skal være liste: {type(peer['peer_terms'])}"
    )
    assert peer["peer_terms"], "peer_terms skal ikke være tom"


@pytest.mark.network
def test_compute_value_score_end_to_end(polet_product):
    from tools.value_score import compute_value_score

    result = compute_value_score(polet_product, vintage=KNOWN_VINTAGE)

    expected_keys = {
        "wine_name",
        "polet_id",
        "price",
        "value_verdict",
        "summary",
        "quality_tier",
        "vivino",
        "aperitif",
        "peer",
        "user_scores",
    }
    missing = expected_keys - set(result.keys())
    assert not missing, f"compute_value_score mangler keys: {missing}"

    assert isinstance(result["summary"], str) and result["summary"].strip(), (
        "summary skal være ikke-tom streng"
    )
    assert result["wine_name"], "wine_name er tom"
    assert result["polet_id"], "polet_id er tom"
    assert result["price"] is not None and result["price"] > 0, (
        f"price skal være positiv: {result['price']}"
    )


@pytest.mark.network
def test_compute_value_score_is_cached(polet_product):
    """Andre kall skal være rask (cache hit, < 0.5s)."""
    from tools.value_score import compute_value_score

    # Varm cachen
    compute_value_score(polet_product, vintage=KNOWN_VINTAGE)

    t0 = time.time()
    compute_value_score(polet_product, vintage=KNOWN_VINTAGE)
    elapsed = time.time() - t0

    assert elapsed < 0.5, (
        f"Cached call tok {elapsed:.2f}s — cache treffer ikke. "
        "Sjekk _value_cache_get / LOGIC_VERSION."
    )
