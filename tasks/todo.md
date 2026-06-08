# Todo

## Aktivt

### 🔧 Fiks WAF-blokkering av Polet (egen ren sesjon — høy prioritet)
**Problem (2026-06-08):** Polets webshop-API (`vmpws`) er WAF-blokkert — `requests`-kall gir 403. `tools/vinmonopolet.py` (search/get_product_details), `value_score.py` og klokke-similarity er dermed døde via `requests`. Offentlig CSV avviklet; åpent API for tynt (kun varenr+navn); presse-API krever pressebehov. Fungerende vei: ekte nettleser (Playwright) — bevist manuelt i dag.

**Mål:** delt nettleser-henter som både Polet og en framtidig `vivino_sync` bruker. Skissert retning (ADR-019): (1) bulk-sveip webshop-søk → lokalt katalog-snapshot for bredde (varenr, navn, pris, kategori, land, region); (2) on-demand produktside for dybde (klokker, drue) på finalister; (3) drift-vern (fixture-test à la ADR-011); (4) bump `LOGIC_VERSION` i value_score for å invalidere cache.

**Åpen beslutning ved oppstart:** Python-Playwright-avhengighet (autonomt, headless, testbart, men tung dep + browser-binær) vs. Claude-drevet Playwright-MCP som mater snapshot/cache (ingen ny dep, men Claude må i loop for refresh). Avklar dette først.

**Kontekst-pekere:** [ADR-019](../docs/ARCHITECTURE.md), teknisk gjeld #0, `knowledge/_archive/rapport.md` (utdatert-notis), CLAUDE.md § Vinmonopolet-tool.

## Backlog
- [ ] Begynn å bygge klokke-tabell i `knowledge/smaksprofil.md` for topp-viner (kun Fenocchio Barbera er der nå)
- [ ] Vurder å legge til et drueblending-kompendium for druer brukeren liker (Barbera, Nebbiolo, Riesling, Sangiovese, Tannat, Corvina-blend)
- [ ] Test mot 3 reelle scenarier etter strukturskifte: hverdagsrød under 250 kr, osso buco-paring, Etna-utvidelse

## Ferdig
- [x] 2026-05-12: Strukturert prosjekt fra claude.ai til Claude Code (mappestruktur + CLAUDE.md + WSET-konvertering)
- [x] 2026-05-12: Verifisert at vinmonopolet.py fungerer mot dagens Polet-HTML (klokker, stil, druer, lukt, smak hentes korrekt)
- [x] 2026-05-12: Bygget `knowledge/sommelier.md` (3298 linjer faglig vinkunnskap) via 6 parallelle research-subagenter
- [x] 2026-05-12: Splittet i to-lags kunnskaps-arkitektur: `knowledge/` (alltid lastet, lean) vs `deep-knowledge/` (on-demand, WSET L3). 13 region-filer i deep-knowledge oppgradert til L3-standard (klima, jord, viti, vinifisering, lover, marked) via 8 parallelle subagenter. Stripped alle bruker-spesifikke referanser fra deep-knowledge så det er nøytral fagreferanse.
- [x] 2026-05-12: Lagt inn eksplisitt feedback-løkke i CLAUDE.md og smaksprofil.md – levende dokumenter som oppdateres fra Vivino-dumps og bruker-feedback.
- [x] 2026-05-14 — User-fit-score v0 implementert. Se roadmap.md, ADR-015.
