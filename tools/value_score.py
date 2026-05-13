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

import re
from statistics import median
from typing import Optional

from tools.aperitif import get_aperitif_score
from tools.scores import get_user_scores
from tools.vinmonopolet import filter_results, search
from tools.vivino import get_vivino_rating


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


def _peer_percentile(
    polet_product: dict,
    peer_search_terms: Optional[list[str]] = None,
) -> Optional[dict]:
    """
    Sammenlign pris med andre viner i samme kategori + land.
    Returnerer dict med median, percentile (0-1), n.
    Percentile: 0.0 = billigst, 1.0 = dyrest.
    """
    category = polet_product.get("main_category", {}).get("name")
    country = polet_product.get("main_country", {}).get("name")
    district = polet_product.get("district", {}).get("name")
    price = polet_product.get("price", {}).get("value")

    if price is None or not category:
        return None

    # Bygg søketermer hvis ikke gitt. Bredere fall-back-rekke.
    if not peer_search_terms:
        peer_search_terms = []
        if district:
            peer_search_terms.append(district)
        if country:
            peer_search_terms.append(country)
        peer_search_terms.append(category)  # fall-back: kategori alene

    seen_codes = set()
    peers: list[float] = []
    for term in peer_search_terms or []:
        try:
            results = search(term, page_size=50)
        except Exception:
            continue
        # Først prøv smal filtrering, deretter løsne
        for f_country in (country, None):
            filtered = filter_results(results, category=category, country=f_country)
            for p in filtered:
                code = p.get("code")
                if code and code != polet_product.get("code") and code not in seen_codes:
                    seen_codes.add(code)
                    v = p.get("price", {}).get("value")
                    if v:
                        peers.append(v)
            if len(peers) >= 10:
                break
        if len(peers) >= 20:
            break

    if len(peers) < 5:
        return None

    peers_sorted = sorted(peers)
    below = sum(1 for p in peers_sorted if p < price)
    percentile = below / len(peers_sorted)

    return {
        "percentile": round(percentile, 2),
        "median_price": round(median(peers_sorted), 1),
        "sample_size": len(peers_sorted),
        "peer_terms": peer_search_terms,
    }


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

    below_median = peer and peer["percentile"] < 0.4
    above_median = peer and peer["percentile"] > 0.7

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
    peer_search_terms: Optional[list[str]] = None,
    fetch_vivino: bool = True,
    fetch_aperitif: bool = True,
) -> dict:
    """
    Beregn samlet verdivurdering for en vin på Polet.

    Args:
        polet_product: dict fra tools.vinmonopolet.search()
        vintage: Valgfri årgang (for Vivino-vintage-match)
        peer_search_terms: Override-søketermer for peer-gruppe
        fetch_vivino / fetch_aperitif: Sett False for å hoppe over

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

    user_scores = get_user_scores(polet_id)
    user_score_data = max(user_scores, key=lambda e: e["score"]) if user_scores else None

    vivino_data = None
    if fetch_vivino:
        vivino_data = get_vivino_rating(_clean_for_vivino(name), vintage=vintage)
        # Forkast hvis navne-match er svak — det er sannsynligvis en annen vin
        if vivino_data and vivino_data.get("name_match_confidence") == "weak":
            vivino_data["_discarded"] = True

    aperitif_data = None
    if fetch_aperitif:
        aperitif_data = get_aperitif_score(polet_id, wine_name=name)

    peer = _peer_percentile(polet_product, peer_search_terms)

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
    if peer:
        pct = int(peer["percentile"] * 100)
        parts.append(
            f"pris i {pct}. percentil av {peer['sample_size']} peers (median {peer['median_price']} kr)"
        )

    verdict_text_map = {
        "veldig_godt_kjop": "Veldig godt kjøp",
        "godt_kjop": "Godt kjøp",
        "akseptabelt": "Akseptabelt",
        "dyrt_for_kvaliteten": "Dyrt for kvaliteten",
        "usikkert": "Usikkert — for lite data",
    }
    summary = f"{verdict_text_map[verdict]}. " + ". ".join(parts) + "."

    return {
        "wine_name": name,
        "polet_id": polet_id,
        "price": price,
        "user_scores": user_scores,
        "vivino": vivino_data,
        "aperitif": aperitif_data,
        "peer": peer,
        "quality_tier": quality,
        "value_verdict": verdict,
        "summary": summary,
    }


if __name__ == "__main__":
    import json
    import sys

    from tools.vinmonopolet import search

    query = sys.argv[1] if len(sys.argv) > 1 else "Thymiopoulos Rose Xinomavro"
    vintage = int(sys.argv[2]) if len(sys.argv) > 2 else 2024

    results = search(query, page_size=5)
    if not results:
        print(f"Ingen treff på Polet for '{query}'")
        sys.exit(1)

    p = results[0]
    v = compute_value_score(p, vintage=vintage)
    print(json.dumps(v, indent=2, ensure_ascii=False))
    print()
    print("SAMMENDRAG:")
    print(v["summary"])
