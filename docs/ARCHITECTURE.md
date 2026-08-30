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

### ADR-017: Eval-harness før v1 — modell-agnostisk rangerings-måling

**Status:** Accepted (2026-06-08)

**Kontekst.** Roadmap-en eskalerer user-fit fra v0 (regler) til v1 (vektet sum) til v2 (Ridge). Triggeren mellom versjonene var subjektiv ("mangler jeg rangering innenfor tier?"). Uten en måte å måle om en ny modell faktisk *slår* den forrige, ville v1/v2 være vibes-drevet — og med n=111 single-user-ratinger er overfitting-risikoen reell.

**Beslutning.** Bygg evaluerings-harnessen (`tools/eval_fit.py`) som et eget, modell-agnostisk steg *før* v1. En "scorer" er `Callable[[dict], float | None]`. Harnessen måler hver scorer mot brukerens egne `Your rating` via Spearman + NDCG@5 på en tidsbasert train/test-split (`Scan date < 2024-01-01`), med fire baselines (random, vivino_avg, style_avg, critic) og dagens v0-tier konvertert til ordinal score.

**Hvorfor før v1.** Da blir "bygg v1?" et empirisk spørsmål, ikke en magefølelse. v0-vs-baseline-tallene avgjør om v1 i det hele tatt er rettferdiggjort.

**Konsekvenser.**
- ✅ Første kjøring viste **v0_tier Spearman +0.59** — slår style_avg (+0.06) og random (+0.30). v0 fanger reell signal; **v1-triggeren er ikke oppfylt**.
- ✅ **vivino_avg (+0.63) er en overraskende sterk baseline** — listen en v1 må slå er høyere enn roadmap antok.
- ✅ Avslørte at critic-DB-en (Polet-varenr) overlapper **1/111** med brukerens drukne viner — rapportert som warning, ikke skjult.
- ⚠️ n_test=24 → alle metrikker er indikative, ikke konklusive. Harnessen printer stående advarsel.

**Arkitekturføringer.**
- Ren stdlib (scipy finnes ikke) — average-rank Spearman håndterer de mange ties i ratingene.
- Determinisme er hard krav: seedet PRNG for random-baseline, deterministisk lockbox-valg (ingen `random`/`Date.now`). Gjør resultater testbare.
- Lockbox rapporteres BÅDE som `test_full` og `test_ex_lockbox` — på statisk v0 koster lockbox signal uten å beskytte mot noe; hard utelukkelse håndheves først ved v1-tuning.
- Critic- og v0-baselines scores on-the-fly på CSV-radene (ingen varenr-join mulig).

**Alternativer vurdert.** Bygge v1 direkte og evaluere etterpå — forkastet: da har man ingen baseline å vurdere v1 mot, og fristelsen til å rasjonalisere et dårlig resultat er stor. p-verdier — forkastet: meningsløst på n=24 uten scipy.

---

### ADR-018: Øl-fit deriverer fra Untappd-CSV, ikke fra smaksprofil-markdown

**Status:** Accepted (2026-06-08)

**Kontekst.** Vin-fit (ADR-015) parser `knowledge/smaksprofil.md` fordi de *kuraterte* preferanse-seksjonene (no-go, druer du liker, regioner) bare finnes der. Øl-fit trenger en analog tier-klassifiser, men øl har ingen Polet-katalog å klassifisere — den klassifiserer selve BJCP-stilfamiliene (~24 fra `untappd_stats.STYLE_FAMILIES`).

**Beslutning.** `tools/beer_fit.py` deriverer familie-statistikken **direkte fra Untappd-CSV** via `untappd_stats.agg_by_family()`, ikke ved å re-parse den rendrede øl-blokken i smaksprofil.md. beer_v0.json og øl-blokken er sibling-artefakter fra samme kilde (CSV), ingen avhenger av å parse den andre.

**Hvorfor avvik fra vin-mønsteret.** Øl-blokken er 100 % auto-derivert — det finnes ingen kuraterte øl-seksjoner å miste ved å hoppe over markdown-parsing. Og re-parsing av rendret markdown var den skjøre veien: doble «Bekymringer»/«Blindspots»-overskrifter (vin + øl) i samme dokument, og vinens tabellparser kaster N-kolonnen som terskel-logikken trenger. Derivering fra CSV gjenbruker testet aggregeringskode og holder beer_v0.json alltid konsistent med kilden.

**Konsekvenser.**
- ✅ Ingen markdown-parsing-skjørhet, ingen duplikat-heading-felle.
- ✅ Stilfamilie→tier alltid synkron med CSV; auto-regenereres av `untappd_stats.main()`.
- ✅ Gjenbruker `classify_style()` som mapper — ingen divergens mellom blokk og fit.
- ⚠️ Hvis en kuratert øl-seksjon (f.eks. øl-no-go) innføres senere, må den eksponeres *programmatisk* (ikke kun i markdown), ellers ser beer_fit den ikke. `BEER_NO_GO`-konstanten ligger klar for dette.
- ⚠️ very_fit-terskel løsnet til n≥3 + snitt≥3.85 (fra vinens n≥3 + 4.0) fordi øl-datasettet er tynnere (~90 check-ins) — brukerbeslutning, dokumentert i kode.

**Arkitekturføringer.**
- Output `data/user_fit/beer_v0.json` indeksert på stilfamilie (ikke varenr) — respekterer ADR-002 (strukturert data i `data/`).
- `classify_beer()`-bro for batch: manuell innliming av øl → `classify_style` → tier. Ingen scraper i v0 (det finnes ingen øl-katalog å iterere).
- Blindspot (n≤1) gir aldri very_fit selv ved høyt snitt — samme anti-falsk-presisjon som vin-fit confidence-cap.

