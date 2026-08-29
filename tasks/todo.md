# Todo

## Aktivt

### Komplett rødvins-snapshot med klokker (startet 2026-08-29)

**Mål:** komplett rødvin-dekning (flaske + 3 l) i `data/polet/`, med klokker som minimum
på hele basen, slik at snapshotet kan være utgangspunkt for dybdesøk.

**Fase 0 — rekognosering: FERDIG 2026-08-29.** Verifiserte funn (alle live-målt):

| Funn | Verdi | Konsekvens |
|---|---|---|
| Rødvin totalt | **13 775** (75 cl: 12 498 · 300 cl: **313**) | «Komplett» = 574 sider a 24 |
| `pageSize`-tak | **24** — alt over gir stille 24 | `_PAGE_SIZE = 50` i `refresh_polet.py` har alltid vært en løgn |
| `currentPage` | Virker helt til siste side (573) | Full enumerering er mulig, ingen dyp-paginerings-tak |
| `volume`-fasett | `volume:300` → 313, alle verifisert 300 cl | 3 l er ett presist søk, ikke et filter |
| `facets[]` i svaret | Alltid tom | Fasett-koder kan ikke oppdages, må probes |
| **`Garvestoffer`** | **Returnerer 13 775 i HVER bøtte — ignoreres** | **Stille bug i `polet_facets.py`** |
| `Tannin(Sulfates)` | 5 401 for bøtte 7-8 — filtrerer | Dette er den ekte garvestoff-koden |
| `Soedme` / `Bitterhet` | 0 treff | Ikke gyldige for rødvin |
| Klokke-dekning | Fylde 11 029 · Friskhet 10 986 av 13 775 | ~2 750 røde har ingen klokker i det hele tatt |
| Produkt-JSON-API | `/vmpws/v2/vmp/products/<kode>` → **404** | Dybde må fortsatt gå via produktsiden |
| Produktside-blob | `<script type="application/json">` **finnes live** | Klokker/druer/stil/lukt/smak/emballasje som ren JSON → erstatter 12 regex |
| `browser_evaluate` + `filename` | Skriver payload til fil, ikke kontekst | Sveip i batcher a 25 sider uten kontekst-kollaps |

**Sveip-design.** Ryggrad: full enumerering av `mainCategory:rødvin` (574 sider) — volum ligger
på raden, så 3 l faller ut gratis. Klokker: kartesisk sveip Fylde × Friskhet × Tannin(Sulfates)
= 216 kombinasjoner (~460 sider + 216 probe-kall) gir alle tre klokkene i én passering,
mot ~1 370 sider for tre separate 1-dim-sveip. Lekkasje (vin som mangler én dimensjon)
måles mot ryggraden til slutt; målt 0,4 % på ett par.

**Status 2026-08-29 kl. 18:00.** Ryggraden er ingestet og verifisert: **14 113 rader** (13 807 rødvin),
0 ugyldige, 0 usorterte, 867 B/rad, 12 MB. Dekningen er snudd: Frankrike 61 → 5 959, Italia 83 → 3 763,
Spania 52 → 1 111, Tyskland 0 → 368, **3 l 62 → 314**, Basisutvalget 121 → 468.
Kontroll 1/5/6 OK (13 775 unike · 313 på 3 l · 12 498 på 75 cl — fasett og enumerering enige).
Suiten: 282 grønne. ADR-024 skrevet, ADR-023 superseder-merket, runbook rettet.
Gjenstår: klokkesveipet (venter på kvotevindu ~18:48) + kontroll 2/3/4, så fase 4.

**Nye funn som ikke sto i planen:**
- **Timeskvote ~800–900 kall** (`429` + `Retry-After: 3399`). Avgjør fase 4 kvantitativt.
- **`sort=relevance` hopper over produkter under paginering** — 13 775 rader ga 13 774 unike.
  Union med `name-asc` fanget `19591401`. Paginer alltid deterministisk.
- **32 rødviner var avregistrert** (12 utgått, 9 utsolgt, 3 langtidsutsolgt, 8 aktiv) — alle med
  `buyable: true`. BESLUTTET 2026-08-29: slettet via ny `polet_store.prune_delisted`
  (kategori-avgrenset, nekter >10 % sletting uten `force`). Rødvin er nå eksakt 13 775.
