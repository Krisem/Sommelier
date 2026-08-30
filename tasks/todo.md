# Todo

## Aktivt

**Sveip 2026-08-30.** Ni agenter, disjunkt fileierskap. Utgangspunkt: 291 tester grønne, commit `b162d3e`.
Status nå: **397 tester grønne**, ingenting committet (venter på at sveipen fullfører).

| Agent | Oppdrag | Resultat |
|---|---|---|
| A | Klokke-tabell | ✅ 6 → 25 rader. **Klokkene diskriminerer ikke** (korr. +0,16/+0,09/−0,10; alle 6 grupper med identiske klokker spenner ratingskalaen) → ADR-025 |
| B | 3 scenarier | ✅ Fant **8 bugs**. Osso buco klart bedre; B1 firedoblet av ekspansjonen |
| C | `data/reference/` | ✅ **Ikke slettet** — var uattribuert kilde til `sommelier.md` §4 og `norsk-marked.md` §10. Gjeld #7 omskrevet, attribusjoner lagt inn, `bjcp_2021.pdf`-referansen var hallusinert |
| D | Vivino-sync | ✅ 5 nye ratinger (117 → 122). Runbook rettet: DOM-en har eksakte UTC-tidsstempler, metadata må brace-matches |
| E | Hvit/musserende/rosé | 🔄 Hvitvin **komplett: 9 765** (407 sider = `totalResults`). Musserende i gang, rosé gjenstår |
| F0 | B6 statusfilter | ✅ `active_only` opt-in. Muteringstest beviste at default måtte stå (13 feil + 5 errors hvis snudd) |
| F1 | B2 + B3 | ✅ Barbera 3 → 95, Etna 36 → 74, similarity 13 → **718 av 771**. Toleranse-funn: ADR-024 var «påkoblet i navnet, ikke i rangeringen» |
| F2 | B4 + B5 | ✅ `risky` **0 → 408**, blindsoner 3 → 25 land. Fire nivå-innsnevringer. To-inngang-feil funnet via uendret sanity-sjekk |
| F3 | B1 peer-percentil | ✅ Pichon Baron 0,72 → **0,50** percentil, 50 → 4 938 peers. **28,2 %** av 400 viner får korrigert verdict → ADR-026 |

**Ikke fikset, bevisst:** B7 (samme vin på flere varenumre) — se Backlog, forbeholdene kan avlyse den.
**Levert dokumentasjon:** ADR-025, ADR-026, ADR-027 (+ amendments), gjeld #7 omskrevet, #9/#10/#11 nye,
`lessons.md` +3 poster, runbook-rettelser i `polet_refresh.md` og `vivino_refresh.md`.

**Gjenstående gate:** ingen commit før E er ferdig — en commit midt i sveipen låser en halv katalog.

### Beslutninger som venter (sveip 2026-08-30)

- [ ] **Skal `active_only=True` bli default i `polet_store.query`?** F0 landet den bevisst som opt-in
      med uendret default, fordi tre andre agenter jobbet i katalogen samtidig. Muteringstest viste at
      å snu defaulten gir **13 feil + 5 errors** i `test_vinmonopolet.py` og `test_value_score.py` —
      altså er det en reell atferdsendring, ikke en opprydding. Avgjøres etter at F1/F2/F3 har landet.
      Argument for: 2 196 av 13 775 rødviner er ikke kjøpbare, hvorav 1 264 lyver med `buyable: true`.
- [ ] **Hva gjør vi med `lanseres` (376 varer)?** De har `buyable: false` og fjernes av `active_only`,
      men de er kommende lanseringer — potensielt interessante å *vise*, bare ikke som kjøpbare nå.
- [ ] **Gjør oversettelsesfeilen umulig i stedet for testet mot** *(F2, 2026-08-30)*.
      `tools/profile_stats.py::blindspots()` returnerer strengen `"Germany Red Wine (n=2)"`. Førte den
      **land og kategori strukturert**, kunne `user_fit` droppet hele `_LAND_NO_TO_EN`-tabellen, og
      oversettelsen ville vært eksakt i stedet for et oppslag — altså ville hele B4-feilklassen vært
      umulig, ikke bare dekket av tester. F2 lot den stå bevisst: strengen rendres inn i den managed
      blokka i `smaksprofil.md`, og `untappd_stats.py` speiler mønsteret. **Må tas samlet, ikke ensidig.**
