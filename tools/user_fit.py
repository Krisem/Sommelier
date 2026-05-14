"""
User-fit classifier v0 — regel-basert tier-klassifisering av viner mot brukerens smaksprofil.

Parser `knowledge/smaksprofil.md` og klassifiserer en gitt vin i én av fem bøtter:
`very_fit | fit | neutral | risky | no_go`.

Output er deterministisk og fullt forklarbar via `rule_fired` + `reasons`-feltene.

Se `docs/ARCHITECTURE.md` § ADR-015 og `roadmap.md` § "v0 — Rule-based tier classifier"
for designbeslutninger.

Eksempel:
    from tools.user_fit import classify, load_profile_rules
    rules = load_profile_rules()
    result = classify({"navn": "Fratta Pasini Ripasso", "stil": "Italian Ripasso"}, rules)
    # → {"tier": "very_fit", "rule_fired": "bekreftet_snitt", ...}

CLI:
    python3 -m tools.user_fit   # re-genererer data/user_fit/v0.json
"""

import functools
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
SMAKSPROFIL_PATH = REPO_ROOT / "knowledge" / "smaksprofil.md"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "data" / "user_fit" / "v0.json"

# Terskler — eksplisitt navngitt for at en endring krever bevisst valg
_VERY_FIT_AVG_THRESHOLD = 4.0
_RISKY_AVG_THRESHOLD = 3.3  # samme som "Bekymringer"-grensen i smaksprofil


# ---------------------------------------------------------------------------
# Smaksprofil-parsing
# ---------------------------------------------------------------------------


def _find_section(text: str, heading_patterns: list[str]) -> Optional[str]:
    """
    Finn første seksjon hvis heading matcher et av mønstrene (regex, case-insensitive).

    Returnerer body inntil neste heading på samme eller høyere nivå, eller None.
    Tolerant for varianter: '## Foo', '### Foo', med/uten mellomrom.
    """
    for pat in heading_patterns:
        # Match heading-linje (## eller ###), fang nivå og posisjon
        rx = re.compile(rf"^(#{{2,4}})\s*{pat}\s*$", re.MULTILINE | re.IGNORECASE)
        m = rx.search(text)
        if not m:
            continue
        level = len(m.group(1))
        start = m.end()
        # Stopp ved neste heading av samme eller høyere nivå
        stop_rx = re.compile(rf"^#{{2,{level}}}\s+\S", re.MULTILINE)
        stop_m = stop_rx.search(text, pos=start)
        end = stop_m.start() if stop_m else len(text)
        return text[start:end]
    return None


def _bullet_items(section_text: str) -> list[str]:
    """
    Trekk ut bullet-items fra en seksjon. Renser bold-syntax og parantetiske notater.

    "- **Italian Ripasso** – n=5, snitt 4.10"  →  "Italian Ripasso"
    "- Domaine de Sulauze Pomponette Rosé (din eneste 1.0)" → "Domaine de Sulauze Pomponette Rosé"
    """
    items: list[str] = []
    for line in section_text.splitlines():
        m = re.match(r"^\s*[-*]\s+(.+)$", line)
        if not m:
            continue
        raw = m.group(1).strip()
        # Strip bold markers
        raw = raw.replace("**", "")
        # Cut at " – " or " — " (em/en dash with spaces) — alt etter dette er statistikk/notat
        raw = re.split(r"\s+[–—-]\s+", raw, maxsplit=1)[0]
        # Strip parantetiske notater
        raw = re.sub(r"\s*\([^)]*\)\s*$", "", raw).strip()
        # Strip leftover trailing punctuation
        raw = raw.rstrip(",.;:")
        if raw:
            items.append(raw)
    return items


def _parse_style_avg_table(section_text: str) -> dict[str, float]:
    """
    Parse en markdown-tabell på formen
        | Kategori | N | Snitt | Snitt 2024+ |
        |---|---|---|---|
        | Italian Ripasso | 5 | 4.10 | – |
    Returnerer {"Italian Ripasso": 4.10, ...}.
    """
    out: dict[str, float] = {}
    if not section_text:
        return out
    for line in section_text.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---") or "Snitt" in line and "Kategori" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        name = cells[0]
        # Avvis header-rad
        if name.lower() in ("kategori", "stil", "stilfamilie") or "---" in name:
            continue
        try:
            avg = float(cells[2].replace(",", "."))
        except ValueError:
            continue
        if name:
            out[name] = avg
    return out