- **Regex-parseren henter ikke `land`/`produsent`/`årgang`** — nøstet markup, aldri fanget av test.

**Fase 4 BESLUTTET 2026-08-29:** 3 l + Basisutvalget + Tilleggsutvalget = 1 180 viner,
**1 153 mangler details** → to kvotevinduer. Arbeidsliste ligger i `scratchpad/sweep/fase4_urls.json`.
Rekkefølge: 3 l først (minste gruppe, eksplisitt etterspurt), så Basis, så Tillegg.
Italia-båndet (75 cl, 150–500 kr, ytterligere ~1 960) er IKKE med — kan tas senere.

**Arbeidsdeling (disjunkt fileierskap):**
- [x] **A — shape:** prune `productAvailability` + `images` + `main_sub_category` ved ingest
      (~1 624 → ~849 B/rad), migrer eksisterende katalog, `set_clock_buckets()`.
      Eier: `tools/polet_store.py`, `tests/test_polet_store.py`, `tools/migrate_catalog_shape.py`.
- [x] **B — dybde-parser:** `parse_product_json` mot den innebygde JSON-blobben.
      Eier: `tools/polet_details.py`, `tests/test_polet_details.py`, ny fixture.
- [x] **C — sveip-plumbing:** fjern falsk `Garvestoffer`, `_PAGE_SIZE` 50 → 24, pagineringshjelper,
      sveip-plan. Eier: `tools/polet_facets.py`, `tools/refresh_polet.py`, deres tester.
- [~] **D — browser-sveip:** ryggrad FERDIG (574/574), klokkesveip venter på kvote. Kjører ryggrad + kartesisk klokke-sveip, dumper rå JSON til scratchpad.
      Eier: ingen repo-filer.
- [ ] **Wiring + ingest + ADR-024** (hovedtråd, etter at A–D har landet).
- [ ] **Fase 4 — dybde** for prioritert utsnitt (alle 313 3 l + Basisutvalget + Italia/FR/ES).

## Backlog
- [x] ~~**Kjerne-land klokke-topp (utsatt fra 2026-07-02)**~~ — superseded av «Komplett rødvins-snapshot» over; den gamle formuleringen bygde dessuten på `Garvestoffer`-fasetten, som ikke filtrerer. Opprinnelig: — utvid snapshot med IT/FR/DE/ES rødvin i sweet-spoten (Fylde 7-8 × Friskhet 9-12, ~723 røde). Ble rate-limitet ut i facet-sweepen; kjør senere med gentle backoff (`polet_facets.build_facet_queries`).
- [ ] **Hvit/musserende-ekspansjon** — samme facet-sweep for aromatisk hvit (østerrike/tyskland/new_zealand) når den frontier-fila bygges, + musserende. Utsatt for å holde snapshot bundet denne runden.
- [ ] Begynn å bygge klokke-tabell i `knowledge/smaksprofil.md` for topp-viner (Fenocchio + Paraje Altamira der nå — fortsett å utvide)
- [ ] Vurder å legge til et drueblending-kompendium for druer brukeren liker (Barbera, Nebbiolo, Riesling, Sangiovese, Tannat, Corvina-blend)
- [ ] Test mot 3 reelle scenarier etter strukturskifte: hverdagsrød under 250 kr, osso buco-paring, Etna-utvidelse

