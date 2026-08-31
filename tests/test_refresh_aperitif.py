"""Tester for tools.refresh_aperitif — parsing av Aperitifs listesider og
drift-vernet i sveipen.

Fixturene er ekte rader klippet fra live-sider 2026-08-31:
- `pollisten_side1.html`  — toppen av lista (poeng 98-99) + en whiskyrad, som
  beviser at én sveip dekker både vin og whisky.
- `pollisten_side520.html` — én rad med varenummer og én uten (Horeca, med
  99999-prissentinelen). Side 520 hadde 30 scorede rader og bare 18 med
  varenummer, så dette er normaltilfellet, ikke et kantfelt.
- `pollisten_side600.html` — rader uten poeng, altså der lista slutter å være
  interessant.

Sveipen skriver til repoet, så drift-vernet er testet på oppførsel: den skal
AVBRYTE framfor å skrive halvt (lesson 2026-05-14, «HTML-scraping må ha
drift-vern»).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tools.refresh_aperitif import (
    SweepAborted,
    is_writable,
    page_url,
    parse_list_page,
    sweep,
    write_snapshot,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "aperitif"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _rows_html(html: str) -> list[str]:
    """De rå `<li>`-blokkene, så en test kan bygge sider med utvalgte rader."""
    import re

    return re.findall(r'<li class="product-list-element".*?</li>', html, re.S)


def _page(rows: list[str]) -> str:
    return (
        '<html><body><div class="product-list"><ul class="favorites-list">'
        + "".join(rows)
        + "</ul></div></body></html>"
    )


# ─── Paginering ──────────────────────────────────────────────────────

def test_page_1_is_the_bare_path():
    assert page_url(1).endswith("/pollisten")


def test_later_pages_use_the_path_form_not_the_query_form():
    """`?side=N` returnerer side 1 uansett N (verifisert live 2026-08-31)."""
    url = page_url(2)
    assert url.endswith("/pollisten/pollisten,7,2")
    assert "?" not in url


# ─── Parsing ─────────────────────────────────────────────────────────

def test_parses_every_field_from_a_top_row():
    row = parse_list_page(_fixture("pollisten_side1.html"))[0]
    assert row["polet_id"] == "18971701"
    assert row["score"] == 99
    assert row["wine_name"] == "Mugnier Musigny Grand Cru"
    assert row["vintage"] == 2018
    assert row["country"] == "Frankrike"
    assert row["area"] == "Musigny"
    assert row["category"] == "Rødvin"
    assert row["assortment"] == "Bestillingsutvalget"
    assert row["price"] == 21749.90
    assert row["volume"] == 0.75
    assert row["aperitif_url"].startswith("https://www.aperitif.no/pollisten/produkt/")


def test_vintage_comes_from_the_link_text_not_the_title():
    """Title-attributtet mangler årgangen; lenketeksten har «… (2018)»."""
    html = _fixture("pollisten_side1.html")
    assert 'title="Mugnier Musigny Grand Cru"' in html
    assert parse_list_page(html)[0]["vintage"] == 2018


def test_one_sweep_covers_whisky_too():
    """Whisky ligger i samme liste — derfor er dette én sveip, ikke to."""
    rows = parse_list_page(_fixture("pollisten_side1.html"))
    assert any((r["category"] or "").startswith("Whisky") for r in rows)


def test_row_without_varenummer_is_parsed_but_not_writable():
    rows = parse_list_page(_fixture("pollisten_side520.html"))
    without = [r for r in rows if r["polet_id"] is None]
    assert without, "fixturen skal ha en rad uten varenummer"
    assert without[0]["score"] is not None      # den ER scoret
    assert not is_writable(without[0])          # men kan ikke slås opp


def test_horeca_price_sentinel_becomes_none():
    """99999.00 er «ingen forbrukerpris», ikke en pris på 99 999 kroner."""
    rows = parse_list_page(_fixture("pollisten_side520.html"))
    horeca = [r for r in rows if r["assortment"] == "Horeca"]
    assert horeca, "fixturen skal ha en Horeca-rad"
    assert horeca[0]["price"] is None


def test_category_and_region_in_one_span_are_split():
    """Eldre rader skriver «Rødvin,  Italia - Toscana» i class-spanet."""
    rows = parse_list_page(_fixture("pollisten_side520.html"))
    row = [r for r in rows if r["polet_id"] is None][0]
    assert row["category"] == "Rødvin"
    assert row["area"] == "Italia - Toscana"


def test_unscored_rows_have_no_score():
    rows = parse_list_page(_fixture("pollisten_side600.html"))
    assert rows and all(r["score"] is None for r in rows)
    assert all(not is_writable(r) for r in rows)


# ─── Validering ──────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "patch",
    [
        {"polet_id": None},
        {"polet_id": "1234"},        # for kort
        {"polet_id": "123456789"},   # for langt
        {"score": None},
        {"score": 0},
        {"score": 101},
        {"wine_name": None},
    ],
)
def test_positive_validation_rejects_each_broken_field(patch):
    good = parse_list_page(_fixture("pollisten_side1.html"))[0]
    assert is_writable(good)
    assert not is_writable({**good, **patch})


# ─── Drift-vern i sveipen ────────────────────────────────────────────

def _pager(pages: list[str]):
    """
    Fetch-stub: side N → pages[N-1], deretter en side uten produktrader.

    Hver side får unike `data-product-id` (suffikset med sidetallet), slik at
    gjenbruk av samme fixture i testen ikke utløser «identisk side»-vernet —
    det vernet har sin egen test.
    """
    def fetch(url: str):
        n = 1 if url.endswith("/pollisten") else int(url.rsplit(",", 1)[1])
        if n > len(pages):
            return "<html></html>"
        return pages[n - 1].replace('data-product-id="', f'data-product-id="{n}')
    return fetch


def test_sweep_stops_after_consecutive_pages_without_points():
    scored = _fixture("pollisten_side1.html")
    empty = _fixture("pollisten_side600.html")
    rows, meta = sweep(
        fetch=_pager([scored, empty, empty]),
        stop_after_empty=2,
        delay=0,
        max_pages=50,
    )
    assert meta["pages_fetched"] == 3
    assert meta["last_page_with_points"] == 1
    assert len(rows) == len([r for r in parse_list_page(scored) if is_writable(r)])


def test_sweep_aborts_when_pagination_does_not_advance():
    """`?side=N`-feilen: hver side returnerer bit-identisk side 1."""
    scored = _fixture("pollisten_side1.html")
    with pytest.raises(SweepAborted, match="rykker ikke"):
        sweep(fetch=lambda url: scored, delay=0, max_pages=5)


def test_sweep_aborts_on_a_page_with_zero_product_rows():
    scored = _fixture("pollisten_side1.html")
    with pytest.raises(SweepAborted, match="0 produktrader"):
        sweep(fetch=_pager([scored]), delay=0, max_pages=5)


def _med_poeng(html: str, poeng: list[int]) -> str:
    """Sett poengene på fixture-radene, i rekkefølge."""
    ut, i = [], 0
    for bit in _rows_html(html):
        ut.append(
            re.sub(
                r'<span class="number">\s*\d+\s*</span>',
                f'<span class="number">{poeng[i % len(poeng)]}</span>',
                bit,
                count=1,
            )
        )
        i += 1
    return _page(ut)


def test_sweep_aborts_when_sorting_is_no_longer_points_desc():
    """Ekte drift: hele siden hopper opp, ikke én rad."""
    html = _fixture("pollisten_side1.html")
    lav = _med_poeng(html, [70])
    høy = _med_poeng(html, [95])
    with pytest.raises(SweepAborted, match="points_desc"):
        sweep(fetch=_pager([lav, høy]), delay=0, max_pages=5)


def test_a_single_out_of_order_row_does_not_abort_the_sweep():
    """
    Ekte tilfelle fra sveipen 2026-08-31: side 132 hadde én 89 midt i tretti
    90-ere, og side 133 var full av 90-ere igjen. Den første utgaven av vernet
    sammenlignet sidens HØYESTE mot forrige sides LAVESTE og døde på side 133
    av 560. Lista er monoton på sidenivå, ikke på radnivå.
    """
    html = _fixture("pollisten_side1.html")
    med_avvik = _med_poeng(html, [90, 89, 90])   # én lavere midt i blokka
    neste = _med_poeng(html, [90])
    tom = _fixture("pollisten_side600.html")

    rows, meta = sweep(
        fetch=_pager([med_avvik, neste, tom, tom]),
        stop_after_empty=2,
        delay=0,
        max_pages=10,
    )
    assert meta["pages_fetched"] == 4
    assert meta["last_page_with_points"] == 2


def test_sweep_aborts_when_a_page_never_answers(monkeypatch):
    import tools.refresh_aperitif as m

    monkeypatch.setattr(m.time, "sleep", lambda s: None)  # ikke vent 22 s i test
    with pytest.raises(SweepAborted, match="svarte ikke"):
        sweep(fetch=lambda url: None, delay=0, max_pages=5)


def test_transient_failure_is_retried_not_fatal(monkeypatch):
    """Ett fall er ikke drift — side 3 falt i første kjøring og svarte 200 rett
    etterpå. Sveipen skal overleve det."""
    import tools.refresh_aperitif as m

    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    scored = _fixture("pollisten_side1.html")
    empty = _fixture("pollisten_side600.html")
    pages = _pager([scored, empty, empty])
    calls = {"n": 0}

    def flaky(url):
        calls["n"] += 1
        return None if calls["n"] == 2 else pages(url)

    rows, meta = sweep(fetch=flaky, stop_after_empty=2, delay=0, max_pages=50)
    assert meta["page_retries"] == 1
    assert meta["pages_fetched"] == 3


def test_sweep_deduplicates_varenumre():
    """
    Samme varenummer på to sider skal telles, ikke skrives to ganger.

    Realistisk form: samme vin dukker opp igjen med IDENTISK poeng ved en
    sidegrense — altså uten at sorteringsvernet skal reagere.
    """
    top_row = _rows_html(_fixture("pollisten_side1.html"))[0]
    p1 = _page([top_row])
    p2 = _page([top_row])
    empty = _fixture("pollisten_side600.html")
    rows, meta = sweep(
        fetch=_pager([p1, p2, empty, empty]), stop_after_empty=2, delay=0, max_pages=50
    )
    assert [r["polet_id"] for r in rows] == ["18971701"]
    assert meta["duplicate_varenumre_skipped"] == 1


# ─── Skriving ────────────────────────────────────────────────────────

def test_snapshot_is_written_sorted_and_deterministically(tmp_path):
    rows = [r for r in parse_list_page(_fixture("pollisten_side1.html")) if is_writable(r)]
    write_snapshot(rows[::-1], {"generated_at": "x"}, directory=tmp_path)
    lines = (tmp_path / "scores.ndjson").read_text(encoding="utf-8").splitlines()
    ids = [json.loads(line)["polet_id"] for line in lines]
    assert ids == sorted(ids, key=int)
    assert json.loads(lines[0]) == json.loads(json.dumps(json.loads(lines[0])))


def test_meta_carries_the_price_bias_caveat():
    """Forbeholdet skal ligge I snapshotet, ikke bare i en planfil."""
    scored = _fixture("pollisten_side1.html")
    empty = _fixture("pollisten_side600.html")
    _, meta = sweep(fetch=_pager([scored, empty, empty]), stop_after_empty=2, delay=0)
    assert "0,80" in meta["forbehold"]["prisbias"]
    assert "godt kjøp" in meta["forbehold"]["ingen_kjopsflagg"]


# ─── Sidecache (gjenopptakelse) ──────────────────────────────────────

def test_cached_fetch_only_hits_the_network_once_per_page(tmp_path, monkeypatch):
    """
    En sveip er ~560 sider à ~12 s. Uten mellomlagring koster ett fall på side
    222 alt arbeid før den — som skjedde i første fullskala-kjøring 2026-08-31.
    """
    import tools.refresh_aperitif as m

    kall = []
    monkeypatch.setattr(m, "_default_fetch", lambda url: kall.append(url) or "<html>x</html>")
    fetch = m.cached_fetch(tmp_path)

    assert fetch(m.page_url(7)) == "<html>x</html>"
    assert fetch(m.page_url(7)) == "<html>x</html>"   # nå fra disk
    assert len(kall) == 1
    assert (tmp_path / "side-0007.html").exists()


def test_a_failed_page_is_not_cached(tmp_path, monkeypatch):
    """Ellers ville et fall blitt permanent ved neste kjøring."""
    import tools.refresh_aperitif as m

    monkeypatch.setattr(m, "_default_fetch", lambda url: None)
    assert m.cached_fetch(tmp_path)(m.page_url(9)) is None
    assert not list(tmp_path.glob("*.html"))


def test_page_timeout_is_longer_than_the_measured_page_time():
    """
    Sidene måtte 0,4–12 s 2026-08-31. `_http_get` sin default på 15 s lot en
    marginalt treg side se ut som «svarer ikke», og fire slike på rad drepte
    sveipen. Sveipen setter derfor sin egen timeout.
    """
    from tools.refresh_aperitif import PAGE_TIMEOUT

    assert PAGE_TIMEOUT >= 45