@functools.lru_cache(maxsize=1)
def load_profile_rules(path: Optional[str] = None) -> dict:
    """
    Parse `knowledge/smaksprofil.md` og bygg strukturert regelsett.

    Tolerant for små variasjoner i seksjons-navn. Manglende seksjoner →
    tom liste/dict, ikke unntak.

    Bruk `path` (string) for å override default i tester. Path-arg er en del
    av cache-nøkkel, så testing-overrides re-parses korrekt.
    """
    smaksprofil_path = Path(path) if path else SMAKSPROFIL_PATH
    if not smaksprofil_path.exists():
        print(
            f"[user_fit] WARN: smaksprofil ikke funnet: {smaksprofil_path}",
            file=sys.stderr,
        )
        return {
            "no_go": [],
            "bekymringer": [],
            "bommet_druer_regioner": [],
            "bekreftet_stiler": [],
            "bekreftede_druer": [],
            "regioner_pluss": [],
            "blindspots": [],
            "stil_snitt": {},
        }

    text = smaksprofil_path.read_text(encoding="utf-8")

    # No-go-liste (konkrete viner)
    nogo_sec = _find_section(text, [r"No-?go-?liste.*"])
    no_go = _bullet_items(nogo_sec) if nogo_sec else []

    # Bekymringer (auto-derivert, stil-nivå)
    bek_sec = _find_section(text, [r"Bekymringer.*"])
    bekymringer = _bullet_items(bek_sec) if bek_sec else []

    # Druer/regioner som har bommet
    bommet_sec = _find_section(text, [
        r"Druer\s*/\s*regioner\s*som\s*har\s*bommet.*",
        r"Druer\s+og\s+regioner\s+som\s+har\s+bommet.*",
    ])
    bommet = _bullet_items(bommet_sec) if bommet_sec else []

    # Bekreftede mønstre — stil-navn med n≥3, snitt≥4.0
    bekreftet_sec = _find_section(text, [r"Bekreftede\s+m[øo]nstre.*"])
    bekreftet_stiler = _bullet_items(bekreftet_sec) if bekreftet_sec else []

    # Druer du vet du liker
    druer_sec = _find_section(text, [
        r"Druer\s+du\s+vet\s+du\s+liker.*",
        r"Bekreftede\s+druer.*",
    ])
    bekreftede_druer = _bullet_items(druer_sec) if druer_sec else []

    # Regioner du dras mot
    reg_sec = _find_section(text, [
        r"Regioner\s+du\s+dras\s+mot.*",
        r"Regioner\s+du\s+liker.*",
    ])
    regioner_pluss = []
    if reg_sec:
        # Disse er numererte: "1. **Nord-Italia** (Piemonte, Veneto) – ..."
        for line in reg_sec.splitlines():
            m = re.match(r"^\s*(?:\d+\.|[-*])\s+(.+)$", line)
            if not m:
                continue
            raw = m.group(1).replace("**", "")
            raw = re.split(r"\s+[–—-]\s+", raw, maxsplit=1)[0]
            raw = re.sub(r"\s*\([^)]*\)\s*$", "", raw).strip()
            raw = raw.rstrip(",.;:")
            if raw:
                regioner_pluss.append(raw)

    # Blindspots (eksplisitt-listede områder med lite data)
    blind_sec = _find_section(text, [r"Blindspots.*"])
    blindspots: list[str] = []
    if blind_sec:
        for line in blind_sec.splitlines():
            m = re.match(r"^\s*[-*]\s+(.+)$", line)
            if not m:
                continue
            raw = m.group(1).replace("**", "")
            # Kutt på " – " (forklaring) men behold "(n=1)"-suffix-strippe
            raw = re.split(r"\s+[–—]\s+", raw, maxsplit=1)[0]
            raw = re.sub(r"\s*\(n\s*[=≤]\s*\d+\)\s*$", "", raw, flags=re.IGNORECASE).strip()
            raw = raw.rstrip(",.;:")
            if raw:
                blindspots.append(raw)

    # Stil-snitt-tabell (auto-derivert "Per regional stil")
    stil_sec = _find_section(text, [
        r"Per\s+regional\s+stil.*",
        r"Stil-?snitt.*",
    ])
    stil_snitt = _parse_style_avg_table(stil_sec) if stil_sec else {}

    rules = {
        "no_go": no_go,
        "bekymringer": bekymringer,
        "bommet_druer_regioner": bommet,
        "bekreftet_stiler": bekreftet_stiler,
        "bekreftede_druer": bekreftede_druer,
        "regioner_pluss": regioner_pluss,
        "blindspots": blindspots,
        "stil_snitt": stil_snitt,
    }

    # Sanity-check — log uvanlig tilstand
    if not no_go and not bekymringer and not bekreftet_stiler:
        print(
            "[user_fit] WARN: parser hentet ingen regler — sjekk smaksprofil-struktur",
            file=sys.stderr,
        )

    return rules