**Relatert.** [ADR-015](#adr-015-user-fit-score-v0--rule-based-tier-classifier) (vin-fit-mønsteret dette speiler med ett bevisst avvik), [ADR-002](#adr-002-score-db-plasseres-i-knowledge-ikke-data) (data/knowledge-grensen).

---

### ADR-019: Datatilgang via ekte nettleser — Vivino og Polet bak WAF

**Status:** Accepted (2026-06-08)

**Kontekst.** To eksterne kilder prosjektet er bygd på har strammet bot-vernet siden tool-ene ble skrevet:
- **Vinmonopolet webshop-API** (`vmpws`, anbefalt i `knowledge/_archive/rapport.md`) svarer nå **403** på `requests`-kall — WAF gjenkjenner ikke-nettleser-TLS-fingeravtrykk og header-profil. Rammer `tools/vinmonopolet.py` (search, get_product_details) og alt som bygger på det (`value_score.py`, `find_similar_by_clocks`).
- **Vivino-profilen** krever innlogget sesjon og blokkerer `WebFetch` (403).
- Vinmonopolets **offentlige produkt-CSV** er avviklet (2026). Åpent API gir kun varenr + kortnavn (ingen pris/region); presse-API har rik data men krever dokumentert pressebehov; lukket API er kun for grossister.

**Beslutning.** Den fungerende, felles veien til begge kilder er en **ekte nettleser (Playwright)**: korrekt TLS-fingeravtrykk, fullt header-sett, JS-kjøring og cookie-håndtering passerer WAF. Standardiser på ett delt henter-lag som både Vivino-synk og Polet bruker, i to moduser — bulk-sveip (bredde → lokalt snapshot) + on-demand (dybde → produktside). *(Konkret fikse-plan utarbeides i egen sesjon — se `tasks/todo.md`.)*

**Konsekvenser.**
- ✅ Eneste vei som faktisk virker for rik Polet-data + Vivino-historikk i dag.
- ✅ Et lokalt katalog-snapshot eliminerer per-spørring-skraping og WAF-eksponering for bredde-spørringer.
- ⚠️ Webshop-API er ikke en av Polets tre sanksjonerte API-er — bruk er ToS-gråsone. Akseptert for personlig, lavt-volum bruk; den lovlige rik-data-veien (presse-API) er reelt stengt for en privatperson.
- ⚠️ DOM-avhengig — trenger drift-vern (fixture-test, jf. [ADR-011](#adr-011-html-fixture-test-for-polet-drift)).
- ⚠️ Playwright er tyngre enn `requests` (browser-oppstart) → snapshot for bredde, ikke per-spørring.

**Alternativer vurdert.** (a) Spoofe browser-headere i `requests` — forkastet: WAF sjekker TLS-fingeravtrykk, blir katt-og-mus. (b) Offisiell åpen CSV / API — forkastet: CSV avviklet, åpent API for tynt (kun varenr+navn). (c) Presse-API — forkastet: krever pressebehov-søknad brukeren ikke kan dokumentere.

**Relatert.** Teknisk gjeld #0 (vmpws WAF-blokk), [ADR-011](#adr-011-html-fixture-test-for-polet-drift) (Polet-drift-vern), roadmap § Vivino auto-sync.

---

### ADR-020: Repo-committet Polet-snapshot + cross-device (desktop refresh / Android read-only)

**Status:** Accepted (2026-06-08). **Refresh-asymmetrien delvis superseded av [ADR-021](#adr-021-remote-browser-via-cdp--device-agnostisk-refresh) (2026-06-09)** — snapshot-modellen (lagring, validering, alders-merking) står uendret, men «desktop = refresh / Android = read-only»-rollene er erstattet av device-agnostisk remote-browser-refresh.

**Kontekst.** [ADR-019](#adr-019-datatilgang-via-ekte-nettleser--vivino-og-polet-bak-waf) etablerte at den eneste fungerende veien forbi WAF-en er en ekte nettleser, og skisserte «lokalt snapshot for bredde + on-demand dybde» — men lot lagringen og henter-mekanismen være uavklart. Samtidig kjører brukeren Claude Code på **to enheter**: desktop (Mac med Playwright-MCP + lokal chromium) og Android (Claude Code + repo, men **ingen nettleser**). Et snapshot i `~/.cache/sommelier/` løser ikke dette — cachen er enhets-lokal og deles ikke, så Android ville stått uten Polet-data overhodet. Den åpne beslutningen fra `tasks/todo.md` (Python-Playwright vs. Claude-drevet Playwright-MCP) måtte også avgjøres.

**Beslutning.** Flytt varig Polet-data **inn i repoet** under `data/polet/`, og driv refresh via **Claude-drevet Playwright-MCP** (ikke en Python-Playwright-avhengighet). Datamodellen er tre-delt og selv-identifiserende:

- `data/polet/catalog.ndjson` — bredde: ett produkt per linje i rik `vmpws`-shape, sortert på `code`, hver med `fetched_at`.
- `data/polet/catalog_meta.json` — `generated_at`, `count`, `category_coverage`.
- `data/polet/details/<varenr>.json` — dybde: klokker/druer/stil/lukt/smak, hver med selv-identifiserende `code`/`url`/`fetched_at`.
- `data/polet/_orphan_details.json` — rekonstruerte klokkedata uten code-mapping, som venter på re-knytting.

`tools/polet_store.py` er det eneste lag-grensesnittet: lesere (`read_catalog`, `lookup`, `query`, `read_details`, `catalog_age_days`, `catalog_generated_at`, `details_fetched_at`), skrive-helpers (`upsert_products`, `save_details`) og exception `PoletRefreshRequired(url, hint)`. Serialiseringen er deterministisk (`sort_keys`, sortert NDJSON) for å unngå git-merge-støy på tvers av enheter.

Cross-device-rollene er asymmetriske og eksplisitte:

- **Desktop = read + REFRESH.** Refresh-ritualet: `browser_navigate` til `https://www.vinmonopolet.no/` (passerer WAF) → `browser_evaluate` med `fetch('/vmpws/v2/vmp/products/search?q=…&pageSize=…')` for bredde (rik JSON) → `fetch(product_url)` for dybde-HTML → mat write-helpers → commit `data/polet/`. Runbook: [`polet_refresh.md`](polet_refresh.md).
- **Android = READ-ONLY** konsument av committet snapshot. Får bredde/klokker/similarity fritt; vin utenfor snapshot gir `PoletRefreshRequired` med «refresh fra desktop»-hint (ikke krasj).

`tools/vinmonopolet.py` leser nå snapshot i stedet for `requests`; cache-miss → `PoletRefreshRequired`. `parse_product_html` er **uendret** (fortsatt fixture-testet, [ADR-011](#adr-011-html-fixture-test-for-polet-drift)). `tools/value_score.py` bumper `LOGIC_VERSION` v1→v2 ([ADR-004](#adr-004-logic_version-i-value_score-cache-nøkkel)), inkluderer snapshot-`generated_at` i cache-nøkkelen, og alders-merker verdict.

**Konsekvenser.**
- ✅ Android får full Polet-funksjonalitet (bredde, klokker, similarity, value) uten nettleser — committet snapshot er felles source-of-truth på tvers av enheter.
- ✅ Ingen ny tung avhengighet: Playwright-MCP finnes allerede på desktop, ingen browser-binær i repoet eller `requirements`.
- ✅ `save_details` har **positiv validering** — krever forventet varenr + navn + (klokke|pris) og avviser WAF-challenge-HTML og DOM-drift før skriving. Dette supplerer fixture-testen ([ADR-011](#adr-011-html-fixture-test-for-polet-drift)): fixture fanger drift i parseren, positiv validering fanger drift/challenge ved skriving til snapshot.
- ✅ Deterministisk serialisering gjør snapshot-diffs linjebaserte og merge-vennlige cross-device.
- ✅ Value-verdict er alders-merket (`snapshot_age_days`, `snapshot_generated_at`); når alderen > 14 dager degraderes språket («Basert på snapshot fra <dato> (X dager gammelt) — pris/lager kan ha endret seg, verifiser på polet.no før kjøp»). `PoletRefreshRequired` svelges ikke — den gir `peer_status=refresh_required` + tydelig summary.
- ⚠️ Snapshot-ferskhet avhenger av **manuell desktop-refresh**. Android kan aldri refreshe selv. Ingen automatisk cron — bruker må kjøre ritualet bevisst.
- ⚠️ `find_similar_by_clocks` hopper over viner som ikke er i snapshot — similarity er begrenset av dekningen.
- ⚠️ Webshop-`vmpws` er fortsatt ToS-gråsone (arvet fra [ADR-019](#adr-019-datatilgang-via-ekte-nettleser--vivino-og-polet-bak-waf)) — akseptert for personlig, lavt-volum bruk.

**Bekreftet transport (2026-06-08).** Browser-`fetch` mot `vmpws`-JSON gir **200 forbi WAF**; `?fields=FULL` gir 400 (droppet); produktside-HTML gir 200 og matcher `parse_product_html`.

**Faktisk seed-resultat.** `tools/seed_polet_store.py` rekonstruerte engangs fra `~/.cache/sommelier/`: **67 katalog-produkter, 4 details mappet, 118 orphans** (de gamle details-URL-ene var overskrevet av cache-TTL, så klokkedata kunne ikke knyttes til varenr automatisk).

**Alternativer vurdert.** **Python-Playwright** (autonomt, headless, testbart) — forkastet: tung avhengighet + browser-binær, og det **hjelper ikke Android** (ingen browser der uansett), så cross-device-problemet ville bestått. **Snapshot i `~/.cache/sommelier/`** — forkastet: enhets-lokal cache deles ikke, Android ville stått uten data. **Polet åpent/presse-API** — fortsatt forkastet av samme grunner som i ADR-019.

**Relatert.** [ADR-019](#adr-019-datatilgang-via-ekte-nettleser--vivino-og-polet-bak-waf) (etablerte «ekte nettleser»-veien; ADR-020 konkretiserer lagring + cross-device), [ADR-009](#adr-009-polet-fasett-api-i-_peer_percentile-ikke-3-fritekstsøk) (kode≠navn i fasett-oppslag), [ADR-011](#adr-011-html-fixture-test-for-polet-drift) (drift-vern, nå supplert av positiv validering i `save_details`), [ADR-004](#adr-004-logic_version-i-value_score-cache-nøkkel) (LOGIC_VERSION-bump), [`polet_refresh.md`](polet_refresh.md) (runbook), teknisk gjeld #0.

---

### ADR-021: Remote browser via CDP — device-agnostisk refresh

**Status:** Accepted (2026-06-09). Superseder refresh-asymmetrien i [ADR-020](#adr-020-repo-committet-polet-snapshot--cross-device-desktop-refresh--android-read-only) (snapshot-modellen selv står uendret).

**Kontekst.** ADR-020 låste refresh til **desktop** fordi den krevde lokal chromium som når Cloudflare *direkte* med en genuin browser-TLS-fingerprint (Android hadde ingen browser → read-only). Det etterlot to problemer: (1) Android kunne aldri refreshe, og (2) en **tredje kjørekontekst** har siden blitt sentral — **Claude Code on the web**, som kjører i en sky-container bak Anthropics Egress Gateway.

Empirisk test i web-containeren (2026-06-09): jeg installerte ekte headless chromium og kjørte refresh-ritualet mot Polet. Resultat:

| Test | Container (lokal chromium bak Egress Gateway) | Remote browser (Browserbase, via CDP) |
|---|---|---|
| Generell egress (example.com) | ✅ 200 | — |
| Forside `vinmonopolet.no` | ✅ 200 (ekte innhold) | ✅ 200 |
| **`/vmpws/` søke-API (bredde)** | ❌ **403 «Sorry, you have been blocked»** | ✅ **200 (rik JSON)** |
| **Produktside-HTML (dybde)** | ❌ **403 «Attention Required \| Cloudflare»** | ✅ 200 |

**Rotårsak.** Egress tvinges gjennom Anthropics Egress Gateway (`issuer: O=Anthropic; CN=Egress Gateway SDS Issuing CA`), som **terminerer og re-originerer TLS**. Cloudflare ser dermed gatewayens datasenter-IP og TLS-fingerprint, ikke chromiums, og hard-blokkerer de bot-beskyttede `/vmpws/`-endepunktene — nettopp dem refresh trenger. Genuin-fingerprint-trikset virker *kun* når chromiums egen TLS når Cloudflare direkte (vanlig desktop). Samme MITM-problem gjelder mange bedriftsproxyer. Web-research bekrefter at Cloudflare rutinemessig flagger datasenter-IP-er.

**Beslutning.** Frikoble refresh fra enheten ved å drive ritualet mot en **remote browser via CDP**. Selve browsingen (forside-nav + same-origin `fetch`) kjører på en remote browser-tjeneste (Browserbase / Browserless) med ren egress og genuin browser-fingerprint, så Cloudflare møter *tjenestens* browser — ikke din lokale proxy. Claude kobler til via Playwright-MCP sin `--cdp-endpoint`. **Registreringen er automatisk og device-agnostisk:** repoet committer en `.mcp.json` som registrerer `playwright`-serveren med `--cdp-endpoint ${POLET_BROWSER_CDP}`. Det eneste per-enhet-steget er å sette env-variabelen `POLET_BROWSER_CDP` (CDP-URL + token) — token bor KUN i env, aldri i repoet. Ingen `claude mcp add`, ingen config-fil-kopiering. **Refresh-ritualets logikk er uendret** (navigate → `browser_evaluate` fetch → `refresh_polet.py` ingest-helpers → `polet_store` validering); kun *hvor browseren kjører* flyttes. Dette er den **foretrukne veien på alle enheter — også desktop** — slik at det finnes én refresh-rutine, ikke device-branching.

MCP-serveren kobler seg til skybrowseren **lazily** — først ved første browser-tool-kall, ikke ved sesjonsstart (verifisert 2026-06-09). I read-sesjoner ligger den dormant og bruker null remote-browser-tid; er `POLET_BROWSER_CDP` usatt (`${POLET_BROWSER_CDP:-}` → tomt), starter serveren rent men dormant og blokkerer ingenting. Det holder Browserbase gratis-tier (~1 browser-time/mnd) trygt — budsjett brukes kun ved faktisk refresh.

**Bekreftet transport (2026-06-09).** Browserbase **gratis-tier** (uten paid residential-proxy) passerer Vinmonopolets Cloudflare: `wss://connect.browserbase.com?apiKey=…` + `connectOverCDP` → forside 200, `/vmpws/`-API 200 (rik JSON). Den statiske auto-session-URL-formen fungerer direkte som MCP `cdpEndpoint` (ingen REST-pre-steg). `proxies:true` krever betalt plan (402), men trengs *ikke* for Vinmonopolet.

**Konsekvenser.**
- ✅ **Device-agnostisk:** desktop, Android og Claude Code on the web refresher identisk — enhver enhet som når CDP-websocketen kan refreshe.
- ✅ **Robust forbi Cloudflare:** WAF-en møter tjenestens genuine browser; uavhengig av lokal egress-vei (MITM-proxy eller ei).
- ✅ **Snapshot-modellen uendret:** ingest, positiv validering, deterministisk serialisering, alders-merking fra ADR-020 står — kun transporten byttes.
- ✅ **Token ut av repoet:** gitignored config + `.example.json`-template; ingen hemmelighet committes.
- ✅ **Gratis i praksis:** Browserbase free-tier (~1 browser-time/mnd) dekker lavvolum månedlig refresh.
- ⚠️ **Ekstern avhengighet + konto:** krever en remote-browser-konto og en token å forvalte per enhet. Polling/høyt volum vil sprenge gratis-tier.
- ⚠️ **Lokal chromium i MITM-miljø kan ikke refreshe** — datasenter-IP/fingerprint hard-blokkeres (bevist). Dokumentert så ingen prøver det på nytt.
- ⚠️ **Desktop med lokal chromium** fungerer fortsatt (genuin fingerprint, direkte egress) og beholdes som no-account nød-utvei, men er ikke standardveien.
- ⚠️ Webshop-`vmpws` er fortsatt ToS-gråsone (arvet fra [ADR-019](#adr-019-datatilgang-via-ekte-nettleser--vivino-og-polet-bak-waf)) — akseptert for personlig, lavvolum bruk.

**Alternativer vurdert.** **Lokal chromium i sky-containeren** — forkastet: Egress Gateway-MITM gir hard 403 (empirisk bevist). **Endre nettverkspolicy til passthrough** — utilstrekkelig alene: selv uten MITM blokkeres datasenter-IP-en av Cloudflare uten residential-proxy. **Termux + headless chromium på Android** — mulig (residential mobil-IP + genuin chromium), men skjørt oppsett og hjelper *ikke* web/sky-sesjonen; remote-CDP dekker alle tre kontekstene med ett oppsett. **Cloudflare Web Bot Auth** (lansert mai 2026, signerte agent-requests) — lovende fremtidig legit-vei, men krever at Vinmonopolet opt-in-er; ikke tilgjengelig nå.

**Relatert.** [ADR-020](#adr-020-repo-committet-polet-snapshot--cross-device-desktop-refresh--android-read-only) (snapshot-modellen denne bygger på), [ADR-019](#adr-019-datatilgang-via-ekte-nettleser--vivino-og-polet-bak-waf) («ekte nettleser»-veien), [ADR-009](#adr-009-polet-fasett-api-i-_peer_percentile-ikke-3-fritekstsøk) (fasett-koder), [`polet_refresh.md`](polet_refresh.md) (runbook), [`polet-mcp.config.example.json`](polet-mcp.config.example.json) (config-template), teknisk gjeld #0a.

---

### ADR-022: Vivino-sync levert — Playwright-MCP-skraping av innlogget profil-feed

**Status:** Accepted (2026-07-02). Realiserer roadmap § «Vivino auto-sync» (planlagt siden 2026-06-08).

**Kontekst.** Roadmapen hadde lenge «Vivino auto-sync» planlagt: metoden var bevist manuelt 2026-06-08, men bevisst utsatt til Polet-snapshotet var stabilt. Den underliggende smerten sto uendret — `data/vivino/full_wine_list.csv` eldes stille fordi Vivino ikke har åpen API, og den offisielle CSV-eksporten må trigges manuelt og lander som e-post-ZIP. Vivino sitter dessuten bak samme type bot-vern som Polet ([ADR-019](#adr-019-datatilgang-via-ekte-nettleser--vivino-og-polet-bak-waf)): innlogget sesjon kreves og `WebFetch`/`requests` gir 403.

**Beslutning.** Pakk den beviste metoden som `tools/vivino_sync.py` med runbook [`vivino_refresh.md`](vivino_refresh.md). Ritualet skraper den **innloggede** Vivino-profil-feeden via Playwright-MCP (samme «ekte nettleser»-vei som Polet): egen rating leses fra stjerne-ikonene ved å summere `icon-N-pct`-klassene og dele på 100 (f.eks. 4× `icon-100-pct` + 1× `icon-40-pct` = 4.4), diffes mot `data/vivino/full_wine_list.csv`, og nye rader merges idempotent. Merge-helperen dedup-er på **Winery + Wine name + Vintage**, så gjentatte kjøringer er trygge. `profile_stats.py` kjøres etterpå slik at den managed blokka i `smaksprofil.md` (og fit-artefaktene) alltid speiler fersk data.

**Konsekvenser.**
- ✅ Staleness fjernes on-demand — synk på kommando, ingen ventetid på e-post-eksport.
- ✅ Idempotent (dedup på winery+wine+vintage) → trygt å re-kjøre uten duplikatrader.
- ✅ Restaurant-viner og andre kilder utenfor Vivino kan fortsatt logges manuelt via `vivino_sync.py` med JSON-input (samme merge-vei).
- ⚠️ Avhengig av **innlogget sesjon** — cookien kan utløpe, da må Kristoffer logge inn på nytt i Playwright-nettleseren.
- ⚠️ DOM-avhengig (stjerne-ikon-klasser, `.user-activity-item`) — samme drift-risiko som Polet ([ADR-011](#adr-011-html-fixture-test-for-polet-drift)); brekker hvis Vivino redesigner feeden.
- ⚠️ ToS-gråsone — kun egen profil, lavt volum (arvet fra [ADR-019](#adr-019-datatilgang-via-ekte-nettleser--vivino-og-polet-bak-waf)).

**Alternativer vurdert.** **Offisiell GDPR-eksport** — forkastet som primærvei: manuell trigging, lander som e-post-ZIP, samme staleness som før. **`requests`/`WebFetch`** — forkastet: WAF gir 403 (bekreftet, jf. ADR-019).

**Relatert.** [ADR-019](#adr-019-datatilgang-via-ekte-nettleser--vivino-og-polet-bak-waf) («ekte nettleser»-veien som denne bruker), [ADR-011](#adr-011-html-fixture-test-for-polet-drift) (DOM-drift-vern), [`vivino_refresh.md`](vivino_refresh.md) (runbook), roadmap § Vivino auto-sync (nå levert).

---

### ADR-023: Live facet-sweep + trait-filtrering + snapshot-ekspansjon

**Status:** Accepted (2026-07-02). **Fasett-listen og «full bredde»-påstanden er superseded av ADR-024 (2026-08-29)** — AND/OR-funnet og modulstrukturen står uendret, men tre av de seks oppgitte trait-fasettene virker ikke, og sveipene som ble kjørt under denne ADR-en var stille avkortet av et `pageSize`-tak. Se korreksjonen under «Funn».

**Kontekst.** Polet-snapshotet var 557 produkter — under 2 % av katalogen (~36k) — og for smalt for reell utforskning. New World-viner manglet helt: søk på Zuccardi/Catena/Mullineux ga `PoletRefreshRequired` fordi de aldri var i snapshotet. Samtidig ville en naiv utvidelse (committe hele katalogen, eller hente details for alt) enten sprenge repoet eller bli rate-limitet ut.

**Funn (verifisert denne økta).** `vmpws`-søke-API-et (virker fra browser-kontekst, jf. [ADR-019](#adr-019-datatilgang-via-ekte-nettleser--vivino-og-polet-bak-waf)/[ADR-021](#adr-021-remote-browser-via-cdp--device-agnostisk-refresh)) støtter **TRAIT-fasetter**: `Fylde`, `Friskhet`, `Garvestoffer`, `Soedme`, `Tannin` (Sulfates) og `Bitterhet`, hver som **bøtter** `1-2 · 3-4 · 5-6 · 7-8 · 9-10 · 11-12`. **Kritisk funn:** repeterte facet-tokens av *samme* fasett kombineres som **AND, ikke OR** — `:Friskhet:7-8:Friskhet:9-10` gir 0 treff. Et klokke-**intervall** må derfor kjøres som **flere queries** (én per bøtte) og unioneres client-side. Dette formet den nye modulen `tools/polet_facets.py`: `build_facet_query` (én bøtte per dimensjon), `build_facet_queries` (intervall → liste queries, kartesisk over bøtter), `parse_search_products` — ren, med 20 tester.

> **KORREKSJON (2026-08-29, ADR-024).** Fasett-listen over er feil på tre av seks. Målt live mot `mainCategory:rødvin` (13 775 treff): `Garvestoffer` returnerer **13 775 i hver bøtte** — den ignoreres stille, så en query som «filtrerer» på den gir hele katalogen tilbake. `Soedme` og `Bitterhet` gir 0 treff for rødvin. Kun `Fylde`, `Friskhet` og `Tannin(Sulfates)` filtrerer. `Tannin(Sulfates)` *er* garvestoffer — samme klokke heter `Garvestoffer` i produktsidens JSON og `Tannin(Sulfates)` i søke-fasettene, og det er den kollisjonen som skapte feilen. Ingen anbefaling ble påvirket: `polet_facets` hadde null importører utenfor sine egne tester og var aldri wiret inn. Videre var **«hentet i full bredde» i beslutning (a) ikke sant** — `pageSize` har et servertak på 24, mens sveipen brukte 50, så hver kategori×land-sveip stoppet på det API-et ga i stedet for det den ba om. Det forklarer skjevheten i det resulterende snapshotet (Portugal 293 mot Italia 83).

**Beslutning.**
- **(a) Utvid snapshot-BREDDEN langs utforsknings-aksene via live facet-sweep.** Kjøpbar rødvin fra Argentina, Chile, Sør-Afrika, Australia, New Zealand, Portugal, Østerrike og Hellas hentet i full bredde → snapshot 557 → **1849** produkter.
- **(b) Klokke-similarity på den utvidede poolen går via LIVE facet-query** (browser, egress-avhengig per [ADR-021](#adr-021-remote-browser-via-cdp--device-agnostisk-refresh)), **ikke** offline `find_similar_by_clocks` — fordi katalog-linjene ikke bærer klokker (details er egne filer, ikke hentet for de 1299 nye produktene).
- **(c) Rollefordeling:** snapshot = bredde + Android-baseline; live facet-query = klokke-rekkevidde på desktop.

**Konsekvenser.**
- ✅ `search`/`search_with_facets` dekker nå New World — Zuccardi/Catena/Mullineux m.fl. finnes i snapshotet.
- ✅ Trait-filtrering (Fylde/Friskhet/…) er nå en søkbar dimensjon via `polet_facets.py`, med korrekt AND/OR-semantikk (intervall = union av per-bøtte-queries).
- ⚠️ Offline `find_similar_by_clocks` er fortsatt begrenset til viner som har details — de 1299 nye linjene har ingen klokker offline.
- ⚠️ Snapshot ~3× større (repo-størrelse-avveining bevisst akseptert — bredde valgt fremfor slankt repo).
- ⚠️ Kjerne-land-toppen (IT/FR/DE/ES klokke-filtrert til Fylde 7-8 × Friskhet 9-12) ble rate-limitet ut og er **utsatt**.

**Alternativer vurdert.** **Hente details for alle 1299 nye** — forkastet: rate-limitet, ugjennomførbart. **Committe hele 36k-katalogen** — forkastet: repo-bloat. **Uttrykke klokke-range som repeterte facets i én query** — forkastet: fungerer ikke (samme fasett = AND → 0 treff); må unioneres client-side som flere queries.

**Relatert.** [ADR-021](#adr-021-remote-browser-via-cdp--device-agnostisk-refresh) (egress-avhengig live facet-query), [ADR-020](#adr-020-repo-committet-polet-snapshot--cross-device-desktop-refresh--android-read-only) (snapshot-modellen som utvides), [ADR-019](#adr-019-datatilgang-via-ekte-nettleser--vivino-og-polet-bak-waf) («ekte nettleser»-veien), [ADR-009](#adr-009-polet-fasett-api-i-_peer_percentile-ikke-3-fritekstsøk) (fasett-API i peer-percentile).

---

### ADR-024: Komplett rødvins-snapshot — målt API-sannhet, prunet shape, klokker via fasett-sveip

**Status:** Accepted (2026-08-29). Superseder fasett-listen og «full bredde»-påstanden i [ADR-023](#adr-023-live-facet-sweep--trait-filtrering--snapshot-ekspansjon); AND/OR-funnet og modulstrukturen derfra står uendret.

**Kontekst.** Snapshotet var 1 849 produkter, og formen på det speilet ikke brukeren men den siste sveipen som tilfeldigvis ble kjørt: Portugal 293, Sør-Afrika 231, Australia 211 — mot **Italia 83, Frankrike 61, Spania 52, Tyskland 0**. Vivino-historikken sier det motsatte: 50 av 97 ratede rødviner er italienske, og Italia har hans høyeste landssnitt (3,86). Snapshotet var altså tynnest nettopp der han drikker mest. Oppdraget var komplett rødvin — flaske *og* 3 l — med klokker på hele basen, slik at snapshotet kan være utgangspunkt for dybdesøk og ikke bare et oppslagsverk.

**Funn (alle live-målt 2026-08-29, mot `mainCategory:rødvin`).**

| Funn | Måling | Konsekvens |
|---|---|---|
| Rødvin totalt | **13 775** (75 cl: 12 498 · 300 cl: 313) | «Komplett» er 574 sider, ikke et skjønnsspørsmål |
| **`pageSize`-tak** | **24.** 24/25/48/50 → alle `pagination.pageSize: 24` | `_PAGE_SIZE = 50` var en løgn; **hver sveip kjørt under ADR-023 var stille avkortet** |
| `currentPage` | Virker til siste side (573 ga 23; 600 ga 0) | Full enumerering er mulig; ingen dyp-paginerings-tak |
| `volume`-fasett | `volume:300` → 313, alle verifisert 300 cl | 3 l er ett presist søk |
| `facets[]` i svaret | **Alltid tom** | Fasett-koder kan ikke oppdages — de må probes, og en feil kode feiler *stille* |
| **`Garvestoffer`** | **13 775 i HVER bøtte** | Ignoreres stille — en «filtrert» query gir hele katalogen |
| `Tannin(Sulfates)` | 5 401 (bøtte 7-8) | Dette *er* garvestoffer i fasett-navnerommet |
| `Soedme` / `Bitterhet` | 0 treff | Ikke gyldige for rødvin |
| Klokke-dekning | Fylde 11 029 · Friskhet 10 986 | ~2 750 rødviner har ingen klokker hos Polet i det hele tatt |
| Produkt-JSON-API | `/vmpws/v2/vmp/products/<kode>` → **404** | Dybde må gå via produktsiden |
| Produktside-blobb | `<script type="application/json">` finnes | Klokker/druer/stil/matparring/lagring som ren JSON |
| **Rate-limit** | `429` + **`Retry-After: 3399`** | **Timeskvote på ~800–900 kall**, ikke en kort throttle |
| Sorterings-stabilitet | `relevance`: 13 775 rader → 13 774 unike | Paginering på relevans **hopper over** produkter |

**Navnerom-kollisjonen som skapte fasett-buggen.** Samme klokke heter `Garvestoffer` i produktsidens JSON og `Tannin(Sulfates)` i søke-fasettene. `tools/vinmonopolet.py` og `tools/polet_details.py` bruker `Garvestoffer` *riktig* — de leser detaljer. `tools/polet_facets.py` brukte den *feil* — den bygger søk. Begge navnene er korrekte i hvert sitt lag, og det er nettopp derfor fella er lett å gå i. `_TRAP_DIMS` kaster nå med en melding som sier hvilket navnerom man er i.

**Ingen anbefaling ble påvirket:** `polet_facets` hadde null importører utenfor sine egne tester — modulen ble bygget 2026-07-02 og aldri wiret inn. Fella var ladd, men aldri utløst.

**Beslutning.**

- **(a) Prun katalog-shapen.** `productAvailability` (30,5 % av bytene), `images` (15,4 %) og `main_sub_category` (alltid `{}`) strippes ved ingest. Ingen kode leste dem fra snapshotet; bilde-URL-er er avledbare fra varenr, og lagerstatus er ferskvare som et snapshot uansett ikke kan holde. Målt på de 1 849 gamle radene: 1 631 → 849 B/rad, **47,6 % spart**. Migrering er idempotent, atomisk og radbevarende (1 849 inn → 1 849 ut, 0 avvik utover prune-lista).
- **(b) Full enumerering som ryggrad**, ikke land-for-land-sveip. Volum ligger på raden, så 3 l faller ut gratis — ingen egen 3 l-sveip.
- **(c) Klokker via kartesisk fasett-sveip** Fylde × Friskhet × Tannin(Sulfates) — 216 celler gir alle tre klokkene i én passering (~460 sider) mot ~1 370 for tre 1-dim-sveip. Oppløsningen er bøtte (±1), ikke eksakt heltall; eksakte klokker kommer fra dybde for det utsnittet som får details.
- **(d) Dybde foretrekker JSON-blobben**, med regex som fallback. `save_details` stempler `parser`-proveniens og avviser en blobb hvis produktobjektets varenr ikke er det vi ba om — den gamle valideringen så bare at koden fantes *et sted* i HTML-en.
- **(e) Paginer alltid på en deterministisk sortering.** `relevance` er ustabil mellom kall og hopper over produkter. Union av `relevance` + `name-asc` ga 13 775 eksakt; den tapte vinen var `19591401`.

**Konsekvenser.**
- ✅ Rødvin 1 543 → **13 807**, hele katalogen. Frankrike 61 → 5 959, Italia 83 → 3 763, Spania 52 → 1 111, Tyskland 0 → 368. **3 l: 62 → 314.** Basisutvalget 121 → 468.
- ✅ To uavhengige målemetoder er enige om målslicene: fasett-`totalResults` og full enumerering gir begge 12 498 på 75 cl og 313 på 3 l.
- ✅ Snapshot 12 MB i stedet for ~22 MB uprunet. Katalogen er fortsatt deterministisk sortert og linjebasert.
- ✅ Regex-parseren er ikke lenger eneste dybdevei — og ekvivalenstesten viser at JSON-veien ikke mister noe (`kun_html == {}`).
- ⚠️ **Rate-limiten er nå det bindende planleggingsgrunnlaget — men det er TO bøtter, ikke én.** Søke-API-et (`/vmpws/`) svarer `Retry-After: 3399` (timeskvote, ~800–900 kall). **Produktside-HTML er en egen bøtte med `Retry-After: 300`** — fem minutter, målt 2026-08-29 etter 71 sider. De to straffes altså helt ulikt, og et estimat som blander dem er verdiløst. Kapasiteten er nå målt over tre sykluser: **~82 produktsider per syklus, ~10 sider i minuttet vedvarende.** Dybde for alle 13 775 er dermed **~24 timer** — konklusjonen om at details må være et prioritert utsnitt står altså *sterkere* enn før, selv om den opprinnelige begrunnelsen («16 kvotevinduer à én time») var bygget på feil bøtte.
- ⚠️ **Produktside-straffen eskalerer: 300 s → 3600 s ved vedvarende belastning** (målt 2026-08-30 etter flere timers burst-and-wait). De 300 sekundene er første trinn i en trapp, ikke en fast straff. En stor dybdejobb må derfor kjøres med lavere takt fra start eller med innlagt hvile — og ~24-timers-anslaget for hele katalogen er et gulv, ikke et tak.
- ⚠️ **`Retry-After` er for optimistisk på produktsider — vent lenger enn headeren ber om.** Målt: pause 5,3 min → 83 sider, pause 5,4 min → **34 sider**, pause 7,3 min → 82 sider. Headeren sier konsekvent 300 sekunder, men bøtta er ikke fylt opp igjen på det tidspunktet, og å adlyde den bokstavelig gir ustabilt og halvert utbytte. Praktisk regel: **vent ~7,5 minutter, ikke 5.**
- ⚠️ **`metode`-feltet finnes bare på ~69 % av produktsidene** (49 av de 71 første). Det er feltet som avslører fatlagring og appassimento, altså det som faktisk skiller kraft fra klokker (se `smaksprofil.md` § «Kraftigere kan IKKE søkes på Fylde-klokka»). `stil` og `stil_beskrivelse` dekker ~89 % og er delvis erstatning.
- ✅ **Dybde levert for hele det prioriterte utsnittet (2026-08-30):** 3 l 313/313, Basisutvalget 468/468, Tilleggsutvalget 481/481 — 1 153 sider hentet, **0 avvist**, og **0 av 1 153 manglet JSON-blobben**, så regex-fallbacken ble aldri brukt. 1 668 details i repoet, 1 378 av dem rødvin. Ingen andre statuskoder enn `429` forekom i hele sveipet (ryggrad 866/8, klokker 679/0, details 1 187/16) — ingen 404, 403, 500 eller overlevende timeout.
- ⚠️ Klokker er bøtte-oppløsning (±1) for basen. Eksakt kun der details finnes.
- ⚠️ ~2 750 rødviner får aldri klokker — Polet har dem ikke.
- ✅ **Avregistrerte varer slettes nå.** 32 rødviner i snapshotet fantes ikke i den komplette enumereringen (12 `utgatt`, 9 `utsolgt`, 3 `langtidsutsolgt`, 8 `aktiv`) — men sto alle med `buyable: true` og `expired: false`, fordi flaggene var sanne 2026-07-02. Et snapshot akkumulerer altså stille varer som *ser* kjøpbare ut for alltid. `polet_store.prune_delisted` fjerner dem (og deres details-filer). Etter en komplett sveip er fravær informasjon — men **kun i den kategorien som faktisk er enumerert**, og funksjonen nekter å slette mer enn 10 % uten `force=True`, siden en stille avkortet sveip (jf. `pageSize`-taket) ellers ville tømt katalogen. Rødvin i snapshotet er nå eksakt 13 775.
- ⚠️ Hvit-, rosé- og musserende vin er urørt og har fortsatt den gamle, avkortede dekningen.

**Alternativer vurdert.** **Land-for-land-sveip** (som ADR-023) — forkastet: det var nettopp den metoden som ga skjevheten, og med et `pageSize`-tak på 24 avkortes hvert land stille. **Tre separate 1-dim klokke-sveip** — forkastet: ~1 370 sider mot 676 for kartesisk, og gir samme informasjon. **Details for hele katalogen** — forkastet på et målt tall, ikke en magefølelse: ~16 timer kvote. **Beholde uprunet shape** — forkastet: 46 % av bytene var felt ingen leste, og ved 13 775 rader er det 10 MB. **Fullføre `name-asc`-passeringen etter at unionen traff 13 775** — forkastet: 282 kall av en knapp kvote på et spørsmål som allerede var besvart.

**Amendment 2026-08-30 — `name-asc` er ikke helt stabil den heller.** ADR-024 anbefalte `name-asc` som det deterministiske alternativet til `relevance`, som hopper over produkter under paginering. Det er bedre, men **ties i navnefeltet gir samme klasse feil.** Målt under musserende-sveipen: 3 081 rader hentet, **3 080 unike**. Duplikatet lå nøyaktig på sidegrensen 78/79, i en klynge på fjorten Lilbert-Fils-champagner med kolliderende navn, og én vare (`19711701`) ble hoppet over. Den ble funnet ved målrettet produsentsøk, ikke ved å paginere om igjen.

**Konsekvens for metoden:** ingen sorteringsnøkkel med ties er trygg under paginering, og en avkortet sveip ser ut som en komplett. Den eneste pålitelige kontrollen er **`unike koder == totalResults`** — ikke antall rader, som teller duplikatet med og kommer ut riktig. Kjør den per kategori, og behandle avvik som en manglende vare å oppspore, ikke som en avrunding.

**Relatert.** [ADR-023](#adr-023-live-facet-sweep--trait-filtrering--snapshot-ekspansjon) (superseder fasett-listen), [ADR-020](#adr-020-repo-committet-polet-snapshot--cross-device-desktop-refresh--android-read-only) (snapshot-modellen), [ADR-011](#adr-011-html-fixture-test-for-polet-drift) (drift-vern; JSON-blobben reduserer eksponeringen), [ADR-009](#adr-009-polet-fasett-api-i-_peer_percentile-ikke-3-fritekstsøk) (kode ≠ navn — samme klasse feil), [`polet_refresh.md`](polet_refresh.md) (runbook), teknisk gjeld #1.

---

### ADR-025: Klokke-similarity degradert til grovfilter — målt null diskriminering

**Status:** Accepted (2026-08-30). Presiserer og begrenser bruken av `find_similar_by_clocks`; supplerer [ADR-016](#adr-016-no-filter-bubble-prinsippet-for-user-fit-score). Løser teknisk gjeld #6, men ikke slik posten forutsatte.

**Kontekst.** Gjeld #6 sa at klokke-profil-tabellen i `smaksprofil.md` var «kvasi-teater med n=2» — altså at problemet var for lite data. Tabellen ble derfor utvidet fra Vivino-historikken mot Polet-snapshotet: 117 ratede viner → 32 ekte vin-nivå-treff i katalogen → **21 med klokker i `data/polet/details/`** → 19 nye rader, tabellen nå 25 rader. Hypotesen var at flere rader ville gjøre klokke-similarity brukbar.

**Funn (n=20, målt 2026-08-30 mot `knowledge/smaksprofil.md` md5 `22ea47d5`).** Det motsatte.

| Klokke | Korrelasjon med brukerens rating |
|---|---|
| Fylde | **+0,16** |
| Friskhet | **+0,09** |
| Garvestoffer | **−0,10** |

Alle tre er støy. Verre: **alle seks gruppene med identiske klokker spenner over ratingskalaen.**

- **Samme varenummer, to dommer.** 9111501 Vincent Girardin Terroir Noble er ratet **4.5** (årgang 2010) og **3.8** (2023). Klokkene er identiske per definisjon — det er samme produkt. Årgang og moden alder forklarer det klokkene ikke kan.
- **8/8/8, den trippelen brukeren har flest av:** Patria Femina Etna Rosso **4.1**, Chapoutier Belleruche **3.0**, Dom. de la Janasse Côtes du Rhône **2.0**. **2,1 poengs spenn på identiske klokker.**
- Fire tilsvarende grupper (8/9/8, 9/8/8, 8/8/6, og det opprinnelige 8/9/7 Fenocchio 4.6 vs Vespa «for lett»).

**Vespa-bommen 2026-08-29 var altså ikke et uheldig enkelttilfelle — den var regelen.** Den ene observasjonen som utløste mistanken, viste seg å beskrive hele datasettet.

**Andrehånds-svakhet, like viktig.** **Ingen av de 19 nye radene har klokker fra den årgangen som faktisk ble ratet.** Snapshotet fører dagens årganger; ratingene er 1–14 år eldre. Hver rad er derfor merket `[≠ a→b]` (rating fra årgang *a*, klokker fra årgang *b*) eller `[? →b]` når Vivino mangler årgang. Korrelasjonene over måler i praksis *dagens* klokker mot *fortidens* dom. Det svekker konklusjonen om at klokkene ikke diskriminerer — men det redder ikke klokkene, for motsigelse A er årgangs-uavhengig: der er det samme varenummer.

**Beslutning.**

1. `find_similar_by_clocks` er **et grovfilter for stil-slektskap**, ikke en rangerings- eller preferansemodell. Resultater skal presenteres som «smaker i samme retning», aldri som «noe like godt» eller «noe kraftigere».
2. Backlog-posten om å kjøre similarity offline over 10 986 katalograder kan gjennomføres, men **kun** under merkelappen over. Skala fikser ikke et signal som er null.
3. Rangering innenfor et klokke-treff skal skje på det som faktisk skilte i motsigelsene: appellasjonsnivå, fat/metode, literpris, årgang og drue.
4. Tabellen beholder **alle** motsigelsene og det nye negative ankeret (Janasse 2.0, laveste rødvins-rating i settet, midt i klokke-skyen). En tabell som bare viste treff ville vært en filterboble og brutt [ADR-016](#adr-016-no-filter-bubble-prinsippet-for-user-fit-score).

**Alternativer vurdert.** **Fjerne klokke-similarity helt** — forkastet: stil-slektskap er reell nytte, og verktøyet er billig. **Vekte klokkene inn i user-fit-scoren** — forkastet på målingen: å vekte inn et signal med korrelasjon ~0 ville fortynnet de signalene som virker. **Vente på årgangsriktige klokker før konklusjon** — forkastet: de finnes ikke og kan ikke skaffes (Polet fører ikke historiske årganger), og motsigelse A avgjør spørsmålet uten dem. **Utvide tabellen videre for å få n opp** — forkastet: gjeld #6 antok at n var problemet; denne målingen viser at det ikke var det.

**Amendment 2026-08-30 — «påkoblet i navnet, ikke i rangeringen».** Da `find_similar_by_clocks` ble koblet til katalogens `clock_buckets` (fra 13 til **718 av 771** vurderte kandidater), kom likevel **alle 8 topptreffene fra `details/`**. Årsaken er strukturell, ikke en bug: en bøtte-vin får midtpunkt 7,5 og kan aldri treffe en target på 8, mens en eksakt 8/9/7 treffer blink. De 615 bøtte-vinene var altså vurdert og deretter utestengt fra toppen — utvidelsen var reell i tellingen og illusorisk i resultatet. Fikset med `tolerance` (±0,5 for bøtter, som er hva et 2-intervall faktisk sier) og midtpunkt-avstand som sekundærnøkkel, så målte verdier beholder forrang. Toppsjiktet gikk fra 8 til 50 viner. Lærdommen generaliserer: **at en datakilde er koblet til er ikke det samme som at den påvirker utfallet** — tell begge deler.

**Relatert.** [ADR-016](#adr-016-no-filter-bubble-prinsippet-for-user-fit-score) (no-filter-bubble), [ADR-024](#adr-024-komplett-rødvins-snapshot--målt-api-sannhet-prunet-shape-klokker-via-fasett-sveip) (klokke-bøttene similarity leser fra), [ADR-015](#adr-015-user-fit-score-v0--rule-based-tier-classifier) (rangeringen dette IKKE skal mates inn i), teknisk gjeld #5 og #6.

---

### ADR-026: Peer-percentil måles mot hele populasjonen, ikke et utvalg på 50

**Status:** Accepted (2026-08-30). Avviker bevisst fra transportvalget i [ADR-009](#adr-009-polet-fasett-api-i-_peer_percentile-ikke-3-fritekstsøk) og fjerner legacy-stien derfra. Hensikten i ADR-009 består: peer-gruppen skal være strukturert (kategori × land), ikke fritekst.

**Kontekst.** `_peer_percentile` kalte `search_with_facets(facets, page_size=50)`, som gjør `query()[:50]`. Katalogen skrives sortert på `str(code)`, så «peer-gruppen» var i praksis **de 50 laveste varenumrene i landet**. `pageSize`-taket på 24 er *ikke* involvert — `search_with_facets` leser snapshotet på disk, ikke API-et; feilen er ren lokal sortering pluss avkorting.

**Funn.**

| Måling | Verdi |
|---|---|
| Pichon Baron (15690101, 709,30 kr) før | «72. percentil av 50 peers, median 362,4 kr» |
| Samme vin etter | «**50. percentil av 4 938 peers, median 704,9 kr**» |
| Uavhengig fasit | percentil 0,49–0,50, median 704,9–720,2 kr |
| Verdict-endring, 400 rødviner (seed 7) | **28,2 %** (113/400) |

**Skjevheten har fortegn — den er ikke støy.** Peer-utvalgets median mot gruppens sanne median: Frankrike 362 mot **720 kr**, Italia 387 mot 438, all rødvin 385 mot 500. De laveste varenumrene er systematisk billigere, så hver vin ble målt mot en kunstig billig referanse og verdict skjøvet ensrettet mot «dyr». Feilen midlet seg altså ikke ut over mange oppslag.

**Feilen skalerte med katalogen.** Flip-raten var 7,5 % på det gamle snapshotet (1 543 rødviner) og 30,5 % på det nye (13 775) — ekspansjonen i [ADR-024](#adr-024-komplett-rødvins-snapshot--målt-api-sannhet-prunet-shape-klokker-via-fasett-sveip) firedoblet den. Målt per kategori er 98 % av rødvinene i land-pools over 50, mot 34 % av hvitvinene i dag; hvitvin vokser 64× i den pågående sveipen og går fra 33 % til 0,5 % dekning.

**Beslutning.**

1. `_peer_percentile` kaller **`polet_store.query` direkte** — den trenger populasjonen, ikke et søk. Avviket fra ADR-009s fasett-API er bevisst: fasett-API-et var riktig da alternativet var tre fritekstsøk mot et live-API; mot et komplett snapshot på disk er populasjonen tilgjengelig direkte.
2. **Peer-gruppen er aktive varer** (`polet_store.is_active`), erklært i `peer_terms` som `status:aktiv` / `status:alle`. Avgjørende argument er drift, ikke smak: snapshotet akkumulerer avregistrerte rader, så andelen utgåtte vokser monotont mens den aktive hylla ikke gjør det — medianen ville drevet av seg selv uten at én pris endret seg. 2 196 av 13 775 rødviner er inaktive; 5 pools (36 viner) treffer fallbacken.
3. **`_peer_percentile_legacy` og `peer_search_terms` er fjernet.** Ingen caller passerte parameteren (grep over `*.py`/`*.md`/`*.json`), og «bredere fallback» var en fiksjon mot snapshot-data: legacy gikk fritekst mot *produktnavn*, så `name_contains="frankrike"` ga 0 treff og `"rødvin"` ga 10 tilfeldige viner med ordet i navnet. Den var skrevet for et live-API som ikke lenger er der.
4. Fallback-stigen er bevart: ingen andre viner i kategori × land → `refresh_required`; under 5 aktive peers → hele populasjonen; fortsatt under 5 → `None` (Polet har få viner der, og en refresh ville vært en usann instruks).

**Test-lærdommen er like viktig som fiksen.** Suiten var 291 grønne gjennom hele buggen, fordi den tester logikk på små fixtures og ikke oppførsel ved katalogskala. En assertion på et *tall* (`sample_size == 50`) ville bekreftet feilen. Den som fanger den er et *forhold mellom det som ble sett og det som fantes*: `sample_size >= 0.9 * (len(query(kategori, land)) - 1)`. Nå dekket av `test_peer_pool_is_whole_population_at_any_scale` (parametrisert 12/60/500) og `test_peer_sample_equals_declared_population_for_every_pool`, som holder funksjonen til sin egen `peer_terms`-erklæring for **hver** kategori × land. Fiksen er mutasjonstestet: gjeninnført `[:50]` får fem tester til å falle, og fjernet aktiv-filter får fire til å falle.

**En foreslått test ble målt bort — noter hvorfor, så den ikke gjeninnføres.** Siden skjevheten før fiksen hadde entydig fortegn (peer-medianen systematisk *lavere* enn populasjonens), lå det nær å asserte på fortegn. Målt på de 11 pools med ≥ 100 viner blir fortegnet imidlertid **mer** ensrettet etter fiksen, ikke mindre: 75 % → **82 % negative**. Årsaken er at aktiv-filteret selv er ensrettet — utgåtte varer er marginalt dyrere enn aktive, så medianen faller litt i nesten hver pool. En fortegns-assertion ville altså feilet på *riktig* kode. `test_peer_median_does_not_drift_from_population_median` asserter derfor på **magnitude**, med terskel 15 %: 3,5× klaring over største observerte avvik etter fiksen (4,2 %, Italia) og 2× under den minste B1-feilen. Største avvik før fiksen var −49,7 % (Frankrike), nå −2,1 %.

**Alternativer vurdert.** **Heve `page_size` til et høyt tall** — forkastet: flytter taket i stedet for å fjerne det, og gjenskaper feilen ved neste ekspansjon. **Beholde legacy som fallback** — forkastet på måling: den ville bygget peer-grupper av urelaterte viner. **La inaktive varer bli i poolen** — forkastet på drift-argumentet over. **Gå via `search_with_facets` med større tak** — forkastet: den funksjonen endres samtidig av en annen fiks (B2), og percentilen trenger uansett populasjonen, ikke et søk.

**Relatert.** [ADR-009](#adr-009-polet-fasett-api-i-_peer_percentile-ikke-3-fritekstsøk) (transportvalget dette avviker fra), [ADR-024](#adr-024-komplett-rødvins-snapshot--målt-api-sannhet-prunet-shape-klokker-via-fasett-sveip) (ekspansjonen som firedoblet feilen), [ADR-003](#adr-003-tre-tier-kvalitets-hierarki-i-value_score) (value-hierarkiet percentilen inngår i), teknisk gjeld #5.

---

### ADR-027: Spesifisitet slår generalitet i user-fit — og regler valideres på fordeling, ikke antall

**Status:** Accepted (2026-08-30). Endrer early-exit-rekkefølgen i [ADR-015](#adr-015-user-fit-score-v0--rule-based-tier-classifier); no-filter-bubble-prinsippet i [ADR-016](#adr-016-no-filter-bubble-prinsippet-for-user-fit-score) står uendret og er begrunnelsen.

**Kontekst.** `user_fit` klassifiserte 13 775 rødviner som **2 401 `fit`, 11 374 `neutral`, 0 `very_fit`, 0 `risky`, 0 `no_go`.** Reglene var skrevet på engelsk mot en norsk katalog. Konsekvensen var invertert: `risky` og `no_go` er ADR-016s vern mot filterboble, så et system som aldri kan advare blir stille optimistisk.

**Fem lag, ikke ett.** (1) Namespace — needles matchet ikke norske felter. (2) **`sub_District` ble aldri lest**, og uten den er katalogen praktisk talt stum: distriktet sier «Veneto», appellasjonen «Valpolicella Ripasso» ligger i underdistriktet. (3) `_find_section` returnerte første treff, så den kuraterte prosa-blindsonen var død kode (og øl-blokka måtte klippes bort, ellers lekker «Kölsch / Altbier» inn som vinmønster). (4) Parse-feil: et helt avsnitt som én needle, uparet parentes. (5) `rule_fired` løy — alle `fit` het `bekreftet_drue`, også rene region-treff.

**Beslutning 1 — spesifisitet slår generalitet.** 368 tyske rødviner ble `fit` fordi «Tyskland» står i *Regioner du dras mot*, og region-treffet (regel 4) fyrer før blindspot (regel 5). Men profilens egen parentes sier «(Mosel, Rheingau – **Riesling**)» — altså hvitt. Regelen leste land og ignorerte kategori. Ny presedens: **når en `<Land> <Kategori>`-blindspot navngir både land og kategori, og region-needelen bare navngir landet, vinner blindspot** — men kun når region er eneste regel-4-treff. En bekreftet drue eller stil er egen evidens og overstyres ikke. Resultat: 367 blindspot, 1 `fit` (den ene har en bekreftet drue i navnet). Blindspot-fordelingen gikk fra **3 land til 25**.

**Beslutning 2 — en bekymring avledet fra instegsviner skal ikke arves oppover i appellasjonshierarkiet.** «Burgundy Red» hviler på tre ratinger som alle ligger på Bourgogne/Hautes-Côtes-nivå; en bred lesning ville stemplet 2 662 viner `risky` på n=3. Côte d'Or går derfor til `blindspot` med lav konfidens i stedet. **Samme korreksjon ble anvendt på Sør-Rhône etter gjennomgang:** de tre ratingene er Lirac 4.0, Chapoutier Belleruche Côtes-du-Rhône 3.0 og Janasse Côtes du Rhône 2.0 — to av tre er basisnivå, og den ene som ligger et hakk opp scoret høyest. Å la Châteauneuf-du-Pape arve `risky` derfra er samme feilslutning. Bekymringen bindes til basisnivået; høyere appellasjoner merkes blindspot med n og snitt synlig (ADR-016 — ingenting skjules, påstanden nedgraderes).

**Beslutning 2c — fravær av nivåinformasjon er ikke bevis for at vinen ligger utenfor nivået.** Nivå-porten gjelder bare når en *annen* appellasjon faktisk er synlig i raden. En vin med `stil: "Provence Rosé"` og ingen appellasjon forblir `risky` — innsnevringen er en presisering av en regel, ikke et nytt krav om bevis for å advare.

Innsnevringen ble anvendt på fire regler (Burgund, Sør-Rhône rød, Sør-Rhône hvit, Southern Italy Red) pluss Provence-rosé. Målte effekter: Sør-Rhône rød 317 → 141 treff (176 til blindsone); Southern Italy Red `very_fit` 498 → **413**, der de 85 som flyttet er nøyaktig Puglia 45 + Campania 33 + Calabria 4 + Basilicata 2 + Molise 1, og 81 av dem får `fit` med lav konfidens framfor å falle helt ut. **Merk at innsnevringen ble lagt inn to steder per regel:** både den kuraterte needelen og den auto-deriverte stilmerkelappen matchet uavhengig, og å fikse bare den ene lot regelen leve videre via engelsk substring.

**Beslutning 3 — `no_go = 0` på katalogen er riktig, ikke stille.** Eksakt no-go krever årgang, og Polet fører bare gjeldende. Brukerens laveste rødvin (Janasse Côtes du Rhône, 2.0) finnes i ny årgang og får `risky` med grunnen «samme vin i en annen årgang». Testen for `no_go` går derfor på eksakt navn, ikke på frekvens.

**Valideringslærdommen — den generaliserer utover denne modulen.** Blindspot-regelen fyrte 422 ganger og *så* derfor frisk ut. De 422 kom fra tre land av femten — Portugal, Chile, Uruguay — utelukkende fordi de staves likt på norsk og engelsk, pluss én tysk vin med ordet «Germany» i merkenavnet mens 367 andre fikk ingenting. **Treffantall duger ikke som helsesjekk på en regel; bare fordelingen avslører at den matcher på stavelsessammenfall i stedet for mening.**

Samme linse avslørte en maskert test i selve fiksen: en mutasjon som fjernet landoversettelsen overlevde første runde, fordi assertions om at blindspot fyrer for Tyskland og Spania ble oppfylt av *kuratert prosa* som aldri rørte landtabellen — grønn av feil grunn. Fikset med en libanesisk rødvin (`1005301`) som verken har egen matcher eller prosa bak seg, så treffet kan bare gå via `Libanon → Lebanon`, og testen asserterer på hvilken needle som står i begrunnelsen.

**Beslutning 2b — `classify()` har to innganger, og en regel må gjelde i begge.** Nivå-innsnevringen ble først lagt bare i den norske katalog-matcheren. Sanity-sjekken mot de 122 ratede kom da ut **helt uendret** — umulig hvis Lirac faktisk hadde flyttet seg, og dermed selv beviset på feilen. Årsak: `eval_fit` kjører `classify()` på Vivino-CSV, der `stil` er engelsk («Southern Rhône Red»), og der traff den gamle, ikke-innsnevrede regelen fortsatt. **Samme vin fikk ulik dom avhengig av kilde** — og eval-harnessen fra [ADR-017](#adr-017-eval-harness-før-v1--modell-agnostisk-rangerings-måling), som er beslutningsgrunnlaget for om user-fit v1 skal bygges, målte den regelen som *ikke* var i drift. Nivå-porten er derfor kryss-språklig (appellasjonsnavnene er like i begge kilder; kun bindestreker skiller), låst av to tester. Generelt: enhver regelendring må verifiseres mot begge innganger, og en sanity-sjekk som ikke rikker seg når den burde, er et funn — ikke en bekreftelse.

Innsnevringen er implementert som en generell mekanisme (`_NIVA_INNSNEVRET`), ikke et engangsunntak, og Burgund er lagt inn i den. Grunnen: Côte d'Or havnet riktig i dag bare fordi «Pinot Noir generelt» tilfeldigvis dekket den — et sammentreff, ikke en mekanisme, og det ville ikke overlevd en redigering av den blindsone-linja.

**Resultat (rødvin).** 498 `very_fit` · 2 839 `fit` · 10 031 `neutral` · 408 `risky` · 0 `no_go`. Sanity mot de 122 faktisk ratede vinene er monoton uten unntak, og **separasjonen ble skarpere av innsnevringen**: very_fit 4,10 → fit 4,01 → neutral 3,85 → risky **3,00** (var 3,08, fordi Lirac 4.0 forlot `risky`) → no_go 2,00. `tests/test_user_fit.py` gikk 56 → 90; åtte gjeninnføringer av de gamle feilene fanges nå alle.

**B5 var oppslagsvei, ikke regenerering.** `classify_code(code)` / `classify_codes([...])` slår opp katalograden og klassifiserer direkte — 100 % dekning uten en derivert fil imellom. `data/user_fit/v0.json` dekket 66 av 14 081 varenumre (0,47 %), og CLAUDE.md steg 6b var dermed usann 99,5 % av gangene uten at noe sa fra.

**Alternativer vurdert.** **Oversette hele profilen til engelsk** — forkastet: `smaksprofil.md` er source-of-truth og skrives av brukeren på norsk (ADR-015 prinsipp 2). **Beholde engelsk matching og oversette katalogen** — forkastet: 14 081 rader mot ~50 needles. **Regenerere `v0.json` for hele katalogen** — forkastet: en unødvendig stor derivert artefakt er sin egen gjeld når `classify()` virker direkte på en rad. **La region slå blindspot som før** — forkastet på målingen: 367 viner fikk positiv merkelapp på et signal som gjaldt en annen kategori.

**Relatert.** [ADR-015](#adr-015-user-fit-score-v0--rule-based-tier-classifier) (regel-rekkefølgen dette endrer), [ADR-016](#adr-016-no-filter-bubble-prinsippet-for-user-fit-score) (vernet som aldri fyrte), [ADR-017](#adr-017-eval-harness-før-v1--modell-agnostisk-rangerings-måling) (`eval_fit` kjører `classify()` på engelsk Vivino-data — begge veier må virke), [ADR-025](#adr-025-klokke-similarity-degradert-til-grovfilter--målt-null-diskriminering) (samme lærdom: koblet til ≠ påvirker utfallet).

---

## Kjent teknisk gjeld

Ranket etter risiko × sannsynlighet.

| # | Gjeld | Hvorfor det er gjeld | Når det blir et problem | Trigger for å adressere |
|---|---|---|---|---|
| ~~**0**~~ | ~~`requests`-laget mot Polet `vmpws` er WAF-blokkert (403)~~ **ADRESSERT 2026-06-08** | Løst via repo-committet snapshot + Playwright-MCP-refresh ([ADR-020](#adr-020-repo-committet-polet-snapshot--cross-device-desktop-refresh--android-read-only)). `tools/vinmonopolet.py` leser nå `data/polet/` | — | — (se ny gjeld #0a/#0b) |
| **0a** | **Snapshot-ferskhet avhenger av manuell refresh** | Ingen cron; data eldes til noen kjører ritualet. (Device-låsen er borte — ADR-021: refresh kan nå kjøres fra alle enheter via remote browser, inkl. Android/web.) Verdict alders-merkes underveis | Når brukeren handler på et snapshot som er uker gammelt (pris/lager kan ha endret seg) | Kjør refresh fra hvilken som helst enhet ([`polet_refresh.md`](polet_refresh.md)); value-verdict degraderer språket ved alder >14 d |
| **0b** | **118 orphan-details venter re-knytting** | Rekonstruerte klokkedata uten code-mapping i `_orphan_details.json` (gamle cache-URL-er overskrevet av TTL) | Similarity/dybde mangler for disse vinene til de re-hentes med varenr | Re-hent details for finalister via desktop-refresh; matchede orphans flyttes til `details/<varenr>.json` |
| 1 | Polet HTML-scraping i `parse_product_html` | 12 regex over Polets DOM — sårbar for redesign | Når Polet kommer med ny webshop (sannsynlig <12 mnd) | Fixture-test feiler (allerede på plass — ADR-011); supplert av positiv validering i `save_details` (ADR-020) |
| 2 | `knowledge/scores/` krysser data/knowledge-grensen (ADR-002) | Strukturelt data, lagret som knowledge | Ved 2000+ entries eller behov for sekundær-indeks | Manuell vurdering hver 6. mnd |
| 3 | Aperitif sitemap-bootstrap er 34 HTTP-kall | Cold path ved første kjøring eller etter 30 d | Når brukeren stiller første Aperitif-spørsmål på over en måned | Vurder lazy-pre-fetch i `tools/aperitif.py` |
| 4 | `tools/scores.index()` re-parser 422 entries per prosess | `lru_cache` er prosess-lokal; Bash-call = ny prosess | Ved 5000+ entries (>500 ms parse-tid) | Bygg `knowledge/scores/_index.json` ved git pre-commit |
| 5 | `find_similar_by_clocks` er sekvensiell | Henter detaljer N×M for kandidater | Ved bulk-similarity-søk | Parallellisér med ThreadPoolExecutor |
| ~~**6**~~ | ~~Klokke-profil-tabellen har bare 2 oppføringer~~ **AVKLART 2026-08-30 — premisset var feil** | Tabellen er nå 25 rader, og målingen viser at problemet ikke var n: klokkene korrelerer ~0 med brukerens rating (+0,16 / +0,09 / −0,10), og alle 6 grupper med identiske klokker spenner over ratingskalaen. Se [ADR-025](#adr-025-klokke-similarity-degradert-til-grovfilter--målt-null-diskriminering) | — (ikke lenger «for lite data»; nå en kjent grense for metoden) | Bruk klokkene kun som stil-grovfilter. Gjenstående reell svakhet: klokkene er fra dagens årgang, ratingene 1–14 år eldre |
| 7 | **Kuratert innhold destillert fra `data/reference/*.pdf` uten kildehenvisning** (`knowledge/sommelier.md` §4, `deep-knowledge/norsk-marked.md` §10) *(omformulert 2026-08-30 — den gamle posten «11 MB død last, slett» hadde feil premiss)* | Provenansen finnes kun i selve PDF-ene. Uten attribusjon kan hverken påstandene verifiseres, opphavsretten respekteres eller kilden oppdateres — og PDF-ene ser ut som død last, som denne posten selv feilaktig konkluderte. `knowledge/cicerone.md:202` pekte på en `bjcp_2021.pdf` som **aldri har eksistert i repoet** (verifisert mot alle 60 commits — ingen blob, ingen sletting): en hallusinert filsti, ikke et opprydnings-etterslep. Innholdet er ekte destillat av BJCP 2021, så feilen var attribusjonsformen, ikke kunnskapen. Rettet 2026-08-30 til en ren kildehenvisning | Ved neste oppryddingsrunde: 11 MB ser slettbart ut, og sletting gjør kunnskapen usporbar permanent. Også når TWS-tabellen skal årsoppdateres og ingen vet hva den kom fra | Legg inn kildelinjer etter konvensjonen i `knowledge/wset_l2_sat.md:3`. Først deretter kan PDF-ene beholdes bevisst som arkiv — eller slettes trygt |
| 8 | `~/.cache/sommelier/` har ingen GC | Vokser monotont | Ved >10 000 cache-filer (~50 MB) | Skriv `tools/cache_gc.py` med mtime-basert cleanup |
| 9 | **Årgangstabellen i `deep-knowledge/norsk-marked.md` §10 er tre årganger bak** — kilden (TWS Vintage Chart 2024, publisert 12.02.2024) stopper på 2022 | Repoet brukes til å kjøpe vin nå. 2023/2024-hvitviner er hyllevare, 2023 Bordeaux og Burgund er i handelen, Barolo 2022 slippes i år — ingen har dekning. Nord-Rhône-raden stopper så tidlig som 2019. Champagne-radene 2013 og 2019 og Piemonte 2021 ligger dessuten utenfor chartet — supplert av kuratoren uten kilde. Overskriften «de siste 15» er selvmotsigende: fra 2026 skulle spennet vært 2011–2026, innholdet er 2008–2022 | Allerede et problem ved ethvert årgangsspørsmål om 2023+ | Skaff nyere årgangschart og utvid tabellen. Kortsiktig: eksplisitt varsel om udekkede årganger (gjort 2026-08-30) |
| 10 | **Prosaen i `smaksprofil.md` er ikke koblet til `profile_stats` og glir fra den managed blokken ved hver synk** | Seks tallpåstander i prosaen (datagrunnlag, snitt per kategori, «Italia er hjemmebanen») vedlikeholdes for hånd mens blokka over dem regenereres automatisk. Avviket var 13 viner før Vivino-synken 2026-08-30 og 18 etter — det vokser hver gang noen synker | Allerede et problem: en leser som stoler på prosaen får 104 ratede når sannheten er 122. Påstandene er foreløpig fortsatt sanne, så feilen er stille | Tallene rettet 2026-08-30. Varig fiks: test som sammenligner prosaens tall mot managed blokk og feiler ved avvik |
| 11 | **`PoletRefreshRequired` betyr ikke lenger det den sier for komplett enumererte kategorier** | `search()` kaster ved null treff med hintet «refresh katalogen fra desktop». Rødvin er nå enumerert eksakt (13 775), så null treff betyr **«Polet fører den ikke»** — ikke «snapshotet er utdatert». Koden sier fortsatt det siste, og sender brukeren på et tungt rate-limitet ritual der riktig svar er «den finnes ikke, her er et alternativ». Strider mot anti-hallusineringsregelen i `CLAUDE.md` | Allerede nå for rødvin; gjelder hvit/musserende/rosé straks sveipen 2026-08-30 lander | Krever kompletthets-felter i `catalog_meta.json` (`total_results`, `enumerated`, `method`, `completed_at` per kategori) — de skrives under sveipen, ikke etterpå. Deretter er fiksen ren kode. Påstanden må alders-degraderes som `SNAPSHOT_STALE_DAYS`; `prune_delisted` bygger på samme premiss og bør lese samme felt |
| 12 | **Katalogen er doblet fra 12 til ~24 MB og committes i sin helhet ved hver refresh** | ADR-024 aksepterte 12 MB bevisst etter pruning til 849 B/rad. Sveipen 2026-08-30 tok snapshotet fra 14 081 til ~27 400 rader. Selve fila er håndterbar; problemet er at **hver full refresh legger ~24 MB til git-historikken permanent** | Ved noen få refresher: repoet blir tregt å klone og `.git` vokser monotont uten at noen ser det | Mål `.git`-størrelsen etter neste refresh. Alternativer: komprimér ndjson-en (taper lesbare differ), prune flere felter, eller vurder om katalogen skal committes i det hele tatt framfor å bygges av en runbook |

## Når du gjør en ny audit/refactor

1. Les denne fila først — sjekk om endringen kolliderer med en eksisterende ADR
2. Hvis ja: skriv en ny ADR som superseder den gamle, ikke bare endre koden
3. Hvis nei: vurder om endringen er stor nok til å fortjene sin egen ADR
4. Kjør `python3 -m pytest tests/ -v` før og etter — fang regressioner umiddelbart
5. Hvis du endrer fundamentalt på et lag (knowledge-struktur, cache-strategi): oppdater både denne fila OG `README.md`
