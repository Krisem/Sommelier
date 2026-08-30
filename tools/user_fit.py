"""
User-fit classifier v0 — regel-basert tier-klassifisering av viner mot brukerens smaksprofil.

Parser `knowledge/smaksprofil.md` og klassifiserer en gitt vin i én av fem bøtter:
`very_fit | fit | neutral | risky | no_go`.

Output er deterministisk og fullt forklarbar via `rule_fired` + `reasons`-feltene.

Se `docs/ARCHITECTURE.md` § ADR-015 og `roadmap.md` § "v0 — Rule-based tier classifier"
for designbeslutninger.

Reglene kommer fra Vivinos engelske taksonomi; Polet-katalogen er norsk.
`_NO_MATCHERS` broer de to namespacene — uten den fyrte `risky`/`no_go` null
ganger på 13 775 rødviner (se `tasks/exploration/scenario_test_2026-08-30.md`
§ B4). `classify()` godtar både en rå katalograd og en Vivino-CSV-rad.

Eksempel:
    from tools.user_fit import classify, classify_code, load_profile_rules
    rules = load_profile_rules()
    classify({"navn": "Fratta Pasini Ripasso", "stil": "Italian Ripasso"}, rules)
    # → {"tier": "very_fit", "rule_fired": "bekreftet_snitt", ...}

    classify_code("1013801")   # slår opp varenr i Polet-snapshotet
    # → {"tier": "risky", "rule_fired": "bekymring", ...}

Oppslag per varenummer (CLAUDE.md steg 6b) skal gå via `classify_code`, ikke
via `data/user_fit/v0.json` — den fila er score-DB-en (~400 viner), ikke
katalogen (14 081). Se kommentaren over `classify_code`.

CLI:
    python3 -m tools.user_fit                  # re-genererer data/user_fit/v0.json
    python3 -m tools.user_fit 1013801 10614501 # klassifisér varenumre mot katalogen
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


def _find_sections(text: str, heading_patterns: list[str]) -> list[str]:
    """
    Som `_find_section`, men returnerer ALLE seksjoner som matcher.

    Nødvendig fordi `smaksprofil.md` har to Blindspots-seksjoner: den
    auto-deriverte («kategori-kombinasjoner med n ≤ 2») og den kuraterte
    prosaen («eksplisitt mangel på data»). `_find_section` returnerte kun den
    første, så halvparten av blindspot-reglene var stille døde.
    """
    out: list[str] = []
    for pat in heading_patterns:
        rx = re.compile(rf"^(#{{2,4}})\s*{pat}\s*$", re.MULTILINE | re.IGNORECASE)
        for m in rx.finditer(text):
            level = len(m.group(1))
            start = m.end()
            stop_rx = re.compile(rf"^#{{2,{level}}}\s+\S", re.MULTILINE)
            stop_m = stop_rx.search(text, pos=start)
            out.append(text[start : stop_m.start() if stop_m else len(text)])
    return out


# En needle lengre enn dette er brødtekst som har lekket inn i en bullet-liste,
# ikke et matche-mønster. Uten taket havnet et helt Sauvignon Blanc-avsnitt i
# `bommet_druer_regioner` (se scenario_test_2026-08-30.md § B4).
_MAX_NEEDLE_LEN = 60


def _clean_needle(raw: str) -> str:
    """Rens én bullet til et matche-mønster. Tom streng = forkast."""
    raw = raw.replace("**", "").replace("*", "").strip()
    # Cut at " – " / " — " / " - " — alt etter dette er statistikk eller notat
    raw = re.split(r"\s+[–—-]\s+", raw, maxsplit=1)[0]
    # Cut ved kolon: "Sauvignon Blanc: Bare én i hele dataene…" → "Sauvignon Blanc"
    raw = raw.split(":", 1)[0]
    # Strip parantetiske notater — også uparede, som "Tyskland (Mosel, Rheingau"
    raw = re.sub(r"\s*\(.*$", "", raw).strip()
    return raw.rstrip(",.;:").strip()


def _bullet_items(section_text: str, stop_at_subheading: bool = False) -> list[str]:
    """
    Trekk ut bullet-items fra en seksjon. Renser bold-syntax og parantetiske notater.

    "- **Italian Ripasso** – n=5, snitt 4.10"  →  "Italian Ripasso"
    "- Domaine de Sulauze Pomponette Rosé (din eneste 1.0)" → "Domaine de Sulauze Pomponette Rosé"

    `stop_at_subheading` stopper ved første `###`-heading i seksjonen. Brukes på
    prosa-seksjoner som har underseksjoner med bullets som IKKE er regler
    (f.eks. «### New World rødvin – under aktiv utforskning» under Blindspots).
    """
    items: list[str] = []
    for line in section_text.splitlines():
        if stop_at_subheading and re.match(r"^#{3,6}\s+\S", line):
            break
        m = re.match(r"^\s*[-*]\s+(.+)$", line)
        if not m:
            continue
        raw = _clean_needle(m.group(1).strip())
        if not raw:
            continue
        if len(raw) > _MAX_NEEDLE_LEN:
            print(
                f"[user_fit] WARN: forkaster for lang needle ({len(raw)} tegn), "
                f"antatt brødtekst: {raw[:70]}…",
                file=sys.stderr,
            )
            continue
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


def _parse_style_n_table(section_text: str) -> dict[str, int]:
    """
    Som `_parse_style_avg_table`, men henter N-kolonnen.

    N er hele grunnlaget for hvor mye en regel skal veie: «Burgundy Red» med
    snitt 3.27 på n=3 er en observasjon, ikke en lov. Uten N ble hver
    bekymring rapportert med `confidence: "high"`.
    """
    out: dict[str, int] = {}
    if not section_text:
        return out
    for line in section_text.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        name = cells[0]
        if name.lower() in ("kategori", "stil", "stilfamilie") or "---" in name:
            continue
        try:
            out[name] = int(cells[1])
        except ValueError:
            continue
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
            "stil_n": {},
        }

    text = smaksprofil_path.read_text(encoding="utf-8")

    # `smaksprofil.md` er delt mellom vin og øl. Øl-blokka har sine egne
    # «Bekreftede …»/«Bekymringer»/«Blindspots»-seksjoner (BJCP-stilfamilier),
    # som `tools/beer_fit.py` eier. Klipp den bort før vin-parsing — ellers
    # lekker «Kölsch / Altbier» inn som et vin-mønster.
    text = re.sub(
        r"<!--\s*BEGIN AUTO-DERIVED-BEER.*?<!--\s*END AUTO-DERIVED-BEER\s*-->",
        "",
        text,
        flags=re.DOTALL,
    )

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
            raw = _clean_needle(m.group(1))
            if raw and len(raw) <= _MAX_NEEDLE_LEN:
                regioner_pluss.append(raw)

    # Blindspots — BEGGE seksjonene: den auto-deriverte tabellen
    # («kategori-kombinasjoner med n ≤ 2») og den kuraterte prosaen
    # («eksplisitt mangel på data»). Før leste vi bare den første.
    blindspots: list[str] = []
    for blind_sec in _find_sections(text, [r"Blindspots.*"]):
        for raw in _bullet_items(blind_sec, stop_at_subheading=True):
            # "(n=1)"-suffix er allerede strippet av _clean_needle
            if raw not in blindspots:
                blindspots.append(raw)

    # Stil-snitt-tabell (auto-derivert "Per regional stil")
    stil_sec = _find_section(text, [
        r"Per\s+regional\s+stil.*",
        r"Stil-?snitt.*",
    ])
    stil_snitt = _parse_style_avg_table(stil_sec) if stil_sec else {}
    stil_n = _parse_style_n_table(stil_sec) if stil_sec else {}

    rules = {
        "no_go": no_go,
        "bekymringer": bekymringer,
        "bommet_druer_regioner": bommet,
        "bekreftet_stiler": bekreftet_stiler,
        "bekreftede_druer": bekreftede_druer,
        "regioner_pluss": regioner_pluss,
        "blindspots": blindspots,
        "stil_snitt": stil_snitt,
        "stil_n": stil_n,
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

# Norsk Polet-land → engelsk Vivino-land. Samme grunn som kategori-tabellen:
# blindspots er "Germany Red Wine", katalogen sier "Tyskland". Før denne
# tabellen fyrte blindspot-regelen kun for land som staves likt på begge språk
# (Chile, Portugal, Uruguay) — 422 av 13 775 rødviner.
_LAND_NO_TO_EN: dict[str, str] = {
    "Argentina": "Argentina",
    "Australia": "Australia",
    "Bulgaria": "Bulgaria",
    "Canada": "Canada",
    "Chile": "Chile",
    "England": "United Kingdom",
    "Frankrike": "France",
    "Georgia": "Georgia",
    "Hellas": "Greece",
    "Israel": "Israel",
    "Italia": "Italy",
    "Japan": "Japan",
    "Kina": "China",
    "Kroatia": "Croatia",
    "Kypros": "Cyprus",
    "Libanon": "Lebanon",
    "Marokko": "Morocco",
    "New Zealand": "New Zealand",
    "Portugal": "Portugal",
    "Republikken Moldova": "Moldova",
    "Romania": "Romania",
    "Serbia": "Serbia",
    "Slovakia": "Slovakia",
    "Slovenia": "Slovenia",
    "Spania": "Spain",
    "Sveits": "Switzerland",
    "Sverige": "Sweden",
    "Sør-Afrika": "South Africa",
    "Tsjekkia": "Czech Republic",
    "Tyrkia": "Turkey",
    "Tyskland": "Germany",
    "USA": "United States",
    "Ukraina": "Ukraine",
    "Ungarn": "Hungary",
    "Uruguay": "Uruguay",
    "Østerrike": "Austria",
}


# ---------------------------------------------------------------------------
# Namespace-bro: engelsk smaksprofil-regel → norsk Polet-katalog (B4)
# ---------------------------------------------------------------------------
#
# Reglene i `smaksprofil.md` kommer fra Vivinos ENGELSKE taksonomi
# (`Regional wine style` = "Burgundy Red"). Polet-katalogen er norsk og har
# verken stil- eller druefelt — bare land / distrikt / underdistrikt / navn.
# Substring-matching mellom de to namespacene traff aldri, så hele
# advarselsapparatet (`risky`/`no_go`) var dødt på katalogdata: 0 av 13 775
# rødviner. Se ADR-016 og `tasks/exploration/scenario_test_2026-08-30.md` § B4.
#
# Hver needle oversettes til én eller flere ALTERNATIVER. Et alternativ treffer
# når ALLE begrensningene i det holder:
#   land        – `main_country.name`, eksakt (case-insensitivt)
#   distrikt    – `district.name` er én av disse, eksakt
#   under       – substring i `sub_District.name`
#   ikke_under  – substring som DISKVALIFISERER treffet
#   tekst       – substring i navn + distrikt + underdistrikt
#   kategori    – `main_category.name`, eksakt
#   maks_pris   – pris ≤ N kr
#
# Nøkkelen er needle-strengen slik den står i `smaksprofil.md`. Endrer
# `profile_stats.py` et navn, dør oversettelsen — derfor krever
# `tests/test_user_fit.py` at hver needle enten har matcher, treffer katalogen
# på engelsk substring, eller står i `_UNTRANSLATED` med begrunnelse.

# Beaujolais ligger under Polets distrikt «Burgund», men er Gamay og en egen
# stil hos Vivino. Uten denne eksklusjonen ville en Bourgogne-regel dratt med
# seg ~190 Beaujolais-rader.
_BEAUJOLAIS = [
    "Beaujolais", "Fleurie", "Morgon", "Moulin-à-Vent", "Brouilly",
    "Chiroubles", "Chénas", "Juliénas", "Régnié", "Saint-Amour",
]

# Sør-Rhône-appellasjoner. Ført eksplisitt heller enn som «Rhône minus nord»:
# 3 rader har `sub_District: None`, og de skal ikke antas sørlige.
#
# `_SOR_RHONE_BASIS` er instegsnivået — det eneste nivået brukerens historikk
# faktisk dekker med lav rating. Substringen «Côtes du Rhône» fanger også
# «Côtes du Rhône-Villages …». Resten av `_SOR_RHONE` er cru-nivå og går til
# blindsone via `_NIVA_INNSNEVRET`, ikke til `risky`.
_SOR_RHONE_BASIS = ["Côtes du Rhône"]

# Regionalt Bourgogne — nivået alle tre Burgundy Red-ratingene ligger på.
_BOURGOGNE_REGIONALT = ["Bourgogne", "Coteaux Bourguignons"]

_SOR_RHONE = [
    "Côtes du Rhône", "Châteauneuf-du-Pape", "Gigondas", "Vacqueyras",
    "Lirac", "Tavel", "Rasteau", "Cairanne", "Vinsobres", "Ventoux",
    "Luberon", "Costières de Nîmes", "Vaucluse", "Grignan-les-Adhémar",
    "Côtes du Vivarais", "Beaumes-de-Venise", "Duché d'Uzès",
]

# Nord-Italia slik profilen bruker begrepet: «Nord-Italia (Piemonte, Veneto)
# – tyngdepunktet ditt». Emilia-Romagna er bevisst utelatt (nord-*sentral*,
# og ikke representert i historikken).
_NORD_ITALIA = [
    "Piemonte", "Veneto", "Lombardia", "Trentino-Alto Adige",
    "Friuli-Venezia Giuli", "Friuli-Venezia Giulia", "Valle d'Aosta", "Liguria",
]

# Provence-rosé bor ikke bare i Polets distrikt «Provence». Den samme vinen —
# `10876701`/`12591006`/`16908505` Studio by Miraval Rosé 2025 — ligger på tre
# varenumre, to av dem under IGP «Méditerranée». Et matcher-treff kun på
# «Provence» fanget ett av tre. IGP-ene under er de generiske sekkene
# Provence-produsentene tapper rosé på, og «Generisk Provence-rosé» er
# nøyaktig det profilen kaller dem.
# Bandol, Palette og Bellet er Provences seriøse appellasjoner — ikke det
# profilen kaller «generisk». Ingen av dem finnes i historikken.
_PROVENCE_SERIOS = ["Bandol", "Palette", "Bellet"]

_PROVENCE_ROSE_DISTRIKT = [
    "Provence", "Méditerranée", "Var", "Bouches-du-Rhône", "Vaucluse",
    "Alpilles", "Maures", "Alpes-Maritimes",
]

_NO_MATCHERS: dict[str, list[dict]] = {
    # --- Bekymringer (auto-derivert fra Vivinos stilnavn) -------------------
    # «Burgundy Red», n=3, snitt 3.27. Alle tre ratede ligger på REGIONALT
    # Bourgogne-nivå (Bourgogne, Bourgogne Hautes-Côtes de Nuits) — ingen
    # Côte d'Or-landsby eller cru. Regelen bindes derfor til det nivået
    # historikken faktisk dekker. Côte d'Or er ikke «bekymring», det er
    # fravær av data, og fanges av blindspot-regelen «Pinot Noir generelt».
    "Burgundy Red": [
        {"land": "Frankrike", "distrikt": ["Burgund"], "kategori": "Rødvin",
         "under": _BOURGOGNE_REGIONALT, "ikke_under": _BEAUJOLAIS},
    ],
    # «Southern Rhône Red», n=3, snitt 3.00. Ratingene er
    #   4.0 Ch. de Ségriés Lirac · 3.0 Chapoutier Belleruche Côtes-du-Rhône ·
    #   2.0 Dom. de la Janasse Côtes du Rhône.
    # To av tre er basis Côtes-du-Rhône, og den ene som ligger et hakk OVER
    # instegsnivået fikk høyest rating. Bekymringen bindes derfor til
    # instegsnivået — samme avveining som for «Burgundy Red», og av samme
    # grunn: å generalisere fra to basisviner til Châteauneuf-du-Pape er en
    # påstand dataene ikke bærer, og de peker om noe svakt motsatt vei.
    # Cru-nivået (CdP, Gigondas, Vacqueyras, Lirac …) er ikke dermed trygt —
    # det er udokumentert, og merkes som blindsone via `_NIVA_INNSNEVRET`.
    "Southern Rhône Red": [
        {"land": "Frankrike", "distrikt": ["Rhône"], "kategori": "Rødvin",
         "under": _SOR_RHONE_BASIS},
    ],
    "Provence Rosé": [
        {"land": "Frankrike", "distrikt": _PROVENCE_ROSE_DISTRIKT,
         "kategori": "Rosévin", "ikke_under": _PROVENCE_SERIOS},
        {"land": "Frankrike", "kategori": "Rosévin", "tekst": ["Provence"],
         "ikke_under": _PROVENCE_SERIOS},
    ],

    # --- Bekreftede stiler --------------------------------------------------
    "Italian Ripasso": [{"land": "Italia", "tekst": ["Ripasso"]}],
    "Italian Amarone": [{"land": "Italia", "tekst": ["Amarone"]}],
    # Vivinos «Southern Italy Red» dekker Sicilia i denne brukerens data:
    # Etna, Cerasuolo di Vittoria og Terre Siciliane er alle ført der, i
    # tillegg til Castel del Monte (Puglia). Abruzzo og Sardegna er utelatt —
    # Vivino fører dem som egne stiler og de finnes ikke i historikken.
    # Fire ratede, TRE av dem fra Sicilia (Etna 4.1 · Etna 4.1 · Cerasuolo di
    # Vittoria 4.0 · Terre Siciliane 4.0), pluss én uratet Castel del Monte
    # (Puglia). `very_fit` bindes til Sicilia. Resten av Syd-Italia er ikke
    # dermed nedvurdert — den får `fit` via `_NIVA_INNSNEVRET`, med n og
    # fordelingen synlig i begrunnelsen. En falsk `very_fit` er like mye en
    # filterboble som en manglende `risky` (ADR-016): den sender brukeren mot
    # Taurasi og Aglianico på grunnlag av Etna.
    "Southern Italy Red": [
        {"land": "Italia", "kategori": "Rødvin", "distrikt": ["Sicilia"]},
    ],
    "English Sparkling": [{"land": "England", "kategori": "Musserende vin"}],

    # --- Druer/regioner som har bommet (kuratert prosa) ---------------------
    "Generisk Provence-rosé": [
        {"land": "Frankrike", "distrikt": _PROVENCE_ROSE_DISTRIKT,
         "kategori": "Rosévin", "ikke_under": _PROVENCE_SERIOS},
    ],
    # «Sør-Rhône hvit (to lave på Lirac Blanc)». De «to» er samme vin i to
    # årganger — Ch. de Ségriés Lirac Blanc 3.2 og 3.0 — og Lirac ligger OVER
    # basisnivå. Å generalisere derfra nedover til Côtes-du-Rhône blanc og
    # sidelengs til Châteauneuf-du-Pape blanc (Roussanne/Grenache blanc,
    # ofte fatlagret, 400–900 kr) er samme feilklasse som Sør-Rhône rød,
    # i motsatt retning. Bindes til Lirac.
    "Sør-Rhône hvit": [
        {"land": "Frankrike", "distrikt": ["Rhône"], "kategori": "Hvitvin",
         "under": ["Lirac"]},
    ],
    # «Billig Burgund (Labouré-Roi 1.5)» — prisbetinget i profilen selv.
    # Terskelen er hverdagssonen i CLAUDE.md § Pris-soner.
    "Billig Burgund": [
        {"land": "Frankrike", "distrikt": ["Burgund"], "kategori": "Rødvin",
         "maks_pris": 300.0, "ikke_under": _BEAUJOLAIS},
    ],
    "Argentinsk Bonarda": [{"land": "Argentina", "tekst": ["Bonarda"]}],
    "Sauvignon Blanc": [{"tekst": ["Sauvignon Blanc"]}],

    # --- Druer du vet du liker ---------------------------------------------
    # Katalogen har INGEN druefelt. Druene matches derfor mot navn og
    # appellasjon: en Barbera d'Alba sier ikke «Barbera» i drueform noe sted
    # utenom underdistriktet.
    "Barbera": [{"tekst": ["Barbera", "Nizza"]}],
    "Nebbiolo": [{"tekst": [
        "Nebbiolo", "Barolo", "Barbaresco", "Roero", "Gattinara", "Ghemme",
        "Carema", "Boca", "Bramaterra", "Lessona", "Fara", "Sizzano",
        "Valtellina", "Sforzato", "Sfursat",
    ]}],
    "Corvina/Rondinella-blend": [
        {"land": "Italia", "tekst": [
            "Valpolicella", "Amarone", "Ripasso", "Bardolino", "Valpantena",
        ]},
    ],
    "Riesling": [{"tekst": ["Riesling"]}],
    "Chardonnay": [{"tekst": ["Chardonnay", "Chablis", "Blanc de Blancs"]}],
    "Sangiovese": [{"tekst": [
        "Sangiovese", "Chianti", "Brunello di Montalcino", "Rosso di Montalcino",
        "Vino Nobile di Montepulciano", "Rosso di Montepulciano",
        "Morellino di Scansano", "Montecucco", "Carmignano",
    ]}],
    "Tannat": [{"tekst": ["Tannat", "Madiran"]}],

    # --- Regioner du dras mot ----------------------------------------------
    "Nord-Italia": [{"land": "Italia", "distrikt": _NORD_ITALIA}],
    "Tyskland": [{"land": "Tyskland"}],
    "Champagne": [{"land": "Frankrike", "distrikt": ["Champagne"]}],
    "Jura": [{"land": "Frankrike", "distrikt": ["Jura"]}],

    # --- Blindspots i kuratert prosa ---------------------------------------
    "Aromatisk hvitvin": [{"tekst": [
        "Viognier", "Gewürztraminer", "Gewurztraminer", "Torrontés",
        "Torrontes", "Muskat", "Moscato", "Muscat",
    ]}],
    "Spanske rødviner": [{"land": "Spania", "kategori": "Rødvin"}],
    # Côte d'Or-Bourgogne havner her: profilen har null data på cru-nivå, og
    # «Pinot Noir generelt – stor varians (1.5 til 4.5)» er nøyaktig den
    # usikkerheten. Regionalt Bourgogne fanges tidligere av `bekymring`.
    "Pinot Noir generelt": [
        {"tekst": ["Pinot Noir", "Pinot Nero", "Spätburgunder", "Blauburgunder"]},
        {"land": "Frankrike", "distrikt": ["Burgund"], "kategori": "Rødvin",
         "ikke_under": _BEAUJOLAIS},
    ],
}

# Bekymringer som er BEVISST innsnevret til det appellasjonsnivået brukerens
# historikk faktisk dekker. Resten av regionen er ikke dermed trygg — den er
# UDOKUMENTERT, og skal bære et merke om det. `blindspot` med lav konfidens er
# den ærlige dommen: ADR-016 sier tier skal advare, ikke skjule, og en
# blindsone advarer om noe annet enn en bekymring gjør — «jeg vet ikke» i
# stedet for «dette har bommet før».
#
# Uten denne tabellen ville innsnevringen sett ut som en stille frikjennelse.
# Côte d'Or havnet riktig i dag, men bare fordi «Pinot Noir generelt»
# tilfeldigvis dekket den — et sammentreff, ikke en mekanisme.
_NIVA_INNSNEVRET: dict[str, dict] = {
    # `kilde`   – hvilken regelliste needelen står i (må stemme, ellers er
    #             innsnevringen foreldet — se testen)
    # `smal`    – appellasjonene evidensen FAKTISK dekker (kryss-språklig port)
    # `bredere` – resten av regionen, som predikat over Polet-rader
    # `utenfor` – hva den bredere regionen skal få: «blindspot» (vet ikke) på
    #             minussiden, «fit» (positiv, ett hakk ned) på plussiden
    "Burgundy Red": {
        "kilde": "bekymringer",
        "smal": _BOURGOGNE_REGIONALT,
        "bredere": [
            {"land": "Frankrike", "distrikt": ["Burgund"], "kategori": "Rødvin",
             "ikke_under": _BEAUJOLAIS},
        ],
        "utenfor": "blindspot",
        "nivå": "regionalt Bourgogne",
        "evidens": "4.5 og 3.8 Vincent Girardin Bourgogne, 1.5 Labouré-Roi Bourgogne",
    },
    "Southern Rhône Red": {
        "kilde": "bekymringer",
        "smal": _SOR_RHONE_BASIS,
        "bredere": [
            {"land": "Frankrike", "distrikt": ["Rhône"], "kategori": "Rødvin",
             "under": _SOR_RHONE},
        ],
        "utenfor": "blindspot",
        "nivå": "Côtes-du-Rhône og Côtes-du-Rhône-Villages",
        "evidens": "4.0 Ségriés Lirac, 3.0 Chapoutier Belleruche CdR, 2.0 Janasse CdR",
    },
    "Sør-Rhône hvit": {
        "kilde": "bommet_druer_regioner",
        "smal": ["Lirac"],
        "bredere": [
            {"land": "Frankrike", "distrikt": ["Rhône"], "kategori": "Hvitvin",
             "under": _SOR_RHONE},
        ],
        "utenfor": "blindspot",
        "nivå": "Lirac",
        "evidens": "3.2 og 3.0 Ch. de Ségriés Lirac Blanc — samme vin, to årganger",
    },
    "Provence Rosé": {
        "kilde": "bekymringer",
        "smal": ["Côtes de Provence", "Coteaux d'Aix", "Coteaux Varois",
                 "Méditerranée", "Var", "Vaucluse", "Bouches-du-Rhône"],
        "bredere": [
            {"land": "Frankrike", "kategori": "Rosévin",
             "distrikt": _PROVENCE_ROSE_DISTRIKT + _PROVENCE_SERIOS},
        ],
        "utenfor": "blindspot",
        "nivå": "det generiske sjiktet (Côtes de Provence, Coteaux d'Aix)",
        "evidens": "4.0 og 2.0 Miraval Côtes de Provence (samme vin), "
                   "2.5 Whispering Angel, 1.0 Sulauze Coteaux d'Aix",
    },
    "Generisk Provence-rosé": {
        "kilde": "bommet_druer_regioner",
        "smal": ["Côtes de Provence", "Coteaux d'Aix", "Coteaux Varois",
                 "Méditerranée", "Var", "Vaucluse", "Bouches-du-Rhône"],
        "bredere": [
            {"land": "Frankrike", "kategori": "Rosévin",
             "distrikt": _PROVENCE_ROSE_DISTRIKT + _PROVENCE_SERIOS},
        ],
        "utenfor": "blindspot",
        "nivå": "det generiske sjiktet (Côtes de Provence, Coteaux d'Aix)",
        "evidens": "4.0 og 2.0 Miraval Côtes de Provence (samme vin), "
                   "2.5 Whispering Angel, 1.0 Sulauze Coteaux d'Aix",
    },
    "Southern Italy Red": {
        "kilde": "bekreftet_stiler",
        "smal": ["Sicilia", "Sicily", "Etna", "Cerasuolo di Vittoria",
                 "Terre Siciliane", "Nero d'Avola", "Frappato", "Nerello"],
        "bredere": [
            {"land": "Italia", "kategori": "Rødvin",
             "distrikt": ["Puglia", "Campania", "Basilicata", "Calabria", "Molise"]},
        ],
        "utenfor": "fit",
        "nivå": "Sicilia",
        "evidens": "4.1 og 4.1 Etna, 4.0 Cerasuolo di Vittoria, 4.0 Terre Siciliane "
                   "— 3 av 4 ratede er sicilianske",
    },
}


def _niva_utenfor(f: dict, rules: dict, utfall: str) -> Optional[tuple[str, str]]:
    """
    Første nivå-innsnevrede regel der den BREDERE regionen treffer, men nivået
    evidensen dekker ikke gjør. Returnerer (needle, begrunnelse) eller None.

    `utfall` velger side: «blindspot» for innsnevrede bekymringer, «fit» for
    innsnevrede bekreftelser. Porten er kryss-språklig med vilje — se
    `_niva_er_dokumentert`.
    """
    for needle, spec in _NIVA_INNSNEVRET.items():
        if spec["utenfor"] != utfall:
            continue
        if needle not in rules.get(spec["kilde"], []):
            continue
        if _niva_er_dokumentert(needle, f):
            continue
        truffet = _ci_substring_match(needle, f["stil"]) or any(
            _matcher_alt_hit(alt, f) is not None for alt in spec["bredere"]
        )
        if truffet:
            return needle, (
                f"«{needle}» er dokumentert på {spec['nivå']} ({spec['evidens']}), "
                f"men ikke på dette nivået"
            )
    return None

# Needles som bevisst IKKE har en katalog-oversettelse, med begrunnelse.
# `tests/test_user_fit.py` krever at hver needle enten fyrer eller står her —
# en regel som aldri treffer skal være et valg, ikke et uhell.
_UNTRANSLATED: dict[str, str] = {
    "Asiatisk mat": "matkontekst, ikke en vinegenskap — katalogen har ingen felt å matche mot",
    "Naturvin / orange / hudkontakt": (
        "vinifikasjonsmetode; katalog-raden fører ingen metode. `metode` finnes kun i "
        "`data/polet/details/`, som dekker ~10 % av basen (ADR-024)"
    ),
}


def _matcher_alt_hit(alt: dict, f: dict) -> Optional[str]:
    """
    Sjekk ett alternativ mot normaliserte vinfelter. Returnerer en kort,
    menneskelesbar beskrivelse av hva som traff, eller None.
    """
    tekst_hay = " · ".join(x for x in (f["navn"], f["region"], f["underregion"]) if x)

    if "land" in alt and alt["land"].lower() != f["land"].lower():
        return None
    if "kategori" in alt and alt["kategori"].lower() != f["kategori"].lower():
        return None
    if "distrikt" in alt and not any(
        d.lower() == f["region"].lower() for d in alt["distrikt"]
    ):
        return None
    if "ikke_under" in alt and any(
        _ci_substring_match(x, f["underregion"]) or _ci_substring_match(x, f["navn"])
        for x in alt["ikke_under"]
    ):
        return None
    if "maks_pris" in alt:
        if f["pris"] is None or f["pris"] > alt["maks_pris"]:
            return None

    detail: list[str] = []
    if "under" in alt:
        hit = next(
            (x for x in alt["under"] if _ci_substring_match(x, f["underregion"])), None
        )
        if hit is None:
            return None
        detail.append(hit)
    if "tekst" in alt:
        hit = next((x for x in alt["tekst"] if _ci_substring_match(x, tekst_hay)), None)
        if hit is None:
            return None
        detail.append(hit)

    if not detail:
        # Rent land-/distrikt-/kategori-alternativ — nevn det leddet som
        # faktisk avgjorde, ellers ser «Nord-Italia matcher Langhe» ut som
        # en substring-match den ikke er.
        if "distrikt" in alt:
            detail = [f["region"]]
        elif "land" in alt:
            detail = [f["land"]]
        else:
            detail = [x for x in (f["underregion"], f["region"], f["land"]) if x][:1]
    if "maks_pris" in alt and f["pris"] is not None:
        detail.append(f"{f['pris']:.0f} kr")
    return ", ".join(detail) or f["navn"]


def _norm_app(s: str) -> str:
    """Appellasjonsnavn uten bindestreker, for match på tvers av kildene."""
    return re.sub(r"[\s\-–—]+", " ", s.lower()).strip()


def _niva_er_dokumentert(needle: str, f: dict) -> Optional[bool]:
    """
    For nivå-innsnevrede bekymringer: ligger vinen på det nivået historikken
    faktisk dekker? None hvis needelen ikke er innsnevret.

    Sjekken er kryss-språklig med vilje. `_NO_MATCHERS` treffer bare
    Polet-rader; Vivino-rader (som `tools/eval_fit.py` mater inn) treffer via
    engelsk substring på `stil`. Uten denne porten fikk samme vin ULIK tier
    avhengig av hvilken kilde den kom fra — og eval-harnessen fra ADR-017,
    som er beslutningsgrunnlaget for v1, målte den ikke-innsnevrede regelen.
    Appellasjonsnavnene er de samme i begge kilder, kun bindestrekene skiller
    («Côtes-du-Rhône» mot «Côtes du Rhône»).
    """
    spec = _NIVA_INNSNEVRET.get(needle)
    if spec is None:
        return None
    hay = _norm_app(" · ".join(x for x in (f["underregion"], f["region"], f["navn"]) if x))
    if not hay:
        # Ingen appellasjonsinformasjon i det hele tatt. Da kan vi ikke se at
        # vinen ligger utenfor det dokumenterte nivået — og fravær av data er
        # ikke bevis for det motsatte. Innsnevringen er en presisering av en
        # regel, ikke et nytt krav, så informasjonsfattig input beholder den
        # gamle oppførselen.
        return True
    return any(_norm_app(t) in hay for t in spec["smal"])


def _no_matcher_hit(needle: str, f: dict) -> Optional[str]:
    """Første alternativ som treffer for `needle`, som beskrivelse. Ellers None."""
    for alt in _NO_MATCHERS.get(needle, []):
        desc = _matcher_alt_hit(alt, f)
        if desc is not None:
            return desc
    return None


# Polet forkorter produsent-ledd («Dom. de la Janasse»), smaksprofilen skriver
# dem ut («Domaine de la Janasse»). Leddene bærer ingen skillende informasjon,
# så de fjernes fra begge sider før navne-sammenligning.
_NAVNELEDD = re.compile(
    r"\b(dom|domaine|ch|château|chateau|bod|bodegas|bodega|cant|cantina|"
    r"az|agr|tenuta|weingut|wein|castello|quinta|casa|maison|fattoria)\b\.?",
    re.IGNORECASE,
)
_ARGANG = re.compile(r"\b(19|20)\d{2}\b")


def _normalize_name(s: str) -> str:
    """Navn uten produsent-forkortelser, årgang eller dobbel whitespace."""
    s = _NAVNELEDD.sub(" ", s.lower())
    s = _ARGANG.sub(" ", s)
    return re.sub(r"[\s.,]+", " ", s).strip()


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

    # Pris — kun katalog-rader har den. Brukes av prisbetingede regler
    # («Billig Burgund»); None betyr «vet ikke», ikke «gratis».
    pris_raw = wine.get("pris") or wine.get("price")
    if isinstance(pris_raw, dict):
        pris_raw = pris_raw.get("value")
    try:
        pris = float(pris_raw) if pris_raw not in (None, "") else None
    except (TypeError, ValueError):
        pris = None

    return {
        "navn": first("navn", "name"),
        "produsent": first("produsent", "producer"),
        "region": first("region", "district"),
        # Underdistrikt er der Polet legger appellasjonen — «Valpolicella
        # Ripasso», «Barolo», «Bourgogne». Uten dette feltet er katalogen
        # praktisk talt stum: distriktet sier bare «Veneto»/«Burgund».
        "underregion": first("underregion", "sub_District", "subDistrict", "sub_district"),
        "land": first("land", "country", "main_country"),
        "kategori": first("kategori", "main_category", "category"),
        "stil": first("stil", "test", "style"),
        "druer_str": grapes_str,
        "druer_list": grapes_list,
        "varenummer": first("varenummer", "code", "polet_id"),
        "pris": pris,
    }


def _needle_hits(
    needles: list[str], haystacks: list[str], f: dict
) -> list[tuple[str, str]]:
    """
    Match needles mot en vin på TO veier, i denne rekkefølgen:

    1. **Norsk katalog-matcher** (`_NO_MATCHERS`) — landet/distriktet/
       appellasjonen på en Polet-rad.
    2. **Engelsk substring** — den opprinnelige veien. Beholdt fordi
       `tools/eval_fit.py` kjører `classify()` rett på Vivino-CSV-rader, der
       `stil` faktisk ER "Burgundy Red".

    Returnerer [(needle, beskrivelse-av-treffet)] — én per needle.
    """
    hits: list[tuple[str, str]] = []
    hays = [h for h in haystacks if h]
    for n in needles:
        if not n or len(n.strip()) < 3:  # for liberal substring → unngå
            continue
        desc = _no_matcher_hit(n, f)
        if desc is not None:
            hits.append((n, desc))
            continue
        for h in hays:
            if _ci_substring_match(n, h):
                if _niva_er_dokumentert(n, f) is False:
                    break  # regionen matcher, men ikke nivået historikken dekker
                hits.append((n, h))
                break
    return hits


def _evidens(needle: str, rules: dict) -> str:
    """«(n=3, snitt 3.27)» når profilen har tall for stilen, ellers tom streng."""
    n = rules.get("stil_n", {}).get(needle)
    avg = rules.get("stil_snitt", {}).get(needle)
    if n is None and avg is None:
        return ""
    bits = []
    if n is not None:
        bits.append(f"n={n}")
    if avg is not None:
        bits.append(f"snitt {avg:.2f}")
    return f" ({', '.join(bits)})"


def _konfidens_fra_n(needles: list[str], rules: dict) -> str:
    """
    Konfidens fra datagrunnlaget bak den sterkeste regelen som traff.

    En bekymring bygget på n=3 er en observasjon, ikke en lov, og skal ikke
    rapporteres som `high`. Needles uten tall (kuratert prosa som «Billig
    Burgund») teller som medium — de er brukerens egen dom, ikke en statistikk.
    """
    ns = [rules.get("stil_n", {}).get(x) for x in needles]
    known = [x for x in ns if x is not None]
    if not known:
        return "medium"
    top = max(known)
    if top >= 6:
        return "high"
    if top >= 3:
        return "medium"
    return "low"


def _er_land_kategori_blindspot(needle: str) -> bool:
    """
    True for auto-deriverte blindspots på formen «<Land> <Kategori>»
    («Germany Red Wine»). Disse er strengere evidens enn en region-preferanse
    som bare navngir landet — se `classify` regel 4.
    """
    return any(
        needle == f"{land} {kat}"
        for land in set(_LAND_NO_TO_EN.values())
        for kat in set(_KATEGORI_NO_TO_EN.values())
    )


def _blindspot_hit(f: dict, rules: dict) -> Optional[tuple[str, str]]:
    """
    Første blindspot som treffer vinen som `(needle, beskrivelse)`, ellers None.

    Blindspots kommer i to former: auto-deriverte «Land Kategori»-strenger på
    engelsk («Germany Red Wine») og kuratert norsk prosa («Pinot Noir
    generelt»). Den engelske formen krever at BÅDE land og kategori er
    oversatt fra norsk — ellers fyrer den bare for land som staves likt på
    begge språk.
    """
    kategori_en = _KATEGORI_NO_TO_EN.get(f["kategori"], "")
    land_en = _LAND_NO_TO_EN.get(f["land"], "")
    haystacks = [
        f["land"], f["kategori"], f["stil"], f["produsent"], f["navn"],
        f["region"], f["underregion"], kategori_en, land_en,
    ]
    if f["land"] and f["kategori"]:
        haystacks.append(f"{f['land']} {f['kategori']}")
    if land_en and kategori_en:
        haystacks.append(f"{land_en} {kategori_en}")
    haystacks = [h for h in haystacks if h]
    combined = " ".join(haystacks).lower()

    _TYPEORD = ("wine", "vin", "red", "white", "rosé", "rose", "sparkling",
                "fortified", "dessert")
    # Nivå-innsnevrede bekymringer først: «regionen matcher, nivået i
    # historikken gjør det ikke» er en mer presis begrunnelse enn en generisk
    # blindsone som tilfeldigvis dekker samme vin.
    niva = _niva_utenfor(f, rules, "blindspot")
    if niva:
        return niva[0], niva[1] + " — udokumentert, ikke trygt"

    for bs in rules.get("blindspots", []):
        desc = _no_matcher_hit(bs, f)
        if desc is not None:
            return bs, f"«{bs}» ({desc})"
        parts = bs.split()
        if len(parts) >= 2 and any(p.lower() in _TYPEORD for p in parts):
            # Sammensatt "Land Kategori": alle ledd må finnes
            if all(p.lower() in combined for p in parts if len(p) > 2):
                return bs, f"«{bs}»"
        else:
            for hay in haystacks:
                if _ci_substring_match(bs, hay):
                    return bs, f"«{bs}» i «{hay}»"
    return None


def classify(wine: dict, rules: Optional[dict] = None) -> dict:
    """
    Klassifisér én vin mot smaksprofil-reglene.

    Args:
        wine: dict med vinfelter (alle valgfrie). Godtar både en rå Polet-
            katalograd (`code`/`name`/`main_country`/`district`/`sub_District`/
            `main_category`/`price`) og et manuelt dict
            (navn, produsent, region, underregion, land, kategori, stil,
            druer, varenummer, pris).
        rules: Optional dict fra `load_profile_rules()`. Hvis None, lastes default.

    Returns:
        dict med keys: tier, reasons, confidence, rule_fired.

    Regelprioritet (early-exit):
        1. no_go          — navn-substring i no_go-liste
        2. bekymring      — stil/region/drue i Bekymringer eller bommet
        3. bekreftet_snitt — stil i bekreftet_stiler OG stil_snitt ≥ 4.0
           (nedgraderes til `fit` + `blindspot_cap` hvis vinen også er en
           blindspot — roadmap-prinsipp 4: blindspot får aldri `very_fit`)
        4. bekreftet_drue / bekreftet_stil / region_pluss — drue, stil eller region
        5. blindspot      — kategori-kombinasjon eller kuratert blindsone
        6. default
    """
    if rules is None:
        rules = load_profile_rules()

    f = _extract_wine_fields(wine)
    reasons: list[str] = []

    # Samle "fritekst-haystacks" der stil/region/drue kan ligge
    style_region_haystacks = [
        f["stil"], f["region"], f["underregion"], f["produsent"], f["land"],
        f["druer_str"], f["navn"],
    ]
    style_region_haystacks = [h for h in style_region_haystacks if h]

    # Logg manglende felt — påvirker konfidens, ikke regel-utfall
    missing = [k for k in ("navn", "stil", "land") if not f[k]]
    if missing:
        reasons.append(f"Mangler felt: {', '.join(missing)} — best-effort match.")

    # --- Regel 1: no_go (navn-substring) -------------------------------------
    # No-go-oppføringene bærer årgang («… Côtes du Rhône 2015»), og Polet
    # fører bare gjeldende årgang. Eksakt treff → `no_go`. Samme vin i en
    # annen årgang → `risky` (regel 2), ikke stillhet: profilen sier selv at
    # «ny årgang kan være annerledes», ikke at den er utenfor mistanke.
    nogo_annen_argang: Optional[str] = None
    if f["navn"]:
        navn_norm = _normalize_name(f["navn"])
        for nogo_wine in rules.get("no_go", []):
            if _ci_substring_match(nogo_wine, f["navn"]):
                reasons.insert(0, f"Vin-navn matcher no-go-listen: «{nogo_wine}».")
                return {
                    "tier": "no_go",
                    "reasons": reasons,
                    "confidence": "high",
                    "rule_fired": "no_go",
                }
            if nogo_annen_argang is None:
                nogo_norm = _normalize_name(nogo_wine)
                if nogo_norm and nogo_norm in navn_norm:
                    nogo_annen_argang = nogo_wine

    # --- Regel 2: bekymring/bommet (stil/region/drue) ------------------------
    bek_hits = _needle_hits(rules.get("bekymringer", []), style_region_haystacks, f)
    bommet_hits = _needle_hits(
        rules.get("bommet_druer_regioner", []), style_region_haystacks, f
    )
    if nogo_annen_argang or bek_hits or bommet_hits:
        if nogo_annen_argang:
            reasons.insert(
                0,
                f"Samme vin står på no-go-listen i en annen årgang: "
                f"«{nogo_annen_argang}». Ny årgang kan være annerledes — men "
                f"dette er ikke ukjent terreng.",
            )
        for needle, hay in bek_hits:
            reasons.insert(
                0,
                f"Stil-snitt under bekymrings-terskelen: «{needle}»"
                f"{_evidens(needle, rules)} matcher «{hay}».",
            )
        for needle, hay in bommet_hits:
            reasons.insert(0, f"Drue/region har bommet før: «{needle}» matcher «{hay}».")
        return {
            "tier": "risky",
            "reasons": reasons,
            "confidence": _konfidens_fra_n(
                [n for n, _ in bek_hits] + [n for n, _ in bommet_hits], rules
            ),
            "rule_fired": "bekymring",
        }

    # Blindspot beregnes FØR regel 3 fordi den kan kappe `very_fit`
    # (roadmap-prinsipp 4), ikke bare fordi den er regel 5.
    bs_treff = _blindspot_hit(f, rules)
    bs_needle, blindspot = bs_treff if bs_treff else (None, None)

    # --- Regel 3: bekreftet_snitt (stil i bekreftet OG snitt ≥ 4.0) ----------
    stil_snitt = rules.get("stil_snitt", {})
    for bekr_stil in rules.get("bekreftet_stiler", []):
        hit = _needle_hits([bekr_stil], style_region_haystacks, f)
        if not hit:
            continue
        avg = stil_snitt.get(bekr_stil)
        if avg is None or avg < _VERY_FIT_AVG_THRESHOLD:
            continue
        reasons.insert(
            0,
            f"Bekreftet stil «{bekr_stil}»{_evidens(bekr_stil, rules)} "
            f"— snitt ≥ {_VERY_FIT_AVG_THRESHOLD}. Treff: «{hit[0][1]}».",
        )
        if blindspot:
            # Prinsipp 4: stil-evidensen er ekte, men kategori-evidensen er tynn.
            reasons.insert(
                0,
                f"Nedgradert fra very_fit: vinen ligger også i en blindsone — {blindspot}.",
            )
            return {
                "tier": "fit",
                "reasons": reasons,
                "confidence": "low",
                "rule_fired": "blindspot_cap",
            }
        return {
            "tier": "very_fit",
            "reasons": reasons,
            "confidence": _konfidens_fra_n([bekr_stil], rules),
            "rule_fired": "bekreftet_snitt",
        }

    # --- Regel 4: fit — drue ELLER stil ELLER region ------------------------
    drue_hits = _needle_hits(
        rules.get("bekreftede_druer", []),
        [f["druer_str"], f["navn"], f["stil"], f["underregion"]],
        f,
    )
    stil_hits = _needle_hits(rules.get("bekreftet_stiler", []), style_region_haystacks, f)
    region_hits = _needle_hits(
        rules.get("regioner_pluss", []),
        [f["region"], f["underregion"], f["produsent"], f["land"], f["navn"]],
        f,
    )
    # Spesifisitet slår generalitet. «Germany Red Wine (n=2)» navngir BÅDE land
    # og kategori; region-needelen «Tyskland» navngir bare landet — og profilens
    # parentes sier «(Mosel, Rheingau – Riesling)», altså hvitt. Uten denne
    # regelen ble alle 368 tyske rødviner `fit` fordi brukeren liker
    # Mosel-Riesling. Det er stille optimisme: en positiv dom bygget på evidens
    # om en annen kategori. Gjelder kun når region er ENESTE treff — en
    # bekreftet drue eller stil er egen evidens og overstyres ikke.
    if (
        region_hits
        and not drue_hits
        and not stil_hits
        and bs_needle
        and _er_land_kategori_blindspot(bs_needle)
    ):
        region_hits = []

    # Innsnevret bekreftelse: stilen er bekreftet, men ikke på dette
    # underområdet. Positiv merkelapp ett hakk ned, med n og fordelingen
    # synlig — ikke `very_fit`, og ikke stillhet.
    niva_fit = _niva_utenfor(f, rules, "fit") if not stil_hits else None

    if drue_hits or stil_hits or region_hits or niva_fit:
        for needle, hay in drue_hits:
            reasons.insert(0, f"Bekreftet drue «{needle}» matcher «{hay}».")
        for needle, hay in stil_hits:
            reasons.insert(
                0,
                f"Bekreftet stil «{needle}»{_evidens(needle, rules)} matcher «{hay}».",
            )
        for needle, hay in region_hits:
            reasons.insert(0, f"Foretrukket region «{needle}» matcher «{hay}».")
        if niva_fit:
            reasons.insert(
                0,
                f"{niva_fit[1]}{_evidens(niva_fit[0], rules)} — positivt merke, "
                f"men ett hakk ned fra very_fit.",
            )
        # Regel-merket sier hvilken av de tre som faktisk traff. Før het alle
        # tre `bekreftet_drue`, også de 2 401 rene region-treffene.
        if drue_hits:
            fired = "bekreftet_drue"
        elif stil_hits or niva_fit:
            fired = "bekreftet_stil"
        else:
            fired = "region_pluss"
        return {
            "tier": "fit",
            "reasons": reasons,
            "confidence": "low" if (blindspot or niva_fit) else "medium",
            "rule_fired": fired,
        }

    # --- Regel 5: blindspot --------------------------------------------------
    if blindspot:
        reasons.insert(0, f"Blindsone — profilen har lite eller ingen data: {blindspot}.")
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
        # Har vi katalog-raden, bruk dens felter (land/distrikt/underdistrikt/
        # pris) — score-DB-en har bare navn + produsent-streng.
        katalog = _lookup_catalog(polet_id)
        if katalog:
            wine = {**katalog, "navn": wine["navn"] or katalog.get("name", "")}
        out[polet_id] = classify(wine, rules)
    return out


# ---------------------------------------------------------------------------
# Oppslag mot Polet-katalogen (B5)
# ---------------------------------------------------------------------------
#
# `data/user_fit/v0.json` er derivert fra `knowledge/scores/` og dekker de ~400
# vinene som har kritiker-score — 0,47 % av katalogens 14 081 varenumre. Den
# er IKKE en katalog-indeks, og skal ikke bli det: en 14 081-raders derivert
# artefakt måtte regenereres ved hver snapshot-refresh og ville vært utdatert
# oftere enn den var riktig.
#
# Riktig oppslagsvei for et vilkårlig varenummer er `classify_code()`, som
# klassifiserer katalog-raden direkte. Det er samme kodesti, uten filen
# imellom, og dekker 100 % av katalogen.


@functools.lru_cache(maxsize=1)
def _catalog_index() -> dict[str, dict]:
    """
    {varenr: katalograd}, bygget én gang per prosess.

    `polet_store.lookup()` re-parser hele katalogen (14 081 linjer) per kall —
    ufarlig for ett oppslag, 5,8 millioner linje-parsinger for et batch på 400.
    Indeksen er prosess-lokal, samme mønster (og samme kjente begrensning) som
    `tools.scores.index()`; se teknisk gjeld #4.
    """
    try:
        from tools import polet_store
    except ImportError:  # pragma: no cover — polet_store er en del av repoet
        return {}
    try:
        return {
            str(p["code"]): p for p in polet_store.read_catalog() if p.get("code")
        }
    except Exception as e:  # snapshot mangler / er korrupt — ikke en klassifiseringsfeil
        print(f"[user_fit] WARN: kunne ikke lese Polet-katalogen: {e}", file=sys.stderr)
        return {}


def _lookup_catalog(code: str) -> Optional[dict]:
    """Katalog-rad for et varenummer, eller None."""
    return _catalog_index().get(str(code).strip())


def classify_code(code: str, rules: Optional[dict] = None) -> Optional[dict]:
    """
    Slå opp et varenummer i Polet-snapshotet og klassifisér raden direkte.

    Dette er oppslagsveien for batch-spørringer (CLAUDE.md steg 6b), ikke
    `data/user_fit/v0.json` — se modulkommentaren over.

    Returnerer classify()-output utvidet med `varenummer` og `navn`, eller
    None hvis varenummeret ikke finnes i snapshotet (da trengs en refresh,
    se `docs/polet_refresh.md`).
    """
    product = _lookup_catalog(code)
    if product is None:
        return None
    result = classify(product, rules if rules is not None else load_profile_rules())
    result["varenummer"] = product.get("code", str(code))
    result["navn"] = product.get("name", "")
    return result


def classify_codes(codes: list[str]) -> dict[str, Optional[dict]]:
    """`classify_code` for flere varenumre. Regelsettet lastes én gang."""
    rules = load_profile_rules()
    return {str(c): classify_code(c, rules) for c in codes}


def classify_catalog(category: Optional[str] = None) -> dict[str, dict]:
    """
    Klassifisér hele (eller en kategori av) Polet-snapshotet, i minnet.

    Brukes av testene for fordelings-assertions. Skrives bevisst ikke til
    disk — se modulkommentaren over.
    """
    from tools import polet_store

    rules = load_profile_rules()
    out: dict[str, dict] = {}
    for product in polet_store.read_catalog():
        if category:
            cat = product.get("main_category") or {}
            if str(cat.get("name", "")).lower() != category.lower():
                continue
        code = product.get("code")
        if code:
            out[str(code)] = classify(product, rules)
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
            # Selv-dokumenterende omfang: fila er score-DB-en, ikke katalogen.
            # Uten dette leste CLAUDE.md steg 6b den som en katalog-indeks og
            # bommet på 99,5 % av varenumrene.
            "source": "knowledge/scores/",
            "scope": (
                "Kun viner med kritiker-score (~400 av katalogens 14 000+). "
                "For et vilkårlig varenummer: bruk tools.user_fit.classify_code(code), "
                "som klassifiserer Polet-katalograden direkte."
            ),
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


def _print_codes(codes: list[str]) -> None:
    """CLI-utskrift for `python3 -m tools.user_fit <varenr> ...`."""
    for code, res in classify_codes(codes).items():
        if res is None:
            print(f"{code}: ikke i snapshot — kjør refresh (docs/polet_refresh.md)")
            continue
        print(f"{code}  {res['navn']}")
        print(f"  {res['tier']} · {res['rule_fired']} · konfidens {res['confidence']}")
        for r in res["reasons"]:
            print(f"    - {r}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        # Oppslagsvei for CLAUDE.md steg 6b: klassifisér varenumre direkte mot
        # katalogen. Ingen fil-omvei, full katalogdekning.
        _print_codes(args)
        sys.exit(0)

    path = write_v0_json()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    meta = data["_meta"]
    print(f"Skrev: {path}")
    print(f"Klassifisert: {meta['n_classified']} viner (kun score-DB — se _meta.scope)")
    print("Tier-fordeling:")
    for tier in ("very_fit", "fit", "neutral", "risky", "no_go"):
        n = meta["tier_counts"].get(tier, 0)
        print(f"  {tier:10s} {n:4d}")
