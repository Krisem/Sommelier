# Todo

## Aktivt

### Prosjekt: utvid pool + smartere utforsking (2026-07-02)
Fra brukerønske. Alle 4 valgt. Subagenter for ren kode/docs + meg for browser-sweep + QA.

**Verifiserte fakta (denne økta):**
- `vmpws`-API virker fra browser-kontekst (WAF blokkerer `requests` i Python — jf. ADR-019/021; live-query er browser-only + egress-avhengig).
- Klokke-fasetter er bøtter: `1-2 · 3-4 · 5-6 · 7-8 · 9-10 · 11-12` for `Fylde/Friskhet/Garvestoffer/Soedme/Tannin(Sulfates)/Bitterhet`.
- Query: `:relevance:Friskhet:9-10:Fylde:7-8:mainCategory:rødvin:mainCountry:argentina`. Kategori/land-koder lowercase.
- Produkt-JSON fra API = samme shape som `catalog.ndjson`-linjer (upsert lagrer as-is).

**Fase 1 — facet-sweep-mekanikk (kode) [subagent] — gater Fase 2**
- [ ] `tools/polet_facets.py` (rene funksjoner, ingen nettverk): `build_facet_query(...)` (range→union av bøtter) + `parse_search_products(api_json)` (filtrer `buyable`, felt-shape lik eksisterende catalog-linjer).
- [ ] `tests/test_polet_facets.py`: query-assembly, bøtte-mapping, buyable-filter, felt-shape.

**Fase 2 — utvid snapshot (browser-sweep) [meg]**
- [ ] Kategorier: rødvin/hvitvin/musserende_vin. Utforsknings-land full bredde (buyable): argentina, chile, sør-afrika, australia, new-zealand, portugal, østerrike, hellas, usa. Kjerne-land klokke-filtrert (Fylde 5-8 + Friskhet 7-12): italia, frankrike, tyskland, spania. Mål ~1500–2500.
- [ ] Sweep → `upsert_products` → commit. Verifiser `find_similar_by_clocks` treffer New World.

**Fase 3 — generalisér utforsknings-flight [subagent]**
- [ ] `tasks/exploration/INDEX.md` (frontier-liste over åpne blindsoner) + flytt `newworld_exploration.md` → `tasks/exploration/newworld.md` + `_TEMPLATE.md` + CLAUDE.md-linje.

**Fase 4 — roadmap/ADR-rydding [subagent, etter 1+2]**
- [ ] roadmap.md: Vivino auto-sync → Levert. ADR: Vivino-sync levert + live facet-sweep/trait-filtrering.

**QA (til slutt) [meg]**
- [ ] `pytest` grønn · snapshot-integritet (NDJSON + meta-count) · smoke `vinmonopolet.py` + `find_similar_by_clocks` · rene commits.

## Backlog
- [ ] Begynn å bygge klokke-tabell i `knowledge/smaksprofil.md` for topp-viner (Fenocchio + Paraje Altamira der nå — fortsett å utvide)
- [ ] Vurder å legge til et drueblending-kompendium for druer brukeren liker (Barbera, Nebbiolo, Riesling, Sangiovese, Tannat, Corvina-blend)
- [ ] Test mot 3 reelle scenarier etter strukturskifte: hverdagsrød under 250 kr, osso buco-paring, Etna-utvidelse

