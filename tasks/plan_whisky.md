# Plan — whisky som tredje fagområde

> **Status:** forslag, ikke besluttet. Skrevet 2026-08-31 etter research av to agenter, én devil's
> advocate og én QA-agent.
> **Målt mot:** HEAD `c901b8b`, `catalog.ndjson` `count` 27 402, `data/untappd/checkins.csv`,
> `data/vivino/full_wine_list.csv` (122 ratede).
> Alle tall er målt i repoet eller verifisert mot kilde. Underlagsrapportene lå i en scratchpad som
> ikke overlever sesjonen — det som betyr noe er gjengitt her.

## Brukerens ønske

> «Du er god på vin og øl, jeg vil ha muligheten til å grave i whisky. Hvordan kan vi gjøre dette?
> Jeg kan manuelt rate whiskyer med karakter og kommentar, men vi trenger et faglig fundament også
> som hjelper meg med anbefalinger.»

## Anbefaling i én setning

**Bygg fundamentet tynt og datainnhentingen først — og spør brukeren hva han allerede har smakt før
noe kode skrives, fordi det er den eneste handlingen som flytter whisky fra n=0 i dag.**

---

## Det som ble målt, og som styrer planen

| # | Funn | Tall | Konsekvens |
|---|---|---|---|
| 1 | **Ølkanalen er allerede død** | Siste Untappd-check-in **2026-01-16**. 2025: 29 → 2026: **1**. CSV sist endret 12. mai. `untappd_stats.py` har **null nettverkskode** — innføringen er manuell. `beer_v0.json` ble likevel regenerert 30. aug på data fra januar | Whisky ville vært samme løp, med dyrere flasker og lavere frekvens. **Dette er planens viktigste enkeltfakta** |
| 2 | Notat-premisset holder ikke i tallene | Fritekst skrevet **4 av 211 ganger (1,9 %)** — `Your review` 0/122, `your_notes` 0/89, `Personal Note` 4/122 | Et notatskjema kan ikke bære signalet. Karakteren må klare seg alene |
| 3 | Tier-modellen kan ikke virke ved sin egen terskel | SD 0,61 (vin) / 0,54 (øl). Tier-stigen spenner 0,65 poeng. Ved n=3 per bøtte er 95 % KI **±0,69** — bredere enn hele stigen. Trengs ~14 per bøtte ≈ **84 ratinger**. Empirisk: 89 ølratinger over 20 familier ga **to** bekreftede preferanser | Ingen fit-modell på år |
| 4 | Han er hjemmedrikker | **72 av 75** stedsmerkede check-ins er «Untappd at Home» | Håpet om at drammer på bar øker takten er motbevist |
| 5 | Polet-katalogen er tom for whisky | `brennevin` = **2 rader** (begge grappa). `main_sub_category` — det eneste feltet som skiller whisky fra gin/rom — står i `PRUNED_CATALOG_FIELDS` og finnes i **0** rader | Katalogsveip krever kodeendring først |
| 6 | Brennevin har eget klokke-navnerom | Grappa-detaljfila har `{"Frukt": 9, "Fylde": 6}`. `Frukt` finnes i **1 av 1 664** detaljfiler. `clock_dims_for_category("brennevin")` kaster `ValueError` — kategorien er **uprobet** | Fasettkodene må probes. Ugyldig kode **feiler stille og returnerer hele kategorien** |
| 7 | Vinmonopolet har whisky-klokker | **Fylde / Fat / Røyk**, 1–12. Verifisert mot Polets klokke-artikkel + produktsider 18665101 (Feddie) og 11342501 (Évadé) | Reimplementerer i praksis Diageos Flavour Map med en tredje fat-akse |
| 8 | **Aperitif dekker whisky, nøklet på varenummer** | **939 produktrader / 32 sider, 337 med poeng 66–97.** Under ett minutt med `curl`. JSON-LD på produktsiden har `sku`, `ratingValue`, `manufacturer`, `category` | Eneste kilde som allerede er nøklet på Polets varenummer. Skriver rett inn i `knowledge/scores/`-formatet |
| 9 | Dekningen er bedre enn den ser ut, og **ikke** prisskjev | På det praktiske universet (Basis + Spesialutvalg): **176 av 217 = 81 %**. Median 984 vs 1 000 kr, flat per desil | Innvendingen om prisskjev dekning faller |
| 10 | Men scoren gjenforteller prislappen | Spearman(poeng, pris) **+0,65**; medianpris stiger monotont **448 → 2 225 kr** gjennom poengbåndene | For en value-fokusert bruker er «høyest score» nær «dyrest» |
| 11 | Deep-knowledge-verdien er svært ujevnt fordelt | `ol-norge-norden.md` (93 l) bærer ekte, ikke-pretrainet info: eierskap, allokeringskanaler, juleøl-slipp 5. nov. `ol-hopdominert.md` (528 l) er α-syrer og linalool-terskler — lærebokstoff modellen har | Av foreslåtte ~2 700 linjer er anslagsvis **150–250 reelt tilført** |
| 12 | Whisky har ingen BJCP | Ingen aktør publiserer en åpen stilkatalog. WSET L3 Spirits dekker **ikke** irsk eller japansk blant sine elleve kjernekategorier | Ankeret må være juridisk kategori, ikke en stiltaksonomi |

