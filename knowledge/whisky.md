# Whisky-kjerne

> Lean kjerne. Lastes ved whisky-forespørsler sammen med `smaksprofil.md`. **Filen er
> bevisst tynn.** Whisky har ingen BJCP, og det som er verdt å skrive ned er der modellen
> faktisk bommer eller mangler — juridiske definisjoner, Polets egne akser, norsk sortiment —
> ikke lærebokkjemi den allerede kan. Målt anslag: av et foreslått 2 700-linjers fundament var
> 150–250 linjer reelt tilført ([`tasks/plan_whisky.md`](../tasks/plan_whisky.md) funn 11).

## Status: n=7

**Brukeren har syv registrerte whisky-ratinger** (`data/whisky/ratings.csv`, diktert
2026-08-31). Det er nok til å slå opp og sammenligne, og altfor lite til å modellere:

| Flaske | Rating | Pris | Aperitif | Torv (Polets Røyk) |
|---|---:|---:|---:|---|
| Nikka Coffey Grain | 4,50 | 700 | 85 | nei (1/12) |
| Talisker 10 | 4,25 | 630 | 88 | ja (7/12) |
| Highland Park 12 | 4,25 | 600 | 87 | lett (5/12) |
| Balvenie DoubleWood 12 | 4,25 | 800 | 88 | nei (2/12) |
| Lagavulin 16 | 4,00 | 1 100 | 92 | ja (10/12) |
| Laphroaig 10 | 4,00 | 665 | 89 | ja (9/12) |
| Glenmorangie Quinta Ruban 14 | 3,75 | 880 | — | nei (ingen klokker) |

- **Fortsatt ingen fit-score, ingen tier, ingen «du vil like denne».** Tier-stigen spenner 0,65
  poeng mens SD på brukerens egne ratinger er 0,61; ved n=3 per bøtte er 95 % KI ±0,69 — bredere
  enn hele stigen. Det trengs ~84 ratinger før en modell kan si noe. Ved n=7 er SD **0,23** og
  seks av sju ligger mellom 4,00 og 4,50. Si hva flasken *er*, ikke hva han vil synes om den.
- **Bunnen er tom.** Ingen rating under 3,75. Utvalget er flasker han valgte å kjøpe, så det
  bærer et seleksjonsbias som gjør høye snitt uinformative. Det som mangler er flaskene han
  ikke likte.
- **Det eneste som skiller seg ut, er uenighet med kritikerne, ikke et smaksmønster.** Nikka
  Coffey Grain er hans topp (4,50) og utvalgets laveste Aperitif-poeng (85); Lagavulin 16 har
  høyest Aperitif-poeng (92) og ligger nederst blant de fire torvede. Aperitif-poeng korrelerer
  +0,66 med pris, så dette er en prisobservasjon like mye som en smaksobservasjon.
- **Torv skiller ikke i tallene — men det er sannsynligvis fordi konteksten mangler, ikke
  fordi preferansen mangler.** Se neste avsnitt. Ikke presenter «torv betyr ingenting for deg»
  som et funn.
- **Vin- og øl-profilen overføres ikke uten videre.** Den ene broen som er rimelig å anta er
  røyk/fenol: brukeren har ratet Rauchbier-familien som blindsone (n=1), altså ukjent — ikke som
  en preferanse. Ikke antatt torv-toleranse fra noe som helst.

## Kontekst er en del av dommen, ikke metadata rundt den

Kristoffer sa 2026-08-31, om at torv ikke skilte i de sju tallene:

> «Jeg tror ikke det er støy, det er kontekst. En whisky med mye torv er nydelig på en kald
> høstdag eller vinterdag, mens en highland park passer seg mye bedre sen vår.»

Det er en korreksjon av hvordan tallene skal leses, og den er delvis testbar på de 89
ølratingene som har dato:

| | n | snitt rating | median ABV |
|---|---:|---:|---:|
| Kald sesong (okt–mar) | 53 | 3,41 | **6,5 %** |
| Varm sesong (apr–sep) | 36 | 3,37 | **5,4 %** |

