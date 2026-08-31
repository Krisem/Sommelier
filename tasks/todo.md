# Todo

## Aktivt — plan godkjent 2026-08-31

Sveipen 2026-08-30 er landet og committet (`7ba0f4d`…`49ce241`). Restansen etter den er sekvensert i
seks faser. Full plan med begrunnelser, tall og verifiseringssteg:
`~/.claude/plans/imperative-spinning-hare.md`.

**Utgangspunkt målt 2026-08-31:** HEAD `49ce241`, 399 tester grønne, katalog 27 402
(rødvin 13 775 · hvitvin 9 762 · musserende 3 081 · rosé 782 · brennevin 2), 1 664 details
(rødvin 1 379 · hvitvin 140 · musserende 95 · rosé 48 · brennevin 2).

**Status ved sesjonsslutt 2026-08-31, andre økt.** Fase 3, 4 og 5 (alt som ikke krever
ratinger) er ferdige og committet, **471 tester grønne**, arbeidstreet rent. Måleomgangen ligger
i [`maaling_2026-08-31.md`](maaling_2026-08-31.md), festet til revisjon og katalog-md5.
Dokumentasjonen er tatt igjen: ADR-028, ADR-029, ADR-030, amendment på ADR-017, README, roadmap
og `deep-knowledge/INDEX.md`.

### ✅ Fase 2 LANDET 2026-08-31 kl. 14:48

Aperitif-sveipen fullførte. **557 sider, 2 retries i hele kjøringen, 0 feil.**
`data/aperitif/scores.ndjson` har **15 672 rader** (5,7 MB) + `meta.json`. Siste side med poeng
var 554. Sidecachen ligger fortsatt i `~/.cache/sommelier/aperitif-pages/` (557 filer) og kan
slettes når snapshotet er pushet.

Prosessen **overlevde at sesjonen ble stengt** fordi stdout/stderr pekte på en vanlig fil, ikke en
pipe fra den døde terminalen. Hadde det vært en pipe, ville den dødd på `BrokenPipeError`.
Merk for neste gang: **at en prosess finnes i `ps` er ikke bevis for at den arbeider** — sammenlign
mtime på nyeste `side-*.html` mot klokka i samme kommando.

Whisky-seksjonen i `knowledge/whisky.md` er nå skrevet på snapshotet: 316 whiskyer har
Aperitif-poeng, 16 nordiske, 8 norske. Hovedfunnet er priset — nordisk og skotsk har **samme
medianscore (89)**, men medianprisen er 833 mot 1 201 kr.

**To fallgruver er allerede betalt for, ikke gjeninnfør dem:** sveipens egen timeout (60 s, ikke
`_http_get`s 15) og sorterings-vernet som sammenligner medianer, ikke ytterpunkter.

**Styrende prinsipp:** mål én gang. Fase 3 (kodefiksene) kommer før Fase 4 (måleomgangen), fordi
F2s tall er et øyeblikksbilde fra *midt* i sveipen.

**Underlag for Fase 5 og 6** — researchet 2026-08-31, med målinger og forbehold:
[`plan_whisky.md`](plan_whisky.md) · [`plan_objektiv_anbefaling.md`](plan_objektiv_anbefaling.md).
Begge er nå besluttet i den grad Fase 5/6 beskriver; de gjenstående åpne spørsmålene står i
Fase 6-gaten under.

---

## ⬅ VENTER PÅ KRISTOFFER

