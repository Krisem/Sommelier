# Sommelier

Personlig digital sommelier OG cicerone som Claude Code-prosjekt. Anbefaler både vin og øl basert på Vivino- og Untappd-historikk + felles smaksprofil, parrer drikke til mat med kjemisk presisjon, henter klokker/pris fra Vinmonopolet, slår opp i en kuratert kritiker-score-database, og lærer av tilbakemeldinger over tid.

> **Arkitektur-dokumentasjon:** Alle designvalg, trade-offs og kjent teknisk gjeld er dokumentert som ADR-er i [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Les den før du gjør refactors.

## Hva systemet kan

**Anbefale**
- Foreslå **vin og øl** ut fra dokumenterte preferanser (Vivino + Untappd + felles smaksprofil) – med eksplisitt merking av `[PRØVD]`, `[LIKNENDE]` eller `[NYTT]`, samt `[USA]` ved amerikansk opprinnelse (no-filter-bubble-prinsippet: synliggjøres, ikke filtreres bort — se [ADR-016](docs/ARCHITECTURE.md#adr-016-no-filter-bubble-prinsippet-for-user-fit-score)).
- Verifisere mot Polet (pris, lager, klokker, drueblanding, stil for både vin og øl) – betinget, ikke automatisk: bare ved kjøp, value-spørsmål, eller når klokker faktisk hjelper.
- Finne lignende viner via klokke-profil-similarity (euklidsk avstand på fylde/friskhet/garvestoff).
- Be om presisering ("vin eller øl?") kun ved ekte tvetydighet — gå direkte når lean er åpenbar.
- **Vise det som faktisk kan kjøpes.** Søk filtrerer bort utsolgt, utgått og langtidsutsolgt (3 685 av 27 402 rader); kommende lanseringer vises med `kommer_snart`-flagg i stedet for å skjules ([ADR-029](docs/ARCHITECTURE.md#adr-029-kjøpbarhet-er-default-lanseres-er-en-tredje-tilstand)).
- **Svare på whisky** — juridisk kategori, Polets Fylde/Fat/Røyk, servering. Betinget: kun når whisky nevnes, eller ved dessert, ost, digestif og kveldsdram. Whisky står på n=7, altså for tynt til en modell (~84 trengs) — systemet sier hva flasken *er*, aldri hva du vil synes om den.

**Vurdere value**
- `tools/value_score.py` kombinerer tre signaler til én vurdering:
  1. **Kuratert kritiker-score** (`knowledge/scores/` — DN m.fl., per varenummer) — høyeste tillit
  2. **Aperitif.no** — faglig norsk vurdering (1–100 + "godt kjøp"-flagg). Snapshot i `data/aperitif/` gir poeng offline; produktsiden hentes for «godt kjøp»-flagget, som ikke finnes i lista
  3. **Vivino** — crowd-rating (1–5 + antall ratings)
  4. **Peer-percentile** — hvor prisen ligger relativt til lignende viner på Polet (via fasett-API)
- Output: `value_verdict` (veldig_godt_kjop / godt_kjop / akseptabelt / dyrt_for_kvaliteten / usikkert) + kort begrunnelse.
- Cache-strategi og prioritering: se [ADR-003](docs/ARCHITECTURE.md#adr-003-tre-tier-kvalitets-hierarki-i-value_score).

**Vurdere ellers**
- Velge mellom to flasker du allerede eier eller har på en restaurant-/bar-meny – uten Polet-støy.
- Parre vin OG øl til mat med kjemisk presisjon – inkludert *tilberedningsmetode* (rå/dampet/stekt/grillet/braisert/røkt/friert) som egen dimensjon for begge fag.
- Sesongbevissthet for øl (juleøl november, fersk-hop september, lyse stiler sommer).

**Lære – kontinuerlig over tid**
- Hver ny Vivino-rating mater modellen: kjør `profile_stats.py` etter eksport, og auto-blokken i `smaksprofil.md` regenereres.
- Hver ny Untappd-rating mater modellen: kjør `untappd_stats.py` etter ny scrape, og en parallell øl-blokk i `smaksprofil.md` regenereres med stilfamilier, ABV-spenn, sesongmønster og topp/bunn.
- Når du sier "den vinen/ølet var glimrende" eller "ikke foreslå den igjen" – Claude oppdaterer `smaksprofil.md` umiddelbart. Smaksprofilen er et felles, levende dokument for vin og øl.
- Korreksjoner av Claudes resonnement havner i `tasks/lessons.md`, slik at samme feil ikke gjentas.
- Klokke-profiler for topp-rated viner (4.5+) akkumuleres automatisk i `smaksprofil.md` som biprodukt av legitime søk.
- Nyere ratings vektes tyngre enn eldre (smaken modnes).

**Faglig dybde**
- **Vin: WSET Level 3-nivå** referansestoff per region, lastet on-demand.
- **Øl: Cicerone Level 2/3-nivå** referansestoff per stilfamilie, lastet on-demand.
- Servering, dekantering, lagring, glass, parring-kjemi i parallelle oppslagsfiler for vin og øl.

## Struktur

```
.
├── CLAUDE.md                          autoloaded instruksjon for Claude
├── docs/
│   └── ARCHITECTURE.md                ADR-basert design-rasjonale (les ved audit/refactor)
│
├── knowledge/                         alltid lastet
│   ├── sommelier.md                   vin-kjerne: drueprofiler, parring-lover, workflow + Vinmonopolets rammeverk (klokker, stiler, matfarger)
│   ├── cicerone.md                    øl-kjerne: tre akser, stilfamilier, friskhet, workflow + BJCP-rammeverk (ABV/IBU/SRM, hop/malt/gjær, glass)
│   ├── smaksprofil.md                 felles profil + auto-derivert vin- og øl-statistikk
│   ├── whisky.md                      whisky-kjerne: juridiske kategorier, Polets Fylde/Fat/Røyk, servering (n=7 — for tynt til modell)
│   ├── wset_l2_sat.md                 WSET tasting-vokabular
│   ├── scores/                        kuratert kritiker-score-DB (varenr-indeksert)
│   │   ├── INDEX.md                   skjema + liste over kilder
│   │   ├── dn_maislipp_rose_2026.md   170 viner
│   │   ├── dn_maislipp_musserende_2026.md   106 viner
│   │   ├── dn_tysklandslipp_2026.md   111 viner
│   │   ├── dn_maislipp_25_beste_2026.md   25 viner
│   │   └── dn_17mai_handleliste_2026.md   10 viner
│   └── _archive/                      historiske notater
│
├── deep-knowledge/                    on-demand (les via INDEX.md-router)
│   ├── INDEX.md                       trigger-ord → fil-oppslag
│   ├── italia.md, frankrike.md, tyskland.md, spania.md, portugal.md, …
│   ├── champagne-musserende.md, naturvin-orange.md, aromatisk-hvit.md
│   ├── new-world.md, pinot-noir.md, ovrige-regioner.md
│   ├── servering-og-lagring.md        vin-kjemi + tilberedningsmetode-tabell
│   ├── norsk-marked.md                vin-importører, vintage, drikkevindu, Polet
│   ├── ol-hopdominert.md, ol-belgisk.md, ol-tysk-tjekkisk.md,
│   ├── ol-maltdominert.md, ol-sur-vill.md,
│   ├── ol-servering-parring.md, ol-norge-norden.md
│
├── data/
│   ├── polet/                         repo-committet Polet-snapshot: catalog.ndjson (27 402 varer) + details/ (1 664 sider)
│   ├── aperitif/                      Aperitif-snapshot: varenr → poeng, sveipet fra Pollisten
│   ├── vivino/                        Vivino-eksport (CSV) – 172 viner, 122 ratet (115 distinkte)
│   ├── untappd/checkins.csv           Untappd-scrape (90 check-ins, 2019–2026)
│   ├── whisky/                        ratings.csv + README (tom — Kristoffer dikterer i chat)
│   ├── reference/                     PDF-er (Food&Wine, Zoecklein, TWS Vintage)
│   └── user_fit/                      pre-computet fit-klassifisering (regenereres av profile_stats.py)
│
├── tools/
│   ├── vinmonopolet.py                Polet-søk mot snapshot (search, search_with_facets, get_product_details, parse_product_html, find_similar_by_clocks)
│   ├── polet_store.py                 lese/skrive-lag for data/polet/ (query, lookup, details, statusfilter)
│   ├── polet_facets.py, polet_live.py, polet_details.py, refresh_polet.py, seed_polet_store.py
│   ├── aperitif.py                    Aperitif-score: snapshot + on-demand scraping
│   ├── refresh_aperitif.py            sveiper Pollistens listesider → data/aperitif/scores.ndjson
│   ├── vivino.py                      Vivino lookup + diskcache
│   ├── scores.py                      Indekserer knowledge/scores/*.md per varenummer
│   ├── value_score.py                 Kombinerer kuratert + Aperitif + Vivino + peer-percentile (parallell I/O, 24t cache)
│   ├── profile_stats.py               auto-derivér vin-statistikk fra Vivino-CSV
│   ├── untappd_stats.py               auto-derivér øl-statistikk fra Untappd-CSV
│   ├── user_fit.py                    rule-based fit-classifier mot smaksprofil (v0)
│   ├── beer_fit.py                    stilfamilie → tier for øl
│   ├── eval_fit.py                    modell-agnostisk rangerings-eval mot brukerens egne ratinger
│   ├── vivino_sync.py                 merger nye Vivino-ratinger inn i CSV (idempotent)
│   └── aroma_wheel.html               D3-sunburst med Davis/Noble-hjul
│
├── tests/                             pytest-suite (481 tester, ~23s, alle offline)
│   ├── conftest.py                    legger repo-roten på sys.path
│   ├── test_knowledge_content.py      innholds-basert (fil-agnostisk) + whisky-forbeholdene
│   ├── test_user_fit.py               regel-parsing, matching og fordelings-assertions mot ekte katalog
│   ├── test_polet_store.py            query/statusfilter/round-trip
│   ├── test_refresh_aperitif.py       parsing av listesider + drift-vernet i sveipen
│   ├── test_managed_block_roundtrip.py   alt utenfor sentinelene skal være bit-identisk
│   ├── test_scores_index.py, test_value_score.py, test_vinmonopolet.py, test_eval_fit.py, …
│   ├── test_vinmonopolet_html_fixture.py   drift-vern mot Polet DOM-endringer
│   └── fixtures/                      pinnet HTML for Polet-produktside og Aperitif-listesider
│
└── tasks/
    ├── todo.md                        aktive oppgaver
    ├── lessons.md                     læring fra korreksjoner og egne feil
    ├── maaling_2026-08-31.md          måleomgang, festet til revisjon + katalog-md5
    ├── plan_whisky.md, plan_objektiv_anbefaling.md
    └── exploration/                   utforsknings-frontier per blindsone
```

## Bruk

Start Claude Code i denne mappa – `CLAUDE.md` lastes automatisk. Skriv f.eks.:

**Vin**
- "Foreslå en rødvin under 300 kr til lasagne i kveld"
- "Hva drikker jeg til osso buco på torsdag?"
- "Jeg liker Etna Rosso – hva annet bør jeg prøve?"
- "Er denne verdt 450 kr?" + lenke/navn

**Øl**
- "Foreslå en IPA jeg ikke har prøvd"
- "Hva passer til Wienerschnitzel?"
- "Anbefal et juleøl i år"
- "Hva er forskjellen på West Coast og NEIPA?"

**Begge fag**
- "Hva drikker jeg til pizza i kveld?"  *(forventer "vin eller øl?"-oppfølger)*
- "Velg mellom disse to flaskene jeg har"  *(bilde / navn – ingen Polet-oppslag)*
- "Vurder dette vinkartet" eller "dette ølkartet"  *(bilde fra restaurant)*

## Kommandolinje

```bash
# Auto-derivér vin-statistikk etter ny Vivino-eksport
python3 tools/profile_stats.py

# Auto-derivér øl-statistikk etter ny Untappd-scrape
python3 tools/untappd_stats.py

# Regenerér user-fit-klassifisering for hele score-DB-en
python3 -m tools.user_fit

# Smoke-test Polet-tilkobling
python3 tools/vinmonopolet.py

# Full value-score-vurdering for én vin (alle kilder + verdict)
python3 -m tools.value_score "Tornatore Etna Rosso" 2022

# Klokke-profil similarity (vin)
# NB: finner STIL-SLEKTNINGER, ikke «noe like godt» (ADR-025 — klokkene korrelerer ~0 med rating).
# Leser klokker fra details/ OG katalogens clock_buckets; bøtte-treff merkes «±1 (bøtte)».
python3 -c "
from tools.vinmonopolet import find_similar_by_clocks
hits = find_similar_by_clocks(
    target_clocks={'Fylde': 8, 'Friskhet': 9, 'Garvestoffer': 7},
    queries=['Barbera d Alba', 'Dolcetto', 'Nebbiolo Langhe'],
    max_price=400,
    category='Rødvin',
    top_k=5,
)
for h in hits:
    print(h['distance'], h['product']['name'])
"

# Score-DB-oppslag for ett varenummer
python3 -c "
from tools.scores import get_user_scores
for s in get_user_scores('4416401'):
    print(f'[{s[\"score\"]}] {s[\"kilde\"]} / {s[\"test\"]}')
"

# Aroma-hjul – åpne i nettleser
open tools/aroma_wheel.html

# Kjør hele test-suiten
python3 -m pytest tests/ -v
```

## Test-suite

**481 tester på ~23 sekunder, alle offline** (per 2026-08-31). Bygd som innholds-baserte kontrakt-tester, ikke implementasjonsdetaljer — de bevokter påstander i `knowledge/`-filene og oppførselen til `tools/`, så de faller når prosaen og tallene glir fra hverandre. Tester med `@pytest.mark.network` krever Polet/Aperitif/Vivino-tilgang.

**Legger du til en test: muter antagelsen og bekreft at den faktisk feiler.** «Grønn av feil grunn» er den mest gjentatte feilen i dette repoet, og den går begge veier — en test som aldri når koden den påstår å teste, og en fixture som mangler et felt produksjonsdata alltid har. Muter det *nøyaktige* uttrykket testen påstår noe om, og sjekk at det er den testen som faller.

```bash
python3 -m pytest tests/ -v                   # alle
python3 -m pytest tests/ -m 'not network'     # bare offline-tester
python3 -m pytest tests/test_vinmonopolet_html_fixture.py -v   # bare Polet-drift-test
```

**HTML-fixture-test** (`test_vinmonopolet_html_fixture.py`) er drift-vern mot Polet-redesigns: pinnet HTML for én produktside (Fenocchio Barbera, brukerens 4.6-vin) med 14 assertions. Feiler synlig hvis Polets DOM endrer seg. Refresh-script i fil-docstring. Se [ADR-011](docs/ARCHITECTURE.md#adr-011-html-fixture-test-for-polet-drift).

## User-fit-score

Pre-computet fit-klassifisering av alle viner i score-DB-en mot brukerens smaksprofil. Eliminerer behovet for at Claude per-vin resonnerer mot smaksprofilen på batch-spørringer.

**Oppslag for et vilkårlig varenummer:** `python3 -m tools.user_fit <varenr> [...]`, eller `from tools.user_fit import classify_code, classify_codes`. Klassifiserer katalograden direkte — full dekning, ingen derivert fil imellom.

**Output-fila** `data/user_fit/v0.json` gir tier (`very_fit / fit / neutral / risky / no_go`) per varenummer, men **bare for viner som finnes i score-DB-en**: 409 av katalogens 27 402 varenumre (1,5 %, målt 2026-08-31). Den er et evaluerings-artefakt, ikke en oppslagstabell — bruk `classify_code` til oppslag.

**Regenereres** automatisk når `profile_stats.py` kjører (etter Vivino-eksport), eller manuelt via `python3 -m tools.user_fit` uten argumenter.

**Versjons-roadmap:** se [`roadmap.md`](roadmap.md). v0 er rule-based; v1/v2 planlagt for kontinuerlig rangering og lærte vekter.

**Designvalg:** se [ADR-015](docs/ARCHITECTURE.md#adr-015-user-fit-score-v0--rule-based-tier-classifier).

## Cache

Alt eksternt caches på disk i `~/.cache/sommelier/`:

| Kilde | TTL | Path |
|---|---|---|
| Polet search | 24t | `search_*.json` |
| Polet fasett-søk | 24t | `search_facets_*.json` |
| Polet produktdetaljer | 7d | `details_*.json` |
| Vivino | 7d | `vivino/*.json` |
| Aperitif score (per vin) | 14d | `aperitif/score_*.json` |
| Aperitif listesider (sveip) | permanent, manuell | `aperitif-pages/side-NNNN.html` |
| Aperitif sitemap | 30d | `aperitif/sitemap_index.json` |
| value_score (full pipeline) | 24t | `value_score/v1_*.json` |

Mappa kan slettes når som helst for å resette. Detaljer + begrunnelse for TTL-valg: [ARCHITECTURE § Cache-hierarkiet](docs/ARCHITECTURE.md#cache-hierarkiet).

## Performance

Etter optimaliserings-økten 2026-05-14:

| Operasjon | Cold | Warm |
|---|---:|---:|
| `compute_value_score` | ~10s | <50ms |
| `_peer_percentile` (fasett-API) | 160ms | <1ms |
| `tools.scores.index()` (422 entries) | 50ms | <1ms |
| Full test-suite (481 tester) | ~23s | ~23s |

## Vedlikehold

**Etter ny Vivino-eksport:**
1. Overskriv `data/vivino/full_wine_list.csv` (kolonner er stabile).
2. Kjør `python3 tools/profile_stats.py` – auto-blokken i `smaksprofil.md` regenereres.
3. Be Claude om å gjennomgå mønstre – nye favoritter / no-go / oppdatert blindspots.
4. `profile_stats.py` regenererer også `data/user_fit/v0.json` automatisk.

**Etter ny Untappd-scrape:**
1. Untappd har ingen åpen eksport — full historikk krever autentisert Playwright-scrape (Claude kan kjøre det). Etter at `data/untappd/checkins.csv` er oppdatert:
2. Kjør `python3 tools/untappd_stats.py` – øl-blokken i `smaksprofil.md` regenereres.
3. Be Claude om å gjennomgå nye stiler / bryggerier / sesongmønstre.

**Etter refresh av Aperitif-snapshotet:**
1. `python3 -m tools.refresh_aperitif --cache-dir ~/.cache/sommelier/aperitif-pages` ✍️
2. Sveipen tar ~560 sider à 12–26 s, altså 2–4 timer. Den **avbryter framfor å skrive halvt** ved tom side, paginering som ikke rykker, eller sortering som endrer seg — så `data/aperitif/` er enten komplett eller urørt.
3. `--cache-dir` gjør en avbrutt sveip gjenopptagbar: allerede hentede sider leses fra disk. Bruk alltid flagget.
4. Commit `data/aperitif/scores.ndjson` + `meta.json`.

**Etter nytt Polet-slipp med kritiker-test:**
1. Be Claude om å parse PDF-en (eller artikkelen) inn i `knowledge/scores/<kilde-slug>.md` etter skjemaet i `INDEX.md`.
2. Verifiser med `python3 -m pytest tests/test_scores_index.py -v`.
3. Oppdater `knowledge/scores/INDEX.md` med ny rad i "Eksisterende kilder"-tabellen.

**Hvis Polet endrer HTML-struktur:**
1. `python3 -m pytest tests/test_vinmonopolet_html_fixture.py -v` vil feile synlig.
2. Inspiser hvilke felt som mangler, fiks regex i `tools/vinmonopolet.py:parse_product_html`.
3. Re-fetch fixture: følg scriptet i docstring til `tests/test_vinmonopolet_html_fixture.py`.
4. Verifiser at alle 14 fixture-tester passerer.

**Når du endrer scoring-logikken (`_value_verdict` i `tools/value_score.py`):**
1. Bump `LOGIC_VERSION = "v1"` til neste tall — invaliderer all gammel cache automatisk.
2. Se [ADR-004](docs/ARCHITECTURE.md#adr-004-logic_version-i-value_score-cache-nøkkel).

## Designvalg

Alle vesentlige designvalg er dokumentert som ADR-er (Architecture Decision Records) i [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Bla gjennom for kontekst på hvorfor ting er gjort som de er — særlig:

- Hvorfor score-DB er markdown og ikke SQLite ([ADR-002](docs/ARCHITECTURE.md#adr-002-knowledgescores-som-markdown-ikke-sqlite))
- Hvorfor tre-tier kvalitets-hierarki (kuratert > Aperitif > Vivino) ([ADR-003](docs/ARCHITECTURE.md#adr-003-tre-tier-kvalitets-hierarki-i-value_score))
- Hvorfor Polet-data ligger som repo-committet snapshot ([ADR-020](docs/ARCHITECTURE.md#adr-020-repo-committet-polet-snapshot--cross-device-desktop-refresh--android-read-only), [ADR-021](docs/ARCHITECTURE.md#adr-021-remote-browser-via-cdp--device-agnostisk-refresh))
- Hvorfor klokke-similarity er degradert til grovfilter ([ADR-025](docs/ARCHITECTURE.md#adr-025-klokke-similarity-degradert-til-grovfilter--målt-null-diskriminering)) — klokkene korrelerer ~0 med brukerens egne ratinger
- Hvorfor reglene og katalogen skriver samme språk ([ADR-028](docs/ARCHITECTURE.md#adr-028-ett-vokabular-i-stedet-for-to--norsk-på-begge-sider-av-matchingen)) — og hva det kostet i målt rangeringsevne
- Hvorfor kjøpbarhet er default i søk ([ADR-029](docs/ARCHITECTURE.md#adr-029-kjøpbarhet-er-default-lanseres-er-en-tredje-tilstand))
- Hvorfor knowledge-filer ble slått sammen
- Hvilken teknisk gjeld vi kjenner og når den blir kritisk
