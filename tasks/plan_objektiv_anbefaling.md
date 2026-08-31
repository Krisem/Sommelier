# Plan — objektiv anbefaling + prediksjon

> **Status:** forslag, ikke besluttet. Skrevet 2026-08-31 etter research av fire agenter,
> to devil's advocate-agenter og én QA-agent (17 tall etterprøvd: 14 bekreftet, 2 avvik, 1 delvis).
> **Målt mot:** HEAD `c901b8b`, `catalog.ndjson` `count` 27 402, `generated_at` 2026-08-30T20:05:22Z,
> `full_wine_list.csv` 122 ratede viner.
> Alle tall under er målt i repoet, ikke anslått. Underlagsrapportene lå i en scratchpad som ikke
> overlever sesjonen — det som betyr noe er gjengitt her.

## Brukerens ønske

> «Jeg er bekymret for at vi havner i en boble styrt av smakspreferansene mine, og går glipp av mye
> god og spennende vin (og potensielle nye favoritter). Jeg vil derfor at vin-anbefalinger, både fra
> vinlister og på spørsmål om spesifikke flasker til forskjellige anledninger kommer med
> anbefalinger - og så avslutter med objektive anbefalinger. Hva går for å være det beste til det jeg
> ber om? Og hva kommer jeg til å synes om det.»

Presiserende eksempel:

> «Jeg ber om rødvin til torsk, og du kommer tilbake med "dette er den som matcher din profil best,
> men objektivt sett ville hvitvin Y vært det beste valget. du pleier derimot å gi denne typen
> hvitvin dårlig score."»

Eksemplet er tredelt, ikke todelt: (1) beste svar **innenfor** rammen, (2) beste svar **uten**
rammen — altså at premisset i spørsmålet selv kan overprøves, (3) ærlig prediksjon på (2).

---

## Anbefaling i én setning

**Bygg del 1 og 2. Bygg del 3 med et effektkrav som gjør den taus mesteparten av tiden, og la den
være taus framfor å si «uavklart».**

---

## Det som ble målt, og som styrer planen

| # | Funn | Tall | Konsekvens |
|---|---|---|---|
| 1 | Kandidat-genereringen er italiensk | Søk avledet av profilen når ~22 % av rødvin ≤ 500 kr; ~86–99 % av treffene er italienske avhengig av strengvalg | Bobla sitter i **retrieval**, ikke i rangeringen. ADR-016 opererer på det som allerede overlevde |
| 2 | Kritiker-dekning er for tynn til å rangere på | **384 av 27 402 = 1,4 %**, alt fra DN. 5 av 1 448 rødviner ≤ 250 kr | ADR-016s `sorted(-critic_score)` er ikke kjørbar i praksis |
| 3 | «Objektivt best» ≈ «dyrest» | Spearman(DN-score, pris) **+0,801** samlet; holder innen kategori: musserende +0,86, rød +0,69, hvit +0,58, rosé +0,45 | Objektiv rangering **må** skje innenfor prissone |
| 4 | Appellasjon er det eneste objektive signalet med skala | `sub_District` dekker **72,5 %** av katalogen, 1 212 unike. Permutasjonstest (400 stokkinger, 137 viner / 25 appellasjoner): η² **0,473** mot null-median ~0,17 | Appellasjons-retrieval er hovedfiksen. **Forbehold:** de 137 er 51 hvit / 48 musserende / 32 rosé / **6 rød** |
| 5 | Nivåmarkører er en prismarkør, ikke en kvalitetsmarkør | Riserva/Cru/Superiore: +5,0 DN-poeng rått, men **+2,5 / +1,1 / −0,8 innenfor prissone**. Medianpris 680 mot 300 kr | Ikke bruk som objektivt signal |
| 6 | Blindsonene er de han har likt best | `rule_fired == blindspot` snitt **4,15**, over `bekreftet_snitt` 4,10 og `bekreftet_drue` 4,00. **6 654 varer** allerede klassifisert | Utforskningsverdien er 80 % bygget og usynlig i output |
| 7 | Prediksjonsevnen sitter i bunnen av skalaen | R² **0,364** totalt, men **0,059** innenfor `very_fit`/`fit`/`neutral` (109 av 122 viner). 66 % av ratingene er ≥ 4,0 | Kan advare, kan ikke love. Delvis **rangebegrensning** — en egenskap ved dataene, ikke en defekt |
| 8 | ADR-017 er delvis utdatert | Like-for-like på harnessens egen metrikk: `v0_tier` +0,588 → **+0,332** (halvert). `vivino_avg` +0,632 → **+0,607** (uendret) | ADR-017 må amenderes for `v0_tier`. `vivino_avg` er fortsatt lista å slå |
| 9 | Aperitif kan 37-doble den faglige dekningen | Polliste: 856 sider × **30 rader** = 25 670 viner, poeng t.o.m. ~side 475 → ≈ **14 300 scorede varenumre** (~52 % av katalogen). ~480 kall, ~2 min | Dette er enableren for hele featuren |
| 10 | `tools/aperitif.py:200` har en stille bug | Regex `\d{7,8}` bommer på **587 av 27 402** varenumre (2,1 %) som er 5–6 siffer | Aperitif-score har manglet for de vinene hele tiden |