## Ferdig
- [x] 2026-06-09: **Device-agnostisk Polet-refresh (remote browser via CDP) — ADR-021.** Refresh er ikke lenger desktop-bundet. Empirisk verifisert: lokal chromium i web-containeren (Claude Code on the web) hard-blokkeres av Cloudflare (403 på `/vmpws/` + produktsider) fordi Anthropics Egress Gateway re-originerer TLS → datasenter-fingerprint. Løsning: pek Playwright-MCP på en **remote browser via CDP** (`browser.cdpEndpoint`). Verifisert at **Browserbase gratis-tier** (`wss://connect.browserbase.com?apiKey=…`, `connectOverCDP`) passerer WAF-en: forside 200 + `/vmpws/`-API 200 (rik JSON), uten paid residential-proxy. Foretrukket vei på ALLE enheter (desktop/Android/web) — én rutine, ingen device-branching; lokal desktop-chromium degradert til nød-utvei. Leveranser: ADR-021 + ADR-020 status-amendment + tech-debt #0a oppdatert (`docs/ARCHITECTURE.md`), device-agnostisk runbook (`docs/polet_refresh.md`), config-template (`docs/polet-mcp.config.example.json`, secret gitignored), transport-agnostisk docstring (`tools/refresh_polet.py`), oppdatert `CLAUDE.md` + `roadmap.md`. **Oppsett automatisert:** committet `.mcp.json` auto-registrerer Playwright-MCP med `--cdp-endpoint ${POLET_BROWSER_CDP}` (verifisert: starter rent uten env-var, kobler lazily → null Browserbase-budsjett før faktisk refresh). Eneste per-enhet-steg er å sette env-var `POLET_BROWSER_CDP`.
- [x] 2026-06-09: **Full desktop-refresh av Polet-snapshot kjørt.** Katalog utvidet **67 → 516** (friske priser + peer-pools fra Vivino-historikk; meta.generated_at fersk). Details hentet for **hele katalogen: 516/516** (514 m/klokker; de 2 uten er grappa) via desktop-Playwright-MCP med høflig adaptiv backoff (~1,4s spacing — Polet rate-limiter straffer bulk, så ~25 trege runder + én cooldown). Ingest via 4 parallelle sub-agenter, 0 avvist av positiv validering. value_score har nå full peer-prising (f.eks. Fenocchio: 50 peers). De gamle 118 orphans er nå superseded for katalog-viner (kun relevante for ev. ikke-katalogiserte oppslag). Runbook: `docs/polet_refresh.md`.
- [x] 2026-06-08: **Fikset WAF-blokkering av Polet** (ADR-020). `vmpws` er WAF-blokkert for `requests`; løst med repo-committet snapshot i `data/polet/` + Claude-drevet Playwright-MCP-refresh (forkastet Python-Playwright — tung dep + hjelper ikke Android). Cross-device: desktop = read+refresh, Android = read-only. Nye moduler: `tools/polet_store.py` (lesere + write-helpers m/ positiv validering + `PoletRefreshRequired`), `tools/seed_polet_store.py`, `tools/refresh_polet.py`. `vinmonopolet.py`/`value_score.py` leser snapshot; value alders-merkes; `LOGIC_VERSION` v1→v2. Seed-tall: **67 katalog-produkter, 4 details mappet, 118 orphans**. Runbook: `docs/polet_refresh.md`.
- [x] 2026-05-12: Strukturert prosjekt fra claude.ai til Claude Code (mappestruktur + CLAUDE.md + WSET-konvertering)
- [x] 2026-05-12: Verifisert at vinmonopolet.py fungerer mot dagens Polet-HTML (klokker, stil, druer, lukt, smak hentes korrekt)
- [x] 2026-05-12: Bygget `knowledge/sommelier.md` (3298 linjer faglig vinkunnskap) via 6 parallelle research-subagenter
- [x] 2026-05-12: Splittet i to-lags kunnskaps-arkitektur: `knowledge/` (alltid lastet, lean) vs `deep-knowledge/` (on-demand, WSET L3). 13 region-filer i deep-knowledge oppgradert til L3-standard (klima, jord, viti, vinifisering, lover, marked) via 8 parallelle subagenter. Stripped alle bruker-spesifikke referanser fra deep-knowledge så det er nøytral fagreferanse.
- [x] 2026-05-12: Lagt inn eksplisitt feedback-løkke i CLAUDE.md og smaksprofil.md – levende dokumenter som oppdateres fra Vivino-dumps og bruker-feedback.
- [x] 2026-05-14 — User-fit-score v0 implementert. Se roadmap.md, ADR-015.
