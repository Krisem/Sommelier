# Polet-refresh — device-agnostisk runbook

> Praktisk oppskrift for å oppdatere det repo-committede Polet-snapshotet i `data/polet/`.
> Bakgrunn og designvalg: [ADR-020](ARCHITECTURE.md#adr-020-repo-committet-polet-snapshot--cross-device-desktop-refresh--android-read-only) (snapshot-modellen) og [ADR-021](ARCHITECTURE.md#adr-021-remote-browser-via-cdp--device-agnostisk-refresh) (remote browser — *hvorfor* refresh ikke lenger er desktop-bundet).

## Hvem kan kjøre dette

**Alle enheter** — desktop, Android *og* Claude Code on the web — så lenge du kobler refresh-browseren til en **remote browser-tjeneste via CDP**. Selve sidehentingen skjer da på tjenestens rene egress (genuin browser-fingerprint), som passerer Vinmonopolets Cloudflare-WAF. Lokal-enheten din driver bare browseren over en CDP-websocket; den trenger ingen egen chromium.

> **Hvorfor ikke bare lokal browser overalt?** Cloudflare hard-blokkerer datasenter-IP-er og ikke-browser-TLS. På en **vanlig desktop** når chromium Cloudflare *direkte* med genuin fingerprint → fungerer. Men i et MITM-proxy-miljø (Claude Code on the web går gjennom Anthropics Egress Gateway, likeledes mange bedriftsproxyer) ser Cloudflare proxyens datasenter-fingerprint, ikke chromiums → **hard 403**. Empirisk bekreftet 2026-06-09: lokal chromium i web-containeren fikk 200 på forsiden men 403 «Sorry, you have been blocked» på `/vmpws/` og produktsider. Remote browser via CDP omgår dette fordi WAF-en møter *tjenestens* browser, ikke din proxy. Se [ADR-021](ARCHITECTURE.md#adr-021-remote-browser-via-cdp--device-agnostisk-refresh).

## Oppsett

**MCP-registreringen er automatisk** — repoet har en committet [`.mcp.json`](../.mcp.json) som registrerer Playwright-MCP pekt på en remote browser via `--cdp-endpoint ${POLET_BROWSER_CDP}`. Du trenger **ikke** `claude mcp add` eller å kopiere noen config-fil. Det eneste per-enhet-steget er å sette én hemmelig env-variabel:

1. **Skaff en CDP-endpoint** fra en remote browser-tjeneste:
   - **Browserbase** (verifisert 2026-06-09 — *gratis-tier holder* for lavvolum månedlig refresh): lag konto → API-nøkkel. CDP-URL: `wss://connect.browserbase.com?apiKey=DIN_KEY`. Gratis-tier kjører uten residential-proxy (paid), men Browserbases egen IP + genuin chromium passerer Vinmonopolets Cloudflare likevel.
   - **Browserless** (alternativ): `wss://production-sfo.browserless.io?token=DITT_TOKEN`.
2. **Sett `POLET_BROWSER_CDP`** til hele CDP-URL-en (med token). Token er en hemmelighet — den bor KUN i env, aldri i repoet:
   - **Claude Code on the web:** legg den inn som env-variabel i miljø-konfigurasjonen (env/secrets) for environmentet.
   - **Desktop/Android (shell):** `export POLET_BROWSER_CDP='wss://connect.browserbase.com?apiKey=DIN_KEY'` i shell-profilen (`~/.zshrc` / `~/.bashrc`).
3. **Det er alt.** Neste Claude Code-sesjon i repoet får `playwright`-MCP-serveren (`browser_navigate` / `browser_evaluate`) automatisk, koblet mot skybrowseren.

> **Late connect — ingen budsjett-lekkasje:** MCP-serveren kobler seg til skybrowseren først ved *første* browser-tool-kall (verifisert 2026-06-09), ikke ved sesjonsstart. Den bare ligger der dormant i vanlige read-sesjoner og bruker null Browserbase-tid før du faktisk refresher. Er `POLET_BROWSER_CDP` ikke satt, starter serveren rent men dormant (tomt endpoint) — den blokkerer ingenting.

> **Remote-CDP er den foretrukne veien på ALLE enheter — også desktop.** Én refresh-rutine å vedlikeholde, identisk oppførsel overalt, ingen device-branching. Lokal desktop-chromium (Playwright-MCP med default lokal browser) fungerer fortsatt på en vanlig Mac med direkte egress, men er nå kun en **nød-utvei** hvis du midlertidig er uten remote-konto — ikke standardoppsettet.
>
> *Alternativ (config-fil i stedet for env-var):* `cp docs/polet-mcp.config.example.json polet-mcp.config.json` (gitignored), fyll inn `cdpEndpoint`, og pek MCP-en på den med `--config`. Nyttig hvis du trenger `cdpHeaders` (f.eks. Browserless token-i-header). Env-var-veien over er enklere og er standarden.

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

## Rate-limit — målt, ikke gjettet (2026-08-29)

Polet har en **timeskvote på ~800–900 forespørsler**. Målt under den komplette rødvins-sveipen: ~520 sider gikk fint på ~39 min, deretter ga sidene `429` med **`Retry-After: 3399`** — altså 57 minutter, en times-kvote og ikke en kort throttle.

> Den gamle formuleringen her («maks ~30 produktoppslag per sesjon») var et anslag uten måling og er nå erstattet. Den var både for streng for bredde-søk og gjorde det umulig å planlegge dybde.

Praktiske følger:
- **Bredde og dybde teller likt.** Det er antall HTTP-kall som er valutaen, ikke hva de returnerer. Én katalogside (24 produkter) koster like mye som én produktside (1 produkt) — derfor er bredde ~24× mer effektivt per kall.
- **Full enumerering av rødvin = 574 sider.** Det er godt innenfor ett vindu.
- **Dybde for alle 13 775 rødviner = ~16 kvotevinduer (~16 timer).** Details er derfor permanent et *prioritert utsnitt*, ikke noe som tas «senere». Til referanse: alle 3 l + hele Basisutvalget er 694 manglende details — det fyller ett vindu.
- **Sjekk HTTP-status per side.** En `429` som telles som data gir stille avkorting. Stopp ved første `429`; en retry brenner bare kvote.
- **Produktsider er en EGEN bøtte med egen straff.** Søk gir `Retry-After: 3399` (57 min); produktsider gir `Retry-After: 300` (5 min). Ikke bland dem i et estimat — det var nettopp det som ga et 16-timers-anslag der det riktige er ~24.
- **Ikke stol på `Retry-After` for produktsider — vent ~7,5 min, ikke de 5 den ber om.** Målt over tre sykluser: 5,3 min pause → 83 sider, 5,4 min → 34, 7,3 min → 82. Bøtta er ikke fylt opp igjen når headeren sier den er det, så bokstavelig lydighet gir ustabilt og omtrent halvert utbytte. Vedvarende takt med riktig pause: **~82 sider per syklus, ~10 sider i minuttet.**
- **⚠️ Straffen ESKALERER ved vedvarende belastning: 300 s → 3600 s.** Dette er det viktigste å vite før en stor jobb. Etter flere timers sammenhengende burst-and-wait hoppet `Retry-After` fra 300 til **3600 sekunder** (målt 2026-08-30: 54 sider hentet, så 3600; neste kall ga 0 sider og 3107 — samme blokk med nedtelling). **De 300 sekundene er altså første trinn i en trapp, ikke en fast straff.** 7,5-minutters-rytmen fungerer, men ikke i det uendelige. Planlegg en stor jobb (>500 sider) enten med lavere takt fra start — f.eks. ~50 sider per syklus i stedet for å presse til `429` — eller med en lengre hvile innlagt underveis. Estimatet på ~24 timer for hele katalogen er derfor et **gulv, ikke et tak**.
- **Bøtta har et tak rundt 65–85 sider — å vente lenger enn 7,5 min gir ingenting.** Målt: etter en pause på flere timer (maskinen sov natten over) ga første kall 64 sider, altså samme størrelsesorden som etter 7,5 minutter. Det er altså en kapasitetsgrense per syklus, ikke en lineært opptjent kvote. Praktisk: 7,5 min er både minimum og optimum — lengre pauser er bortkastet tid, kortere gir halvert utbytte.
- **Burst-and-wait slår jevn pacing.** Hent til `429`, vent ut cooldownen, fortsett. Hvert `browser_evaluate` er uansett begrenset av et tidstak, så jevn pacing koster flere verktøykall uten å gi mer data.
- Browserbase gratis-tier har i tillegg ~1 browser-time/mnd — rikelig til månedlig refresh, ikke til polling.

## Paginering og sortering — to feller

**`pageSize` har et servertak på 24.** Målt: 24/25/48/50 gir alle `pagination.pageSize: 24`. Ber du om 50, får du 24 uten noen feilmelding. Alle sveip kjørt før 2026-08-29 var stille avkortet av dette. Bruk `currentPage` for å paginere — den virker helt ut (side 573 av 574 ga 23 produkter).

**Paginer aldri på `sort=relevance`.** Relevans-rangering er ikke stabil mellom kall, så paginering både dupliserer og **hopper over** produkter. Målt: en full `relevance`-passering ga 13 775 rader, men bare 13 774 unike — ett produkt forsvant. Bruk `name-asc` (deterministisk). Og tell alltid unike koder mot `totalResults` til slutt; et skip er usynlig uten den tellingen.

**Fasett-koder feiler stille.** `facets[]` i søkesvaret er alltid tomt, så du kan ikke oppdage gyldige koder — du må probe. En ugyldig kode blir *ignorert*, ikke avvist, så queryen returnerer hele katalogen mens du tror den filtrerte. Kontrollen er å sammenligne `totalResults` mot det ufiltrerte tallet: er de like, filtrerer ikke fasetten din. For rødvin er kun `Fylde`, `Friskhet` og `Tannin(Sulfates)` gyldige — `Garvestoffer` er navnet i produktsidens JSON, ikke i søke-fasettene.

## Butikk-spesifikt live-oppslag (øl, og «har butikk X varen?»)

Snapshotet er vin-only og har **bevisst ikke** butikk-lager (ADR-020) — lager er
ferskvare. Nevner brukeren et **konkret pol** (øl *eller* vin), er «er den inne
der?» selve premisset, ikke en detalj. Da må du gå **live**, ikke gjette fra
snapshot eller sortimentskunnskap (se `tasks/lessons.md` 2026-07-04).

`tools/polet_live.py` holder den testbare delen (URL-bygging + JSON-parsing);
nett-hoppet skjer i browseren (samme WAF-omgåelse som over — naviger først, så
`fetch` same-origin via `browser_evaluate`):

```
browser_navigate  →  https://www.vinmonopolet.no/          # sett WAF-cookies
```
```python
from tools.polet_live import stores_url, find_store, product_search_url, parse_products

# 1) finn butikk-ID (q-param filtrerer ikke på dette endepunktet — filtrer klient-side)
#    browser_evaluate: () => fetch('<stores_url()>').then(r => r.json())
store = find_store(<stores_json>, "Røa")        # → {'id': '335', ...}

# 2) søk filtrert til den butikken (availableInStores-fasett)
#    browser_evaluate: () => fetch('<product_search_url(...)>').then(r => r.json())
url = product_search_url("geuze", store_id=store["id"])   # category="øl" er default
parse_products(<hits_json>)   # → [{code, name, style, abv, volume, price, stock}, …]
```

`stock` (f.eks. `"5 i butikken"`) kommer kun med når søket er filtrert på
`store_id`. **Aldri anbefal en vare for et navngitt pol uten bekreftet `stock`
der.** Fordelen over et øl-snapshot: ett billig kall gir ferskt lager + stil +
pris, uten detalj-rate-limiten — og lager kan et snapshot uansett ikke holde.

## Når snapshotet er gammelt

Hvis en vin ikke er i snapshot, får du `PoletRefreshRequired` med hint om å refreshe — det er forventet, ikke en feil. Value-anbefalinger på gammelt snapshot er alders-merket; formidle det videre til brukeren («snapshot er X dager gammelt — verifiser pris på polet.no»). Med remote-CDP-oppsettet kan refresh nå kjøres fra hvilken som helst enhet, inkludert mobil og web.
