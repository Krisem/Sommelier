# Scenario-test etter snapshot-ekspansjonen (ADR-024)

> Formål: verifisere at snapshot-ekspansjonen 1 543 → 13 775 rødviner faktisk gir **bedre svar**,
> ikke bare flere. Tre reelle scenarier kjørt offline mot `data/polet/` med prosjektets egne
> verktøy. Opprettet 2026-08-30.
>
> **Avvik fra `_TEMPLATE.md`:** malen beskriver en *utforskningsflight* (hypotese → kuratert
> flaskeliste → tracking). Dette er en **verifikasjon**, ikke en flight — det finnes ingen flasker
> å kjøpe her. Strukturen følger malens konvensjoner (falsifiserbar påstand, ankere, «slik leser vi
> resultatene»), men er organisert per scenario.
>
> **Verifisert mot:** `data/polet/catalog.ndjson` @ commit `6e984aa` (14 081 rader, 13 775 rødvin,
> `generated_at` 2026-08-29T15:52). Kontroll-korpus: samme fil @ `06cc4ad` (1 849 rader, 1 543
> rødvin) hentet ut med `git show` — alle før/etter-tall under er målt på begge, ikke anslått.
> `python3 -m pytest tests/ -q` → **291 passed** både før og etter. Ingen av funnene under fanges
> av testsuiten.

## Påstanden som ble testet

**«Det 20× større datagrunnlaget gir bedre anbefalinger, ikke bare flere.»**

Dommen: **delvis sann, og den er ujevnt fordelt.** *Katalogen* ble dramatisk bedre. *Verktøyene som
leser katalogen* ble målbart dårligere, fordi tre av dem har harde tak (`page_size`) eller
navnerom-antakelser som var ufarlige ved 1 543 rader og er ødeleggende ved 13 775.

---

## Scenario 1 — hverdagsrød under 250 kr

**Dom: DELVIS.** Utvalget er transformert. Rangeringsmekanismen som skal håndtere utvalget er det ikke.

**Kall:**
```python
polet_store.query(category="rødvin", max_price=250)   # + volume 75 cl, buyable, status aktiv
```

| | Gammelt snapshot | Nytt snapshot |
|---|---|---|
| Kandidater (rødvin ≤ 250 kr, 75 cl, kjøpbar, aktiv) | **401** | **1 448** |
| …fra Italia | 10 | **490** |
| …fra Frankrike | 3 | **400** |
| …fra Spania | 11 | 256 |
| …med kritiker-score i `knowledge/scores/` | – | **5** (0,3 %) |
| `user_fit`-tier | 7 fit / 394 neutral | 249 fit / 1 199 neutral |

**Det som er ekte bedre.** Det gamle snapshotet hadde 10 italienske og 3 franske hverdagsviner —
Italia er hjemmebanen hans (50 av 97 ratede rødviner). Snapshotet var altså tynnest nøyaktig der
han handler mest. Det er borte nå. Konkrete treff som ikke fantes før: `10614501` Casteloro
Valpolicella Ripasso Superiore 170 kr, `10390201` Cascina Castlet Barbera d'Asti Il Nido 210 kr,
`10282301` Carretta Langhe Nebbiolo 250 kr — alle i den Nord-Italia-stripen profilen peker på.

**Det som ble verre.** ADR-016 foreskriver default-rangering `sorted(wines, key=-critic_score)`.
Av 1 448 kandidater har **5** en kritiker-score. Den foreskrevne default-rangeringen er ikke lenger
kjørbar i denne prissonen — 99,7 % av feltet har ingen sorteringsnøkkel. Rangeringen faller
implisitt tilbake på Claudes prosa-skjønn, uten at noe sier fra om at det skjedde.

---

## Scenario 2 — osso buco-paring

**Dom: FUNGERER.** Klart det sterkeste resultatet av ekspansjonen.

Kunnskapslaget var allerede på plass: `deep-knowledge/servering-og-lagring.md:324` klassifiserer
braisert/langtidskokt som medium-høyt fylde · medium-høyt syre · **høyt tannin**, og navngir modent
Barolo, Brunello, eldre Burgund, Cornas. Testen er om katalogen kan levere det kunnskapslaget ber om.

**Kall:** `polet_store.query(category="rødvin", min_price=250, max_price=500)` → 4 320 aktive/kjøpbare
75 cl → 3 938 har `clock_buckets` → **1 806** treffer braisert-målprofilen (Fylde/Friskhet/Tannin
alle ≥ bøtte `7-8`).

Klassiske osso buco-kandidater i 250–500-sonen, før mot nå:

| Stil | Gammelt | Nytt |
|---|---|---|
| Barolo | **1** | 54 |
| Barbaresco | **0** | 24 |
| Brunello | **0** | 10 |
| Valtellina (Nebbiolo) | **0** | 10 |
| Amarone | **0** | 29 |
| Langhe/annet Nebbiolo | 6 | 72 |
| Ripasso | 1 | 19 |

Før ekspansjonen kunne systemet ikke svare på osso buco uten å gå utenfor snapshotet: 1 Barolo,
0 Barbaresco, 0 Brunello, 0 Valtellina, 0 Amarone. Nå er hele den klassiske paringsvifta til stede,
og `clock_buckets` lar den filtreres på struktur uten et eneste `details`-oppslag. Dette er
ekspansjonen som gjør kunnskapslaget *operativt* i stedet for teoretisk.

