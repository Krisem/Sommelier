# Polet-refresh — desktop-runbook

> Praktisk oppskrift for å oppdatere det repo-committede Polet-snapshotet i `data/polet/`.
> Bakgrunn og designvalg: [ADR-020](ARCHITECTURE.md#adr-020-repo-committet-polet-snapshot--cross-device-desktop-refresh--android-read-only) (les den hvis du lurer på *hvorfor*).

## Hvem kan kjøre dette

**Kun desktop.** Refresh krever en ekte nettleser forbi WAF-en — det betyr Claude Code på Mac med **Playwright-MCP + lokal chromium**. Android-enheten er read-only og kan aldri refreshe; den konsumerer bare det committede snapshotet.

Forutsetninger:
- Playwright-MCP koblet til (`browser_navigate`, `browser_evaluate` tilgjengelig).
- Repoet sjekket ut, du står på en branch der `data/polet/` kan committes.

## Hvorfor browser-fetch (ikke `requests`)

`requests` mot `vmpws` gir 403 (WAF gjenkjenner ikke-nettleser-TLS). Men når du **først har navigert til vinmonopolet.no i en ekte nettleser**, kan du kjøre `fetch()` fra samme origin via `browser_evaluate` — da arver kallet browserens TLS-fingeravtrykk, cookies og headere og slipper gjennom.

Bekreftet 2026-06-08:
- `fetch('/vmpws/v2/vmp/products/search?…')` → **200** (rik JSON).
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

- Bruk `q`-syntaks / fasetter som i [ADR-009](ARCHITECTURE.md#adr-009-polet-fasett-api-i-_peer_percentile-ikke-3-fritekstsøk) — husk at fasett-verdier er `.code` (lowercase: `rødvin`, `italia`), ikke `.name`.
- Mat JSON-en inn i write-helperne (`tools/refresh_polet.py` ingest-helpers → `tools/polet_store.py:upsert_products`). Hver linje får `fetched_at`; NDLJSON sorteres deterministisk på `code`.

### 3. Kjør peer-pool-sveip

Peer-poolene er kategori×land-kombinasjonene `value_score` trenger for percentil-beregning. Hent søkestrengene fra `tools/refresh_polet.py:peer_pool_queries()` og kjør hvert søk gjennom samme `fetch`-mønster som steg 2. Dette holder katalogen bred nok til at value-anbefalinger har et reelt sammenligningsgrunnlag.

### 4. Hent dybde for finalister (details)

For de 2–3 mest aktuelle vinene (ikke alle — se rate-limit):

```js
fetch('<product_url>').then(r => r.text())
```

Send HTML-en gjennom `parse_product_html` (uendret) → write-helper `tools/polet_store.py:save_details`. Hver fil får selv-identifiserende `code`/`url`/`fetched_at`.

**Re-knytting av orphans:** `_orphan_details.json` inneholder 118 rekonstruerte klokke-poster uten varenr. Når du henter en produktside med kjent varenr som matcher en orphan, flyttes den til `details/<varenr>.json`. Over tid tømmes orphan-fila ved normal finalist-henting.

### 5. Verifiser

- **`save_details` har positiv validering** — den krever forventet varenr + navn + (klokke|pris) og **avviser WAF-challenge-HTML og DOM-drift** før skriving. Får du en avvisning: du fikk sannsynligvis en challenge-side, ikke produktsiden — naviger på nytt (steg 1) og prøv igjen.
- **Git-diff er linjebasert** (deterministisk serialisering). Sjekk `git diff data/polet/` — endringene skal være lesbare per-linje, ikke en omstokking av hele fila. Stor støy = noe er galt med serialiseringen.
- Oppdatér `catalog_meta.json` (`generated_at`, `count`, `category_coverage`) skjer via write-helperne — bekreft at `generated_at` har flyttet seg.

### 6. Commit

Commit `data/polet/` på en branch. Når Android puller, ser den friskt snapshot. Value-verdict slutter å degradere språket så snart `snapshot_age_days` faller under 14.

## Rate-limit

Maks **~30 produktoppslag per sesjon**. Bredde-søk (steg 2/3) er billige (ett kall per søk, mange produkter). Det er dybde-hentingen (steg 4, én produktside per kall) som teller mot grensen — derfor kun finalister, ikke hele trefflista.

## Når snapshotet er gammelt (Android-perspektiv)

Du kan ikke refreshe fra Android. Hvis en vin ikke er i snapshot, får du `PoletRefreshRequired` med hint om å refreshe fra desktop — det er forventet, ikke en feil. Value-anbefalinger på gammelt snapshot er alders-merket; formidle det videre til brukeren («snapshot er X dager gammelt — verifiser pris på polet.no»).