- [ ] **Rate whiskyen du har drukket.** *(sa 2026-08-31 at han gjør det samme kveld)*
      Dette er den eneste posten i hele planen som ikke kan gjøres uten deg, og den blokkerer Fase 5.
      Whisky står på **n=0** i dag; alt annet i planen er kode og måling.

      **Slik gjør du det:** bare skriv det i chat, én linje per flaske, i vilkårlig rekkefølge.
      Claude skriver radene inn i `data/whisky/ratings.csv` — du skal ikke redigere noen fil.
      Format som holder:

      > Lagavulin 16 – 4,5, røyk og tørr avslutning
      > Jameson – 2,75, kjedelig
      > Nikka From The Barrel – 4,25

      **Skalaen er 5-punkt med kvart-trinn** (1,0–5,0), samme som Vivino og Untappd — tersklene i
      `beer_fit.py` og `user_fit` er kalibrert på den, så en annen skala ødelegger sammenlignbarheten.
      **Notat er valgfritt.** Fritekst ble skrevet 4 av 211 ganger (1,9 %) på vin og øl, så
      karakteren må klare seg alene — ikke la et manglende notat stoppe deg fra å ta med en flaske.
      **Husker du ikke navnet presist, ta det du husker** — Claude slår opp varenummer, destilleri,
      juridisk kategori, ABV, alder og torv mot Polet og Aperitif.

      **Hvorfor det haster mer enn det ser ut:** en tier-modell trenger ~84 ratinger (SD 0,61 mot en
      tier-stige som spenner 0,65 poeng). 10–20 flasker i kveld er ikke nok til en modell, men det er
      mer enn hele byggeplanen leverer på et år uten deg — og det avgjør om Fase 5 skal bygge
      anbefalinger eller bare lesestoff.

- [ ] **Vin og øl: er det noe uratet?** Ikke etterspurt, bare flagget. Vin går via en Vivino-sync
      (`docs/vivino_refresh.md`), ikke chat — si ifra om du har ratet noe i appen siden 30. august, da
      kjører jeg synken. Ølkanalen er død (siste Untappd-check-in 2026-01-16), så har du drukket øl
      verdt å registrere, må vi finne en annen vei inn enn Untappd.

- [x] **To designspørsmål før Fase 6 kan starte** — BESVART 2026-08-31: **ja til begge.**
      Den objektive delen får overprøve rammen i spørsmålet, og prediksjonsdelen får være taus
      mesteparten av tiden. Fase 6 er dermed ulåst (~8–11 t, ikke påbegynt). (fra
      [`plan_objektiv_anbefaling.md`](plan_objektiv_anbefaling.md)). Målingene fra Fase 4 er nå
      klare, så de kan legges fram: skal den objektive delen kunne overprøve *rammen* i spørsmålet
      ditt, og aksepterer du at prediksjonsdelen er taus mesteparten av tiden?

- [x] **Fire funn fra måleomgangen — ALLE AVGJORT 2026-08-31.** Se «Avgjort» under.
      Opprinnelig formulering: Ingen av dem er handlet på — se
      [`maaling_2026-08-31.md`](maaling_2026-08-31.md) for tallene.

      1. **«Jura (Chardonnay)» står som region du dras mot på grunnlag av én vin i to årganger**
         (Rolet, 4,4 og 4,1). Skal den stå, nedgraderes til blindsone, eller merkes n=1?
      2. **Alle 218 `very_fit` i musserende er engelsk musserende** — hver eneste Polet fører —
         på grunnlag av tre ratinger. Skal terskelen for `bekreftet_snitt` heves over n=3?
      3. **Hvitvin og rosé kan aldri nå `very_fit`**, fordi ingen av profilens fire bekreftede
         stiler er hvit eller rosé. Er det riktig, eller skal toppkarakteren kunne nås per
         kategori?
      5. **NYTT, funnet 2026-08-31 tredje økt: «Jura» treffer «Jurançon».** Regelen løfter 202
         kjøpbare varer fra `neutral` til `fit`. **196 er ekte Jura; 6 er det ikke** — fem
         Jurançon (en sørvest-appellasjon uten slektskap til Jura) og én «Jurassique».
         Målt gjennom `classify()` selv, ikke en gjenimplementering.
         **Dette er samme feilklasse som «Redoma»→«Red», som Fase 3 mente den hadde gjort
         umulig** — den overlever på `regioner_pluss`-stien fordi `_ci_substring_match` er en
         naken substring uten ordgrense, og navnefeltet er en av haystackene. Fiksen er ikke
         gratis: `_ci_substring_match` brukes av alle needle-typene, så en ordgrense der må
         måles mot hele katalogen før den lander. **Avventer spørsmål 1** — ryker «Jura», ryker
         fem av de seks av seg selv.

      4. **B7: 24 viner der samme vin og årgang ligger på flere varenumre til ulik pris.**
         Beychevelle 2019 koster 1 199,90 og 2 188,90 samtidig, og `value_score` sier ingenting.
         Fiksen er en oppslagssjekk, ikke en modell — skal jeg bygge den?

---

### Fase 1 — nullkost-fikser (~1,5 t)