# ---------------------------------------------------------------------------
# Klassifisering
# ---------------------------------------------------------------------------


def _ci_substring_match(needle: str, haystack: str) -> bool:
    """Case-insensitive substring-match. Tom needle/haystack → False."""
    if not needle or not haystack:
        return False
    return needle.lower() in haystack.lower()


def _any_match(needles: list[str], haystacks: list[str]) -> list[tuple[str, str]]:
    """Returnerer liste av (needle, haystack) for alle treff. Tom needle hoppes over."""
    hits: list[tuple[str, str]] = []
    for n in needles:
        if not n or len(n.strip()) < 3:  # for liberal substring → unngå
            continue
        for h in haystacks:
            if _ci_substring_match(n, h):
                hits.append((n, h))
                break  # ett treff per needle holder
    return hits


# Eksplisitt sub-region → makro-region mapping. Holder _any_match presis (substring),
# men lar oss matche "Piemonte" mot regioner_pluss-entry "Nord-Italia" uten
# å innføre bidireksjonell substring (som gir false positives som "USA" → "Russia").
_REGION_ALIASES: dict[str, list[str]] = {
    "Nord-Italia": ["Piemonte", "Veneto", "Lombardia", "Trentino", "Alto Adige", "Friuli"],
    "Tyskland": ["Mosel", "Rheingau", "Pfalz", "Rheinhessen", "Nahe", "Baden"],
    "Champagne": [],  # Champagne er allerede region-navn, ingen aliaser
    "Jura": [],
}

# Norsk Polet-kategori → engelsk Vivino-stil. Brukes for blindspot-matching
# fordi blindspots er på engelsk ("United States White Wine") men Polet-data
# er på norsk ("Hvitvin"). Uten denne mappingen fyrer aldri blindspot-rule på
# norsk input — fatalt for batch over Polet-DB.
_KATEGORI_NO_TO_EN: dict[str, str] = {
    "Hvitvin": "White Wine",
    "Rødvin": "Red Wine",
    "Rosévin": "Rosé Wine",
    "Rose": "Rosé Wine",
    "Musserende vin": "Sparkling",
    "Musserende": "Sparkling",
    "Sterkvin": "Fortified Wine",
    "Hetvin": "Fortified Wine",
    "Dessertvin": "Dessert Wine",
    "Perlende vin": "Sparkling",
    "Champagne": "Sparkling",
}


def _region_alias_hits(needle: str, haystacks: list[str]) -> list[tuple[str, str]]:
    """
    Sjekk om needle (makro-region som 'Nord-Italia') matcher via sub-region-aliaser.
    Returnerer (needle, hay) for første treff (alias-navn i hay).
    """
    aliases = _REGION_ALIASES.get(needle, [])
    for alias in aliases:
        for h in haystacks:
            if _ci_substring_match(alias, h):
                return [(needle, h)]
    return []


