# Roadmap

> Forward-looking versjonsplan for features. Skiller seg fra `docs/ARCHITECTURE.md` ved at ADR-ene der dokumenterer **valgte** beslutninger; roadmap-en her dokumenterer **planlagte** løsninger med trade-offs og når neste versjon trigges.
>
> Når et roadmap-element implementeres, skrives det også en ADR i `docs/ARCHITECTURE.md` med konkrete vekter/parametre, og elementet flyttes til "Levert" nederst i denne fila.

## Innhold

- [Vivino auto-sync](#vivino-auto-sync) — direkte lesing av Vivino-profilen via Playwright (ingen manuell eksport)
- [Evaluerings-harness](#evaluerings-harness) — modell-agnostisk rangerings-eval, bygges før v1
- [User-fit-score](#user-fit-score) — pre-computet rangering av score-DB-viner mot smaksprofil
- [Øl-fit — Untappd-paritet](#øl-fit--untappd-paritet) — utvid fit-tankegangen fra vin til øl
- [Levert](#levert) — features som er implementert (peker til ADR)

---

## Vivino auto-sync

**Status:** ✅ **LEVERT 2026-07-02** — se [Levert](#levert)-tabellen nederst. Historikk og designbegrunnelse beholdt under for kontekst.

> **LEVERT 2026-07-02** → `tools/vivino_sync.py` + runbook [`docs/vivino_refresh.md`](docs/vivino_refresh.md). Skraper innlogget profil-feed via Playwright-MCP (egen rating fra `icon-N-pct`-stjerneklasser /100), differ mot CSV, idempotent merge (dedup på winery+wine+vintage), kjører `profile_stats.py` etterpå. Full begrunnelse i [ADR-022](docs/ARCHITECTURE.md#adr-022-vivino-sync-levert--playwright-mcp-skraping-av-innlogget-profil-feed).

Manuell metode ble bevist 2026-06-08 og **bevisst utsatt** til etter Polet-snapshotet var stabilt — Polet-WAF-fiksen (samme «ekte nettleser»-vei, [ADR-019](docs/ARCHITECTURE.md#adr-019-datatilgang-via-ekte-nettleser--vivino-og-polet-bak-waf)/[ADR-020](docs/ARCHITECTURE.md#adr-020-repo-committet-polet-snapshot--cross-device-desktop-refresh--android-read-only)) ble prioritert først. **NB:** Vivino sitter bak samme type bot-vern, så sync bruker den device-agnostiske remote-browser-via-CDP-transporten ([ADR-021](docs/ARCHITECTURE.md#adr-021-remote-browser-via-cdp--device-agnostisk-refresh)) — ellers hard-blokkeres den i MITM-proxy-miljøer (web-container) akkurat som Polet.

### Hvorfor

Roadmapen forutsatte tidligere at re-trening skjer «ved hver Vivino-eksport» (se v2). Men Vivino har **ingen åpen API**, og den offisielle CSV-eksporten må trigges manuelt og lander i e-post. Resultatet var at `data/vivino/full_wine_list.csv` lå 3 måneder bak (104 ratede mot 111 reelle) før synken 2026-06-08, og oppdateringen krevde manuell scraping + håndfylling av felter (`Regional wine style`, `Average rating`) — en data-kvalitets-risiko.

**Datatilgang er den egentlige flaskehalsen, ikke modellen.** Dette elementet har høyere prioritet enn v1/v2 av user-fit-score.

### Bevist metode (2026-06-08)

Claude kan nå lese Vivino-historikken **direkte og på egenhånd** via Playwright-MCP — ingen manuell eksport nødvendig:

- **Profil-URL:** `https://www.vivino.com/en/users/kristoffers4` (offentlig, men krever innlogget sesjon — Kristoffer logger inn én gang i Playwright-nettleseren, deretter holder cookien).
- **Activity-feed:** hver rating er et `.user-activity-item`-element.
- **Din rating** ligger kodet som stjerne-ikoner — summér `icon-NN-pct`-klassene / 100 (f.eks. 4× `icon-100-pct` + 1× `icon-40-pct` = 4.4).
- **Eksakt tidsstempel** i `title`-attributtet på `/en/activities/<id>`-lenken.
- **Vin-metadata** (produsent, navn, årgang, region, land, community-snitt) fra `.activity-wine-card`; `data-vintage_id` på samme element.
- **Diff** mot CSV på `Winery` + `Wine name` for å finne nye ratinger.
- Klikk «Show more» for å paginere bakover i historikken ved full re-sync.

### Neste steg — `tools/vivino_sync.py`

Pakk metoden over som et verktøy som speiler `untappd_stats.py`-mønsteret:

1. Playwright-innlogging (gjenbruk lagret sesjon der mulig).
2. Les activity-feeden, paginer til siste kjente `Scan date`.
3. Hent **kanoniske** felter fra hver vinside (drue, stil, snitt) — ikke håndgjettet som ved den manuelle synken.
4. Diff mot CSV, append nye rader.
5. Kall `profile_stats.py` automatisk til slutt.

**Pros / Cons:**

| Pros | Cons |
|---|---|
| Fjerner staleness permanent — synk på kommando | Avhengig av Vivinos DOM (samme drift-risiko som Polet — bør ha fixture-test, jf. ADR-011) |
| Eliminerer håndfylling → riktig data-provenans | Krever innlogget Playwright-sesjon (cookie kan utløpe) |
| Gjenbrukbar; speiler eksisterende øl-flyt | ToS-gråsone — kun for egen profil, lavt volum |

**Trigger:** Bygges før neste større user-fit-iterasjon, slik at modellen alltid trenes på fersk data.

---

## Evaluerings-harness

**Status:** Planlagt — bygges som eget steg før user-fit v1

### Hvorfor

v1/v2 av user-fit-score kan ikke stoles på uten en måte å måle om en ny modell faktisk slår den forrige. Eval-planen finnes allerede (Spearman, NDCG@5, tidsbasert split, 15-vin lockbox) men er begravet *inne i* v1-beskrivelsen. Løftet ut som eget, **modell-agnostisk** steg blir «v0 vs v1 vs v2» et empirisk spørsmål i stedet for den subjektive triggeren beslutningstreet bruker i dag.

### Hva

- Tidsbasert train/test-split: før 2024-01-01 = train, etter = test.
- Primær metrikk: Spearman rank-korrelasjon på testsettet. Sekundær: NDCG@5.
- Baselines som enhver modell må slå: random, Vivino-avg, stil-snitt-alene, critic-score-alene.
- 15 viner holdt som final lockbox.
- Kjør samme harness mot v0-tiers (konvertert til ordinal score) for å få en konkret baseline før v1 i det hele tatt bygges.

**Trigger for v1:** Harnessen viser at v0's fem tier-bøtter er for grove (kan ikke skille rangering brukeren faktisk bryr seg om).

> **LEVERT 2026-06-08** → `tools/eval_fit.py`. Full begrunnelse, resultattabell og konklusjon i [ADR-017](docs/ARCHITECTURE.md#adr-017-eval-harness-før-v1--modell-agnostisk-rangerings-måling). Kort: v0 slår baselines, men vivino_avg (+0.63) er sterkest — **bli i v0, v1-trigger ikke oppfylt.** Kjør `python3 -m tools.eval_fit` for ferske tall.

---

## User-fit-score

**Status:** v0 under bygging (2026-05-14)

### Hvorfor

Smaksprofilen er operasjonelt usynlig for batch-spørringer. Claude må reasoning per-vin i runtime. Tre konkrete brukerflows er praktisk umulige eller smertefullt langsomme:

1. "Topp 10 fra maislippet for meg" → 170 viner × inference = minutter
2. "Vis alle Polet-røde under 400 kr med høyt fit" → krever iterering over hele katalogen
3. "Hvorfor er denne feilmatch for meg?" → ad-hoc resonnement uten dekomponering

User-fit-score løser dette ved å gjøre smaksprofilen til en operativ funksjon over kataloger.

### Designprinsipper (uavhengig av versjon)

1. **Fit ⊥ value.** Hold to akser i output. Fit svarer "vil jeg like det?", value svarer "er prisen riktig?". Aldri bland disse i én score.
2. **smaksprofil.md forblir source-of-truth.** Fit-JSON er derivert artefakt, regenereres ved `profile_stats.py`-kjøring.
3. **Lagre i `data/user_fit/`**, ikke `knowledge/scores/` (per ADR-002 — strukturert data, ikke kuratert prosa).
4. **Confidence er like viktig som score.** Blindspot-viner får aldri "very_fit", uansett feature-summen.
5. **Egen modul `tools/user_fit.py`.** Ikke utvid `value_score.py` — ortogonalitet hele veien ned.
6. **Forklarbarhet > presisjon.** Hver score skal være additivt dekomponert eller regel-merket.

### v0 — Rule-based tier classifier (1 time)

**Hva:** Parser smaksprofil.md → klassifiserer hver vin i score-DB-en i én av fem bøtter: `very_fit | fit | neutral | risky | no_go`.

**Logikk (early-exit, første treff vinner):**
1. Vin-navn substring-match mot `## No-go-liste` → `no_go`
2. Region/stil match mot `Bekymringer` eller `Druer/regioner som har bommet` → `risky`
3. Stil-snitt ≥ 4.0 med n ≥ 3 i bruker-historikk → `very_fit`
4. Drue eller stil i `Bekreftede mønstre` eller `Druer du vet du liker` → `fit`
5. Region/kategori i `Blindspots` → `neutral` med flagg `[NYTT, lav konfidens]`
6. Default → `neutral`

**Output:** `data/user_fit/v0.json`

```json
{
  "_meta": {"version": "v0", "generated_at": "...", "n_classified": 422},
  "<polet_id>": {
    "tier": "very_fit | fit | neutral | risky | no_go",
    "reasons": ["string", ...],
    "confidence": "high | medium | low",
    "rule_fired": "no_go | bekymring | bekreftet_snitt | bekreftet_drue | bekreftet_stil | region_pluss | blindspot | blindspot_cap | default"
  }
}
```

**Pros / Cons:**

| Pros | Cons |
|---|---|
| Ferdig på 1 time | Bare 5 bøtter — ingen rangering innenfor tier |
| Fullt forklarbar per regel | Bruker ikke klokker (krever Polet-detail-fetch) |
| Null ML-risiko, deterministisk | Subjektive tier-grenser |
| Setter umiddelbar baseline | Kan ikke svare "hvilken er best av disse fit-vinene?" |
| Trivielt å forklare for bruker | Fanger ikke interaksjoner (drue × region × klokker) |

**Når v0 er nok:** Tier-merking på rangerte resultater, eksplisitt advarsel på `risky`/`no_go`. **OBS**: tier brukes som *merke*, ikke som *filter* — se [ADR-016 No-filter-bubble](docs/ARCHITECTURE.md#adr-016-no-filter-bubble-prinsippet-for-user-fit-score). Tier-first-sortering kun ved eksplisitt brukerønske om personalisering.

**Trigger for å avansere til v1:** Når bruker spør "rangér disse" og v0's tier-grupper er for grove.

### v1 — Weighted linear sum med manuelle vekter (3 timer)

**Hva:** 6 håndvalgte features, manuelt satt vekt, normaliser med sigmoid til 0–100 score. Tier fortsatt utledet fra terskler.

**Features:**

| # | Feature | Initial vekt | Kilde |
|---|---|---|---|
| 1 | `style_affinity` (snitt(rating \| Regional wine style), recency-vektet, Country-fallback når n<3) | 1.0 | Vivino-CSV |
| 2 | `klokke_distance` (euklidsk til topp-vin-centroid per type) | 0.8 | Polet detail (krever fetch) |
| 3 | `critic_score_normalized` (DN/Aperitif 0–100 → 0–1) | 0.7 | `knowledge/scores/` |
| 4 | `grape_affinity` (multi-hot mot bekreftede druer / bommet) | 1.0 | Polet detail |
| 5 | `blindspot_penalty` (binær → confidence-cap, ikke score-penalty) | n/a | smaksprofil |
| 6 | `no_go_knockout` (hard score=0) | n/a | smaksprofil |

**Evaluering:**
- Tidsbasert train/test-split: før 2024-01-01 = train (~65 viner), etter = test (~39)
- Primær metrikk: Spearman rank-korr på testsettet
- Sekundær: NDCG@5
- Baselines som må slås: random, Vivino-avg, stil-snitt-alene, critic-score-alene
- Hold 15 viner som final lockbox

**Pros / Cons:**

| Pros | Cons |
|---|---|
| Kontinuerlig 0–100 score → ekte rangering | Manuelle vekter er subjektive |
| Auditerbar per feature-bidrag | Fanger ikke feature-interaksjoner |
| Lett å tune ved kjent dårlig oppførsel | Klokker mangler ofte på rosé/musserende → graceful degrade nødvendig |
| Inkluderer klokker (eneste sensoriske dimensjon) | Krever Polet-detail-fetch for hver scored vin |

**Trigger for å avansere til v2:** Manuelle vekter viser systematisk skjev rangering på testsettet (Spearman < 0.4 mot ground truth), og signal-til-støy peker mot at vektene faktisk kan læres.

### v2 — Vekter lært fra 104 ratinger (8 timer)

**Hva:** Samme features som v1, men vekter fittet via **Ridge regression** (L2=1.0) på de 104 ratingene. 5-fold CV på treningssettet, 15 viner som final lockbox.

**Output utvides med:**
- Per-feature konfidens-intervall
- R² × `min(n_similar_seen/5, 1)` som per-vin confidence
- `model_metadata`: koeffisienter, CV-RMSE, trening-dato

**Re-trening:** Automatisk i `profile_stats.py` ved hver Vivino-eksport. Hvis CV-RMSE forverres > 0.3 vs forrige kjøring → console-varsel ("smak har skiftet, vurder algoritme-revisjon").

**Pros / Cons:**

| Pros | Cons |
|---|---|
| Empirisk grunnlagt — ikke vibes | n=104 er på grensen for stabilitet |
| Selvjusterende ved nye ratinger | Overfitting-risiko hvis feature-set vokser |
| Detekterer smaks-drift over tid | Ridge-koeffisienter krever forklaring de færreste forstår |
| Confidence-intervall per prediksjon | 8 timer arbeid + evaluerings-infra |

**Trigger for å avansere videre:** v2 har vist dårlig rank-korr selv etter tuning, eller bruksmønsteret krever feature-interaksjoner (f.eks. drue × klima for å fange "off-dry tysk fungerer kun med høy syre").

### Alternativ vurdert og forkastet: TF-IDF + Rocchio cosine

Konseptuelt elegant: vin = bag-of-tokens, brukerprofil = rating-vektet sentroid, score = cosine similarity. Brukes i Pandora Music Genome (delvis), Yelp content-fallback.

**Hvorfor forkastet for primær fit-score:**
- Cosine ignorerer at noen features bør matte mer (klokker > prissone)
- Negative preferanser (Provence-rosé 2.38 snitt) underrepresentert med mindre eksplisitt modellert
- Mister kategoriske vetoer (no_go-liste) — alt blir gradient
- Vanskelig å integrere med eksisterende tier-vokabular

**Kan brukes som *sekundær* mekanisme:** "Viner du har likt som ligner mest på denne" — forklaringskomponent, ikke ranking.

### Beslutningstre — når trigger neste versjon?

```
v0 i bruk → spør: "Mangler jeg rangering innenfor tier?"
   ├── Nei → bli i v0
   └── Ja  → v1
            │
            v1 i bruk → spør: "Mangler jeg presisjon eller drift-deteksjon?"
               ├── Nei → bli i v1
               └── Ja  → v2
                        │
                        v2 i bruk → spør: "Mangler jeg interaksjoner eller cross-region-læring?"
                           ├── Nei → bli i v2
                           └── Ja  → vurder collaborative-features (krever flere brukere) eller embedding-modell (krever betydelig ML-infra)
```

---

## Øl-fit — Untappd-paritet

**Status:** Planlagt — fit-tankegangen er i dag vin-only

### Hvorfor

Prosjektet er eksplisitt dual (vin + øl, felles smaksprofil), men `tools/user_fit.py` og hele user-fit-roadmapen dekker kun vin. `smaksprofil.md` har allerede en auto-derivert øl-blokk (fra `untappd_stats.py` over ~90 check-ins) med stilfamilier, ABV-spenn og sesongmønster — men den er operasjonelt usynlig for batch-spørringer på samme måte som vin-profilen var før user-fit. Øl-anbefalinger hviler i dag på per-forespørsel-resonnement.

### Åpent designspørsmål (ærlig)

Vin-fit pre-computer mot en konkret katalog: Polet score-DB-en (422 entries indeksert på varenummer). **Øl har ingen tilsvarende indeksert katalog** — ingen Polet øl-score-DB. Så øl-fit kan ikke bare speile «pre-compute mot katalog»-mønsteret. To veier:

- **(a) Fit per BJCP-stilfamilie** (~30 faste familier) → billig oppslagstabell, brukes ved anbefalingstid. Lavere oppløsning, men matcher tilgjengelig data og er den naturlige granulariteten for øl-anbefalinger.
- **(b) Score enkeltøl on-demand** mot øl-blokken (stilfamilie, ABV-spenn, sesong) ved anbefalingstid. Ingen katalog nødvendig, men ingen pre-compute-gevinst.

**Anbefaling:** start med (a). n≈90 check-ins er for tynt for per-øl-scoring, og stilfamilie er uansett riktig nivå for øl-rec.

### v0 — Stilfamilie-tier (speiler vin-v0)

Parser øl-blokken i `smaksprofil.md` → klassifiserer hver BJCP-stilfamilie i `very_fit | fit | neutral | risky | no_go` etter samme early-exit-logikk som vin-v0 (bekreftede mønstre, ABV-spenn-match, sesong, no-go). Output: `data/user_fit/beer_v0.json` indeksert på stilfamilie.

**Caveat:** n≈90 er enda tynnere enn vinens 111. **Kun regel-basert v0** — ingen ML-stige for øl før datagrunnlaget vokser vesentlig. Eval-harnessen (over) gjenbrukes når/hvis øl får kontinuerlig score.

**Trigger:** Når brukeren ber om personaliserte øl-anbefalinger i batch (f.eks. «hvilke av disse 10 på Untappd-lista vil jeg like») og per-forespørsel-resonnement blir for tregt.

> **LEVERT 2026-06-08** → `tools/beer_fit.py`. Begrunnelse for arkitektur-avviket (derivér fra CSV, ikke parse markdown) og innbakte brukerbeslutninger (very_fit løsnet til n≥3/3.85; manuell innliming) i [ADR-018](docs/ARCHITECTURE.md#adr-018-øl-fit-deriverer-fra-untappd-csv-ikke-fra-smaksprofil-markdown). Auto-regenereres av `untappd_stats.main()`. Kjør `python3 -m tools.beer_fit`.

---

## Levert

| Element | Dato | Modul | ADR | Nøkkelresultat |
|---|---|---|---|---|
| Evaluerings-harness | 2026-06-08 | `tools/eval_fit.py` (15 tester) | [ADR-017](docs/ARCHITECTURE.md#adr-017-eval-harness-før-v1--modell-agnostisk-rangerings-måling) | v0_tier +0.59 Spearman — slår baselines; **v1-trigger ikke oppfylt**. vivino_avg (+0.63) er listen v1 må slå. |
| Øl-fit v0 | 2026-06-08 | `tools/beer_fit.py` (15 tester) | [ADR-018](docs/ARCHITECTURE.md#adr-018-øl-fit-deriverer-fra-untappd-csv-ikke-fra-smaksprofil-markdown) | Stilfamilie→tier fra Untappd-CSV. 1 very_fit / 1 fit / 3 risky / 14 neutral. |
| Vivino auto-sync | 2026-07-02 | `tools/vivino_sync.py` + [`docs/vivino_refresh.md`](docs/vivino_refresh.md) | [ADR-022](docs/ARCHITECTURE.md#adr-022-vivino-sync-levert--playwright-mcp-skraping-av-innlogget-profil-feed) | Skraper innlogget profil-feed via Playwright-MCP; idempotent merge (dedup winery+wine+vintage); staleness fjernet on-demand. |
| Live facet-sweep + snapshot-ekspansjon | 2026-07-02 | `tools/polet_facets.py` (20 tester) | [ADR-023](docs/ARCHITECTURE.md#adr-023-live-facet-sweep--trait-filtrering--snapshot-ekspansjon) | Trait-fasetter (Fylde/Friskhet/…) med korrekt AND/OR-semantikk; snapshot 557 → 1849, New World nå dekket. |

> User-fit og øl-fit har fortsatt fremtidige versjoner beskrevet i seksjonene over (user-fit v1/v2, øl-fit utvidelser) — kun v0/harness er levert.
