# Polet-refresh — device-agnostisk runbook

> Praktisk oppskrift for å oppdatere det repo-committede Polet-snapshotet i `data/polet/`.
> Bakgrunn og designvalg: [ADR-020](ARCHITECTURE.md#adr-020-repo-committet-polet-snapshot--cross-device-desktop-refresh--android-read-only) (snapshot-modellen) og [ADR-021](ARCHITECTURE.md#adr-021-remote-browser-via-cdp--device-agnostisk-refresh) (remote browser — *hvorfor* refresh ikke lenger er desktop-bundet).

## Hvem kan kjøre dette

**Alle enheter** — desktop, Android *og* Claude Code on the web — så lenge du kobler refresh-browseren til en **remote browser-tjeneste via CDP**. Selve sidehentingen skjer da på tjenestens rene egress (genuin browser-fingerprint), som passerer Vinmonopolets Cloudflare-WAF. Lokal-enheten din driver bare browseren over en CDP-websocket; den trenger ingen egen chromium.

> **Hvorfor ikke bare lokal browser overalt?** Cloudflare hard-blokkerer datasenter-IP-er og ikke-browser-TLS. På en **vanlig desktop** når chromium Cloudflare *direkte* med genuin fingerprint → fungerer. Men i et MITM-proxy-miljø (Claude Code on the web går gjennom Anthropics Egress Gateway, likeledes mange bedriftsproxyer) ser Cloudflare proxyens datasenter-fingerprint, ikke chromiums → **hard 403**. Empirisk bekreftet 2026-06-09: lokal chromium i web-containeren fikk 200 på forsiden men 403 «Sorry, you have been blocked» på `/vmpws/` og produktsider. Remote browser via CDP omgår dette fordi WAF-en møter *tjenestens* browser, ikke din proxy. Se [ADR-021](ARCHITECTURE.md#adr-021-remote-browser-via-cdp--device-agnostisk-refresh).

## Oppsett (én gang per enhet)

1. **Skaff en CDP-endpoint** fra en remote browser-tjeneste:
   - **Browserbase** (verifisert 2026-06-09 — *gratis-tier holder* for lavvolum månedlig refresh): lag konto → API-nøkkel. CDP-URL: `wss://connect.browserbase.com?apiKey=DIN_KEY`. Gratis-tier kjører uten residential-proxy (paid), men Browserbases egen IP + genuin chromium passerer Vinmonopolets Cloudflare likevel.
   - **Browserless** (alternativ): `wss://production-sfo.browserless.io?token=DITT_TOKEN`.
2. **Lag den gitignored config-fila** (token er en hemmelighet — aldri i repoet):
   ```sh
   cp docs/polet-mcp.config.example.json polet-mcp.config.json
   # rediger polet-mcp.config.json → sett inn din cdpEndpoint
   ```
   `polet-mcp.config.json` står i `.gitignore`.
3. **Pek Playwright-MCP på den remote browseren.** Enten som MCP-server i Claude Code:
   ```sh
   claude mcp add playwright -- npx @playwright/mcp@latest --config "$(pwd)/polet-mcp.config.json"
   ```
   (eller legg tilsvarende i `.mcp.json`). Da blir `browser_navigate` / `browser_evaluate` tilgjengelige og kjører mot skybrowserne.

> **Remote-CDP er den foretrukne veien på ALLE enheter — også desktop.** Én refresh-rutine å vedlikeholde, identisk oppførsel overalt, ingen device-branching. Lokal desktop-chromium (Playwright-MCP med default lokal browser) fungerer fortsatt på en vanlig Mac med direkte egress, men er nå kun en **nød-utvei** for hvis du midlertidig er uten remote-konto — ikke standardoppsettet.

## Hvorfor browser-fetch (ikke `requests`)

`requests`/`curl` mot `vmpws` gir 403 (WAF gjenkjenner ikke-nettleser-TLS). Når du **først har navigert til vinmonopolet.no i en ekte nettleser**, kan du kjøre `fetch()` fra samme origin via `browser_evaluate` — kallet arver browserens TLS-fingerprint, cookies og headere og slipper gjennom.

Bekreftet:
- `fetch('/vmpws/v2/vmp/products/search?…')` → **200** (rik JSON). *(via remote browser 2026-06-09: 200; via lokal chromium bak Egress Gateway: 403)*
- `?fields=FULL` → **400** (ikke støttet — ikke bruk det).
- Produktside-HTML → **200**, matcher `parse_product_html`.

## Steg-for-steg

### 1. Passer WAF

```
browser_navigate  →  https://www.vinmonopolet.no/
```

Lar browseren sette cookies. Alt videre `fetch` kjøres som same-origin fra denne fanen.

### 2. Hent bredde (katalog)

For hvert søk, kjør via `browser_evaluate`:

```js
fetch('/vmpws/v2/vmp/products/search?q=<søk>&pageSize=<n>')
  .then(r => r.json())
```

- Bruk `q`-syntaks / fasetter som i [ADR-009](ARCHITECTURE.md#adr-009-polet-fasett-api-i-_peer_percentile-ikke-3-fritekstsøk) — husk at fasett-verdier er `.code` (lowercase: `rødvin`, `italia`), ikke `.name`. URL-encode hele `q` (de norske kodene har `ø`/`å`).
- Mat JSON-en inn i write-helperne (`tools/refresh_polet.py:ingest_search_payload` → `tools/polet_store.py:upsert_products`). Hver linje får `fetched_at`; NDLJSON sorteres deterministisk på `code`.

### 3. Kjør peer-pool-sveip

Peer-poolene er kategori×land-kombinasjonene `value_score` trenger for percentil-beregning. Hent søkestrengene fra `tools/refresh_polet.py:peer_pool_queries()` og kjør hvert søk gjennom samme `fetch`-mønster som steg 2. Dette holder katalogen bred nok til at value-anbefalinger har et reelt sammenligningsgrunnlag.

### 4. Hent dybde for finalister (details)

For de 2–3 mest aktuelle vinene (ikke alle — se rate-limit):

```js
fetch('<product_url>').then(r => r.text())
```

Send HTML-en gjennom `parse_product_html` (uendret) → write-helper `tools/polet_store.py:save_details` (via `tools/refresh_polet.py:ingest_details_html`). Hver fil får selv-identifiserende `code`/`url`/`fetched_at`.

**Re-knytting av orphans:** `_orphan_details.json` inneholder rekonstruerte klokke-poster uten varenr. Når du henter en produktside med kjent varenr som matcher en orphan, flyttes den til `details/<varenr>.json`. Over tid tømmes orphan-fila ved normal finalist-henting.

### 5. Verifiser

- **`save_details` har positiv validering** — den krever forventet varenr + navn + (klokke|pris) og **avviser WAF-challenge-HTML og DOM-drift** før skriving. Får du en avvisning: du fikk sannsynligvis en challenge-side, ikke produktsiden — naviger på nytt (steg 1) og prøv igjen.
- **Git-diff er linjebasert** (deterministisk serialisering). Sjekk `git diff data/polet/` — endringene skal være lesbare per-linje, ikke en omstokking av hele fila. Stor støy = noe er galt med serialiseringen.
- `catalog_meta.json` (`generated_at`, `count`, `category_coverage`) oppdateres via write-helperne — bekreft at `generated_at` har flyttet seg.

### 6. Commit

Commit `data/polet/` på en branch. Når en annen enhet puller, ser den friskt snapshot. Value-verdict slutter å degradere språket så snart `snapshot_age_days` faller under 14.

## Rate-limit

Maks **~30 produktoppslag per sesjon**. Bredde-søk (steg 2/3) er billige (ett kall per søk, mange produkter). Det er dybde-hentingen (steg 4, én produktside per kall) som teller mot grensen — derfor kun finalister, ikke hele trefflista. Browserbase gratis-tier har dessuten ~1 browser-time/mnd; det er rikelig til et månedlig refresh, men ikke til kontinuerlig polling.

## Når snapshotet er gammelt

Hvis en vin ikke er i snapshot, får du `PoletRefreshRequired` med hint om å refreshe — det er forventet, ikke en feil. Value-anbefalinger på gammelt snapshot er alders-merket; formidle det videre til brukeren («snapshot er X dager gammelt — verifiser pris på polet.no»). Med remote-CDP-oppsettet kan refresh nå kjøres fra hvilken som helst enhet, inkludert mobil og web.