def _extract_wine_fields(wine: dict) -> dict:
    """
    Normaliser felter fra ulike kilder (Polet-API, score-DB, manuelt input).

    Returnerer dict med strenger (tom streng hvis manglende).
    """
    def first(*keys: str) -> str:
        for k in keys:
            v = wine.get(k)
            if isinstance(v, dict):
                # Polet-stil: {"name": "Rødvin"}
                v = v.get("name") or v.get("value")
            if v:
                return str(v).strip()
        return ""

    grapes_raw = wine.get("druer") or wine.get("grapes") or ""
    if isinstance(grapes_raw, list):
        grapes_str = ", ".join(str(g) for g in grapes_raw)
        grapes_list = [str(g).strip() for g in grapes_raw if g]
    else:
        grapes_str = str(grapes_raw)
        grapes_list = [g.strip() for g in re.split(r"[,/;]", grapes_str) if g.strip()]

    return {
        "navn": first("navn", "name"),
        "produsent": first("produsent", "producer"),
        "region": first("region", "district"),
        "land": first("land", "country", "main_country"),
        "kategori": first("kategori", "main_category", "category"),
        "stil": first("stil", "test", "style"),
        "druer_str": grapes_str,
        "druer_list": grapes_list,
        "varenummer": first("varenummer", "code", "polet_id"),
    }