---

## Devil's advocate — de tre innvendingene, og hva jeg gjør med dem

### I1. Bobla er ikke synlig i atferden

| Periode | n | Italia | Land | Unike stiler | HHI (land) | Snitt |
|---|---:|---:|---:|---:|---:|---:|
| 2014–2018 | 67 | 37 % | 13 | 39 | 0,234 | 3,70 |
| 2019–2025 | 34 | 35 % | 8 | 21 | 0,270 | 3,92 |
| **2026** | **21** | **19 %** | **8** | **17** (10 aldri sett før) | **0,156** | **4,05** |

2026 er det bredeste og best likte året i datasettet. Bredden kan være *effekten* av at systemet ble
bygget — men da er beviskravet for enda et lag høyere, ikke lavere.

**Hva jeg gjør:** planen begrunnes ikke i boble-premisset. Den begrunnes i brukerens eget eksempel —
at *rammen* han spør innenfor noen ganger er faglig gal. Det er en mindre og mer etterprøvbar
påstand.

### I2. Prediksjonsregelen ville sagt noe usant

R1 foreslo `n ≥ 3 fra ≥ 2 produsenter`. Kjørt på alle 122 ratinger passerer 14 av 59 stilgrupper —
men bare **3 skiller seg fra snittet (3,82) med |t| ≥ 2,5, og 2 av de 3 er positive og på hjemmebane**
(Southern Italy Red 4,05, Amarone 4,13). Provence Rosé passerer regelen (n=4, 3 produsenter,
snitt 2,38) med spenn **1,0–4,0** — featuren ville sagt «du pleier å gi denne dårlig score» der én av
fire er en firer. Samme feilklasse som klokkene i ADR-025.

**Hva jeg gjør:** bytt tellekrav mot **effektkrav** — gruppepåstand kun når snittet ligger ≥ 2,5
standardfeil fra 3,82. Den blir taus mesteparten av tiden. Det er det ærlige utfallet.

### I3. Kuraterte forslag blir ikke til kjøp

`tasks/exploration/newworld.md` (2026-07-02) har 19 flasker med varenummer og verifisert lager.
**Null er kjøpt.** Fem av seks frontiers står fortsatt `planlagt`. `smaksprofil.md` «Regioner verdt å
utforske»: 1 av 4 fulgt opp — og tre av de fire er formulert som «du ga 4.1 til X, mer i denne
stilen?», altså avledet av det han allerede likte. Han utforsker likevel (to Rioja + spansk hvit i
juli/august), bare ikke langs de kuraterte aksene.

**Hva jeg gjør:** ingen ny kanal for mer råd. Den objektive delen legges *inn i* svaret han allerede
leser, ikke i et nytt dokument.

---

## Design

### Output-kontrakt

Én liste med to lag per vin — ikke to lister. Belegg: Adomavicius et al. (TOIS 2021) fant at når
personalisert og aggregert vises sammen, dominerer det personaliserte; Loepp (2023) og Starke et al.
(2023) fant ingen gevinst ved fler-liste-oppsett, sistnevnte lavere tilfredshet.

**Del 1 — innenfor rammen.** Som i dag.

**Del 2 — objektiv, betinget.** Utløses av **mekanisme-brudd**, ikke av avstand. Rødvin til torsk
bryter en mekanisme (jod × tannin). Hvitvin til biff bryter ingen — den underleverer bare. Bare det
første utløser overprøving. **Asymmetrien er hele poenget**, og den holder friksjonen nede.

**Del 3 — prediksjon, sjelden.** Formuleres som **historikk, ikke spådom**: «du har ratet fire i
denne stilen mellom 3,4 og 3,7», ikke «du vil ikke like den». Belegg: Fitzsimons & Lehmann
(*Marketing Science* 2004) — råd som motsier brukerens egen uttalte vurdering utløser reaktans og
aktiv motstand. Adomavicius et al. (ISR 2013) — vist prediksjon ankrer faktisk vurdering, og med 122
ratinger forurenser det datasettet som produserte prediksjonen.

**Regel som går lenger enn kildene:** si det ved **kjøpsbeslutningen**, ikke når flaska åpnes. Ankeret
er et konsumtidsproblem; informasjonsverdien ligger ved kjøpet. De to øyeblikkene er allerede
separate samtaler.

**Formuleringsregler:** lever del 1 i sin helhet først. Navngi **én** løsnet betingelse (minimal
relaxation, fra constraint-based recommenders). Gjør det billig å overse. **Unngå «du burde egentlig
…»** — det er korreks på premisset og nøyaktig formen som utløser motstand.