- [x] **1.2 `aperitif.py` varenummer-regex** `\d{7,8}` → `\d{5,8}` + `(?!\d)` i begge mønstrene.
      Rammet 587 av 27 402 varenumre (44 med 5 siffer, 543 med 6). **Feilen var verre enn «score
      mangler»:** uten `polet_id` feiler både årgangs-verifiseringen i pass 1 og stale-sjekken på
      mapping-treffet i `get_aperitif_score`, så de vinene fikk `vintage_mismatch=True` selv når
      siden gjaldt akkurat den vinen — altså en usann påstand videre til brukeren via CLAUDE.md
      steg 6. Ny `tests/test_aperitif.py`, 12 tester, muteringssjekket (gammel regex → 6 feil).
- [x] **1.3 `eval_fit._csv_row_to_wine` setter `underregion`.** Vivino har ett regionfelt med
      varierende granularitet (appellasjon «Côtes du Jura» *eller* distrikt «Rheingau»), så det
      mates inn på begge akser framfor å gjette. **Verifisert null atferdsendring:** eval-harnessen
      gir identiske tall, og 0 av 122 viner skifter tier eller regel.
- [x] **1.4 Flyttet gjeld-#10-prosatesten** fra `test_user_fit.py` § J til
      `test_knowledge_content.py`. Tre tester, ingen endring i innhold.
- [x] **1.5 Slettet backup-filene** og utvidet `.gitignore` med `*.pre-sync-*`.
      **Todo-posten var feil på ett punkt:** `full_wine_list.csv.bak` var *ikke* tracket — `*.bak`
      har ligget i `.gitignore` hele tiden, så konvensjonen var allerede klar. Begge slettet etter
      verifisering: `.pre-sync-2026-08-30` er bit-identisk med `df85d42^`, og `.bak` er en streng
      delmengde av dagens fil (0 rader og 0 ratinger unike for den).
- [x] **1.6 `CLAUDE.md`, tre avvik rettet** (godkjent av Kristoffer 2026-08-31).
      (a) steg 6b peker nå på `python3 -m tools.user_fit <varenr>` / `classify_code`, med eksplisitt
      «ikke slå opp `v0.json`». **NB: dekningstallet i den gamle todo-posten var feil** — v0.json har
      409 varenumre, altså 1,5 % av 27 402, ikke 0,59 %.
      (b) `find_similar_by_clocks` bærer nå ADR-025-forbeholdet.
      (c) «Ingen build/lint/test-suite» erstattet med `python3 -m pytest -q` + muteringskravet.
- [x] **1.7 Ryddet denne fila.** Sveip-tabellen flyttet til `## Ferdig`.
- [ ] **1.1 Whisky steg 0: hva har Kristoffer allerede smakt?** Spurt 2026-08-31, han rater samme
      kveld. Detaljer og format: se **⬅ VENTER PÅ KRISTOFFER** øverst.

### Fase 2 — Aperitif-snapshot ⏳ KODET OG TESTET, SVEIP UNDERVEIS (`4e2caae`, `5a7f13f`, `220cda5`, `3982f2d`)

