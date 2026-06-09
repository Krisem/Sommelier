# Todo

## Aktivt

*(ingen aktive tråder)*

## Backlog
- [ ] **Vivino-sync** (utsatt — ADR-019/020) — `tools/vivino_sync.py` for direkte lesing av Vivino-profilen via Playwright. Metode bevist 2026-06-08, men bevisst nedprioritert til etter Polet-snapshotet er stabilt. Se roadmap § Vivino auto-sync.
- [ ] Begynn å bygge klokke-tabell i `knowledge/smaksprofil.md` for topp-viner (kun Fenocchio Barbera er der nå)
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