def classify(wine: dict, rules: Optional[dict] = None) -> dict:
    """
    Klassifisér én vin mot smaksprofil-reglene.

    Args:
        wine: dict med vinfelter (alle valgfrie):
            navn/name, produsent, region, land/country, kategori/main_category,
            stil/test, druer/grapes (liste eller streng), varenummer/code.
        rules: Optional dict fra `load_profile_rules()`. Hvis None, lastes default.

    Returns:
        dict med keys: tier, reasons, confidence, rule_fired.

    Regelprioritet (early-exit):
        1. no_go    — navn-substring i no_go-liste
        2. bekymring — stil/region/drue i Bekymringer eller bommet
        3. bekreftet_snitt — stil i bekreftet_stiler OG stil_snitt ≥ 4.0
        4. bekreftet_drue — drue i bekreftede_druer ELLER stil i bekreftet_stiler ELLER region i regioner_pluss
        5. blindspot — kategori-kombinasjon i blindspots
        6. default
    """
    if rules is None:
        rules = load_profile_rules()

    f = _extract_wine_fields(wine)
    reasons: list[str] = []

    # Samle "fritekst-haystacks" der stil/region/drue kan ligge
    style_region_haystacks = [
        f["stil"], f["region"], f["produsent"], f["land"], f["druer_str"], f["navn"]
    ]
    style_region_haystacks = [h for h in style_region_haystacks if h]

    # Logg manglende felt — påvirker konfidens, ikke regel-utfall
    missing = [k for k in ("navn", "stil", "land") if not f[k]]
    if missing:
        reasons.append(f"Mangler felt: {', '.join(missing)} — best-effort match.")

    # --- Regel 1: no_go (navn-substring) -------------------------------------
    if f["navn"]:
        for nogo_wine in rules.get("no_go", []):
            if _ci_substring_match(nogo_wine, f["navn"]):
                reasons.insert(0, f"Vin-navn matcher no-go-listen: «{nogo_wine}».")
                return {
                    "tier": "no_go",
                    "reasons": reasons,
                    "confidence": "high",
                    "rule_fired": "no_go",
                }

    # --- Regel 2: bekymring/bommet (stil/region/drue) ------------------------
    bek_hits = _any_match(rules.get("bekymringer", []), style_region_haystacks)
    bommet_hits = _any_match(rules.get("bommet_druer_regioner", []), style_region_haystacks)
    if bek_hits or bommet_hits:
        for needle, hay in bek_hits:
            reasons.insert(0, f"Stil-snitt under bekymrings-terskelen: «{needle}» matcher «{hay}».")
        for needle, hay in bommet_hits:
            reasons.insert(0, f"Drue/region har bommet før: «{needle}» matcher «{hay}».")
        return {
            "tier": "risky",
            "reasons": reasons,
            "confidence": "high",
            "rule_fired": "bekymring",
        }

    # --- Regel 3: bekreftet_snitt (stil i bekreftet OG snitt ≥ 4.0) ----------
    stil_snitt = rules.get("stil_snitt", {})
    for bekr_stil in rules.get("bekreftet_stiler", []):
        for hay in style_region_haystacks:
            if _ci_substring_match(bekr_stil, hay):
                avg = stil_snitt.get(bekr_stil)
                if avg is not None and avg >= _VERY_FIT_AVG_THRESHOLD:
                    reasons.insert(
                        0,
                        f"Bekreftet stil «{bekr_stil}» med snitt {avg:.2f} (≥{_VERY_FIT_AVG_THRESHOLD}).",
                    )
                    return {
                        "tier": "very_fit",
                        "reasons": reasons,
                        "confidence": "high",
                        "rule_fired": "bekreftet_snitt",
                    }

    # --- Regel 4: fit — drue ELLER stil ELLER region ------------------------
    drue_hits = _any_match(rules.get("bekreftede_druer", []),
                            [f["druer_str"], f["navn"], f["stil"]])
    stil_hits = _any_match(rules.get("bekreftet_stiler", []), style_region_haystacks)
    region_haystacks = [f["region"], f["produsent"], f["land"], f["navn"]]
    region_hits = _any_match(rules.get("regioner_pluss", []), region_haystacks)
    # Augmenter med sub-region-aliaser: "Piemonte" → "Nord-Italia"
    for r_needle in rules.get("regioner_pluss", []):
        if any(n == r_needle for n, _ in region_hits):
            continue  # allerede dekket via substring
        alias_hits = _region_alias_hits(r_needle, region_haystacks)
        if alias_hits:
            region_hits.extend(alias_hits)
    if drue_hits or stil_hits or region_hits:
        for needle, hay in drue_hits:
            reasons.insert(0, f"Bekreftet drue «{needle}» matcher «{hay}».")
        for needle, hay in stil_hits:
            reasons.insert(0, f"Bekreftet stil «{needle}» matcher «{hay}».")
        for needle, hay in region_hits:
            reasons.insert(0, f"Foretrukket region «{needle}» matcher «{hay}».")
        return {
            "tier": "fit",
            "reasons": reasons,
            "confidence": "medium",
            "rule_fired": "bekreftet_drue",
        }

    # --- Regel 5: blindspot (kategori-kombinasjon) --------------------------
    # Blindspots er på formen "Germany Red Wine", "Asiatisk mat", "Naturvin / orange / hudkontakt"
    # Sjekk om land + kategori-kombinasjonen matcher
    blindspot_haystacks = [
        f["land"], f["kategori"], f["stil"], f["produsent"], f["navn"]
    ]
    # Normaliser norsk kategori → engelsk (blindspots er engelske; Polet er norsk).
    # Uten dette fyrer aldri blindspot-rule på norsk Polet-data.
    kategori_en = _KATEGORI_NO_TO_EN.get(f["kategori"], "")
    if kategori_en:
        blindspot_haystacks.append(kategori_en)
    # Også bygg sammensatt "Land Kategori"-streng for direkte match
    if f["land"] and f["kategori"]:
        blindspot_haystacks.append(f"{f['land']} {f['kategori']}")
        if kategori_en:
            blindspot_haystacks.append(f"{f['land']} {kategori_en}")
    blindspot_haystacks = [h for h in blindspot_haystacks if h]

    for bs in rules.get("blindspots", []):
        # Spesialhåndtér sammensatte "Land Kategori"-blindspots: krever begge ord
        bs_parts = bs.split()
        if len(bs_parts) >= 2 and any(p.lower() in ("wine", "vin", "red", "white", "rosé", "sparkling", "fortified", "dessert") for p in bs_parts):
            # Sjekk at alle ord finnes i kombinert haystack
            combined = " ".join(blindspot_haystacks).lower()
            if all(part.lower() in combined for part in bs_parts if len(part) > 2):
                reasons.insert(0, f"Kategori-kombinasjon i blindspot: «{bs}».")
                return {
                    "tier": "neutral",
                    "reasons": reasons,
                    "confidence": "low",
                    "rule_fired": "blindspot",
                }
        else:
            for hay in blindspot_haystacks:
                if _ci_substring_match(bs, hay):
                    reasons.insert(0, f"Blindspot-treff: «{bs}» i «{hay}».")
                    return {
                        "tier": "neutral",
                        "reasons": reasons,
                        "confidence": "low",
                        "rule_fired": "blindspot",
                    }

    # --- Regel 6: default ----------------------------------------------------
    reasons.insert(0, "Ingen regler traff — default nøytral.")
    return {
        "tier": "neutral",
        "reasons": reasons,
        "confidence": "medium",
        "rule_fired": "default",
    }