## Ferdig
- [x] 2026-07-02: **Utvid pool + smartere utforsking (4 faser).** (1) `tools/polet_facets.py` + 20 tester — rene vmpws facet-query-byggere; verifiserte at repeterte facets er AND, ikke OR (klokke-range → flere queries unionert). (2) Snapshot 557 → 1849 via live facet-sweep (New World + alt-regioner, bredde). (3) `tasks/exploration/`-frontier-struktur (INDEX + template + newworld flyttet). (4) ADR-022 (Vivino-sync levert) + ADR-023 (facet-sweep) + roadmap Levert. QA: 184 tester grønne, snapshot-integritet OK, smoke OK. Kjerne-land klokke-topp + hvit/musserende utsatt (se Backlog).
- [x] 2026-06-09: **Device-agnostisk Polet-refresh (remote browser via CDP) — ADR-021.** Refresh er ikke lenger desktop-bundet. Empirisk verifisert: lokal chromium i web-containeren (Claude Code on the web) hard-blokkeres av Cloudflare (403 på `/vmpws/` + produktsider) fordi Anthropics Egress Gateway re-originerer TLS → datasenter-fingerprint. Løsning: pek Playwright-MCP på en **remote browser via CDP** (`browser.cdpEndpoint`). Verifisert at **Browserbase gratis-tier** (`wss://connect.browserbase.com?apiKey=…`, `connectOverCDP`) passerer WAF-en: forside 200 + `/vmpws/`-API 200 (rik JSON), uten paid residential-proxy. Foretrukket vei på ALLE enheter (desktop/Android/web) — én rutine, ingen device-branching; lokal desktop-chromium degradert til nød-utvei. Leveranser: ADR-021 + ADR-020 status-amendment + tech-debt #0a oppdatert (`docs/ARCHITECTURE.md`), device-agnostisk runbook (`docs/polet_refresh.md`), config-template (`docs/polet-mcp.config.example.json`, secret gitignored), transport-agnostisk docstring (`tools/refresh_polet.py`), oppdatert `CLAUDE.md` + `roadmap.md`. **Oppsett automatisert:** committet `.mcp.json` auto-registrerer Playwright-MCP med `--cdp-endpoint ${POLET_BROWSER_CDP}` (verifisert: starter rent uten env-var, kobler lazily → null Browserbase-budsjett før faktisk refresh). Eneste per-enhet-steg er å sette env-var `POLET_BROWSER_CDP`.
- [x] 2026-06-09: **Full desktop-refresh av Polet-snapshot kjørt.** Katalog utvidet **67 → 516** (friske priser + peer-pools fra Vivino-historikk; meta.generated_at fersk). Details hentet for **hele katalogen: 516/516** (514 m/klokker; de 2 uten er grappa) via desktop-Playwright-MCP med høflig adaptiv backoff (~1,4s spacing — Polet rate-limiter straffer bulk, så ~25 trege runder + én cooldown). Ingest via 4 parallelle sub-agenter, 0 avvist av positiv validering. value_score har nå full peer-prising (f.eks. Fenocchio: 50 peers). De gamle 118 orphans er nå superseded for katalog-viner (kun relevante for ev. ikke-katalogiserte oppslag). Runbook: `docs/polet_refresh.md`.
- [x] 2026-06-08: **Fikset WAF-blokkering av Polet** (ADR-020). `vmpws` er WAF-blokkert for `requests`; løst med repo-committet snapshot i `data/polet/` + Claude-drevet Playwright-MCP-refresh (forkastet Python-Playwright — tung dep + hjelper ikke Android). Cross-device: desktop = read+refresh, Android = read-only. Nye moduler: `tools/polet_store.py` (lesere + write-helpers m/ positiv validering + `PoletRefreshRequired`), `tools/seed_polet_store.py`, `tools/refresh_polet.py`. `vinmonopolet.py`/`value_score.py` leser snapshot; value alders-merkes; `LOGIC_VERSION` v1→v2. Seed-tall: **67 katalog-produkter, 4 details mappet, 118 orphans**. Runbook: `docs/polet_refresh.md`.
- [x] 2026-05-12: Strukturert prosjekt fra claude.ai til Claude Code (mappestruktur + CLAUDE.md + WSET-konvertering)
- [x] 2026-05-12: Verifisert at vinmonopolet.py fungerer mot dagens Polet-HTML (klokker, stil, druer, lukt, smak hentes korrekt)
- [x] 2026-05-12: Bygget `knowledge/sommelier.md` (3298 linjer faglig vinkunnskap) via 6 parallelle research-subagenter
- [x] 2026-05-12: Splittet i to-lags kunnskaps-arkitektur: `knowledge/` (alltid lastet, lean) vs `deep-knowledge/` (on-demand, WSET L3). 13 region-filer i deep-knowledge oppgradert til L3-standard (klima, jord, viti, vinifisering, lover, marked) via 8 parallelle subagenter. Stripped alle bruker-spesifikke referanser fra deep-knowledge så det er nøytral fagreferanse.
- [x] 2026-05-12: Lagt inn eksplisitt feedback-løkke i CLAUDE.md og smaksprofil.md – levende dokumenter som oppdateres fra Vivino-dumps og bruker-feedback.
- [x] 2026-05-14 — User-fit-score v0 implementert. Se roadmap.md, ADR-015.
