"""
Value-score for viner på Vinmonopolet

Kombinerer tre signaler til én vurdering:
1. Aperitif.no — faglig poengskala 1-100 + "godt kjøp"-flagg
2. Vivino — crowd-rating 1-5 + antall ratings
3. Peer-percentile — hvor pris ligger relativt til lignende viner på Polet

Brukstilfelle: Brukeren vurderer å kjøpe en spesifikk vin. Returnerer
strukturert verdivurdering med kort begrunnelse.

Eksempel:
    from tools.value_score import compute_value_score
    from tools.vinmonopolet import search
    p = search("Thymiopoulos Rose Xinomavro")[0]
    v = compute_value_score(p, vintage=2024)
    print(v["summary"])
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median
from typing import Optional

from tools import polet_store
from tools.aperitif import get_aperitif_score
from tools.polet_store import PoletRefreshRequired
from tools.scores import get_user_scores
from tools.vivino import get_vivino_rating

VALUE_CACHE_DIR = Path.home() / ".cache" / "sommelier" / "value_score"
VALUE_CACHE_TTL = 24 * 60 * 60  # 24 t — Polet-priser kan endres dag-til-dag
LOGIC_VERSION = "v3"  # Bump for å invalidere all cache når scoring-logikken endres
SNAPSHOT_STALE_DAYS = 14  # Eldre snapshot → degradér value-språket (pris/lager kan ha endret seg)


def _snapshot_token() -> str:
    """
    Ferskhets-token for cache-nøkkelen. Når snapshotet refreshes endres
    `generated_at` → cache-nøkkelen endres → gamle (pre-refresh) verdicts
    serveres ikke. Faller til 'na' når meta mangler.
    """
    gen = polet_store.catalog_generated_at()
    if not gen:
        return "na"
    # Hold nøkkelen filnavn-trygg: strip kolon/plus fra ISO-stempelet.
    return re.sub(r"[^0-9A-Za-z]", "", gen)


def _value_cache_path(polet_id: str, vintage: Optional[int]) -> Path:
    VALUE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return VALUE_CACHE_DIR / f"{LOGIC_VERSION}_{_snapshot_token()}_{polet_id}_{vintage or 'NV'}.json"


def _value_cache_get(polet_id: str, vintage: Optional[int]):
    p = _value_cache_path(polet_id, vintage)
    if not p.exists() or (time.time() - p.stat().st_mtime) > VALUE_CACHE_TTL:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _value_cache_set(polet_id: str, vintage: Optional[int], value: dict) -> None:
    p = _value_cache_path(polet_id, vintage)
    try:
        p.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _apply_snapshot_age(result: dict) -> dict:
    """
    Re-regn snapshot-alder og bygg `summary` fra `_base_summary` ved HVERT retur
    (også cache-treff). Cachet alder kan ellers fryse på dag 13 (ingen advarsel)
    og serveres på dag 14+ uten advarsel — det undergraver ærlig-aldersmerking
    som er hele poenget for Android. Idempotent: bygger alltid fra _base_summary.
    """
    base = result.get("_base_summary", result.get("summary", ""))
    age = polet_store.catalog_age_days()
    generated_at = polet_store.catalog_generated_at()
    age_int = int(age) if age is not None else None

    summary = base
    if age is not None:
        dato = (generated_at or "")[:10]
        if age > SNAPSHOT_STALE_DAYS:
            summary += (
                f" Basert på snapshot fra {dato} ({age_int} dager gammelt)"
                " — pris/lager kan ha endret seg, verifiser på polet.no før kjøp."
            )
        else:
            summary += f" Basert på snapshot fra {dato} ({age_int} dager gammelt)."

    result["snapshot_age_days"] = age_int
    result["snapshot_generated_at"] = generated_at
    result["summary"] = summary
    return result


def _clean_for_vivino(name: str) -> str:
    """Strip årgang, aksenter, og preposisjoner for å gi Vivino et bedre søk."""
    s = re.sub(r"\b(19|20)\d{2}\b", "", name)
    s = re.sub(r"[éèê]", "e", s)
    s = re.sub(r"[áàâ]", "a", s)
    s = re.sub(r"[óòô]", "o", s)
    s = re.sub(r"[ø]", "o", s)
    s = re.sub(r"[æ]", "ae", s)
    s = re.sub(r"[å]", "a", s)
    s = re.sub(r"\b(de|du|della|del|di|von|aus|le|la|les)\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _quality_tier_from_score_100(score: Optional[float]) -> str:
    """Konverter 1-100-score (DN, Aperitif, etc) til tier."""
    if score is None:
        return "unknown"
    if score >= 92:
        return "very_high"
    if score >= 87:
        return "high"
    if score >= 82:
        return "medium"
    return "low"


def _quality_tier_from_aperitif(score: Optional[int], flag: Optional[str]) -> str:
    if flag == "veldig_godt_kjop":
        return "very_high"
    return _quality_tier_from_score_100(score)


def _quality_tier_from_vivino(rating: Optional[float], count: Optional[int]) -> str:
    if rating is None or count is None:
        return "unknown"
    if count < 50:
        return "unknown"  # for lite støttedata
    if rating >= 4.3:
        return "very_high"
    if rating >= 4.0:
        return "high"
    if rating >= 3.7:
        return "medium"
    return "low"


def _combine_quality(user_tier: str, aperitif_tier: str, vivino_tier: str) -> str:
    """Kuratert > Aperitif (faglig) > Vivino (crowd)."""
    if user_tier != "unknown":
        return user_tier
    if aperitif_tier != "unknown":
        return aperitif_tier
    return vivino_tier


PEER_MIN_SAMPLE = 5  # Under dette er en median ikke en median


def _peer_prices(rows: list[dict], own_code: Optional[str]) -> list[float]:
    """Priser fra `rows`, uten vinen selv og uten prisløse rader."""
    out: list[float] = []
    for r in rows:
        if r.get("code") == own_code:
            continue
        v = (r.get("price") or {}).get("value")
        if v:
            out.append(v)
    return out


def _normaliser_duplikatnavn(navn: str) -> str:
    """Navn til sammenligningsform: små bokstaver, kollapset whitespace."""
    return " ".join(str(navn or "").lower().split())


def billigere_duplikat(polet_product: dict) -> Optional[dict]:
    """Samme vin, samme aargang, samme volum — men et annet varenummer til lavere pris.

    Polet forer samme vin paa flere varenumre. Ch. Beychevelle 2019 laa
    2026-08-31 paa 17062901 til 1 199,90 OG paa 14837601 til 2 188,90: samme
    vin, samme aargang, 82 % prisforskjell. `value_score` sammenlignet mot
    peer-medianen og sa ingenting, fordi begge radene er «normale» for sin
    kategori. Dette er et OPPSLAG, ikke en modell — spoersmaalet er ikke om
    vinen er verdt prisen, men om NOEYAKTIG samme flaske står billigere i
    samme hylle.

    Tre porter, alle maalt fram 2026-08-31 over 247 rodvinsgrupper:

    - **Volum maa vaere likt.** Ellers sammenlignes 375 ml med 750 ml.
    - **Spesialutvalget holdes utenfor.** Det er Polets auksjonskanal, der
      separate partier til ulik pris er forventet og ikke en feil. 468 av 792
      duplikatrader laa der.
    - **Bare aktive varer.** En billigere rad som ikke kan kjopes er stoy.

    Aargangs-forbeholdet er AVKREFTET, ikke antatt: 293 av 313 grupper baerer
    aarstallet i selve navnet, saa identisk navn + volum er i praksis identisk
    vin OG aargang.
    """
    navn = _normaliser_duplikatnavn(polet_product.get("name"))
    pris = (polet_product.get("price") or {}).get("value")
    vol = (polet_product.get("volume") or {}).get("value")
    egen_kode = polet_product.get("code")
    if not navn or pris is None or vol is None:
        return None
    if "spesial" in str(polet_product.get("product_selection", "")).lower():
        return None

    billigst = None
    for rad in polet_store.query(active_only=True):
        if rad.get("code") == egen_kode:
            continue
        if _normaliser_duplikatnavn(rad.get("name")) != navn:
            continue
        if (rad.get("volume") or {}).get("value") != vol:
            continue
        if "spesial" in str(rad.get("product_selection", "")).lower():
            continue
        annen_pris = (rad.get("price") or {}).get("value")
        if annen_pris is None or annen_pris >= pris:
            continue
        if billigst is None or annen_pris < billigst["pris"]:
            billigst = {
                "varenummer": rad.get("code"),
                "pris": annen_pris,
                "utvalg": rad.get("product_selection"),
            }
    if billigst is None:
        return None
    billigst["du_sparer"] = round(pris - billigst["pris"], 2)
    billigst["andel"] = round(1 - billigst["pris"] / pris, 3)
    return billigst


def _peer_percentile(polet_product: dict) -> Optional[dict]:
    """
    Sammenlign pris med HELE peer-populasjonen (samme kategori + land) i snapshotet.
    Returnerer dict med median, percentile (0-1), sample_size.
    Percentile: 0.0 = billigst, 1.0 = dyrest.

    Populasjonen leses direkte fra `polet_store.query` — ikke via
    `vinmonopolet.search_with_facets`. Median og percentil er
    populasjons-statistikk: et `page_size`-tak gjør dem ikke raskere (katalogen
    leses uansett i sin helhet), bare feil. Katalogen er sortert leksikografisk
    på varenummer, så et tak ga «de N laveste varenumrene i landet» — et
    systematisk billigere utvalg, ikke et tilfeldig. Se avviket fra ADR-009.

    Peer-gruppen er som default kun **aktive** varer: verdicten er en
    kjøpsanbefaling, og en percentil mot hyller som ikke finnes er ikke en
    prissammenligning. Utgåtte rader akkumuleres dessuten i snapshotet over tid
    (ADR-024), så medianen ville drevet av seg selv uten at en eneste pris
    endret seg. Er den aktive poolen for tynn, faller vi tilbake til hele
    populasjonen — `peer_terms` sier alltid hvilket grunnlag som ble brukt.
    """
    category_obj = polet_product.get("main_category") or {}
    country_obj = polet_product.get("main_country") or {}
    category_code = category_obj.get("code")
    country_code = country_obj.get("code")
    price = (polet_product.get("price") or {}).get("value")

    # Trenger minst pris + kategori for å sammenligne meningsfullt
    if price is None or not category_code:
        return None

    # Eksplisitt `active_only=False`: peer-analysen TRENGER historikken.
    # Dekningssjekken under skiller «snapshotet mangler kategorien» fra
    # «kategorien finnes, men har for få aktive», og med bare aktive rader
    # ville de to kollapset til samme svar. Prisene filtreres på `is_active`
    # ett hakk lenger ned, der det faktisk hører hjemme.
    population = polet_store.query(
        category=category_code, country=country_code or None, active_only=False
    )

    own_code = polet_product.get("code")
    terms = [f"mainCategory:{category_code}"]
    if country_code:
        terms.append(f"mainCountry:{country_code}")

    if not any(p.get("code") != own_code for p in population):
        # Snapshotet har ingen andre viner i denne kategori+land-kombinasjonen.
        # IKKE svelg som om peer bare var None (det ga enhetsavhengig verdict
        # uten feilmelding). Signalisér eksplisitt at peer-data mangler så
        # compute_value_score kan si «refresh fra desktop for prissammenligning».
        return {"status": "refresh_required"}

    peers = _peer_prices([p for p in population if polet_store.is_active(p)], own_code)
    peer_terms = terms + ["status:aktiv"]

    if len(peers) < PEER_MIN_SAMPLE:
        # Ekte tynn aktiv-pool (snapshotet HAR kategorien). Utgåtte viner er
        # dårligere peers enn aktive, men langt bedre enn ingen peers.
        peers = _peer_prices(population, own_code)
        peer_terms = terms + ["status:alle"]

    if len(peers) < PEER_MIN_SAMPLE:
        # Polet har rett og slett få viner her — en refresh endrer ikke det.
        return None

    peers.sort()
    below = sum(1 for p in peers if p < price)

    return {
        "percentile": round(below / len(peers), 2),
        "median_price": round(median(peers), 1),
        "sample_size": len(peers),
        "peer_terms": peer_terms,
    }


def _peer_has_percentile(peer: Optional[dict]) -> bool:
    """True kun når peer er en ekte pris-sammenligning (ikke None / refresh-signal)."""
    return bool(peer) and "percentile" in peer


def _value_verdict(
    quality: str,
    aperitif_flag: Optional[str],
    peer: Optional[dict],
    price: float,
) -> str:
    """
    Kombinér kvalitet, Aperitif-flagg og pris-relativ til peers.

    Returnerer: veldig_godt_kjop | godt_kjop | akseptabelt | dyrt_for_kvaliteten | usikkert
    """
    if aperitif_flag == "veldig_godt_kjop":
        return "veldig_godt_kjop"
    if aperitif_flag == "godt_kjop":
        return "godt_kjop"

    if quality == "unknown":
        return "usikkert"

    usable_peer = _peer_has_percentile(peer)
    below_median = usable_peer and peer["percentile"] < 0.4
    above_median = usable_peer and peer["percentile"] > 0.7

    if quality == "very_high":
        return "veldig_godt_kjop" if below_median else "godt_kjop"
    if quality == "high":
        if below_median:
            return "godt_kjop"
        if above_median:
            return "akseptabelt"
        return "godt_kjop"
    if quality == "medium":
        if below_median:
            return "akseptabelt"
        if above_median:
            return "dyrt_for_kvaliteten"
        return "akseptabelt"
    # low
    return "dyrt_for_kvaliteten"


def compute_value_score(
    polet_product: dict,
    *,
    vintage: Optional[int] = None,
    fetch_vivino: bool = True,
    fetch_aperitif: bool = True,
    use_cache: bool = True,
) -> dict:
    """
    Beregn samlet verdivurdering for en vin på Polet.

    Args:
        polet_product: dict fra tools.vinmonopolet.search()
        vintage: Valgfri årgang (for Vivino-vintage-match)
        fetch_vivino / fetch_aperitif: Sett False for å hoppe over
        use_cache: Bruk disk-cache på (polet_id, vintage) — TTL 24t

    Returnerer dict med:
        - wine_name, polet_id, price
        - vivino, aperitif (dicts eller None)
        - peer (dict eller None)
        - quality_tier, value_verdict
        - summary (kort norsk sammendrag)
    """
    name = polet_product.get("name", "")
    polet_id = polet_product.get("code", "")
    price = polet_product.get("price", {}).get("value")

    # Cache er kun trygt når flagg-kombinasjonen er standard (alle kilder hentet)
    # OG snapshotet har gyldig meta — uten generated_at kan ulike snapshot-tilstander
    # ikke skilles i cache-nøkkelen, så da hopper vi over cache helt (alltid ferskt).
    use_cache_now = (
        use_cache and polet_id and fetch_vivino and fetch_aperitif
        and polet_store.catalog_generated_at() is not None
    )
    if use_cache_now:
        cached = _value_cache_get(polet_id, vintage)
        if cached is not None:
            return _apply_snapshot_age(cached)

    user_scores = get_user_scores(polet_id)
    user_score_data = max(user_scores, key=lambda e: e["score"]) if user_scores else None

    # Tre uavhengige I/O-bound kall — kjør parallelt (GIL er ikke et problem for requests)
    with ThreadPoolExecutor(max_workers=3) as ex:
        fut_vivino = (
            ex.submit(get_vivino_rating, _clean_for_vivino(name), vintage=vintage)
            if fetch_vivino else None
        )
        fut_aperitif = (
            ex.submit(get_aperitif_score, polet_id, name)
            if fetch_aperitif else None
        )
        fut_peer = ex.submit(_peer_percentile, polet_product)

        vivino_data = fut_vivino.result() if fut_vivino else None
        aperitif_data = fut_aperitif.result() if fut_aperitif else None
        peer = fut_peer.result()

    # Forkast Vivino-treff med svak navne-match — sannsynligvis feil vin
    if vivino_data and vivino_data.get("name_match_confidence") == "weak":
        vivino_data["_discarded"] = True

    user_score_val = user_score_data["score"] if user_score_data else None
    user_tier = _quality_tier_from_score_100(user_score_val)

    apr_score = aperitif_data.get("score") if aperitif_data else None
    apr_flag = aperitif_data.get("value_flag") if aperitif_data else None
    apr_tier = _quality_tier_from_aperitif(apr_score, apr_flag)

    viv_usable = vivino_data and not vivino_data.get("_discarded")
    viv_rating = vivino_data.get("vintage_rating") if viv_usable else None
    viv_count = vivino_data.get("vintage_ratings_count") if viv_usable else None
    viv_tier = _quality_tier_from_vivino(viv_rating, viv_count)

    quality = _combine_quality(user_tier, apr_tier, viv_tier)
    verdict = _value_verdict(quality, apr_flag, peer, price)

    parts = []
    if user_score_data:
        kilde = user_score_data.get("kilde", "intern").split("/")[0].strip()
        parts.append(f"{kilde} {user_score_val:g}/100")
    if aperitif_data and apr_score:
        flag_str = ""
        if apr_flag == "veldig_godt_kjop":
            flag_str = " (veldig godt kjøp)"
        elif apr_flag == "godt_kjop":
            flag_str = " (godt kjøp)"
        parts.append(f"Aperitif {apr_score}/100{flag_str}")
    if viv_usable and viv_rating:
        match_note = ""
        if vivino_data.get("name_match_confidence") == "partial":
            match_note = " *navn-match delvis"
        parts.append(
            f"Vivino {viv_rating}/5 ({viv_count} ratings){match_note}"
        )
    elif vivino_data and vivino_data.get("_discarded"):
        parts.append("Vivino-treff forkastet (feil vin)")

    peer_refresh_required = bool(peer) and peer.get("status") == "refresh_required"
    if _peer_has_percentile(peer):
        pct = int(peer["percentile"] * 100)
        parts.append(
            f"pris i {pct}. percentil av {peer['sample_size']} peers (median {peer['median_price']} kr)"
        )
    elif peer_refresh_required:
        parts.append(
            "peer-data mangler i snapshot — refresh fra desktop for prissammenligning"
        )

    # Duplikat-funnet legges FØRST i parts: det er den eneste linja her som kan
    # spare brukeren et firesifret beløp, og den gjelder uansett hva verdicten
    # ellers lander paa — en «dyrt for kvaliteten» til halv pris er fortsatt
    # samme vin til halv pris.
    _dup = billigere_duplikat(polet_product)
    if _dup:
        parts.insert(
            0,
            f"SAMME vin st\u00e5r p\u00e5 varenummer {_dup['varenummer']} til "
            f"{_dup['pris']:.2f} kr \u2014 du sparer {_dup['du_sparer']:.0f} kr "
            f"({_dup['andel'] * 100:.0f} %)",
        )

    # Base-summary uten aldersmerking. Unngå dobbelt-punktum når parts er tom.
    verdict_text_map = {
        "veldig_godt_kjop": "Veldig godt kjøp",
        "godt_kjop": "Godt kjøp",
        "akseptabelt": "Akseptabelt",
        "dyrt_for_kvaliteten": "Dyrt for kvaliteten",
        "usikkert": "Usikkert — for lite data",
    }
    base_summary = verdict_text_map[verdict] + (". " + ". ".join(parts) + "." if parts else ".")

    result = {
        "wine_name": name,
        "polet_id": polet_id,
        "price": price,
        "user_scores": user_scores,
        "vivino": vivino_data,
        "aperitif": aperitif_data,
        "peer": peer,
        "peer_status": "refresh_required" if peer_refresh_required else "ok",
        "quality_tier": quality,
        "value_verdict": verdict,
        "billigere_duplikat": _dup,
        "_base_summary": base_summary,
    }
    # Aldersmerking regnes ved hvert retur (også cache-treff) — se _apply_snapshot_age.
    # Stale snapshot er nettopp der value/kjøp koster brukeren penger; Android leser
    # dette uten mulighet til å refreshe, så ærlig degradering er obligatorisk.
    _apply_snapshot_age(result)
    if use_cache_now:
        _value_cache_set(polet_id, vintage, result)
    return result


if __name__ == "__main__":
    import json
    import sys

    from tools.vinmonopolet import search

    query = sys.argv[1] if len(sys.argv) > 1 else "Thymiopoulos Rose Xinomavro"
    vintage = int(sys.argv[2]) if len(sys.argv) > 2 else 2024

    try:
        results = search(query, page_size=5)
    except PoletRefreshRequired as e:
        print(f"Ingen treff på Polet-snapshot for '{query}'. {e.hint}")
        sys.exit(1)
    if not results:
        print(f"Ingen treff på Polet for '{query}'")
        sys.exit(1)

    p = results[0]
    v = compute_value_score(p, vintage=vintage)
    print(json.dumps(v, indent=2, ensure_ascii=False))
    print()
    print("SAMMENDRAG:")
    print(v["summary"])
