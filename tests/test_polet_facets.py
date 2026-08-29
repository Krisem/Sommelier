"""
Tester for tools/polet_facets.py — rene bygge-/parse-funksjoner for Polets
`vmpws`-søke-API (ingen nettverk).

NB: repeterte facet-tokens i vmpws er AND (verifisert live 2026-07-02), så
klokke-intervall over flere bøtter må bli FLERE queries (build_facet_queries),
ikke én query med repeterte tokens.
"""

import pytest

from tools import polet_facets


# ─── clock_range_buckets ─────────────────────────────────────────────

def test_range_buckets_single():
    assert polet_facets.clock_range_buckets(7, 8) == ["7-8"]


def test_range_buckets_spans_multiple():
    assert polet_facets.clock_range_buckets(7, 12) == ["7-8", "9-10", "11-12"]


def test_range_buckets_partial_overlap_includes_edges():
    # (6,9): 5-6 (6>=6), 7-8, 9-10 (9<=10).
    assert polet_facets.clock_range_buckets(6, 9) == ["5-6", "7-8", "9-10"]


def test_range_buckets_reversed_input():
    assert polet_facets.clock_range_buckets(12, 7) == ["7-8", "9-10", "11-12"]


# ─── build_facet_query (én bøtte per dim) ────────────────────────────

def test_build_query_category_only():
    assert polet_facets.build_facet_query(category="rødvin") == ":relevance:mainCategory:rødvin"


def test_build_query_category_and_country():
    q = polet_facets.build_facet_query(category="rødvin", country="argentina")
    assert q == ":relevance:mainCategory:rødvin:mainCountry:argentina"


def test_build_query_default_sort_is_relevance():
    assert polet_facets.build_facet_query() == ":relevance"


def test_build_query_custom_sort():
    q = polet_facets.build_facet_query(sort="price-asc", category="hvitvin")
    assert q == ":price-asc:mainCategory:hvitvin"


def test_build_query_single_bucket_per_dim():
    q = polet_facets.build_facet_query(clocks={"Fylde": "7-8"})
    assert q == ":relevance:Fylde:7-8"


def test_build_query_deterministic_dim_order():
    # Insertion-order motsatt av emit-order → output følger fast dim-rekkefølge.
    q = polet_facets.build_facet_query(
        country="argentina",
        category="rødvin",
        clocks={"Friskhet": "9-10", "Fylde": "7-8"},
    )
    assert q == (
        ":relevance:Fylde:7-8:Friskhet:9-10:mainCategory:rødvin:mainCountry:argentina"
    )


def test_build_query_unknown_clock_dim_raises():
    with pytest.raises(ValueError):
        polet_facets.build_facet_query(clocks={"Sødme": "1-2"})  # ingen gyldig fasett-kode


def test_build_query_invalid_bucket_code_raises():
    with pytest.raises(ValueError):
        polet_facets.build_facet_query(clocks={"Fylde": "7-12"})  # ikke en gyldig bøtte


# ─── build_facet_queries (intervall → liste queries) ─────────────────

def test_build_queries_no_ranges_returns_single():
    qs = polet_facets.build_facet_queries(category="rødvin", country="argentina")
    assert qs == [":relevance:mainCategory:rødvin:mainCountry:argentina"]


def test_build_queries_single_dim_range_fans_out_per_bucket():
    qs = polet_facets.build_facet_queries(
        category="rødvin", clock_ranges={"Friskhet": (7, 12)}
    )
    assert qs == [
        ":relevance:Friskhet:7-8:mainCategory:rødvin",
        ":relevance:Friskhet:9-10:mainCategory:rødvin",
        ":relevance:Friskhet:11-12:mainCategory:rødvin",
    ]


def test_build_queries_cartesian_product_two_dims():
    # Fylde (7,8) × Friskhet (7,12) = 1×3 = 3 queries, dim-rekkefølge Fylde før Friskhet.
    qs = polet_facets.build_facet_queries(
        country="italia",
        clock_ranges={"Friskhet": (7, 12), "Fylde": (7, 8)},
    )
    assert qs == [
        ":relevance:Fylde:7-8:Friskhet:7-8:mainCountry:italia",
        ":relevance:Fylde:7-8:Friskhet:9-10:mainCountry:italia",
        ":relevance:Fylde:7-8:Friskhet:11-12:mainCountry:italia",
    ]


def test_build_queries_unknown_dim_raises():
    with pytest.raises(ValueError):
        polet_facets.build_facet_queries(clock_ranges={"Sødme": (1, 2)})


# ─── FALSKE DIMENSJONER (live-målt 2026-08-29) ───────────────────────
#
# `Garvestoffer`, `Soedme` og `Bitterhet` sto i `_CLOCK_DIMS` fram til
# 2026-08-29. `Garvestoffer` er den farlige: vmpws ignorerer den STILLE, så
# queryen returnerte hele katalogen (13 775 røde i HVER bøtte) mens kalleren
# trodde den hadde filtrert. Disse testene finnes for at ingen skal legge den
# inn igjen.

def test_garvestoffer_is_not_a_valid_facet():
    with pytest.raises(ValueError) as exc:
        polet_facets.build_facet_query(category="rødvin", clocks={"Garvestoffer": "7-8"})
    msg = str(exc.value)
    # Meldingen må peke på den riktige koden OG si hvorfor fella er farlig.
    assert "Tannin(Sulfates)" in msg
    assert "13 775" in msg
    assert "ufiltrert" in msg


def test_garvestoffer_rejected_in_range_builder_too():
    with pytest.raises(ValueError) as exc:
        polet_facets.build_facet_queries(clock_ranges={"Garvestoffer": (7, 12)})
    assert "Tannin(Sulfates)" in str(exc.value)