# ---------------------------------------------------------------------------
# Batch over score-DB
# ---------------------------------------------------------------------------


def _score_entry_to_wine(entry: dict) -> dict:
    """
    Map en score-DB-entry (fra tools.scores) til wine-dict for classify().

    Score-DB har ikke separate region/kategori-felt — bruk det vi har:
    name, produsent (inneholder ofte region + land), test (kan tipse om stil),
    notat. Kategori/stil utledes ikke automatisk her.
    """
    produsent = entry.get("produsent", "")
    # Heuristikk: siste komma-separerte ledd er land, nest siste er region
    land = ""
    region = ""
    if produsent:
        parts = [p.strip() for p in produsent.split(",") if p.strip()]
        if len(parts) >= 2:
            land = parts[-1]
        if len(parts) >= 3:
            region = parts[-2]

    return {
        "navn": entry.get("name", ""),
        "produsent": produsent,
        "region": region,
        "land": land,
        "stil": entry.get("test", ""),
        "varenummer": entry.get("varenummer", ""),
    }


def classify_score_db() -> dict:
    """
    Klassifisér alle entries i `knowledge/scores/*` via `tools.scores.index()`.

    Når en vin har flere score-entries (samme varenr i flere kilder), klassifiseres
    den én gang basert på første entry — alle entries deler navn/produsent.

    Returnerer {polet_id: classify-output}.
    """
    from tools.scores import index  # lokal import unngår sykluser ved test-stubbing

    rules = load_profile_rules()
    out: dict[str, dict] = {}
    for polet_id, entries in index().items():
        if not polet_id or not entries:
            continue
        # Bruk første entry — alle deler navn/produsent
        wine = _score_entry_to_wine(entries[0])
        if not wine["navn"]:
            print(
                f"[user_fit] WARN: hopper over varenr {polet_id} (mangler navn)",
                file=sys.stderr,
            )
            continue
        out[polet_id] = classify(wine, rules)
    return out


def write_v0_json(output_path: Optional[str] = None) -> str:
    """
    Klassifisér hele score-DB-en og skriv resultat til disk som JSON.

    Idempotent: samme input → samme output (modulo `generated_at`-timestamp).

    Returnerer absolutt path som ble skrevet.
    """
    out_path = Path(output_path) if output_path else DEFAULT_OUTPUT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)

    results = classify_score_db()

    # Tier-fordeling for meta
    tier_counts: dict[str, int] = {}
    for r in results.values():
        t = r["tier"]
        tier_counts[t] = tier_counts.get(t, 0) + 1

    payload: dict = {
        "_meta": {
            "version": "v0",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_classified": len(results),
            "tier_counts": tier_counts,
        },
    }
    # Sortér på varenr for stabil diff på tvers av kjøringer
    for polet_id in sorted(results.keys()):
        payload[polet_id] = results[polet_id]

    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return str(out_path)


if __name__ == "__main__":
    path = write_v0_json()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    meta = data["_meta"]
    print(f"Skrev: {path}")
    print(f"Klassifisert: {meta['n_classified']} viner")
    print("Tier-fordeling:")
    for tier in ("very_fit", "fit", "neutral", "risky", "no_go"):
        n = meta["tier_counts"].get(tier, 0)
        print(f"  {tier:10s} {n:4d}")