### Det objektive grunnlaget, i prioritert rekkefølge

1. **Mekanisme** — tannin-protein-binding, jod-reaksjon, syre mot fett. Etterprøvbart og
   motsigelig. Kustos et al. (*Food Research International* 136:109463) sier rett ut at etablerte
   parringsmodeller «are generally not good predictors of good or bad pairings» — det som *er* målt
   er mekanismen, ikke kanon. Begge kunnskapsfilene åpner allerede med «Glem regelen 'hvit til fisk,
   rød til kjøtt'».
2. **Appellasjon** innenfor prissone (funn 4).
3. **Kritiker-score der den finnes**, innenfor prissone (funn 3).

**Ikke** nivåmarkører (funn 5). **Ikke** «vis uenigheten mellom kilder»: på de fem vinene repoet har
både DN og Aperitif for, er gjennomsnittlig avvik **1,2 poeng** — de er ikke uavhengige meninger.

---

## Steg

| # | Steg | Innsats | Avhenger av |
|---|---|---|---|
| **1** | **Fiks `aperitif.py:200`:** `\d{7,8}` → `\d{5,8}`. Test med Lagavulin 16 (`464401`) og en 6-sifret vin | 15 min | — |
| **2** | **Eksponer `blindspot` som eget signal i output.** 6 654 varer er klassifisert; det er kategorien han har likt best (4,15). Ingen ny modell — bare gjør det synlige | 1 t | — |
| **3** | **Mekanisme-sjekk som workflow-steg FØR anbefalingen.** Lukket liste med sitat + retning per rad. **NB:** R1 hevdet 13 utløsere; reelt er det **3–4**. Ni av ti «vinmordere» sier «drikk vann/øl» og lisensierer ikke et kategoribytte, og asparges-mekanismen gjelder Sauvignon Blanc (hvit drue) — den kan ikke begrunne bytte fra rødt | 2–3 t | — |
| **4** | **Aperitif-sveip → `knowledge/scores/`.** ~480 kall, 30 rader/side. `robots.txt` tillater listestiene; **blokkerer `?query=`, `/api/`, `/ajax/*`, `/load`** | 3–4 t | 1 |
| **5** | **`sub_district_in` i `polet_store.query`** + prissone-lås som test | 2–3 t | — |
| **6** | **Prediksjonslag med effektkrav** (≥ 2,5 SE fra 3,82). Taus når det ikke slår ut — ingen «uavklart»-linje | 2 t | 4 |
| **7** | **ADR-amendment:** ADR-016 utvides fra filtrering til retrieval; ADR-017 amenderes med `v0_tier` +0,332; ny ADR for mekanisme-overprøving | 1–2 t | 3, 5 |

**Rekkefølge hvis bare noe skal gjøres:** 1 → 2 → 3. Til sammen 3–4 timer, og steg 2 og 3 er det
eneste som er *nytt*.

---

## Åpne spørsmål

1. **Skal den objektive delen kunne overprøve rammen din, eller bare svare innenfor den?**
   Eksemplet ditt sier ja til overprøving. Med 3–4 mekanisme-utløsere vil den fyre sjelden — er det
   for sjelden til å være verdt det?
2. **Aksepterer du at prediksjonsdelen er taus mesteparten av tiden?** Alternativet er å si noe på
   tynnere grunnlag, som med Provence-rosé ville vært direkte misvisende.
3. **Skal Aperitif-sveipen kjøres?** Den 37-dobler den faglige dekningen, men importerer også en
   prisbias (Spearman poeng × pris +0,65 for whisky, +0,80 for DN-vin). Prissone-lås demper, ikke
   fjerner.
4. **Appellasjons-belegget er tynt på rødvin** (6 av 137 viner i testen). Skal vi måle på rødt før
   steg 5, eller bygge og verifisere etterpå?

---

## Kilder

Repo-interne målinger er reproduserbare mot revisjonen i toppen. Eksterne: Adomavicius et al.
(TOIS 2021; ISR 2013), Fitzsimons & Lehmann (*Marketing Science* 23(1), 2004), Loepp (*Frontiers in
Big Data*, 2023), Starke et al. (2023), Kopsacheilis et al. (*JWE* 19(3), 2024), Kustos et al.
(*Food Research International* 136:109463), Hodgson (2008), Steck (2018), Felfernig/Jannach
(constraint-based recommenders).

**Ubekreftet, må ikke behandles som fakta:** at Vinmonopolets åpne API (`products/v0/details-normal`)
inneholder klokkefeltene. Belegget var en **tredjeparts GitHub-kopi** av en OpenAPI-spec — ikke
Vinmonopolets egen dokumentasjon, ingen responseksempler, ingen verifikasjon av Open-tier.
**ADR-019/020 skal ikke skrives om på dette.** Backlog-verdig: fem minutter med en gratis nøkkel
avgjør det.
