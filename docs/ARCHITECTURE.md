# Arkitektur

> Denne fila dokumenterer **hvorfor** systemet er bygget slik det er — ikke bare hva det gjør.
> Når du gjør en audit eller refactor, les her først for å forstå hvilke trade-offs som allerede er evaluert og hvilke konsekvenser hvert valg har.

## Innhold

1. [Overordnet form](#overordnet-form)
2. [Lag-strukturen](#lag-strukturen)
3. [Data- og signal-flyt](#data--og-signal-flyt)
4. [Cache-hierarkiet](#cache-hierarkiet)
5. [Performance-baseline](#performance-baseline)
6. [Architecture Decision Records (ADR)](#architecture-decision-records-adr)
7. [Kjent teknisk gjeld](#kjent-teknisk-gjeld)

---

## Overordnet form

Sommelier er et **personlig, én-bruker-system** kjørt som et Claude Code-prosjekt. Det er ikke en SaaS-applikasjon, ikke et team-verktøy, og ikke en distribuert tjeneste. Designvalgene reflekterer dette — vi velger menneskelig diffbare formater over relasjonelle databaser, prosess-cache over delt cache, og pragmatiske scrapere over autoriserte API-er.

Hjertet er **Claude-as-orchestrator**: Claude leser autoloaded prompt + relevante knowledge-filer, kaller Python-helpers for data fra Polet/Aperitif/Vivino, og syntetiserer en anbefaling. Lokal kode er supportive, ikke autoritativ.

## Lag-strukturen

```
┌──────────────────────────────────────────────────────────────────┐
│ Claude-as-orchestrator (les knowledge → call tools → synthesize) │
└──────────────────────────────────────────────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│ knowledge/   │         │ deep-        │         │ tools/       │
│ (alltid      │         │ knowledge/   │         │ (helpers)    │
│  lastet)     │         │ (on-demand)  │         │              │
├──────────────┤         ├──────────────┤         ├──────────────┤
│ • sommelier  │ ◄────── │ italia.md    │         │ vinmonopolet │
│ • cicerone   │ trigger │ frankrike.md │         │ aperitif     │
│ • smaks-     │ ─────►  │ tyskland.md  │         │ vivino       │
│   profil     │         │ +13 til      │         │ scores       │
│ • wset_l2    │         │ ─────────────│         │ value_score  │
│ • scores/    │         │ INDEX.md     │         │ profile_stats│
│   ↕ scores.py│         │ (trigger-    │         │ untappd_stats│
│              │         │  router)     │         │              │
└──────────────┘         └──────────────┘         └──────┬───────┘
        ▲                                                │
        │                                                ▼
        │                                         ┌──────────────┐
        │ profile_stats.py                        │ Polet API    │
        │ untappd_stats.py                        │ Aperitif.no  │
        │ (auto-derive)                           │ Vivino       │
        │                                         └──────────────┘
        │                                                │
        │                                                ▼
        │                                         ┌──────────────┐
        │                                         │ ~/.cache/    │
        │                                         │  sommelier/  │
┌───────┴──────┐                                  └──────────────┘
│ data/        │
│ vivino/*.csv │
│ untappd/*.csv│
└──────────────┘
```

### Reglene som styrer lagene

| Lag | Inneholder | Inneholder IKKE | Regel |
|---|---|---|---|
| `data/` | Re-eksporterbare ratings + cellar (CSV) | Avledet statistikk, brukerinnsikt | Source-of-truth for *hva som er drukket og ratet* |
| `knowledge/` (rot) | Bruker-syntese + operasjonelle regler | Nøytral fagprosa, varenr-data | Alltid-lastet kontekst — hold lean |
| `knowledge/scores/` | Markdown-DB av kritiker-scorer per varenummer | Bruker-spesifikke notater | Maskin-parsbar via `tools/scores.py` |
| `deep-knowledge/` | Nøytral fagreferanse (WSET L3 / Cicerone L2/3) | Bruker-data, "for deg"-anbefalinger | On-demand via INDEX.md-router |
| `tools/` | Pure Python helpers + HTTP-klienter | Bruker-tilstand | Idempotent, cachet, gjenbrukbar |
| `tests/` | Innholds-baserte kontrakt-tester | Implementasjonsdetaljer | Skal overleve refactors |

## Data- og signal-flyt

**For en anbefaling:**

```
Bruker spør "hva drikker jeg til X?"
        │
        ▼
Claude leser smaksprofil.md + sommelier.md ELLER cicerone.md
        │
        ▼
(Hvis region-spesifikt) Claude leser én deep-knowledge/<region>.md
        │
        ▼
Claude kaller tools/vinmonopolet.py → kandidat-viner
        │
        ▼
(Hvis value-vurdering trengs) Claude kaller tools/value_score.py
        │                                       │
        │            ┌──────────────────────────┼──────────────────────┐
        │            ▼                          ▼                      ▼
        │      knowledge/scores/         Aperitif.no             Vivino
        │      (kuratert, høyest         (faglig norsk)          (crowd)
        │       tillit)
        │            │                          │                      │
        │            └──────────────────────────┴──────────────────────┘
        │                                       ▼
        │                            Kombiner: kuratert > Aperitif > Vivino
        │                            + peer-percentile (Polet fasett-API)
        │                                       ▼
        ▼                                value_verdict + summary
Claude syntetiserer anbefaling med [PRØVD] / [LIKNENDE] / [NYTT]-merke
```

**For feedback-loop:**

```
Bruker korrigerer eller bekrefter
        │
        ├─► Spesifikk vin / drue / region preferanse  → smaksprofil.md
        ├─► Prosess-feil eller regel-misforståelse   → tasks/lessons.md
        └─► Bruker-spesifikt notat i deep-knowledge  → FLYTT til smaksprofil.md
```

## Cache-hierarkiet

Alt caches på disk i `~/.cache/sommelier/`. Cache er prosess-uavhengig (delt mellom alle Claude-økter for samme bruker).

| Cache | TTL | Lokasjon | Hvorfor TTL er valgt slik |
|---|---|---|---|
| Polet `search()` | 24 t | `search_*.json` | Polets katalog er stabil dag-til-dag |
| Polet `search_with_facets()` | 24 t | `search_facets_*.json` | Samme — fasett-resultater varierer med slipps |
| Polet `get_product_details()` | 7 d | `details_*.json` | Klokker/druer endres knapt; pris er mer flyktig men hentes fra search() |
| Vivino-lookup | 7 d | `vivino/*.json` | Crowd-rating drifter sakte |
| Aperitif-score | 14 d | `aperitif/score_*.json` | Faglig vurdering ratet én gang, oppdateres ikke |
| Aperitif-sitemap | 30 d | `aperitif/sitemap_index.json` | URL-katalog endrer seg lite; bootstrap koster ~34 HTTP-kall, så vil ikke gjøre det ofte |
| `compute_value_score()` | 24 t | `value_score/v1_*.json` | Polet-pris kan endres dag-til-dag; *priser* er den minst stabile inputen |
| `tools/scores.index()` | LRU prosess-lokal | (in-memory) | 422 entries parser på 50 ms; ikke verdt disk-cache nå |

Cache-mappa kan slettes når som helst — alt rebuildes lazily.

## Performance-baseline

Målinger gjort 2026-05-14 etter optimaliserings-økten.

| Operasjon | Cold cache | Warm cache |
|---|---:|---:|
| Polet `search()` | 2.4 s | 15 ms |
| `tools.scores.index()` | 50 ms | <1 ms (lru) |
| `_peer_percentile` (fasett-API) | 160 ms | <1 ms |
| `get_aperitif_score` (kjent vin) | 1–2 s | <50 ms |
| `get_aperitif_score` (kald sitemap) | ~35 s | (engangskostnad per 30 d) |
| `compute_value_score` full (typisk) | ~10 s | <50 ms |
| Full test-suite (31 tester) | 1–2 s | 0.9 s |

Worst-case `compute_value_score` cold-cold (alt kalt, bootstrap kreves): ~35 s (Aperitif-sitemap dominerer). Vanlig praksis: bootstrap har skjedd siste 30 d, så reell cold-path er ~10 s.

## Architecture Decision Records (ADR)

Hver ADR har: **Status** (Accepted / Superseded / Deprecated), **Kontekst**, **Beslutning**, **Konsekvenser**, og evt **Alternativer vurdert**.

---

### ADR-001: Markdown som format for kritiker-score-DB

**Status:** Accepted (2026-05-13)

**Kontekst.** Vi har 422 kritiker-scorer fra DN, fordelt på 5 tester (Maislipp rosé, Maislippets 25 beste, musserende-nyheter, tysklandslipp, 17. mai-handleliste). Antallet vil vokse med ~50–200 per Polet-slipp.

**Beslutning.** Lagre som markdown-filer i `knowledge/scores/`, én fil per kilde. Heading-format `### [<score>] <navn> — Varenummer <varenr>` + frontmatter med metadata. Parses av `tools/scores.py` via regex.

**Konsekvenser.**
- ✅ Filer er menneskelig appendable og diff-able i Git
- ✅ Ingen build-step, ingen DB-tooling
- ✅ INDEX.md fungerer som innholdsfortegnelse
- ⚠️ Regex-parsing skjør hvis schema drifter — mitigert ved `test_every_score_file_fully_parsed` (innholds-test)
- ⚠️ Lever på grensen mellom `data/` og `knowledge/` (se ADR-002)

**Alternativer vurdert.** SQLite — forkastet for nå. Verdt å revurdere ved 5000+ entries eller når flere kilder skal støttes med tett kobling.

---

### ADR-002: Score-DB plasseres i `knowledge/`, ikke `data/`

**Status:** Accepted med flagg (2026-05-13)

**Kontekst.** `knowledge/scores/` er strukturelt en database (varenr → score-rader), men lagres som markdown. Det krysser grensen mellom "knowledge = bruker-syntese, alltid lastet" og "data = objektive fakta, eksterne".

**Beslutning.** Behold i `knowledge/scores/` så lenge:
1. Antallet kilder er overkommelig (<20)
2. Markdown forblir det primære grensesnittet for å legge til en kilde

**Konsekvenser.**
- ✅ Konsistent med "markdown-først"-filosofi for menneskelig vedlikehold
- ✅ `knowledge/scores/INDEX.md` fungerer som routing/dokumentasjon
- ⚠️ Bryter med "knowledge skal være bruker-syntese, ikke objektive data"
- ⚠️ Vil bli problematisk ved 5000+ entries eller hvis vi vil indeksere på andre dimensjoner enn varenr

**Trigger for å revurdere.** Når score-DB-en passerer ~2000 entries eller når en annen ikke-varenr-indeks blir nødvendig (f.eks. produsent-rangering).

---

### ADR-003: Tre-tier kvalitets-hierarki i `value_score`

**Status:** Accepted (2026-05-13)

**Kontekst.** Tre kvalitets-signaler er tilgjengelig per vin: kuratert score (DN m.fl.), Aperitif.no faglig, Vivino crowd. De konflikter ofte.

**Beslutning.** Prioritering: **kuratert > Aperitif > Vivino**. `value_verdict` styres av den høyeste tilgjengelige tieren; lavere kilder vises i `summary` for transparens, men driver ikke konklusjonen.

**Konsekvenser.**
- ✅ Brukerens egne valgte kilder (markdown-DB) overstyrer
- ✅ Faglig norsk vurdering vinner over crowd-støy
- ✅ Vivino-data er ikke kastet — bare degradert
- ⚠️ Hvis en kuratert kilde er én tidlig spotsjekk, kan den feilaktig overstyre flere etablerte Aperitif-vurderinger. Mitigér: ikke legg inn enkelt-notater i score-DB-en, kun systematiske tester

**Implementering.** `tools/value_score.py:_combine_quality()`.

---

### ADR-004: `LOGIC_VERSION` i value_score-cache-nøkkel

**Status:** Accepted (2026-05-14)

**Kontekst.** Disk-cache for `compute_value_score` lagrer hele verdivurderingen. Hvis vi endrer `_value_verdict()`-algoritmen, vil gammel cache returnere gammel logikk.

**Beslutning.** Prefiks cache-filnavn med `LOGIC_VERSION = "v1"`. Bump versjonen ved endring av scoring-logikk — det invaliderer all eksisterende cache automatisk.

**Konsekvenser.**
- ✅ Trygt å iterere på `_value_verdict` uten å manuelt slette cache
- ✅ Cache-fil-prefiks gjør det åpenbart hvilken logikk-versjon resultatet er beregnet med
- ⚠️ Manuelt ansvar å huske å bumpe versjonen ved logikk-endringer

**Implementering.** `tools/value_score.py:_value_cache_path()`.

---

### ADR-005: 24 t TTL for value_score-cache (ikke 7 d)

**Status:** Accepted (2026-05-14, erstatter 7 d)

**Kontekst.** Innledende implementering hadde 7 d TTL. Polet-priser kan endres på dag-basis (slipps, nye årganger, utgåtte varer), og pris er en nøkkel-input til verdict.

**Beslutning.** TTL = 24 t.

**Konsekvenser.**
- ✅ Pris-relaterte verdicts holder seg friske
- ✅ Cache er fortsatt nyttig innenfor én session/dag
- ⚠️ Flere cache-misses sammenlignet med 7 d
- ⚠️ Aperitif/Vivino lookups skjer oftere selv om de individuelt har lengre TTL — value_score-cachen frigjør ikke for tidlig

---

### ADR-006: Cache skippes når flagg-kombinasjon er ikke-default

**Status:** Accepted (2026-05-14)

**Kontekst.** `compute_value_score(..., fetch_vivino=False)` returnerer et resultat *uten* Vivino. Hvis dette caches, vil en senere standard-call returnere det stale halv-resultatet.

**Beslutning.** `use_cache_now = use_cache and fetch_vivino and fetch_aperitif`. Bare default-kombinasjonen leses fra og skrives til cache.

**Konsekvenser.**
- ✅ Ingen cache-poisoning
- ✅ Eksperimentelle kall (fetch_x=False) påvirker ikke produksjons-cache
- ⚠️ Eksperimentelle kall får ikke cache-fordel selv ved gjentagelse

---

### ADR-007: Parallel I/O i `compute_value_score`

**Status:** Accepted (2026-05-14)

**Kontekst.** Vivino-lookup, Aperitif-lookup og peer-percentile-beregning er tre uavhengige I/O-bound operasjoner. Sekvensielt: ~10 s cold path.

**Beslutning.** `concurrent.futures.ThreadPoolExecutor(max_workers=3)` rundt de tre kallene. `get_user_scores` (lokal) holdes sekvensiell før.

**Konsekvenser.**
- ✅ ~3× speedup på cold path
- ✅ GIL ikke et problem siden alle tre er `requests.get`
- ⚠️ Stacktraces ved feil er pakket i `Future.result()` — litt mer kryptiske
- ⚠️ Tre samtidige TCP-forbindelser i stedet for én — irrelevant for én bruker

---

### ADR-008: Aperitif-throttle som "min mellom"-modell, ikke "før hver"

**Status:** Accepted (2026-05-14)

**Kontekst.** Original `_http_get` hadde `time.sleep(1.0)` *før* hvert kall. Worst case: 5 kandidat-URLer × (1 s + 1 s HTTP) sekvensielt = 10 s, og enda mer ved sitemap-bootstrap (34 kall × 1 s + HTTP).

**Beslutning.** Spor globalt `_LAST_HTTP_AT`. Sleep kun hvis `delta < REQUEST_DELAY`. Sett `REQUEST_DELAY = 0.25 s`.

**Konsekvenser.**
- ✅ Første kall i en session er aldri unødvendig forsinket
- ✅ Topphastighet 4 req/s ved kontinuerlige kall — fortsatt høflig
- ⚠️ Hvis vi noensinne bulk-scorer 50+ viner i én session, treffer 12 s × 0.25 s = 3 s nedre grense raskere enn før (40 % av total tid blir sleep)
- ⚠️ Aperitif kan introdusere rate-limiting hvis bruksmønsteret endrer seg

---

### ADR-009: Polet fasett-API i `_peer_percentile` (ikke 3 fritekstsøk)

**Status:** Accepted (2026-05-14)

**Kontekst.** Original implementasjon brukte 3 fritekstsøk (district, country, category) + lokal `filter_results`-doble-pass. 2.9 s warm path, 3 s+ cold.

**Beslutning.** Bruk Polets Hybris-style fasett-API: `GET /vmpws/v2/vmp/products/search?q=:relevance:mainCategory:rødvin:mainCountry:italia`. Behold gammel algoritme som `_peer_percentile_legacy` for bakoverkompatibilitet (når caller passerer `peer_search_terms`).

**Konsekvenser.**
- ✅ 1 HTTP-kall vs 3
- ✅ Cold path: 3 s → 0.16 s
- ✅ Peers er Polet-sortert (relevance), mer presis enn vår lokale filtrering
- ⚠️ Avhengig av Hybris-syntaks — sårbar for Polet-redesign
- ⚠️ API capper 24 per side selv ved `pageSize=50`; vi har valgt å ikke paginere

**Gotcha — kostbar erfaring.** Fasett-verdiene må være `.code`-feltet (lowercase: `rødvin`, `italia`), ikke `.name` (`Rødvin`, `Italia`). Store bokstaver gir 0 treff stille.

---

### ADR-010: Pure parser-funksjon skilt ut fra `get_product_details`

**Status:** Accepted (2026-05-14)

**Kontekst.** `get_product_details` blandet HTTP-fetch, disk-cache og HTML-parsing i én funksjon. Parsingen er 12+ regex over Polets HTML — den klart skjøreste delen av kodebasen og umulig å teste uten nettverk.

**Beslutning.** Skill ut `parse_product_html(html: str) -> dict` som pure funksjon. `get_product_details` holder HTTP + cache.

**Konsekvenser.**
- ✅ Parser kan testes mot pinned HTML-fixture (se ADR-011)
- ✅ Mulig å re-parse cached HTML hvis vi senere vil hente ut nye felt
- ✅ Klarere separation of concerns

---

### ADR-011: HTML-fixture-test for Polet-drift

**Status:** Accepted (2026-05-14)

**Kontekst.** Polet kommer sannsynligvis til å redesigne sjekkout/produkt-sidene innen 12 måneder. Når det skjer, vil regex-parserne i `parse_product_html` returnere null eller feil verdier — *stille*. Brukeren oppdager det først når en anbefaling mangler klokker.

**Beslutning.** Pin én produktside (`tests/fixtures/vinmonopolet/fenocchio_barbera_alba_superiore.html`, 41 kB) som drift-snapshot. Test 14 assertions mot kjente verdier (Fylde=8, Friskhet=9, drue=Barbera, stil="Frisk og fruktig", etc.). Refresh-instruksen ligger i docstring i `tests/test_vinmonopolet_html_fixture.py`.

**Hvorfor Fenocchio.** Brukerens 4.6-vin (toppen av Vivino-historikken) — godt forankret, hvis den parsing-feiler er det åpenbart.

**Konsekvenser.**
- ✅ Polet-drift gir umiddelbart en synlig pytest-feil med klar melding
- ✅ Tester kjører offline, raskt (<1 s)
- ⚠️ Manuelt arbeid å refreshe fixture når Polet endrer DOM legitimt
- ⚠️ Bare én vin er pinned — andre produkttyper (musserende, hvitvin, øl) kan ha andre DOM-mønstre

**Mulig utvidelse.** Pin én vin per vintype (rødvin/hvitvin/rosévin/musserende/øl) for bedre dekning.

---

### ADR-012: Knowledge-merge: rammeverk-filer inn i kjernefilene

**Status:** Accepted (2026-05-14, erstatter to-fils-struktur)

**Kontekst.** Vi hadde fire alltid-lastet filer for fagrammeverk: `sommelier.md` + `vinmonopolet_rammeverk.md` for vin, `cicerone.md` + `ol_rammeverk.md` for øl. Asymmetrisk og ekstra-load.

**Beslutning.** Slå `vinmonopolet_rammeverk.md` inn i `sommelier.md` som ny seksjon. Symmetrisk: `ol_rammeverk.md` → `cicerone.md`. De gamle filene slettes.

**Konsekvenser.**
- ✅ ~6 100 tokens spart per melding (alltid-lastet)
- ✅ Symmetrisk struktur for vin og øl
- ⚠️ Resulterende filer er større (sommelier.md ~360 linjer)
- ⚠️ Referanser i tidligere notater (lessons.md, deep-knowledge) måtte oppdateres

---

### ADR-013: Innholds-baserte tester (fil-agnostiske)

**Status:** Accepted (2026-05-14)

**Kontekst.** Tester som hardkoder filnavn ("BJCP må finnes i `knowledge/ol_rammeverk.md`") brekker på legitime refactors. Etter ADR-012 ble fila slettet.

**Beslutning.** Tester søker etter *innhold* på tvers av kataloger ("BJCP må finnes et sted i `knowledge/`"). Filnavn-baserte tester kun for filer som er garanterte invariant (sommelier.md, cicerone.md, smaksprofil.md).

**Konsekvenser.**
- ✅ Tester overlever refactors uten endring
- ✅ Refactor-agenter kan tørge eksisterende tester som regression-vern
- ⚠️ Mindre presist hvor en regresjon ligger når en test feiler

**Implementering.** `tests/test_knowledge_content.py`.

---

### ADR-014: CLAUDE.md-trimming — fjern duplikat, behold synlighet

**Status:** Accepted (2026-05-14)

**Kontekst.** CLAUDE.md hadde grodd til ~17 KB med duplisert innhold fra `knowledge/sommelier.md` (workflow, deep-knowledge-tabell) og `knowledge/smaksprofil.md` (blindspots, pris-soner).

**Beslutning.** Fjern duplikat *kun* der den autoritative kilden alltid leses som del av workflow. Behold seksjoner der synlighet i autoload-prompt har operasjonell verdi:
- Beholdt: Pris-soner (operasjonell beslutning), Workflow, Feedback-løkken-regler (cicerone har ikke samme detaljer)
- Trimmet: Filer-tabell (peker til INDEX.md), kode-eksempel for vinmonopolet.py (lever i tool docstring), Blindspots-liste (komprimert med pointer til smaksprofil.md)

**Konsekvenser.**
- ✅ ~6 100 tokens spart per melding
- ⚠️ Tap av synlighet for kommandoer som tidligere stod i CLAUDE.md
- ⚠️ Workflow må følges troverdig — hvis Claude hopper over "les sommelier.md", mister hun deep-knowledge-router

**Lærdom.** I LLM-workflows er DRY-instinkter feil når kostnaden av å glemme er høy og duplikasjon bare koster tokens. Behold duplikat der det er load-bearing for korrekt oppførsel.

---

### ADR-015: User-fit-score v0 — rule-based tier classifier

**Status:** Accepted (2026-05-14)

**Kontekst.** Smaksprofilen er kun konsultert per-vin på inferens-tid. Batch-spørringer ("topp 10 fra slipp", "alle Polet-røde under 400 kr som passer meg") er praktisk umulige. Vi trenger en pre-computet operasjon over smaksprofil × score-DB. Se [roadmap.md](../roadmap.md) for full versjonsplan (v0/v1/v2).

**Beslutning.** Implementér v0 først: en deterministisk regelmotor som parser `knowledge/smaksprofil.md` og klassifiserer hver vin i `data/user_fit/v0.json` i én av fem tier-bøtter (`very_fit | fit | neutral | risky | no_go`). Ingen ML, ingen lærte vekter, ingen feature-vektor. Bare seks regler i prioritets-rekkefølge.

**Hvorfor regelmotor først.** (a) Trivielt å bygge og verifisere, (b) eliminerer åpenbare no-go før Claude reasoning, (c) tier-vokabular matcher eksisterende `[PRØVD]/[LIKNENDE]/[NYTT]`-konvensjon, (d) etablerer pipeline-arkitektur (generator + writer + reader) som v1/v2 kan utvide.

**Konsekvenser.**
- ✅ Filtrerer ut Provence-rosé / generisk billig Burgund / no-go-liste automatisk
- ✅ smaksprofil-endringer propagerer til alle 422 viner ved én profile_stats.py-kjøring
- ✅ Fullt forklarbar per regel (`rule_fired`-felt i output)
- ⚠️ Bare 5 bøtter — ingen rangering innenfor tier (eksplisitt v0-begrensning, motiverer v1 hvis nødvendig)
- ⚠️ Bruker ikke klokker (krever Polet-detail-fetch — flyttet til v1)

**Arkitekturføringer.**
- Ny modul `tools/user_fit.py` — egen modul, ikke utvidelse av `value_score.py`
- Output i `data/user_fit/v0.json` — strukturert data, ikke `knowledge/scores/` (respekterer ADR-002)
- Regenereres som biprodukt av `profile_stats.py` (idempotent, samme mønster som auto-derived-blokken i smaksprofil)
- Versjons-prefiks i filnavn (`v0.json`) — neste versjon skriver til `v1.json` parallelt, enkelt å sammenligne
- Fit-score er **ortogonalt** til value-score. Ikke bland akser i output.

**Alternativer vurdert.** v1 (weighted sum) og v2 (Ridge-lærte vekter) er dokumentert i roadmap.md som forventede oppfølgings-versjoner. TF-IDF + Rocchio cosine ble vurdert og forkastet — se roadmap.

---

### ADR-016: No-filter-bubble-prinsippet for user-fit-score

**Status:** Accepted (2026-05-14)

**Kontekst.** Den naturlige integrasjons-instinkten ved user-fit-score er å filtrere bort `no_go` og `risky` fra default-resultater — fjerne "dårlige treff" før brukeren ser dem. Dette skaper en *filter bubble*: brukeren eksponeres aldri for objektivt høyt-rangerte viner som ligger i en kategori smaksprofilen er svak på (f.eks. naturvin, Provence-rosé, ukjent New World).

**Beslutning.** Default-oppførsel: rangér batch-spørringer etter **objektiv kvalitet (kritiker-score)**, vis tier som *merke* ved siden av. Aldri auto-filtrér bort `no_go` eller `risky` med mindre brukeren eksplisitt ber om personalisert filtrering.

**Hvorfor.**
- Brukeren har eksplisitt sagt han ikke vil bli skjermet for "objektivt gode viner"
- Tier-systemet er bygd for å *advare*, ikke skjule
- Eksponering for high-score-wines i blindspots er den mest verdifulle utforsknings-mekanismen — det er der smak utvides
- Filter-bubble-anti-patternet er veldokumentert i recsys-litteratur (Pariser 2011, "The Filter Bubble") og særlig alvorlig for én-bruker-systemer der ingen kollektiv intelligens kompenserer

**Implementering.**
- Default-rangering: `sorted(wines, key=lambda w: -w.critic_score)` med tier vist som label/merke
- Tier-first-rangering tillates **kun** når brukeren eksplisitt signaliserer det: "noe jeg garantert vil like", "trygge valg", "ingen risk", "filtrér bort risky" — disse aktiverer en sekundær view
- Eksplisitt no-go-flagg får aldri skjule en vin fra default-output, men må vises tydelig (`⚠ no_go: matcher no-go-listen`)

**Konsekvenser.**
- ✅ Brukeren ser hele kataloget med tier-veiledning, beholder agency
- ✅ Naturlig utforsknings-vektor — høy-score-blindspot-viner forblir synlige
- ✅ Smaksprofilen kan ikke "blokke" preferanse-utvidelse stille
- ⚠️ Lister blir lengre / mindre kuraterte i default-view — krever god UI/output-formatering med tydelig tier-merking
- ⚠️ Brukeren må gjøre den endelige beslutningen — fit-tier reduserer ikke kognitiv last fullt ut

**Eksempel (DN Maislipp rosé):**
```
Default (sortert etter critic):
  92p [fit]      Guy Charlemagne Brut Rosé
  92p [fit]      Charles Heidsieck Rosé Réserve
  91p [neutral]  Tschida Himmel auf Erden Rosé 2024   ← naturvin, blindspot
  90p [fit]      André Clouet Rosé
  86p [risky]    Dom. Oddo Provence Rosé 2025         ⚠ Provence-snitt 2.38

Personalisert (kun ved eksplisitt request):
  92p [fit]      Guy Charlemagne
  92p [fit]      Charles Heidsieck
  90p [fit]      André Clouet
```

**Alternativer vurdert.** Mildt penalty på risky (subtract 5 fra critic-score) — forkastet fordi vilkårlig vektingen tilslører hvilken vin som *faktisk* er høyest-rangert. To kolonner side-om-side — forkastet pga informasjons-overload.

**Relatert.** [ADR-015](#adr-015-user-fit-score-v0--rule-based-tier-classifier) (user-fit-score-mekanikken som dette prinsippet styrer bruken av).

---

## Kjent teknisk gjeld

Ranket etter risiko × sannsynlighet.

| # | Gjeld | Hvorfor det er gjeld | Når det blir et problem | Trigger for å adressere |
|---|---|---|---|---|
| 1 | Polet HTML-scraping i `parse_product_html` | 12 regex over Polets DOM — sårbar for redesign | Når Polet kommer med ny webshop (sannsynlig <12 mnd) | Fixture-test feiler (allerede på plass — ADR-011) |
| 2 | `knowledge/scores/` krysser data/knowledge-grensen (ADR-002) | Strukturelt data, lagret som knowledge | Ved 2000+ entries eller behov for sekundær-indeks | Manuell vurdering hver 6. mnd |
| 3 | Aperitif sitemap-bootstrap er 34 HTTP-kall | Cold path ved første kjøring eller etter 30 d | Når brukeren stiller første Aperitif-spørsmål på over en måned | Vurder lazy-pre-fetch i `tools/aperitif.py` |
| 4 | `tools/scores.index()` re-parser 422 entries per prosess | `lru_cache` er prosess-lokal; Bash-call = ny prosess | Ved 5000+ entries (>500 ms parse-tid) | Bygg `knowledge/scores/_index.json` ved git pre-commit |
| 5 | `find_similar_by_clocks` er sekvensiell | Henter detaljer N×M for kandidater | Ved bulk-similarity-søk | Parallellisér med ThreadPoolExecutor |
| 6 | Klokke-profil-tabellen i `smaksprofil.md` har bare 2 oppføringer | Klokke-similarity er kvasi-teater med n=2 | Allerede et problem ved similarity-spørringer | Akkumulér klokker som biprodukt (per lessons 2026-05-12) |
| 7 | Reference-PDFs i `data/reference/` brukes ikke i workflow | 11 MB død last | Aldri akutt, men tar opp repo-plass | Slett ved neste cleanup-runde |
| 8 | `~/.cache/sommelier/` har ingen GC | Vokser monotont | Ved >10 000 cache-filer (~50 MB) | Skriv `tools/cache_gc.py` med mtime-basert cleanup |

## Når du gjør en ny audit/refactor

1. Les denne fila først — sjekk om endringen kolliderer med en eksisterende ADR
2. Hvis ja: skriv en ny ADR som superseder den gamle, ikke bare endre koden
3. Hvis nei: vurder om endringen er stor nok til å fortjene sin egen ADR
4. Kjør `python3 -m pytest tests/ -v` før og etter — fang regressioner umiddelbart
5. Hvis du endrer fundamentalt på et lag (knowledge-struktur, cache-strategi): oppdater både denne fila OG `README.md`