**Forbehold:** av de 1 806 har 4 kritiker-score og 141 `details` (eksakte klokker + `metode`-feltet
som avslører fatlagring). `metode` er nettopp signalet smaksprofilen sier avgjør «kraft»
(§ «Kraftigere kan IKKE søkes på Fylde-klokka»). Det finnes for 7,8 % av det aktuelle feltet.

---

## Scenario 3 — Etna-utvidelse

**Dom: DELVIS.** Katalogen svarer nå. Konfidens-signalet gjør det ikke.

| | Gammelt | Nytt |
|---|---|---|
| Etna-rødvin i snapshot | **1** | **74** (52 kjøpbare/aktive, 46 med klokker) |
| Prisspenn | – | 245 – 1 991 kr, median 474 |

Produsentene `deep-knowledge/italia.md` § 2.4.8 faktisk navngir, målt mot begge snapshot:

| Produsent | Gammelt | Nytt (kjøpbar/aktiv) |
|---|---|---|
| Graci | 1 | 3 (fra 221 kr) |
| Tascante (Tasca d'Almerita) | 0 | 4 |
| I Custodi | 0 | 2 |
| Terre Nere | 0 | 2 |
| Frank Cornelissen | 0 | 3 |
| Passopisciaro | 0 | 2 |
| Benanti · Donnafugata · Pietradolce | 0 | 1 · 2 · 1 |

Etna-kapittelet i `deep-knowledge/` var ren teori før — hver anbefaling det ga ville truffet
`PoletRefreshRequired`. Nå er 9 av 10 navngitte produsenter kjøpbare, inkludert det kapittelet selv
kaller «det naturlige steget opp… bedre value» (Graci, 221 kr).

**Blindsone-håndteringen sier ikke fra.** Alle 74 klassifiseres `neutral` / `rule_fired: default` /
**`confidence: "medium"`**. Etna er en dokumentert utforskningsfrontier (`smaksprofil.md`
§ «Regioner verdt å utforske», n=1: Donnafugata 4.1) — verktøyet skiller altså ikke «genuint nøytral»
fra «vet ingenting». Det finnes ingen maskinelt signal om lav konfidens å bygge et `[NYTT]`-flagg på;
ærligheten hviler helt på at Claude leser prosaen i `smaksprofil.md` på inferens-tid. Det er ikke et
brudd på ADR-016 (ingenting filtreres bort), men det er heller ingen støtte til den.

---

## Bugs — rangert etter skade

### B1 · `_peer_percentile` sammenligner mot 50 vilkårlige peers · **ØDELAGT AV EKSPANSJONEN**

`value_score._peer_percentile` → `search_with_facets(facets, page_size=50)` → `polet_store.query(...)[:50]`.
Katalogen er sortert leksikografisk på varenummer, og `query()` bevarer rekkefølgen. «Peer-gruppen»
er derfor **de 50 laveste varenumrene i landet** — et systematisk skjevt utvalg, ikke et tilfeldig.

Reproduksjon:
```python
from tools import polet_store
from tools.value_score import compute_value_score
p = polet_store.lookup("15690101")          # Les Griffons de Pichon Baron 2020, 709,30 kr
compute_value_score(p, fetch_vivino=False, fetch_aperitif=False)["summary"]
# → "pris i 72. percentil av 50 peers (median 362.4 kr)"
```
Sann fransk rødvins-median i snapshotet er **720,2 kr** (n=5 958), og vinens sanne percentil er
**0,49** — ikke 0,72. Systemet forteller brukeren at en vin ligger i øvre tredjedel når den ligger på
medianen. Skjevheten er konsekvent pessimistisk (lave varenumre er billigere).

**Målt effekt, samme kodesti, kun sample-kilden byttet** (400 tilfeldige rødviner, seed 7,
`_value_verdict` uendret):

| Snapshot | Andel viner der verdict endres på minst én kvalitetstier |
|---|---|
| Gammelt (1 543 røde) | **7,5 %** |
| Nytt (13 775 røde) | **30,5 %** |

Buggen fantes før, men var stort sett harmløs: Italia hadde 83 viner, så 50 var 60 % av poolen. Nå er
50 av 3 761 = 1,3 %. **Ekspansjonen firedoblet feilraten.** Andre målte medianer: Frankrike
sample 362 mot sann 720 (2×), Italia 387 mot 438, Spania 347 mot 369.

Ikke fanget av noen av de 291 testene.

### B2 · `search()` avkorter før `filter_results()` filtrerer · **FORVERRET AV EKSPANSJONEN**

`vinmonopolet.search(q, page_size=10)` returnerer `products[:page_size]`. `filter_results()` kjører
*etterpå*. Pris-/land-/kategorifilteret ser derfor bare de 10 første treffene.

```python
from tools.vinmonopolet import search, filter_results
len(filter_results(search("Barbera"), max_price=250))   # → 3
# snapshotet har 348 Barbera-rødviner, 94 av dem ≤ 250 kr
```
Gammelt snapshot hadde 16 Barbera i 250–500-sonen totalt, så et tak på 10 kostet lite. Nå kostes
det 97 % av feltet. Samme mønster på `search("Etna")` → 10 av 74.

Beslektet: `search()` matcher kun `name`, ikke `district`/`sub_District`. 38 av de 74 Etna-rødvinene
har ikke «Etna» i navnet (f.eks. `19245001` Vino di Anna Sfuso 2022) og er usynlige for fritekstsøket.

### B3 · `clock_buckets` har null lesere — hele klokke-sveipen er ubrukt

ADR-024 leverte klokke-bøtter på 10 986 av 13 775 rødviner. `grep -rn clock_buckets tools/` gir
treff **kun** i `polet_store.set_clock_buckets` (skriveren). Ingen anbefalingssti leser dem.
`find_similar_by_clocks` går via `get_product_details` → `details/<code>.json`, som finnes for 1 378
rødviner.

```python
find_similar_by_clocks({"Fylde":8,"Friskhet":9,"Garvestoffer":7},
    ["Barbera","Nebbiolo","Barbaresco","Valpolicella Ripasso","Chianti Classico"],
    max_price=500, category="Rødvin", top_k=8)
```
Snapshotet har **753** relevante viner for disse søkestrengene, **701** av dem med `clock_buckets`.
Funksjonen rangerer **13**. Kombinasjonen av B2 (`page_size=30` per søkestreng → 113 igjen) og
details-kravet (→ 13) kaster 98,3 % av det ekspansjonen leverte. De 8 som kommer ut er plausible —
men de er valgt fra 1,7 % av feltet, og ingenting i outputen sier det.

Dette er den dyreste enkeltposten: hovedleveransen i ADR-024 er koblet fra.

### B4 · `user_fit`-reglene er på engelsk, katalogen på norsk — advarslene fyrer aldri

`load_profile_rules()` leser den auto-deriverte blokken i `smaksprofil.md`, som er generert fra
Vivinos **engelske** stilnavn. `polet_store` er norsk. Målt på hele rødvinsbasen (n=13 775):

| tier | antall | | rule_fired | antall |
|---|---|---|---|---|
| neutral | 11 374 | | default | 10 952 |
| fit | **2 401** | | bekreftet_drue | 2 401 |
| very_fit | **0** | | blindspot | 422 |
| risky | **0** | | | |
| no_go | **0** | | | |

- `bekymringer = ["Provence Rosé", "Burgundy Red", "Southern Rhône Red"]` kan aldri matche
  «Bourgogne» / «Rhône». Repro: `user_fit.classify(polet_store.lookup("1013801"))` — Dom. Dupasquier
  Bourgogne Pinot Noir 2024, **229,90 kr** → `neutral` / `default`. Dette er nøyaktig kategorien
  profilen kaller «Billig Burgund» og der hans laveste rødvin noensinne ligger (Labouré-Roi, 1.5).
  Alle 9 billige Bourgogne-rødviner under 250 kr, og alle 76 Rhône-rødviner, får `neutral`.
- `bekreftet_stiler = ["Italian Ripasso", "Italian Amarone", "Southern Italy Red", ...]` matcher
  aldri «Valpolicella Ripasso» eller «Sicilia» → `very_fit` fyrer null ganger på 13 775 viner.
- De 2 401 `fit` er nesten utelukkende ett regel-treff: region «Nord-Italia» via
  `_region_alias_hits` (Piemonte/Veneto). `rule_fired` heter likevel `bekreftet_drue`.
- `bommet_druer_regioner` inneholder et helt avsnitt som én regel («Sauvignon Blanc: Bare én i hele
  dataene (Cloudy Bay 4.5 fra 2015). Ukjent om…») — parseren har slukt brødtekst som et
  matche-mønster. Uskadelig i praksis, men det er en parse-feil.

Buggen er eldre enn ekspansjonen, men var usynlig før: det gamle snapshotet hadde **0** Bourgogne
under 250 kr og 3 franske viner totalt i sonen. Ekspansjonen gjorde en latent bug til en aktiv.

Konsekvensen er en **invertert filter-bubble**: ADR-016 sier tier skal *advare, ikke skjule*.
Advarselen fyrer aldri, så brukeren får ingen advarsel — samme sluttresultat som å filtrere, uten at
noen valgte det.

### B5 · `data/user_fit/v0.json` dekker 66 av 14 081 varenumre

Fila har 409 oppføringer og er generert fra `knowledge/scores/`, ikke fra katalogen. Overlappen med
snapshotet er **66 varenumre (0,47 %)**. CLAUDE.md steg 6b sier «slå opp `data/user_fit/v0.json` per
varenummer» for batch-spørringer — det oppslaget bommer nå 99,5 % av tiden.
`user_fit.classify(produkt)` fungerer derimot direkte på en katalog-rad (det er slik tallene i B4 er
målt), så fiksen er sannsynligvis å bytte oppslagssti, ikke å regenerere fila. Fila er dessuten
stemplet `generated_at: 2026-07-02`, altså fra før ekspansjonen.

### B6 · 1 264 rødviner har `buyable: true` uten å være aktive

| status | buyable=true |
|---|---|
| `utgatt` | 556 |
| `utsolgt` | 543 |
| `langtidsutsolgt` | 165 |

Eksempler: `10063801` Ratte Les Corvées Trousseau 2022 (299,90), `10218801` Olivier Guyot
Chambolle-Musigny VV (1 051,10). `polet_store.query()` filtrerer ikke på `status`, så enhver
kandidatliste bygget på `buyable` alene vil inneholde utgåtte varer. ADR-024 løste det tilgrensende
problemet (varer som *forsvant* fra enumereringen) med `prune_delisted`, men disse er fortsatt i
katalogen med korrekt `status` — det er lesesiden som ikke bruker feltet. Ikke forårsaket av
ekspansjonen, men 20× flere rader betyr 20× flere feiltreff.

---

## Slik leser vi resultatene

**Var ekspansjonen verdt det? Ja — men gevinsten er ikke hentet ut ennå.**

Katalogen gikk fra å være ubrukelig på brukerens egen hjemmebane (10 italienske hverdagsviner,
1 Barolo, 1 Etna-rødvin) til å dekke den fullt ut (490 / 54 / 74). Osso buco og Etna kunne ikke
besvares fra snapshotet før; de kan nå. Det er en ekte, målt forbedring i **hva systemet kan si**.

Men de tre verktøyene som skal *velge* mellom radene har alle et tak fra da katalogen var liten:
`_peer_percentile` (50), `search` (10/30), `find_similar_by_clocks` (details-kravet). Ingen av dem
feiler høylytt — alle returnerer et plausibelt svar bygget på 1–2 % av datagrunnlaget. Og
`user_fit`s advarselsapparat er stille dødt på norsk katalogdata.

Rekkefølgen jeg ville fikset i:
1. **B3** — koble `clock_buckets` inn i `find_similar_by_clocks`. Det er hovedleveransen i ADR-024
   som ligger ubrukt, og fiksen låser opp 701 viner der det i dag er 13.
2. **B1** — peer-poolen må være hele poolen (eller et tilfeldig utvalg), ikke `[:50]`. 30,5 % av
   value-verdictene er feil i dag.
3. **B4** — normalisér navnerommet mellom `smaksprofil.md`s engelske stiltabeller og Polets norske
   felter. Dette er samme klasse feil som `Garvestoffer`/`Tannin(Sulfates)`-kollisjonen i ADR-024.
4. **B2**, **B5**, **B6** — mekaniske, lav risiko.

Ingen av de seks fanges av `tests/` (291 passed). Det er i seg selv et funn: testsuiten dekker
*logikk på små fixtures*, ikke *oppførsel ved katalogskala*. En test som asserterte at
`_peer_percentile` sample_size ≥ 90 % av poolen ville fanget B1 i det øyeblikket snapshotet vokste.

## Ikke verifisert

- Kun **rødvin**. Hvit/rosé/musserende er urørt av ekspansjonen (ADR-024) og ikke testet her.
- `value_score` er kjørt **offline** (`fetch_vivino=False, fetch_aperitif=False`). `quality_tier`
  blir da `unknown` for alt uten kritiker-score, og verdict `usikkert`. B1 er uavhengig av dette —
  peer-percentilen beregnes helt lokalt — men den samlede value-kvaliteten med Vivino + Aperitif
  påkoblet er ikke målt.
- Ingen faktisk smaking. Ingen av kandidatene over er kjøpt eller ratet.

---

## Tillegg (2026-08-30) — partisjonering av fiksene

> Skrevet på bestilling fra hovedtråden, som skal dele B1–B6 ut til parallelle agenter.
> Alle filnavn/funksjonsnavn under er verifisert mot koden, ikke gjengitt fra hukommelsen.

### Hvor årsaken bor

| Bug | Fil | Funksjon(er) | Årsak (ikke symptom) |
|---|---|---|---|
| B1 | `tools/value_score.py` | `_peer_percentile` (l. 233) | Beregner en **populasjonsstatistikk** (median/percentil) på `search_with_facets(..., page_size=50)`, dvs. et bundet, ikke-tilfeldig hode av populasjonen. |
| B2 | `tools/vinmonopolet.py` | `search` (l. 37), `search_with_facets` (l. 64), `filter_results` (l. 108), `find_similar_by_clocks` (l. 252) — **+ `_peer_percentile_legacy` (l. 191) i `value_score.py`** | **Rekkefølge:** `[:page_size]` skjer før predikatene. Taket er legitimt; plasseringen er ikke. |
| B3 | `tools/vinmonopolet.py` | `find_similar_by_clocks` (l. 252), `clock_distance` (l. 234), `CLOCK_DIMS` (l. 231) | Kandidat-klokker hentes kun via `get_product_details` → `details/<code>.json`. `clock_buckets` på katalog-raden leses aldri av noen. |
| B4 | `tools/user_fit.py` | `load_profile_rules` (l. 125), `_REGION_ALIASES` (l. 271), `_KATEGORI_NO_TO_EN` (l. 282), `classify` regel 2–4 (l. 398–450) | Reglene kommer fra Vivinos **engelske** `Regional wine style` (via `profile_stats.agg_by(rows, "Regional wine style")`); `polet_store` er norsk. |
| B5 | `tools/user_fit.py` | `classify_score_db` (l. 544), `write_v0_json` (l. 572) — **+ kallstedet `tools/profile_stats.py:222`** | Fila genereres fra `knowledge/scores/`, ikke fra katalogen. |
| B6 | `tools/polet_store.py` | `query` (l. 112) | `query()` har ingen `status`-parameter; `buyable` er det eneste kjøpbarhets-signalet lesesiden har, og det er sant for 1 264 ikke-aktive rødviner. |

### Deler fil — må til samme agent

- **B2 + B3** deler funksjonen `find_similar_by_clocks`. Ikke bare fila — *samme funksjonskropp*. Kan ikke splittes.
- **B4 + B5** deler `tools/user_fit.py`, og B4s alias-tabeller er modulnivå-state B5 også leser.

### Rekkefølge-avhengigheter

1. **B6 først, og additivt.** `polet_store.query` er felles inngang for B1, B2 og B3. Lander B6 med et *default-på* status-filter, endres kandidatmengden under føttene på de tre andre — inkludert tallene i assertions de nettopp har skrevet. Krev at B6 kun legger til en opt-in-parameter (`status=` / `exclude_status=`) med uendret default, og at hvert kallsted adopterer den eksplisitt. Da er B6 ordensuavhengig.
2. **B1 skal ikke gå via `search_with_facets`.** Ellers er B1 (value_score.py) og B2 (vinmonopolet.py) koblet gjennom et API den ene agenten endrer mens den andre kaller det — og `tests/test_value_score.py` importerer allerede `vinmonopolet`. `_peer_percentile` trenger ikke et *søk*, den trenger *populasjonen*: la den kalle `polet_store.query(category=…, country=…)` direkte. Da blir B1 rent lokal til `value_score.py`. (Merk: dette berører ADR-009, som spesifiserte fasett-API framfor 3 fritekstsøk — hensikten består, men avviket bør noteres av hovedtråden.)
3. **B2 må dekke `_peer_percentile_legacy`**, som ligger i *value_score.py*, ikke vinmonopolet.py. Dette er den ene stedet partisjonen ikke er ren. Enten gir du hele B2-mønsteret til value_score-agenten for den ene funksjonen, eller du erklærer legacy-stien død sammen med B1-fiksen. Jeg anbefaler det siste: fikser du B1 riktig, er `_peer_percentile_legacy` bare en fallback for et kall som ikke lenger kan bomme.

### Er B1 og B2 samme bug?

**Nei — felles opphav, ulik fiks.** Begge stammer fra at `page_size` ble et «hvor mye trenger jeg»-ratt den gang taket sjelden var bindende. Men:

- **B2 er en rekkefølgefeil.** Taket er riktig — brukeren skal ha topp-N. Fiksen er å filtrere før man avkorter. `search_with_facets` er *ikke* rammet av B2: fasettene er allerede påført før `[:page_size]`.
- **B1 er en populasjonsfeil.** Her skal det ikke være et tak i det hele tatt; en median av 50 vilkårlige er ikke en median. Fikser du B2 perfekt, er B1 uendret.

Deler du dem på to agenter: riktig. Men gjør steg 2 over til en betingelse, ellers kolliderer de på `search_with_facets`.

### Fallgruve for B3-agenten — les denne før du rører `clock_distance`

Samme klokke har **tre** navn i dette repoet:

| Lag | Nøkkel | Verdi |
|---|---|---|
| `details/<code>.json` (`vinmonopolet.parse_product_html`) | `Garvestoffer` | heltall 1–12 |
| Katalog-raden (`clock_buckets`) | `Tannin` | bøtte-streng `"7-8"` |
| vmpws søke-fasetter (`polet_facets`) | `Tannin(Sulfates)` | bøtte-kode |

`CLOCK_DIMS = ("Fylde", "Friskhet", "Garvestoffer")`, og `clock_distance` **hopper stille over en dimensjon som mangler i én av profilene** — den returnerer ikke `inf`, den returnerer en finit, plausibel avstand regnet på 2 av 3 akser. Mater man katalogens `clock_buckets` rett inn i `clock_distance`, får man altså et svar som *ser* riktig ut og har mistet garvestoffene. Dette er nøyaktig `Garvestoffer`/`Tannin(Sulfates)`-kollisjonen fra ADR-024, i en tredje variant.

`tools/polet_facets.py` har allerede bøtte-maskineriet (`_CLOCK_BUCKETS`, `clock_range_buckets`, `_TRAP_DIMS`) og **null importører utenfor egne tester** — den er bygget for dette og aldri wiret inn. Gi den til B3-agenten sammen med `vinmonopolet.py`.

### Foreslått partisjon

| Agent | Eier filer | Bugs |
|---|---|---|
| **0 (først, additiv)** | `tools/polet_store.py`, `tests/test_polet_store.py` | B6 |
| **A** | `tools/vinmonopolet.py`, `tools/polet_facets.py`, `tests/test_vinmonopolet.py` | B2, B3 |
| **B** | `tools/user_fit.py`, `tools/profile_stats.py`, `tests/test_user_fit.py` | B4, B5 |
| **C** | `tools/value_score.py`, `tests/test_value_score.py` | B1 |

A, B og C er disjunkte når betingelsen i rekkefølge-punkt 2 holder. `tests/test_vinmonopolet_html_fixture.py`, `tools/polet_details.py` og `tools/refresh_polet.py` skal ingen røre.

---

## Tillegg — rekkefølge mot hvit/musserende/rosé-sveipen

**Fiks seleksjonslaget først.** Ikke som forsiktighet — som måling.

`_peer_percentile` grupperer på (kategori × land). Jeg målte verdict-flip per kategori i dagens snapshot, samme metode som B1:

| Kategori | n | Land-pools > 50 viner | Andel viner i slike pools | Verdict-flip **i dag** |
|---|---|---|---|---|
| Hvitvin | 152 | 1 av 6 | 34 % | **1,3 %** |
| Musserende | 99 | 0 av 3 | 0 % | **0,0 %** |
| Rosévin | 53 | 0 av 3 | 0 % | **0,0 %** |
| Rødvin | 13 775 | 13 av 47 | 98 % | **30,0 %** |

B1 er **ikke** kategori-uavhengig i praksis: den biter først når en (kategori × land)-pool overstiger 50. I hvit/musserende/rosé gjør nesten ingen pool det i dag, så feilen er ~0. Rødvin har 98 % av vinene i pools over taket, og der er den 30 %.

Hvitvin-sveipen er altså ikke *utsatt* for B1 — den vil **innføre** den, i tre kategorier hvor den i dag ikke finnes. Rekkefølgen `E deretter B1` betyr at man gjentar akkurat den feilen ekspansjonen av rødvin allerede har gjort, med fasit i hånd.

**Anbefaling:** B1-fiksen er lokal til `_peer_percentile` og gating-betingelsen er kjent. Kjør Agent C ferdig først, så E. Skal de kjøre parallelt, er det forsvarlig kun hvis E ikke committer det utvidede snapshotet før C er landet — datafila er det som utløser feilen, ikke koden.

---

## Tillegg — skalainvariante assertions

Suiten er 291 tester på 0,56 s, alle mot små fixtures. Det er derfor den er blind: den tester at funksjonene **regner riktig**, aldri at de **har sett hele datagrunnlaget**. Under er fem assertions av den andre typen. De må kjøre mot ekte `data/polet/catalog.ndjson`, ikke fixture — det er hele poenget. Hver hører hjemme i test-fila agenten allerede eier, så ingen deles.

**A1 · Peer-poolen er populasjonen** — `tests/test_value_score.py` (Agent C, fanger B1)
> For et utvalg viner: `_peer_percentile(p)["sample_size"] >= 0.9 * (len(polet_store.query(category=p.kategori, country=p.land)) - 1)`.
> Formulert som andel, ikke som tall — den holder ved 1 543 og ved 137 750. Ville feilet i det øyeblikket noen kategori×land passerte 56 viner.

**A2 · Ber du om N som matcher, får du N hvis N finnes** — `tests/test_vinmonopolet.py` (Agent A, fanger B2)
> For et predikat P (f.eks. `pris ≤ 250`) og en søkestreng q hvor snapshotet har ≥ N treff som oppfyller P:
> `len([x for x in search(q, page_size=N) if P(x)]) == N`.
> Sier ingenting om hvilke N. Tester bare at avkortingen ikke spiste treff som filteret ville beholdt — invariant under enhver katalogstørrelse.

**A3 · Similarity har sett signalet som finnes, og har ikke mistet en akse** — `tests/test_vinmonopolet.py` (Agent A, fanger B3)
> To deler, begge nødvendige:
> (a) For en søkestreng hvor ≥ `10 × top_k` kandidater i snapshotet har klokkedata (`details` **eller** `clock_buckets`): `len(find_similar_by_clocks(...)) == top_k`. Fanger at kandidatpoolen ble kastet.
> (b) `clock_distance(a, b, dims=D)` skal **kaste** når en dimensjon i `D` mangler i `a` eller `b`, ikke stille regne på færre akser. Fanger `Garvestoffer` vs `Tannin` — den tredje utgaven av ADR-024-kollisjonen, og den eneste feilen i B3-fiksen som ikke synes i outputen.

**A4 · Hver regel er konfrontert med hele katalogen** — `tests/test_user_fit.py` (Agent B, fanger B4)
> Klassifisér hele katalogen. Assert at **hver needle i hver regelliste** (`no_go`, `bekymringer`, `bommet_druer_regioner`, `bekreftet_stiler`, `bekreftede_druer`, `regioner_pluss`) enten matcher minst én rad, eller står på en eksplisitt, kommentert `UNTRANSLATED`-liste.
> Dette er den generelle formen av B4: en regel som aldri fyrer er enten feil eller død, og begge deler skal være et bevisst valg. Samme assertion fanger at «Sauvignon Blanc: Bare én i hele dataene (Cloudy Bay…)» er brødtekst som har lekket inn som mønster. Sekundært: assert at `very_fit`, `risky` og `no_go` hver fyrer ≥ 1 gang — 0 av 13 775 er ikke et gyldig utfall for et advarselssystem.

**A5 · Et oppslag som brukes må dekke det den slås opp i** — `tests/test_user_fit.py` (Agent B, fanger B5) og `tests/test_polet_store.py` (Agent 0, fanger B6)
> (a) `len(set(v0.json) & {p.code for p in katalog}) / len(katalog) >= 0.9`. CLAUDE.md steg 6b foreskriver oppslaget; en dekningsgrad på 0,47 % gjør instruksjonen usann uten at noe sier fra.
> (b) Ingen kandidatliste som er ment for brukeren inneholder `status != "aktiv"`. Assert på `query(..., status="aktiv")` at `buyable`-feltet aldri brukes alene som kjøpbarhets-signal.

Felles krav til alle fem: **ingen delt `conftest.py`-fixture.** Hver test importerer `polet_store` direkte. Fem agenter som redigerer én fixture-fil er nøyaktig den kollisjonen partisjonen over er ment å unngå.

---

## Tillegg (2026-08-30, sent) — E-rekkefølgen presisert, og tre funn til om hvit/rosé

Den første anbefalingen min («kjør Agent C ferdig først, så E») navnga bare C. Det var for smalt.
Etter å ha målt hvit/musserende/rosé eksplisitt: **E er koblet til F1 og F2 også, ikke bare F3.**
Presiseringen under erstatter den delen av forrige tillegg.

### Riktig gate er merge-rekkefølge, ikke oppstart

B1 utløses av **datafila**, ikke av at sveipen kjører. E kan derfor kjøre parallelt med alle fire
fikse-agentene. Men gaten er smalere enn «før noen bruker snapshotet til value-vurderinger»: det
finnes ingen menneskelig sjekkpunkt mellom commit og bruk. I det øyeblikket det utvidede
snapshotet er committet, er hver value-vurdering i hver sesjon påvirket, uten et eneste varsel.

> **Gate: ikke commit utvidet hvit/musserende/rosé-katalog før F1, F2 og F3 har landet.**
> Sveipen selv kan starte når som helst.

### E forsterker B2 og B4, ikke bare B1

- **B2:** `search("Riesling")` returnerer i dag nesten hele hvitvinskategorien (n=152), så
  `page_size`-taket biter ikke. Etter E kollapser det nøyaktig som Barbera gjorde (10 av 348).
  F1 er dermed på E-s kritiske sti.
- **B4 har sin høyeste innsats i rosé**, som E er i ferd med å utvide. Provence-rosé er brukerens
  verst dokumenterte kategori (snitt **2,38**, inneholder hans eneste 1.0), og
  `bekymringer = ["Provence Rosé"]` kan aldri matche norsk katalogdata. I dag koster det én vin:
  `16908505` **Studio by Miraval Rosé 2025**, 459,90 kr → `neutral` / `default`. Miraval står på
  no-go-lista (årgangs-pinnet til 2014, så `neutral` er forsvarlig *der*) — men `risky` fra
  Provence-regelen skulle fyrt uansett, og gjør det ikke. Etter E gjelder det hver Provence-rosé
  Polet fører.

### Blindspot-regelen virker bare ved et sammentreff

Alle 422 blindspot-treff i katalogen fordeler seg slik:

| Blindspot | Treff | Hvorfor den fyrte |
|---|---|---|
| Portugal Red Wine | 307 | «Portugal» staves likt på norsk og engelsk |
| Chile Red Wine | 109 | «Chile» staves likt |
| Uruguay Red Wine | 5 | «Uruguay» staves likt |
| Germany Red Wine | **1** | Vinen heter `17227001` **United Winemakers of Germany Pinot Noir** |

`_KATEGORI_NO_TO_EN` leverer «Red Wine», så sammensatt-sjekken tester i praksis bare landordet.
Italy/Spain/Germany/Austria/United States/Lebanon/France/South Africa/Greece finnes ikke som
landnavn i katalogen — de er Italia/Spania/Tyskland/Østerrike/USA/Libanon/Frankrike/Sør-Afrika/Hellas.
Den ene tyske vinen som får blindspot-flagget sitt, er altså den som tilfeldigvis har det engelske
ordet «Germany» i merkenavnet; 367 andre tyske rødviner får ingenting.

Regelen ser ut til å virke fordi den fyrer 422 ganger. Den gjør det på tre land av femten.
For **F2**: `_KATEGORI_NO_TO_EN` løste kategori-halvdelen av dette i sin tid — landhalvdelen og
stilhalvdelen mangler fortsatt.

### `clock_buckets` finnes ikke utenfor rødvin

| Kategori | rader med `clock_buckets` |
|---|---|
| Rødvin | 10 986 / 13 775 |
| Hvitvin | **0** / 152 |
| Musserende | **0** / 99 |
| Rosévin | **0** / 53 |

Klokke-sveipen i ADR-024 var rødvin-only. Fikser **F1** B3 slik at `find_similar_by_clocks` leser
`clock_buckets`, får den fortsatt ingenting å lese utenfor rødvin. Skal similarity virke på hvitvin,
må E inkludere et kartesisk klokke-sveip for de nye kategoriene — det er den dyre delen (rate-limit,
jf. ADR-024s to bøtter). Dette er et scope-punkt for E-briefen, ikke noe F1 kan løse.

---

## Tillegg — B7 (mistanke, delvis målt) og B8 (strukturelt, umålt)

> Skrevet fordi hovedtråden ba om det som ikke rakk å bli målt godt nok. Konfidensnivået er
> oppgitt per punkt. Ingen av disse er delt ut som fiks.

### B7 · Samme vin på flere varenummer til ulik pris — usynlig for `value_score`

**Konfidens: middels.** Målt, men med ett uverifisert premiss (se forbehold).

Grupperer man rødvin på (navn × volum) og teller grupper med mer enn ett varenummer:

| | Grupper | Rader | Grupper med ≥ 10 % prisspredning |
|---|---|---|---|
| Gammelt snapshot | **0** | 0 | 0 |
| Nytt snapshot | **313** | 792 | **142** |

Null før, 313 nå — dette er skapt av ekspansjonen i sin helhet. Verste tilfelle:
`ch. pichon longueville comtesse de lalande 2016`, 75 cl, **fem aktive varenummer fra 2 113 til
3 950 kr** (+87 %). Andre: `ch. beychevelle 2019` 75 cl → `17062901` 1 200 kr mot `14837601`
2 189 kr, begge aktive.

`compute_value_score` slår opp ett varenummer og sammenligner mot land-peers. Den ser aldri at den
*identiske* vinen ligger 989 kr billigere under et annet varenummer i samme snapshot. For et verktøy
hvis eneste jobb er «er dette et godt kjøp» er det den mest direkte formen for feil svar som finnes —
og den er ikke synlig i noen av de seks andre buggene. Sekundært forurenser duplikatene peer-poolen,
som teller samme vin flere ganger.

**Forbehold, og de er reelle:**
- **468 av de 792 radene er `Spesialutvalg`** — Polets auksjons-/raritetskanal, der separate partier
  med ulik proveniens og pris er *forventet*, ikke en feil. Der er dette ikke en bug.
- De resterende 324 (267 Bestilling, 55 Tillegg, 2 Basis) er i normale kanaler, og der er mistanken
  sterkere.
- **Jeg har ikke verifisert at identisk navn + volum betyr identisk produkt.** Det kan skjule ulik
  årgang i navnefeltet, ulik flasketilstand eller ulik importør. Uten `details` for disse radene kan
  jeg ikke avgjøre det, og jeg har ikke hentet dem.
- Nesten hele funnet ligger i den dyre Bordeaux-enden. I brukerens hverdagssone (≤ 250 kr, 75 cl,
  aktiv) er det **2 duplikat-rader av 1 448**. Praktisk brukerpåvirkning i dag: nær null. Det er
  «noe spesielt»-sonen og peer-statistikken som rammes.

**Riktig ramme er antakelig ikke «bug» men «manglende sjekk»:** `value_score` har aldri spurt om
samme vin finnes til en annen pris, fordi det før ekspansjonen ikke fantes noe å spørre om.

### B8 · `PoletRefreshRequired` betyr ikke lenger det den sier — for rødvin

**Konfidens: høy på mekanismen, umålt på konsekvens.**

`vinmonopolet.search()` kaster `PoletRefreshRequired` ved null treff, med hintet «refresh katalogen
fra desktop». Det var riktig da snapshotet dekket 2 % av katalogen. ADR-024 slår selv fast at «etter
en komplett sveip er **fravær informasjon** — men kun i den kategorien som faktisk er enumerert»,
og rødvin er nå enumerert eksakt (13 775).

For rødvin betyr null treff derfor nå **«Polet fører den ikke»**, ikke «snapshotet er utdatert».
Koden sier fortsatt det siste. Konsekvensen er at Claude vil be brukeren kjøre en refresh — et tungt,
rate-limitet ritual — i situasjoner der det korrekte svaret er «den finnes ikke, her er et
alternativ». Det er stikk i strid med anti-hallusineringsregelen i CLAUDE.md, som sier at man skal si
klart fra når Polet ikke har vinen.

Nyansen som gjør dette relevant for **E**: hintet er fortsatt *korrekt* for hvit/musserende/rosé, som
ikke er komplette. Unntaket må altså vite hvilke kategorier som er enumerert — og råstoffet finnes
allerede i `catalog_meta.json` (`category_coverage`). Når E lander, endres svaret for tre kategorier
til, og da bør det endres i kode og ikke i hukommelsen til den som leser.

Jeg har ikke målt hvor ofte dette faktisk inntreffer i en ekte sesjon. Det er derfor en strukturell
observasjon, ikke et tall.

### B8 — hva E må gjøre *under* sveipen

**Dette er ikke utelukkende et kodespørsmål.** Fiksen trenger å vite hvilke kategorier som er
*komplett enumerert*, og den opplysningen finnes ikke i katalogen etterpå.

`catalog_meta.json` har i dag kun `category_coverage`, som er en telling av hva snapshotet
*inneholder*:

```json
{"category_coverage": {"hvitvin": 152, "musserende_vin": 99, "rosévin": 53, "rødvin": 13775}}
```

Den kan ikke skille **«152 hvitviner fordi det er alle som finnes»** fra **«152 hvitviner fordi
sveipen ble avkortet»**. Det er nøyaktig `pageSize`-fella fra ADR-024: en avkortet sveip produserer
et plausibelt tall uten noe merke på seg. Det som gjorde rødvin beviselig komplett var ikke tallet
13 775, men at fasett-`totalResults` og full enumerering **var enige om det** — en måling E har
mens den kjører, og mister i det den er ferdig.

**Konkret, per kategori E enumererer, skriv til meta:**

| Felt | Hvorfor |
|---|---|
| `total_results` fra fasett-API-et | Fasiten sveipen måles mot |
| `enumerated` (antall unike rader hentet) | Likhet med `total_results` er selve komplett-beviset |
| `method` (f.eks. `"relevance+name-asc union"`) | ADR-024 (e): relevans alene hopper over produkter |
| `completed_at` | Kompletthet forvitrer — nye varer listes fortløpende |

Uten dette må neste person kjøre en full sveip på nytt bare for å finne ut om hvitvin er komplett,
og det koster timeskvoten om igjen. Med det er fiksen ren kode: `search()` slår opp kategorien i
meta og velger mellom «Polet fører den ikke» og «snapshotet dekker ikke denne kategorien ennå».

**Alderskomponenten må med.** En kategori som var komplett for 30 dager siden er ikke beviselig
komplett i dag. `polet_store.catalog_age_days()` og `value_score.SNAPSHOT_STALE_DAYS = 14` finnes
allerede — kompletthets-påstanden bør degradere på samme måte som value-språket gjør, og falle
tilbake til dagens refresh-hint når den er for gammel.

**Presedensen finnes allerede i repoet:** `prune_delisted` bygger på nøyaktig samme premiss («etter
en komplett sveip er fravær informasjon, men kun i den enumererte kategorien») og verner seg mot
avkortede sveip med en 10 %-grense og `force=True`. Kompletthet er altså allerede et begrep koden
handler på — det er bare aldri skrevet ned. B8 og `prune_delisted` bør lese samme felt.