---

## Devil's advocate — hovedinnvendingen, og hva jeg gjør med den

**Innvendingen:** øl fikk 3 646 linjer deep-knowledge, en kjernefil, `beer_fit.py` og en egen ADR
bygget rundt en manuell datakanal — og kanalen døde sju måneder senere. Whisky ville gjentatt det,
med høyere flaskepris og lavere frekvens. Å bygge fem deep-knowledge-filer og en fit-modell før
første rating er å bygge infrastruktur for en atferd som ikke er observert.

**Det jeg gjør:**

- **Snur rekkefølgen.** Datainnhenting og friksjonsreduksjon først; fagfundament tynt og målrettet;
  ingen fit-modell, ingen bøtter, ingen fasettprobing, ingen katalogsveip i første omgang.
- **Angriper dødsmåten direkte.** Ølkanalen døde fordi innføring var manuelt arbeid i en fil.
  Whisky-ratinger skal derfor **dikteres i chat** — brukeren sier «Lagavulin 16, 4,25, røykfullt og
  tørt», Claude skriver raden. Ingen fil han vedlikeholder selv.
- **Prioriterer motsatt av det som ble foreslått faglig.** Det som er verdt å skrive ned er der
  modellen faktisk bommer eller mangler: norsk sortiment, Polets klokker og varetype-taksonomi,
  norske/nordiske destillerier, hva som er kjøpbart. Ikke α-syre-ekvivalenten for whisky.

**Der devil's advocate tok feil:** Aperitif-dekningen er ikke prisskjev, og `robots.txt` tillater
listestiene — ToS-forbeholdet var overdrevet.

---

## Faglig anker

Whisky har ingen BJCP. Tredelt anker i stedet:

1. **Juridisk kategori = sannhet.** Scotch Whisky Regulations 2009, US 27 CFR § 5.143 (inkl.
   American Single Malt, egen kategori fra 19.01.2025), EU 2019/787, irsk Technical File, JSLMA.
   Gratis, komplett, primærkilde-verifiserbart. Dette er whiskyens ekvivalent til BJCP-seksjonen i
   `cicerone.md`.
2. **Polets Fylde / Fat / Røyk = søkbar akse** — men se forbeholdet under.
3. **Dave Brooms flavour camps = språk** (Fragrant & Floral · Malty & Dry · Fruity & Spicy · Rich &
   Round · Smoky & Peaty, + fire amerikanske).

**ADR-025-forbeholdet gjelder.** Klokkene er et **grovfilter for stil-slektskap** — «smaker i samme
retning» — aldri «noe du vil like like godt». Hypotesen om at `Røyk` diskriminerer sterkere enn
vinklokkene (nær-binær, produksjonsdeterminert) er **ikke testet**, og må ikke kobles inn i en
rangering før den er det. Merk motargumentet: hvis torv er nær-binært, koder aksen trolig bare
«Islay eller ikke» — noe han kan lese av etiketten uten modell.

**Ikke skriv WSETs SAT for Spirits fra hukommelsen.** Dokumentet finnes (mai 2022, issue 2), men
begge PDF-URL-ene ga 403. Enten skaffes PDF-en, eller så skrives et eget, eksplisitt merket
notatskjema uten å påstå WSET-opphav. Presedensen er `bjcp_2021.pdf`-referansen som viste seg
hallusinert.

---

## Steg