Sterke øl (ABV ≥ 7) får 3,51 om vinteren og 3,55 om sommeren. **Sesongen endrer altså ikke hvordan
han dømmer — den endrer hva han strekker seg etter.** Signalet ligger i valget, ikke i scoren, og
en modell som bare ser karakterer vil aldri finne det uansett hvor mange flasker som rates.

Forbeholdet: n=36 i den varme halvdelen, det er øl og ikke whisky, og Polets sesongutvalg er i seg
selv sesongstyrt. **Behandle dette som en hypotese med retning, ikke som et etablert mønster.**

Konsekvensen for filen du skriver til: `drukket_dato` og `anledning` er egne felter, og de sju
første radene har begge tomme — den konteksten er ikke rekonstruerbar. Spør etter anledningen når
han rater, men **la aldri et manglende svar stoppe raden.**

**Fangst av ratinger: han dikterer i chat, Claude skriver raden.** Ølkanalen døde nettopp fordi
innføring var manuelt filarbeid (siste Untappd-check-in 2026-01-16; 2025: 29 → 2026: 1). Skalaen
er 5-punkt med kvart-trinn, samme som Vivino og Untappd. Notat er valgfritt — fritekst ble
skrevet 4 av 211 ganger (1,9 %), så karakteren må klare seg alene. Ingen app:
[ADR-033](../docs/ARCHITECTURE.md#adr-033-kontekst-fanges-i-dikteringen-ikke-i-en-app).

## Anker 1: juridisk kategori

Whisky har ingen åpen stilkatalog. **Definisjonen er derfor loven**, og den er presis, gratis og
verifiserbar. Alle henvisninger under er verifisert mot primærkilde 2026-08-31.

| Opphav | Hjemmel | Kjernekrav |
|---|---|---|
| **Scotch** | Scotch Whisky Regulations 2009 (UKSI 2009/2890) | Destillert og modnet i Skottland, ≥ 3 år på eikefat ≤ 700 l, ≥ 40 % ABV. Kun vann og karamellfarge (E150A) kan tilsettes. Fem definerte kategorier: single malt, single grain, blended malt, blended grain, blended |
| **Irsk** | Technical File for Irish Whiskey (2014), EU-registrert GI | Destillert og modnet på øya Irland, ≥ 3 år, ≥ 40 %. Kategoriene pot still, malt, grain, blended |
| **USA** | 27 CFR § 5.143 | «Whisky» ≤ 190 proof fra kornmask, lagret på eik, ≥ 40 % ved tapping. Bourbon: ≥ 51 % mais, nye kullsvidde eikefat, inn på fat ≤ 125 proof. Rye tilsvarende med ≥ 51 % rug. **American Single Malt er egen standard fra 19.01.2025** (TTB final rule 18.12.2024): 100 % maltet bygg, ett destilleri, fat ≤ 700 l |
| **EU** | Forordning 2019/787 | Minstekrav for «whisky/whiskey» solgt i EU: kornmask, ≥ 3 år på trefat ≤ 700 l, ≥ 40 %, ingen tilsatt alkohol eller søtning |
| **Japan** | JSLMA-merkeregler, i kraft 01.04.2021, bindende for medlemmer fra april 2024 | Mask med maltet korn, vann fra Japan, mesking/gjæring/destillasjon i Japan, ≥ 3 år på fat ≤ 700 l i Japan, ≥ 40 %. **Bransjestandard uten lovhjemmel** — ikke-medlemmer er ikke bundet, så «japansk whisky» på etiketten er fortsatt ikke en garanti |

**Hvorfor dette er nyttig i praksis, ikke bare pedanteri:** aldersangivelse på en blend gjelder
den *yngste* komponenten. «NAS» (no age statement) er ikke et kvalitetstegn i noen retning — det
er fravær av informasjon, og skal behandles som det. En japansk flaske uten JSLMA-samsvar kan
lovlig inneholde importert skotsk sprit.

## Anker 2: Vinmonopolets egne akser

Polet fører whisky med tre klokker, 1–12 — **et annet namespace enn vinens**:

| Klokke | Leses som |
|---|---|
| **Fylde** | Kropp og intensitet |
| **Fat** | Hvor tydelig fatpreget er — vanilje, karamell, tørket frukt, krydder |
| **Røyk** | Torv/fenol |

Verifisert mot Polets klokke-artikkel og produktsidene `18665101` (Feddie) og `11342501` (Évadé).
I praksis er dette Diageos Flavour Map med en tredje fat-akse.

**ADR-025-forbeholdet gjelder også her, og det er ikke en formalitet.** På vin korrelerer klokkene
~0 med brukerens egne ratinger (+0,16 / +0,09 / −0,10), og hver gruppe med identiske klokker
spenner hele ratingskalaen. Klokkene er et **grovfilter for stil-slektskap** — «smaker i samme
retning» — aldri et argument for at han vil like noe.

Hypotesen om at `Røyk` diskriminerer skarpere enn vinklokkene, fordi torv er nær-binært og
produksjonsbestemt, er **utestet**. Merk motargumentet før noen tester den: hvis aksen er
nær-binær, koder den trolig bare «Islay eller ikke» — noe han kan lese av etiketten uten modell.
Målingen er utsatt til n ≥ 15–20.

**Katalogen dekker whisky fra 1. september 2026.** `data/polet/catalog.ndjson` har
**1 132 whiskyrader** (`main_sub_category.code == "brennevin_whisky"`) — hele Polets
whisky-sortiment, sveipet fra `mainSubCategory:brennevin_whisky` og avstemt mot API-ets eget
`totalResults` på 1 132. Av dem er 902 aktive, 40 lanseres, resten utsolgt eller utgått.

Fram til denne datoen hadde katalogen to brennevinsrader, begge grappa, fordi
`main_sub_category` — det eneste feltet som skiller whisky fra gin og rom — ble prunet bort ved
ingest. Sveipen krevde derfor en kodeendring først, ikke bare et refresh-ritual.

Ett forbehold står igjen:

- **Ingen klokker.** Fylde/Fat/Røyk ligger i produktsidens detalj-JSON, ikke i søkeresultatet,
  og `details/` er ikke hentet for whisky. Klokke-fasettene for brennevin er heller ikke probet —
  `polet_facets.clock_dims_for_category("brennevin")` kaster fortsatt `ValueError`, og det er
  riktig oppførsel: vi vet ikke hvilke koder som filtrerer der, og en ugyldig fasettkode feiler
  STILLE ved å returnere hele kategorien (bekreftet på nytt 2026-09-01 med kontrollkoden
  `Xyzzy`, som ga 4 400 — hele brennevin-totalen).

**Sveipen traff en timeskvote** (HTTP 429, `Retry-After: 3399` per ADR-024) på de to siste sidene
og måtte fullføres i to omganger. Det er dokumentert i `tools/refresh_polet.py` punkt 3b, og er
verdt å vite før noen sveiper en ny kategori.

## Anker 3: Brooms flavour camps — som språk, ikke som taksonomi

Dave Brooms fem leirer er nyttige *å snakke med*, ikke å klassifisere med:

**Fragrant & Floral · Malty & Dry · Fruity & Spicy · Rich & Round · Smoky & Peaty**
(pluss fire amerikanske: Soft Corn · Sweet Wheat · Rich & Oaky · Spicy Rye)

De er én forfatters kart, ikke en standard. Bruk dem til å beskrive og til å foreslå naboer, og si
tydelig at det er et kart — ikke presenter dem som en bransjeinndeling slik BJCP-stiler er det.

## De fire variablene som faktisk forklarer smaken

Når du forklarer hvorfor to whiskyer smaker ulikt, gå til disse før du går til region:

1. **Korn.** Maltet bygg (rikest, mest ester og malt), mais (søtt, mykt, fyldig), rug (tørt,
   pepret, dill), hvete (mildt, brødaktig).
2. **Destillasjonsform.** Pot still i batch beholder tyngre kongenerer → mer karakter. Kolonne
   kontinuerlig gir renere, lettere sprit. Skotsk single malt er pot still per definisjon;
   grain whisky er kolonne.
3. **Fat.** Den største enkeltvariabelen. Ex-bourbon (vanilje, kokos, lys karamell), ex-sherry —
   oloroso eller PX (tørket frukt, nøtter, sjokolade), nye kullsvidde fat (bourbonens
   vanilje/kokos-signatur), etterlagring i vin-, port- eller rom-fat. Fatets *størrelse* og
   *hvor mange ganger det er brukt* betyr like mye som hva som lå i det.
4. **Torv.** Fenoler måles i ppm på maltet, ikke i flasken — tallet på etiketten er derfor et
   tak, ikke en smaksstyrke. Islay-signaturen er torv + kystnær lagring; Höglandene og Speyside
   er stort sett utorvet, med unntak som bekrefter regelen.

## Servering

- **Glass:** tulipanformet (Glencairn, copita) samler aromaen. Tumbler er for is og drinker, ikke
  for å vurdere.
- **Vann:** noen dråper senker ABV og *frigjør* aroma ved å bryte opp esterlag — særlig på
  fatstyrke (> 50 %). Ikke en innrømmelse, en teknikk.
- **Temperatur:** romtemperatur. Is demper aroma kraftig; på en whisky over ~1 000 kr er det
  som regel bortkastet.
- **Fatstyrke:** smak alltid først uten vann, så juster. Rekkefølgen går ikke å reversere.

## Parring — og når du skal la være

Whisky er en **digestif og et solo-glass**, ikke en middagsledsager. Vurder whisky når brukeren
nevner det selv, eller ved dessert, ost, digestif og kveldsdram. Ikke ved «hva drikker jeg til
middagen» — der er vin og øl riktig svar, og whisky ville vært et påtvunget tredje alternativ.

| Situasjon | Retning |
|---|---|
| Blåmuggost, Roquefort | Sherryfat eller torv — salt møter fenol |
| Mørk sjokolade, kaffedessert | PX- eller oloroso-modnet, Rich & Round |
| Eplekake, karamellpudding | Ex-bourbon, Fruity & Spicy |
| Røkt laks, østers | Islay — den ene sjømatparringen som virker |
| Etter måltid, alene | Det han har lyst på. Dette er ikke en parringsøvelse |

## Meta-Critic — hva andre mener, ikke hva du vil mene

`data/whiskyanalysis/` bærer **1 812 whiskyer** fra whiskyanalysis.com: én score aggregert over
**median 9 anmeldere** (min 3, maks 34), med standardavvik. Slå opp via
`tools.whisky_match.resolve(varenr)`; `value_score` legger den på automatisk der den finnes.

**Dekning:** 201 av Polets 1 132 whiskyer er auto-joint (tier A), 37 til på sterk match (tier B).
193 er svake kandidater som venter på at du bekrefter dem —
`python3 -m tools.whisky_match --pending`. 701 har ingen match, og det er stort sett norske
hyllevare-blends og uavhengige fattappinger som ingen kritiker har vurdert.

**Tre forbehold, alle målt:**

- **Samme prisbias som Aperitif.** Spearman(score, prisbånd) = **+0,64** mot Aperitifs +0,66.
  «Høyest Meta-Critic» er i praksis nær «dyrest». Ingen rangering uten prissone-lås.
- **Ikke en uavhengig kilde.** På dine sju flasker korrelerer Meta-Critic **+0,90 med Aperitif**,
  mens begge går motsatt vei av deg (−0,26 og −0,95). To kritikerkilder som er enige med hverandre
  og uenige med deg er ikke to bekreftelser — det er én observasjon, to ganger.
- **Sist oppdatert januar 2023.** Standarduttrykk er dekket; alt lansert etter det finnes ikke.

**Derfor styrer den ikke `value_verdict`** ([ADR-034](../docs/ARCHITECTURE.md#adr-034-whiskybase-er-utilgjengelig--meta-critic-er-kilden-og-den-vektes-ikke)).
Det den faktisk tilfører er **uenighet**: `anmelder_uenighet` når spredningen mellom anmelderne er
i øverste desil, og `kilde_uenighet` når Meta-Critic og Aperitif plasserer flaska minst 30
persentilpoeng fra hverandre. Talisker 10 er et eksempel — 73. percentil hos Meta-Critic, 42. hos
Aperitif. Si at kildene er uenige; ikke velg en vinner på hans vegne.

**Whiskybase ble vurdert og forkastet:** Cloudflare-sperret, scraping i strid med vilkårene, og
API-et er en kommersiell partneravtale. Ikke foreslå den på nytt — se ADR-034.

## Kilder og hva som IKKE står her

Verifisert mot primærkilde: SWR 2009, 27 CFR § 5.143 + TTB final rule 18.12.2024, EU 2019/787,
irsk Technical File (2014), JSLMA-reglene, Vinmonopolets klokke-artikkel.

**Bevisst utelatt, fordi det ikke er verifisert:**

- **WSETs Systematic Approach to Tasting for Spirits.** Dokumentet finnes (mai 2022, issue 2),
  men begge PDF-URL-ene ga 403. Å skrive feltinnholdet fra hukommelsen ville gjentatt
  `bjcp_2021.pdf`-referansen i `cicerone.md`, som viste seg å være en hallusinert filsti.
- **Den irske pot still-endringen** (foreslått 2021/2022) — ikke bekreftet vedtatt.
- **Klyngeantallet hos whiskyanalysis.com** — kilden motsier seg selv (9 eller 10).

## Norsk og nordisk sortiment

> Bygget på `data/aperitif/scores.ndjson`, sveipet 31. august 2026 (557 sider, 15 672 rader).
> Ikke på hukommelse om hva Polet fører. **316 whiskyer har Aperitif-poeng**; det er Aperitifs
> dekning, ikke Polets sortiment — Polet fører flere enn Aperitif har vurdert.

Fordelingen av de 316: Skottland 210, USA 36, Irland 18, Japan 16, **Norge 8**, Frankrike 5,
Canada 4, Finland 3, Danmark 3, Sverige 2.

**Hovedfunnet er priset, ikke poengene.** Median Aperitif-score er den samme for nordisk og
skotsk whisky — 89 begge veier — men medianprisen er ikke:

| Opphav | n | Median score | Spenn | Median pris |
|---|---:|---:|---|---:|
| Skottland | 210 | 89 | 76–97 | 1 201 kr |
| Nordisk | 16 | 89 | 83–95 | 833 kr |
| Norge | 8 | 89 | 85–90 | 870 kr |

Samme poengsum, drøye 350 kroner billigere på medianen. Det er den eneste påstanden dette
avsnittet bærer alene.

**Forbeholdet må leses først.** Spearman(poeng, pris) er **+0,66** over alle 316 — «høyest score»
er i praksis nær «dyrest», så poengene kan ikke brukes til rangering uten en prissone-lås.
Innenfor det nordiske utvalget er sammenhengen langt svakere, **+0,38**, altså er poengene mer
informative der enn i sortimentet som helhet. Det er en observasjon på 16 flasker, ikke en lov.

De norske, sortert på poeng: Myken Hellstrøm à la Hellstrøm (90, 839,90), Feddie Single Malt
(90, 759,90), Myken Sea Mist Arctic Island (90, 899,90), Myken Autumn Gale (89, 899,90), Myken
Ocean Heart (89, 999,90), Gjoleid Mesterens Triple Cask (87, 924,90), Bivrost Yggdrasil (87,
809,90), Haavaldsen Stiger Series 2020 (85, 799,90). Fem av åtte er Myken.

Toppen av det nordiske er dansk og svensk, ikke norsk: DJ Nordic Series Mosgaard Peat & Port
(Danmark, 95) og DJ Nordic Series Smögen 10yo (Sverige, 92).

**Hva dette IKKE sier.** Nesten ingenting om hva Kristoffer vil like — whisky står på n=7, og
Aperitif-poeng er andres dom. Seksjonen svarer på «hva finnes og hva koster det», ikke på
«hva passer meg». Se `## Status: n=7` øverst.
