# Roadmap

> Forward-looking versjonsplan for features. Skiller seg fra `docs/ARCHITECTURE.md` ved at ADR-ene der dokumenterer **valgte** beslutninger; roadmap-en her dokumenterer **planlagte** løsninger med trade-offs og når neste versjon trigges.
>
> Når et roadmap-element implementeres, skrives det også en ADR i `docs/ARCHITECTURE.md` med konkrete vekter/parametre, og elementet flyttes til "Levert" nederst i denne fila.

## Innhold

- [User-fit-score](#user-fit-score) — pre-computet rangering av score-DB-viner mot smaksprofil
- [Levert](#levert) — features som er implementert (peker til ADR)

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
    "rule_fired": "no_go | bekymring | bekreftet_snitt | bekreftet_drue | blindspot | default"
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

## Levert

(Tom — flytt elementer hit etter implementasjon med peker til ADR.)
