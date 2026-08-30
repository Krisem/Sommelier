# Todo

## Aktivt

*(ingen aktive tråder)*

## Backlog
- [ ] **Hvit/musserende/rosé-ekspansjon** — de står fortsatt med gammel, `pageSize`-avkortet dekning
      (hvitvin 152, musserende 99, rosé 53). Samme oppskrift som rødvin: full enumerering + kartesisk
      klokke-sveip. Merk at klokke-dimensjonene er andre for hvitvin (`Soedme` og `Bitterhet` ga 0 treff
      for rødvin, men kan være gyldige der) — probe før du planlegger.
- [ ] **43 rødviner har Fylde uten Friskhet** og faller ut av trippel-basert klokke-ingest. Krever
      1-dim marginalsveip (~1 370 sider) for 0,3 % av basen. Ikke prioritert.
- [ ] **`find_similar_by_clocks` kan nå kjøre offline over 10 986 katalograder** i stedet for kun de med
      details (ADR-023 flagget begrensningen). MEN: må merkes tydelig som «finner stil-slektninger»,
      ikke «finner noe like godt» — Vespa-bommen 2026-08-29 var nettopp klokke-similarity som pekte på
      en vin med identiske klokker og motsatt dom.
- [x] ~~**Kjerne-land klokke-topp (utsatt fra 2026-07-02)**~~ — superseded av «Komplett rødvins-snapshot» over; den gamle formuleringen bygde dessuten på `Garvestoffer`-fasetten, som ikke filtrerer. Opprinnelig: — utvid snapshot med IT/FR/DE/ES rødvin i sweet-spoten (Fylde 7-8 × Friskhet 9-12, ~723 røde). Ble rate-limitet ut i facet-sweepen; kjør senere med gentle backoff (`polet_facets.build_facet_queries`).
- [ ] **Hvit/musserende-ekspansjon** — samme facet-sweep for aromatisk hvit (østerrike/tyskland/new_zealand) når den frontier-fila bygges, + musserende. Utsatt for å holde snapshot bundet denne runden.
- [ ] Begynn å bygge klokke-tabell i `knowledge/smaksprofil.md` for topp-viner (Fenocchio + Paraje Altamira der nå — fortsett å utvide)
- [ ] Vurder å legge til et drueblending-kompendium for druer brukeren liker (Barbera, Nebbiolo, Riesling, Sangiovese, Tannat, Corvina-blend)
- [ ] Test mot 3 reelle scenarier etter strukturskifte: hverdagsrød under 250 kr, osso buco-paring, Etna-utvidelse

## Ferdig
- [x] 2026-08-29/30: **Komplett rødvins-snapshot med klokker og dybde.** Rødvin 1 543 → **13 775**
  (hele Polets sortiment), 3 l 62 → **313**, Basisutvalget 121 → **468**. Klokke-bøtter på **10 986
  (79,8 %)** via kartesisk fasett-sveip. Details for hele det prioriterte utsnittet: 3 l 313/313,
  Basis 468/468, Tillegg 481/481 — 1 153 sider, 0 avvist, 0 uten JSON-blobb. 1 668 details i repoet.
  Katalogen prunet 1 631 → 849 B/rad (47,6 %). 32 avregistrerte varer slettet. Tester 184 → 287.
  ADR-024. **Fem bugs funnet underveis, alle stille:** (1) `pageSize` har servertak 24, så hver
  sveip under ADR-023 var avkortet — det forklarte skjevheten i det gamle snapshotet; (2) fasetten
  `Garvestoffer` filtrerer ikke, den returnerer hele katalogen (riktig kode: `Tannin(Sulfates)`);
  (3) `sort=relevance` hopper over produkter under paginering; (4) regex-parseren hentet aldri
  `land`/`produsent`/`årgang`; (5) snapshotet akkumulerte varer med `buyable: true` som ikke lenger
  fantes. **Kvoten er kartlagt:** to bøtter (søk 3399 s, produktsider 300 s), produktside-straffen
  eskalerer til 3600 s ved vedvarende last, taket er ~65–85 sider/syklus, riktig pause 7,5 min.
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