Verktøyet (`tools/refresh_aperitif.py`, 29 tester) og snapshot-lesingen i `aperitif.py` er
ferdige og committet. Det som gjenstår er å la sveipen fullføre — se advarselen øverst i fila.
Dokumentert i [ADR-030](../docs/ARCHITECTURE.md#adr-030-aperitif-snapshot-som-fallback-og-bulk-kilde--ikke-som-lag-foran-nettverket).

- [x] Sveip vin **og** whisky i én kjøring. `robots.txt` verifisert 2026-08-31: `/pollisten`-stiene
      er tillatt, `?query=` / `/api/*` / `/ajax/*` / `/load` er blokkert (vi bruker ingen av dem).

  **Sondert live 2026-08-31 — fire rettelser til planfilenes tall:**
  - **Pagineringen er `?side=N` — men den virker ikke.** `/pollisten?side=2` returnerer samme 30
    produkter som side 1. Den fungerende formen er stibasert: `/pollisten/pollisten,7,<side>`
    (side 1 = `/pollisten`). Verifisert disjunkte produkter på side 1, 2, 100, 400, 475, 476, 500,
    520, 540, 600, 856, 1000.
  - **Listeraden har alt vi trenger — ingen produktsider nødvendig.** Per
    `<li class="product-list-element">`: `data-product-id`, navn + årgang, `country-area`
    (appellasjon), `class` (Rødvin/Hvitvin/…), `country-name`, `price`, `volume`, `assortment`,
    **`<span class="index">(18971701)</span>` = Polet-varenummer**, og poeng i **samme markup som
    `_parse_product_page` alt matcher** (`<span class="number">99</span><span class="label">POENG`).
  - **Default-sortering er `points_desc`.** Poengene faller monotont: side 1 = 97–99, side 100 = 91,
    side 400 = 86, side 475 = 83, side 500 = 82, side 520 = 80, side 540 = 76–77, side 600 = **ingen
    poeng**. Sveip til poengene tar slutt (et sted mellom 540 og 600) pluss margin — ~560 kall, ikke
    480. Lista fortsetter forbi side 1 000 uten poeng; de sidene er verdiløse for dette.
  - **Ikke alle scorede rader har varenummer.** Side 520 hadde 30 rader med poeng men bare **18**
    med `index`-span; side 540 hadde 25. Anslaget «~14 300 scorede varenumre» er derfor et tak —
    tell faktisk treff under sveipen framfor å regne 30 × sider.
- [x] **Output til `data/aperitif/scores.ndjson`, IKKE `knowledge/scores/`.** Begge planfilene sa
      `knowledge/scores/`; det ville brutt ADR-003, fordi `value_score._combine_quality`
      (`tools/value_score.py:152-158`) rangerer den mappen *over* Aperitif — 14 300 skrapede scorer
      der ville stille overkjørt de 384 kuraterte DN-scorene. Snapshot-mønsteret fra `data/polet/`
      (ADR-020) i stedet; leses av `get_aperitif_score` før nettverk, som også gjør Aperitif-score
      tilgjengelig offline.
- [x] Drift-vern: positiv validering per rad, assert på rader/side, avbryt framfor å skrive halvt.
      **To justeringer måtte til i praksis:** timeouten var kortere enn sidene (drepte sveipen på
      side 222 av 560), og sorterings-vernet sammenlignet ytterpunkter i stedet for medianer
      (drepte den på side 133 fordi side 132 hadde én 89 blant tretti 90-ere). Begge meldte feil
      årsak — de pekte på nettstedet da feilen lå i min egen terskel.
- [x] Skriv prisbias-forbeholdet inn i snapshotet: Spearman(poeng, pris) = +0,65 (whisky) / +0,80
      (DN-vin). «Høyest score» ≈ «dyrest», så prissone-lås er en forutsetning, ikke pynt.

### Fase 3 — rotårsaksklyngen: gjør feilklassen umulig ✅ FERDIG (`24685f0`, `b8490bb`)

Tatt samlet, i rekkefølgen prosa → struktur → forenkling. Round-trip-vernet kom først
(`483c6ab`). **126 av 27 402 varer skifter dom** — se måledokumentet § 5.

To feil funnet i mitt eget arbeid underveis, begge rettet og testdekket: (1) «er dette en
`<Land> <Kategori>`-blindsone?» ble avgjort på needelens FORM, og «Aromatisk hvitvin»
ble lest som land «Aromatisk» — sju italienske musserende mistet region-treffet sitt;
(2) vokabular-byttet alene ville innført en ny feil, fordi «USA» finnes inni «Usatges»,
«Sausal», «Sousa» og «Susana» — 15 hvitviner fra seks andre land ville blitt stemplet
«USA Hvitvin». Derfor er eksakt matching forutsetningen for 3.3, ikke pynt på den.

- [x] **3.1 Prosaen i `knowledge/smaksprofil.md`.** «Tyskland (Mosel, Rheingau – Riesling)» →
      «Tysk Riesling» (parentesen er bærende, men parseren stripper den — derfor finnes hele
      spesifisitetsregelen i ADR-027). «to lave på Lirac Blanc» er n=1 vin i to årganger, ikke n=2.
      Gi de to «Blindspots»-seksjonene distinkte navn.
      **Round-trip-test FØRST** (lesson 2026-08-30 om maler som sletter alt utenfor seg).
- [x] **3.2 Strukturér blindsonene.** `tools/profile_stats.py:87-99` returnerer
      `"Germany Red Wine (n=2)"` → `{"land", "kategori", "n"}`, med rendringen i render-laget.
      `tools/untappd_stats.py` speiler mønsteret og endres i samme commit.
- [x] **3.3 Fjern `_LAND_NO_TO_EN`** (`tools/user_fit.py:368+`) og `_KATEGORI_NO_TO_EN`-bruken i
      `_blindspot_hit` (linje 978-990). Da kan `stop_at_subheading` (linje 119-132, 299) også
      forsvinne. Sluttilstand: `grep -rn "_LAND_NO_TO_EN\|stop_at_subheading" tools/` → 0 treff.
- [x] **3.4 `active_only=True` som default + `lanseres` → `kommer_snart`** (godkjent 2026-08-31).
      2 196 av 13 775 rødviner er ikke kjøpbare, **1 264 av dem med `buyable: true`**. Koster 13 feil
      + 5 errors i `test_vinmonopolet.py` og `test_value_score.py` — **hver test leses og oppdateres
      enkeltvis med en begrunnelse**, ingen masseoppdatering. De 376 kommende lanseringene vises med
      flagg, ikke skjules (samme prinsipp som tier, ADR-016).

### Fase 4 — én måleomgang på ferdig kode ✅ FERDIG

Alt ligger i **[`maaling_2026-08-31.md`](maaling_2026-08-31.md)**, festet til revisjon
`b8490bb` + katalog-md5 `429cce5f9fd73450d7817284f8c65377`.

- [x] User-fit-fordelingen over hele katalogen, både full katalog og kun kjøpbare.
      **Rødvin 413 / 2 923 / 10 031 / 408** — merk at ADR-027s 498 og 2 839 er utdaterte,
      og at avviket stammer fra sveipen 2026-08-30, ikke fra Fase 3.
- [x] Bandol: **9 rader**, alle Bandol (ingen Palette/Bellet i katalogen), alle flytter
      `risky` → blindsone. `risky` 162 → 153. **Bandol ekskluderes faktisk** — svaret er ja.
- [x] Årgangsspredningen: 122 rader = **115 distinkte viner**, sju gjentak. Bare Miraval har
      et stort spenn (2,0). **Planens Girardin-eksempel var feil** — det er to ulike cuvéer
      fra samme produsent, ikke samme vin i to årganger. To påstander faller til n=1:
      «Southern Rhône White» (rettet i 3.1) og **«Jura White» (ikke rettet)**.
- [x] `eval_fit` rekjørt: **`v0_tier` +0,33 → +0,20**, forårsaket av inngangs-oversettelsen.
      Ordningen over alle 122 er fortsatt monoton (4,09 · 3,95 · 3,88 · 3,00 · 2,00).

**Til deg, to funn som ikke er handlinger ennå:**
- «Jura (Chardonnay)» står som region du dras mot på grunnlag av **én vin i to årganger**.
- Alle 218 `very_fit` i musserende er engelsk musserende — hver eneste Polet fører — på
  grunnlag av **tre ratinger**. Hvitvin og rosé kan på sin side aldri nå `very_fit`, fordi
  ingen av profilens fire bekreftede stiler er hvit eller rosé.

### Fase 5 — whisky, kritisk sti ⏳ ALT UNNTATT RATINGENE ER FERDIG (`44787f3`)

- [x] `knowledge/whisky.md` — **139 linjer**, litt under målet fordi seksjonen om norsk/nordisk
      sortiment venter på Aperitif-snapshotet. Tre påstander er testdekket: n=0, ADR-025-forbeholdet
      på klokkene, og at det uverifiserte (WSETs SAT, irsk pot still, klyngeantallet) ikke står
      der som fakta. Opprinnelig formulering: Juridisk kategori som anker (Scotch Whisky
      Regulations 2009, 27 CFR § 5.143 inkl. American Single Malt fra 19.01.2025, EU 2019/787, irsk
      Technical File, JSLMA), Polets Fylde/Fat/Røyk + varetype, Brooms flavour camps som *språk*,
      servering, norsk/nordisk sortiment, workflow.
      **Ikke** WSETs SAT for Spirits fra hukommelsen (403 på begge PDF-URL-ene — presedensen er den
      hallusinerte `bjcp_2021.pdf`-referansen), **ikke** irsk pot still-endringen, **ikke**
      klyngeantallet fra whiskyanalysis.com (selvmotsigende kilde).
- [x] `data/whisky/ratings.csv` opprettet med header + README. **Venter på at du dikterer.**
      Opprinnelig formulering: **Kristoffer dikterer i chat, Claude
      skriver raden** — ølkanalen døde fordi innføring var manuelt filarbeid (siste check-in
      2026-01-16; 2025: 29 → 2026: 1). Notat valgfritt: fritekst ble skrevet 4 av 211 ganger (1,9 %).
- [x] `CLAUDE.md`-routing lagt inn, betinget. `deep-knowledge/INDEX.md` sier eksplisitt at whisky
      IKKE får en deep-knowledge-fil, og hvorfor. Opprinnelig formulering:
- [x] ~~`CLAUDE.md`-routing (trepart, men **betinget** — whisky kun når nevnt, eller ved
      dessert/ost/digestif/kveldsdram) + `deep-knowledge/INDEX.md` + tester.~~
- [ ] **Utsatt, eksplisitt:** fit-modell og tier-stige til n ≈ 84 (SD 0,61 mot tier-stige 0,65 poeng
      — ved n=3 per bøtte er 95 % KI ±0,69, bredere enn hele stigen); ADR-025-målingen på
      Fylde/Fat/Røyk til n ≥ 15–20; katalogsveip av brennevin og fasettprobing kanskje for alltid.

### Fase 6 — objektiv anbefaling (~8–11 t)

**Gate:** to åpne spørsmål i [`plan_objektiv_anbefaling.md`](plan_objektiv_anbefaling.md) må
besvares først — skal den objektive delen kunne overprøve *rammen*, og aksepterer du at
prediksjonsdelen er taus mesteparten av tiden? Legges fram med målingene fra Fase 4.

- [ ] Eksponer `blindspot` som eget signal i output (~1 t). 6 654 varer er klassifisert, snitt
      **4,15** — over `bekreftet_snitt` 4,10 og `bekreftet_drue` 4,00. Ingen ny modell.
- [ ] Mekanisme-sjekk før anbefalingen (~2–3 t). **3–4 reelle utløsere, ikke 13.** Asymmetrien er
      poenget: rødvin til torsk bryter en mekanisme (jod × tannin) og lisensierer overprøving;
      hvitvin til biff bryter ingen, den underleverer bare.
- [ ] `sub_district_in` i `polet_store.query` + prissone-lås som test (~2–3 t). `sub_District`
      dekker 72,5 %, 1 212 unike, η² 0,473 mot null-median ~0,17. **Mål på rødvin først** — de 137
      vinene i testen er 51 hvit / 48 musserende / 32 rosé / 6 rød.
- [ ] Prediksjonslag med effektkrav ≥ 2,5 SE fra 3,82 (~2 t). Historikk, ikke spådom. Sies ved
      kjøpsbeslutningen, ikke når flaska åpnes. Taus når den ikke slår ut.
- [ ] ADR-arbeid: ADR-016 fra filtrering til retrieval, ADR-017 amenderes med `v0_tier`
      +0,588 → +0,332, ny ADR for mekanisme-overprøving.
- [ ] **Ikke bygg:** nivåmarkører som objektivt signal (+2,5 / +1,1 / **−0,8** innenfor prissone —
      en prismarkør, ikke en kvalitetsmarkør); «vis uenigheten mellom kilder» (snittavvik 1,2 poeng
      på de fem vinene med både DN og Aperitif — de er ikke uavhengige meninger).

## Avgjort 2026-08-31, tredje økt — de fire funnene + designporten

Alle besluttet av Kristoffer, implementert og målt. Dokumentert i
[ADR-031](../docs/ARCHITECTURE.md) og [ADR-032](../docs/ARCHITECTURE.md).

1. **Jura n=1 → «merk alltid n=x ved få reviews».** Generalisert, ikke punktfikset:
   `profile_stats.region_evidence` teller ratede viner per regionnedle gjennom den EKTE
   matcheren (`user_fit._needle_hits`), ikke en gjenimplementering. Målt: Champagne n=11
   (10 viner), Tysk Riesling n=6, Nord-Italia n=5 (4 viner), **Jura n=2 (1 vin)**.
   Begrunnelsen sier nå «Foretrukket region «Jura» (n=2, snitt 4.25)».
2. **+ 3. Toppkarakter per kategori, kategori-relativ terskel.** `CONFIRM_MIN_SE` = 1,0 SE over
   eget kategorisnitt, gulv på totalsnittet. **very_fit 575 → 392; rosé 0 → 3.** Southern Italy
   Red falt ut (+0,91 SE) og ble fanget av det nye `positive_styles`-nivået → `fit`, ikke stillhet.
   Kristoffer valgte 1,0 framfor 0,9 selv om 1,0 koster 262 varer mot 3 — 0,9 var kurvetilpasning.
4. **B7 bygget.** `value_score.billigere_duplikat`. Beychevelle 2019: 2 188,90 → finner
   1 199,90 på annet varenummer, sparer 989 kr. Tre porter (volum, Spesialutvalget, aktive),
   alle muteringssjekket.
5. **Fase 6-porten: ja til begge.** Overprøving av rammen tillatt; taus prediksjonsdel akseptert.

**Ett nytt funn, ikke handlet på:** «Jura» treffer «Jurançon» — 6 av 202 varer er falske treff
(fem Jurançon, én «Jurassique»). Samme feilklasse som «Redoma»→«Red» som Fase 3 mente den hadde
gjort umulig; den overlever fordi `_ci_substring_match` mangler ordgrense og vinnavnet er en
haystack. **Ikke fikset:** endringen treffer alle needle-typer og må måles mot hele katalogen først.

**Ikke bygget, med vilje:** memoisering av `polet_store.read_catalog`. `billigere_duplikat` koster
0,19 s per oppslag, samme størrelsesorden som `_peer_percentile` allerede bruker.

## Avklart 2026-08-31 — var åpne beslutninger

- **`CLAUDE.md`-avvikene:** ja til alle tre. Utført i 1.6.
- **Backup-fila:** slettet, sammen med `.bak`. Utført i 1.5.
- **`active_only=True` som default:** ja, med `lanseres` som tredje tilstand. Planlagt i 3.4.
- **`lanseres` (376 varer):** vises med `kommer_snart`-flagg, telles ikke som kjøpbare.
- **Strukturerte blindsoner + prosafiksen:** ja, tas samlet. Planlagt i 3.1–3.3.
- **`eval_fit` `underregion`:** utført i 1.3, verifisert null atferdsendring.
- **Prosatesten:** flyttet i 1.4.
- **Whisky:** hele kritiske stien (steg 0→3). Fase 5.
- **Rekkefølge:** delt slice — fiks + sveip først, så måling.

## Backlog
- [ ] **B7: samme vin på flere varenummer til ulik pris — `value_score` ser det ikke.**
      **Målt 2026-08-31 mot revisjon `44787f3`, katalog-md5 `429cce5f`. Posten er reell, men
      mye smalere enn den så ut — og ett av de tre forbeholdene er avkreftet.**

      Rødvin gruppert på (navn × volum): **313 grupper, 792 rader**, hvorav 142 med ≥10 %
      prisspredning. Så snevrer forbeholdene den inn:

      - **Spesialutvalg-forbeholdet holder:** 468 av de 792 radene er Spesialutvalg, altså
        Polets auksjonskanal, der separate partier til ulik pris er forventet.
      - **Årgangs-forbeholdet er AVKREFTET:** 293 av 313 grupper har årstallet i selve navnet
        («Ch. Beychevelle 2019»), så identisk navn + volum er i praksis identisk vin OG årgang.
        Det styrker posten i stedet for å svekke den.
      - **Hverdagssonen er praktisk talt uberørt:** 3 duplikatgrupper av 1 785 under 250 kr.

      **Kjernen: 24 grupper** — aktive, utenfor Spesialutvalg, ≥10 % spredning. Alle ligger i
      «noe spesielt»-sonen, og de er ekte:

      | Spredning | Vin | Priser |
      |---:|---|---|
      | 82 % | Ch. Beychevelle 2019 | 1 199,90 og 2 188,90 |
      | 55 % | Ch. Bellefont-Belcier 2021 | 489,90 og 760,50 |
      | 39 % | Ch. Grand-Puy-Lacoste 2021 | 799,90 · 999,90 · 1 012,90 · 1 110 (fire i Bestillingsutvalget alene) |

      **Mekanismen er verifisert, ikke antatt.** `compute_value_score("14837601")` — Beychevelle
      til 2 188,90 — svarer «Usikkert, for lite data. Pris i 86. percentil av 4 939 peers
      (median 704,90 kr)». Den sammenligner altså mot alle franske rødviner, og nevner ikke med
      ett ord at **nøyaktig samme vin og årgang ligger 989 kr billigere** på et annet varenummer
      i samme snapshot. Grand-Puy-Lacoste viser at Spesialutvalg-forklaringen ikke dekker det:
      310 kroners spredning innenfor Bestillingsutvalget alene.

      **Anbefaling (ikke bygget — dette er beslutningsgrunnlaget):** ikke en modell, bare en
      oppslagssjekk i `compute_value_score` — finnes samme navn + volum på et annet aktivt
      varenummer til lavere pris, si det. ~24 viner berøres i dag, alle i den sonen der en
      feil koster mest i kroner. Konfidens: høy på mekanismen, lav på at det haster.

- [ ] **Details for hvit/musserende/rosé i det prioriterte utsnittet — 942 rader, ~2 t veggtid.**
      Enumereringen og klokke-sveipen er ferdig (`7ba0f4d`); det som mangler er dybden. Målt
      2026-08-31: hvitvin Basis 338 + Tillegg 299, musserende Basis 145 + Tillegg 83, rosé Basis 61 +
      Tillegg 13, pluss 3 i Spesial/Test. Ved kjent kvote (~65–85 sider/syklus, 7,5 min pause) er det
      ~12–15 sykluser. **Merk:** todo-posten sa tidligere «~3–4 t, 13 625 produkter» — det tallet var
      enumereringen, som er levert. Ingenting i fasene over blokkeres av denne.
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

- [x] **2026-08-30: Sveip med ni agenter, disjunkt fileierskap.** Utgangspunkt 291 tester,
  commit `b162d3e`; resultat 397 grønne, committet i `4a7eead`…`1c43728`.

  | Agent | Oppdrag | Resultat |
  |---|---|---|
  | A | Klokke-tabell | 6 → 25 rader. **Klokkene diskriminerer ikke** (korr. +0,16/+0,09/−0,10; alle 6 grupper med identiske klokker spenner ratingskalaen) → ADR-025 |
  | B | 3 scenarier | Fant **8 bugs**. Osso buco klart bedre; B1 firedoblet av ekspansjonen |
  | C | `data/reference/` | **Ikke slettet** — var uattribuert kilde til `sommelier.md` §4 og `norsk-marked.md` §10. Gjeld #7 omskrevet, attribusjoner lagt inn, `bjcp_2021.pdf`-referansen var hallusinert |
  | D | Vivino-sync | 5 nye ratinger (117 → 122). Runbook rettet: DOM-en har eksakte UTC-tidsstempler, metadata må brace-matches |
  | E | Hvit/musserende/rosé | Komplett enumerert: 304 → **13 625** produkter (hvitvin 9 762, musserende 3 081, rosé 782) |
  | F0 | B6 statusfilter | `active_only` opt-in. Muteringstest beviste at default måtte stå (13 feil + 5 errors hvis snudd) |
  | F1 | B2 + B3 | Barbera 3 → 95, Etna 36 → 74, similarity 13 → **718 av 771**. Toleranse-funn: ADR-024 var «påkoblet i navnet, ikke i rangeringen» |
  | F2 | B4 + B5 | `risky` **0 → 408**, blindsoner 3 → 25 land. Fire nivå-innsnevringer. To-inngang-feil funnet via uendret sanity-sjekk |
  | F3 | B1 peer-percentil | Pichon Baron 0,72 → **0,50** percentil, 50 → 4 938 peers. **28,2 %** av 400 viner får korrigert verdict → ADR-026 |

  **Levert dokumentasjon:** ADR-025, ADR-026, ADR-027 (+ amendments), gjeld #7 omskrevet,
  #9/#10/#11 nye, `lessons.md` +3 poster, runbook-rettelser i `polet_refresh.md` og
  `vivino_refresh.md`. **Ikke fikset, bevisst:** B7 — se Backlog.
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