- [ ] **Prosaen i `smaksprofil.md` er feilkilden tre steder** *(F2, 2026-08-30)*.
      (a) «Tyskland (Mosel, Rheingau – Riesling)» — parentesen er *bærende* (den sier hvitt), men
      parseren stripper parenteser, så regelen ble «Tyskland». Hele spesifisitetsregelen i ADR-027
      finnes på grunn av dette. **Rettes teksten til «Tysk Riesling», blir koden enklere.**
      (b) «Sør-Rhône hvit (to lave på Lirac Blanc)» — n=2 er reelt n=1 vin i to årganger.
      (c) **To seksjoner heter «Blindspots»** på samme nivå, og den kuraterte inneholder
      `### New World rødvin` der bullets er *ratinger*, ikke regler. Krevde `stop_at_subheading`;
      skjørt — en ny underseksjon med bullets lekker inn igjen.
- [ ] **`tools/eval_fit.py::_csv_row_to_wine` setter ikke `underregion`** — Vivinos `Region` (som *er*
      appellasjonen) havner i `region`. Fungerer, men tvinger nivåporten til å lese både `region` og
      `navn`. Én linje ville gjort det eksplisitt.
- [ ] **Flytt gjeld-#10-prosatesten til `tests/test_knowledge_content.py`** — den ligger i
      `test_user_fit.py` § J kun fordi F2 ikke eide den andre fila.
- [ ] **Årgangsspredning på samme vin er større enn profilen forutsetter — vurder å skrive det inn.**
      Tre uavhengige funn 2026-08-30 peker samme vei: `9111501` Vincent Girardin Terroir Noble ratet
      **4.5 (2010) og 3.8 (2023)**; Miraval Côtes de Provence **4.0 og 2.0**; Ségriés Lirac Blanc
      **3,2 og 3,0**. Samme vin, ulik årgang, opptil **2,0 poengs spenn**. Konsekvenser: (a) klokke-
      similarity kan per konstruksjon ikke forklare det (ADR-025 — klokkene er identiske); (b) «to lave
      på Lirac Blanc» i prosaen er egentlig **n=1 vin i to årganger**, ikke n=2 — flere n-tall i
      profilen kan være inflatert på samme måte; (c) en anbefaling som ignorerer årgang er svakere enn
      profilen antyder. Tell opp hvor mange «n=»-påstander som er vin-duplikater før neste revisjon.
- [ ] **Etterverifiser Bandol-innsnevringen når rosé-sveipen har landet.** Regelen er skrevet før
      sveipen (bevisst — den skal være på plass *før* kategorien femtendobles), men treffantall er
      ikke målbart på 53 juni-rader. Når rosé er ~782: mål hvor mange som flytter fra `risky` til
      blindsone, og bekreft at Bandol faktisk ekskluderes.
- [ ] **Re-mål user-fit-fordelingen mot ferdig katalog.** F2s tall er et øyeblikksbilde midt i
      sveipen (`catalog.ndjson` md5 `6f5302e8`, hvitvin 4 616 av ~9 762, rosé/musserende før sveip).
      Rødvinstallene står; hvit/musserende/rosé må måles på nytt.
- [ ] **Fase 2 av hvit/musserende/rosé** (~3–4 t, 13 625 produkter) — klarsignal gis når fiksene har landet.

## Backlog
- [ ] **B7: samme vin på flere varenummer til ulik pris — `value_score` ser det ikke.** Funnet
      2026-08-30. Grupperer man rødvin på (navn × volum): **0 grupper i gammelt snapshot, 313 i
      nytt** (792 rader, 142 med ≥10 % prisspredning). Verste: `ch. pichon longueville comtesse de
      lalande 2016`, 75 cl, **fem aktive varenumre fra 2 113 til 3 950 kr**. `compute_value_score`
      slår opp ett varenummer og sammenligner mot land-peers — den ser aldri at identisk vin ligger
      989 kr billigere under et annet varenummer i samme snapshot.
      **Riktig ramme er «manglende sjekk», ikke «bug»:** spørsmålet fantes ikke før ekspansjonen.
      **Forbehold som kan avlyse posten — les dem før du måler:** 468 av 792 rader er `Spesialutvalg`
      (Polets auksjonskanal, der separate partier til ulik pris er forventet og ikke feil); det er
      *ikke* verifisert at identisk navn + volum betyr identisk produkt (kan skjule årgang i
      navnefeltet, flasketilstand, importør — krever `details` for radene); og i hverdagssonen er
      det 2 duplikat-rader av 1 448. Brukerpåvirkning i dag er nær null — det er «noe spesielt»-sonen
      og peer-statistikken som rammes. Konfidens: middels.
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