| # | Steg | Innsats | Merknad |
|---|---|---|---|
| **0** | **Spør brukeren hva han allerede har smakt og likt.** | 5 min | Kan gi n=10–20 i dag — mer enn hele byggeplanen leverer på et år. **Gjør dette først** |
| **1** | Fiks `aperitif.py:200` (`\d{7,8}` → `\d{5,8}`) | 15 min | Delt med feature 1. Lagavulin 16 = `464401`, seks siffer. Rammer **63 av 931** whisky-varenumre og 587 vin-varenumre |
| **2** | **Aperitif whisky-sveip → `knowledge/scores/`** | 3–4 t | 32 sider, 939 rader, 337 med poeng. Leses av `scores.py` uendret. Gir navn, varenummer, land, klasse, pris, utvalg |
| **3** | **`knowledge/whisky.md` — tynn.** Juridiske kategorier, Polets klokker + varetype, Brooms camps, servering, norsk/nordisk sortiment, workflow. **Mål: ~150–220 linjer, ikke 2 700** | 1 økt | Filnavn = fagområdet. Whisky har ingen etablert rolletittel; «whiskysommelier» ville vært å finne opp en autoritet |
| **4** | **Rating-fangst med null friksjon.** `data/whisky/ratings.csv`, 5-punkt med kvart-trinn (samme skala som Vivino/Untappd — tersklene i `beer_fit.py` og `user_fit` er kalibrert på den). Brukeren dikterer i chat, Claude skriver raden | 1–2 t | Felter: varenummer, navn, destilleri, rating, dato, land/region, juridisk kategori, ABV, alder (null = NAS, og null er informasjon), **torv** (ja/nei/lett/ukjent), fattype, pris. Notat valgfritt — se funn 2 |
| **5** | `CLAUDE.md`-routing + `deep-knowledge/INDEX.md` + tester | 1 t | «Vin eller øl?»-presiseringen blir trepart. Forslag: whisky vurderes kun når nevnt, eller ved dessert/ost/digestif/kveldsdram |
| **—** | **Utsatt til n ≥ 15–20:** ADR-025-målingen på Fylde/Fat/Røyk (korrelasjon per akse, identiske-klokker-testen, én oppdiktet kontrolldimensjon) | 1 økt | Bygg evalueringen før modellen — ADR-017-prinsippet |
| **—** | **Utsatt til n ≥ ~84:** enhver fit-modell eller tier-stige | — | Se funn 3 |
| **—** | **Utsatt, kanskje for alltid:** katalogsveip av brennevin, fasettprobing, de fem deep-knowledge-filene | 45–70 t | Aperitif-lista dekker 81 % av det praktiske universet allerede |

**Kritisk sti:** steg 0 → 1 → 2 → 3. Til sammen én arbeidsdag, og etter det kan han faktisk grave.

---

## Åpne spørsmål

1. **Hva har du allerede smakt?** Grovt holder — «Lagavulin 16, likte godt», «Jameson, kjedelig».
   Dette er billigste datainnsamling i hele prosjektet.
2. **Betyr «grave i whisky» å få anbefalinger, eller å lese og lære?** Planen over antar det
   første. Er det andre som gjelder, er steg 3 hele leveransen og steg 2/4 unødvendige.
3. **Kjøper du flasker, eller drikker du mest dram ute?** Måledataene sier hjemmedrikker, men det
   er målt på øl.
4. **Skal whisky ligge i dette repoet?** For: deler Polet-katalog, varenummer, Aperitif og
   `value_score`-maskineri. Mot: `smaksprofil.md` er allerede 542 linjer med to fagblokker, og
   whisky deler nesten ingen parringslogikk med vin/øl. Anbefaling: samme repo — koblingen mot
   Polet-infrastrukturen er for verdifull til å duplisere.

---

## Kilder

Repo-interne målinger reproduserbare mot revisjonen i toppen. Eksternt verifisert: Scotch Whisky
Regulations 2009 (UKSI 2009/2890), 27 CFR § 5.143 + TTB final rule 18.12.2024 (i kraft 19.01.2025),
EU 2019/787, irsk Technical File (2014), JSLMA-merkeregler (i kraft 01.04.2021, bindende for
medlemmer fra april 2024 — **fortsatt frivillig bransjestandard uten lovhjemmel**), Vinmonopolets
klokke-artikkel, aperitif.no `robots.txt`.

**Ubekreftet, må ikke skrives inn som fakta:** WSETs SAT for Spirits-feltinnhold (403 på begge
PDF-URL-er); den irske pot still-endringen (foreslått 2021/2022, ikke bekreftet vedtatt);
klyngeantallet hos whiskyanalysis.com (kilden er selvmotsigende, 9 eller 10).