@pytest.mark.parametrize("dim", ["Soedme", "Bitterhet"])
def test_zero_hit_dims_rejected(dim):
    # Ga 0 treff for rødvin — å filtrere alt bort er ikke et gyldig sveip.
    with pytest.raises(ValueError) as exc:
        polet_facets.build_facet_query(category="rødvin", clocks={dim: "7-8"})
    assert "0 treff" in str(exc.value)


def test_clock_dims_are_exactly_the_three_measured_ones():
    assert polet_facets._CLOCK_DIMS == ("Fylde", "Friskhet", "Tannin(Sulfates)")


def test_tannin_sulfates_builds_a_query():
    q = polet_facets.build_facet_query(category="rødvin", clocks={"Tannin(Sulfates)": "7-8"})
    assert q == ":relevance:Tannin(Sulfates):7-8:mainCategory:rødvin"


# ─── page_numbers ────────────────────────────────────────────────────

def test_page_numbers_covers_measured_roedvin_total_exactly():
    # 13 775 treff a 24 = 574 sider, 0-basert → siste side er 573 (live-målt:
    # side 573 ga de siste 23 radene, side 600 ga 0).
    pages = polet_facets.page_numbers(13775)
    assert len(pages) == 574
    assert pages[0] == 0
    assert pages[-1] == 573
    # Akkurat nok kapasitet, og ikke én side for mye.
    assert len(pages) * polet_facets.PAGE_SIZE >= 13775
    assert (len(pages) - 1) * polet_facets.PAGE_SIZE < 13775


def test_page_numbers_exact_multiple_has_no_trailing_empty_page():
    assert polet_facets.page_numbers(48) == [0, 1]
    assert polet_facets.page_numbers(49) == [0, 1, 2]


def test_page_numbers_small_and_zero():
    assert polet_facets.page_numbers(1) == [0]
    assert polet_facets.page_numbers(24) == [0]
    assert polet_facets.page_numbers(0) == []
    assert polet_facets.page_numbers(-5) == []


def test_page_size_is_the_server_cap():
    assert polet_facets.PAGE_SIZE == 24


def test_page_numbers_rejects_nonsense_page_size():
    with pytest.raises(ValueError):
        polet_facets.page_numbers(100, page_size=0)


# ─── search_url ──────────────────────────────────────────────────────

def test_search_url_default_page_zero():
    url = polet_facets.search_url(":relevance:mainCategory:rødvin")
    assert url == (
        "/vmpws/v2/vmp/products/search"
        "?q=:relevance:mainCategory:rødvin&pageSize=24&currentPage=0"
    )


def test_search_url_page_and_no_fields_full():
    url = polet_facets.search_url(":relevance:mainCategory:rødvin", page=573)
    assert url.endswith("&pageSize=24&currentPage=573")
    assert "fields=FULL" not in url  # gir 400


def test_search_url_rejects_negative_page():
    with pytest.raises(ValueError):
        polet_facets.search_url(":relevance", page=-1)


def test_search_url_roundtrips_a_built_query():
    q = polet_facets.build_facet_query(
        category="rødvin", clocks={"Fylde": "7-8", "Tannin(Sulfates)": "5-6"}
    )
    url = polet_facets.search_url(q, page=2)
    # Query sendes uencodet (browseren encoder selv) — parenteser bevares.
    assert "Tannin(Sulfates):5-6" in url
    assert url.endswith("currentPage=2")


# ─── parse_search_products ───────────────────────────────────────────

def _catalog_like_product():
    """En liten inline fixture som ligner catalog-shapen (buyable=True)."""
    return {
        "alcohol": {"formattedValue": "13,5%", "value": 13.5},
        "buyable": True,
        "code": "10267301",
        "district": {"code": "italia_veneto", "name": "Veneto"},
        "expired": False,
        "images": [{"format": "thumbnail", "imageType": "PRIMARY", "url": "x.jpg"}],
        "main_category": {"code": "hvitvin", "name": "Hvitvin"},
        "main_country": {"code": "italia", "name": "Italia"},
        "name": "Contra Soarda Breganze Vespaiolo 2023",
        "price": {"formattedValue": "Kr 299,90", "value": 299.9},
        "productAvailability": {"deliveryAvailability": {"availableForPurchase": True}},
        "product_selection": "Bestillingsutvalget",
        "releaseMode": False,
        "status": "aktiv",
        "sub_District": {"code": "italia_veneto_breganze", "name": "Breganze"},
        "sustainable": True,
        "url": "/Land/Italia/.../p/10267301",
        "volume": {"formattedValue": "75 cl", "value": 75.0},
    }


def test_parse_filters_out_not_buyable():
    prod = _catalog_like_product()
    not_buyable = dict(prod, code="999", buyable=False)
    out = polet_facets.parse_search_products({"products": [prod, not_buyable]})
    assert [p["code"] for p in out] == ["10267301"]


def test_parse_excludes_missing_buyable_key():
    prod = _catalog_like_product()
    missing = dict(prod, code="999")
    missing.pop("buyable")
    out = polet_facets.parse_search_products({"products": [prod, missing]})
    assert [p["code"] for p in out] == ["10267301"]


def test_parse_empty_and_missing_products():
    assert polet_facets.parse_search_products({}) == []
    assert polet_facets.parse_search_products({"products": []}) == []
    assert polet_facets.parse_search_products({"products": None}) == []
    assert polet_facets.parse_search_products("not a dict") == []


def test_parse_preserves_all_fields_unchanged():
    prod = _catalog_like_product()
    out = polet_facets.parse_search_products({"products": [prod]})
    assert len(out) == 1
    assert out[0] == prod
