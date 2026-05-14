# Cicerone-kjerne – sommelier for øl

> Lean kjerne. Lastes ved hver øl-forespørsel sammen med `smaksprofil.md` (felles for vin og øl). BJCP-rammeverket (skalaer, hop/malt/gjær-taksonomi, glass) er flettet inn i § "Øl-rammeverk (BJCP)" lenger ned. Dyp regional/stil-kunnskap ligger i `deep-knowledge/ol-*.md`.

## Forhold til vin-systemet

Brukeren er én person, én smaksprofil. Mange parringer går på tvers. Når du foreslår drikke til mat, vurder *både* vin og øl der det er naturlig — ikke split kunstig.

**Sentral forskjell:** vin er sjelden ferskvare (modnes ofte), de fleste øl er ferskvare (degraderer raskt). Det styrer både anbefaling, kjøpsråd og lagring.

## Tre akser å lese øl langs

1. **Maltprofil** – sukker-kilde, farge, kropp, "brød/karamell/kakao/røkt"-aksen
2. **Hop-profil** – bitterhet (IBU) + aroma (citrus, tropisk, gress, harpiks, jord)
3. **Gjær + vann** – ren (lager) vs. ester-rik (engelsk/belgisk ale) vs. fenol-rik (Weissbier, Saison) vs. vill (Brett, Lacto, Pedio)

En IPA er bare "hop-dominert"; en Imperial Stout er "malt-dominert + fat-/gjær-modulert"; en Saison er "gjær-drevet med subtil malt og fersk hop". Forstå alltid en stil i form av disse tre vektorene før parring.

## Stilfamilier (kort oversikt)

Mer detalj (BJCP, skalaer) i § "Øl-rammeverk" lenger ned. Deep-dive per familie i `deep-knowledge/`:

| Familie | Karakter | Klassiske representanter | Deep-knowledge-fil |
|---|---|---|---|
| **Lette lagrøl** | Ren gjæring, lav-medium ABV, brød-/kornpreg | Pilsner (DE/CZ), Helles, Kölsch, Märzen | `ol-tysk-tjekkisk.md` |
| **Pale Ales & IPA** | Hop-dominert, frisk frukt/gress/citrus | American Pale, West Coast IPA, NEIPA, Session IPA, DDH, DIPA | `ol-hopdominert.md` |
| **Stouts & Porters** | Malt-dominert, mørk, ristet, sjokolade/kaffe | Dry Stout, Sweet Stout, Oatmeal, Imperial Stout, Baltic Porter | `ol-maltdominert.md` |
| **Brown Ales & Bocks** | Karamell-/nøtte-malt, balansert | English Brown, American Brown, Dunkel, Bock, Doppelbock | `ol-maltdominert.md` |
| **Belgisk** | Ester-rik gjær, fenoler, ofte krydret/frukt | Saison, Witbier, Tripel, Dubbel, Quad, Belgian Strong | `ol-belgisk.md` |
| **Weissbier & hvete** | Hvete, klar bananfrukt/nellik (DE) eller koriander/sitron (BE) | Hefeweizen, Dunkelweizen, Witbier, Berliner Weisse | `ol-tysk-tjekkisk.md` + `ol-sur-vill.md` |
| **Sur og vill** | Brett, Lacto, Pedio – funk, syre, kompleks utvikling | Lambic, Gueuze, Flanders Red, Berliner Weisse, Gose, Wild Ale | `ol-sur-vill.md` |
| **Sterkt malt-rikt** | Høy ABV, dyp karamell/tørket frukt | Barleywine, Old Ale, Scotch Ale, Eisbock | `ol-maltdominert.md` |
| **Fat-modnet** | Bourbon, rødvin, port, sherry, rom — videre kompleksitet | BA Imperial Stout, BA Barleywine, BA Quad | `ol-maltdominert.md` |

## Friskhet og lagring – motsatt vin

| Stil | Drikkevindu | Hvorfor |
|---|---|---|
| NEIPA / DDH IPA | **1–6 uker etter produksjon** | Tioler og polyfunksjonelle thioler oksideres raskt; oksidert NEIPA smaker karamell og papp |
| West Coast IPA / Pale Ale | 1–3 mnd | Hop-aromer mindre flyktige men fortsatt forgjengelige |
| Pilsner / Helles / lager | 1–4 mnd | Subtile malt-aromer dør raskt; lyssensitiv (skunked på 30 sek) |
| Hefeweizen / Witbier | 1–3 mnd | Bananfrukt og koriander tåler lite tid |
| Saison | 3–12 mnd kjølig, lengre med Brett | Tørre saisoner med Brett kan utvikle seg i år |
| Stout (vanlig) | 3–9 mnd | Holder seg lengre enn lyse stiler |
| Imperial Stout | **1–5+ år ved 8–12 °C** | Polymeriserer som rødvin; karamell, tørket frukt utvikles |
| Barleywine | **2–10 år** | Malt-dominert, lite hop å miste, sukker og alkohol konserverer |
| Gueuze, Lambic | **5–20+ år** | Brett-fermentering har egen utviklingskurve, syre + tannin stabiliserer |
| BA Imperial Stout / BA Barleywine | 1–7 år | Bourbon-toner blir mer integrert med tid |
| Christmas / juleøl | Innen ett år, men noen tåler 2–3 år | Krydret malt, modere ABV |

**Praktisk konsekvens:** spør om produksjons-/holdbarhetsdato ved hop-tunge stiler. Ved Polet og craft-baren — ferskest mulig. For Imperial Stout og Lambic — eldre kan være bedre, ikke verre.

## Servering – temperatur og glass

Detaljer i `deep-knowledge/ol-servering.md` (kommer) og fyldig stil-tabell i § "Øl-rammeverk" lenger ned. Tommelfingerregler:

- **Lyse, hop-dominerte stiler**: 5–8 °C — ikke iskaldt, men kjølig
- **Belgisk og mørkere ale**: 8–12 °C — varmt nok til at ester og fenoler åpner seg
- **Imperial Stout, Barleywine, BA**: 10–14 °C — som lettere rødvin
- **Lambic, Gueuze**: 8–10 °C
- **Tulipanglass** for det meste (NEIPA, Belgian, IPA) — konsentrerer aroma
- **Snifter** for sterkere mørke (Imperial Stout, Barleywine, BA)
- **Stange / Pilsner-glass** for lager
- **Weizen-glass** for Hefeweizen (form støtter skum + bananfrukt)

## Parring-prinsipper

De fleste vin-prinsipper gjelder, men med to viktige tillegg:

### 1. Karbonatisering kutter fett mekanisk
CO₂-bobler skrubber munnen — øl er ofte bedre enn vin til feit/friert mat. Pilsner + fish & chips, Saison + chèvre, Hefeweizen + Wienerschnitzel.

### 2. Bitterhet (IBU) er parallell med tannin, men virker på andre reseptorer
Hop-bitterhet binder seg ikke til spyttproteiner som tannin. Den interagerer med:
- **Fett**: hop kutter fett som bobler, men aroma forsterker også grillrester (citrus/harpiks mot grill).
- **Søtt**: bitterhet kontrasterer søtt — IPA + karri (men pass på chili-alkohol-interaksjon, gjelder også her).
- **Salt**: salt demper bitterhet svakt — saltede snacks med IPA fungerer.
- **Umami**: bitter forsterker umami-percepsjonen — IPA + soya/parmesan = robust kombo.

### 3. Maillard speiler Maillard
Ristet malt (stout/porter) speiler grillet/stekt mat. BBQ + Porter; grillet rødt kjøtt + Brown Ale; sjokoladedessert + Imperial Stout (mørk rost matcher kakao).

### 4. Gjær-karakter trenger speil eller kontrast
- **Belgisk ester-frukt (banan, eple)**: speil med stekt frukt (anddebryst med kirsebær), eller kontrast med saltet (Tripel + sprøstekt and).
- **Fenoler (kryddernellik, røyk)**: Hefeweizen + Wienerschnitzel speiler den brune smørstekte tonen; Rauchbier + grillet pølse er klassiker.

### 5. Brett-funk og syre er som tertiær vin
Lambic / Gueuze: aldrede, sopp-/jord-/halm-/eddik-noter. Parres med modnet ost, charcuterie, eldre vilt. Gose / Berliner Weisse: salt-syre fungerer som Manzanilla — sjømat, ceviche, østers.

### 6. Sesong er sentralt
Brukeren har sagt at øl er sesongbasert for ham. Tenk:

| Sesong | Stiler i fokus |
|---|---|
| Vinter | Imperial Stout, Barleywine, BA-stiler, juleøl, Doppelbock, Belgian Quad |
| Tidlig vår | Bock, Märzen-rester, lyse Pale Ales |
| Sommer | Pilsner, Helles, NEIPA, Wit, Saison, Gose, Berliner Weisse, Radler |
| Sensommer | Fresh-hop / wet-hop IPA (norsk høst-slipp), farmhouse ales |
| Høst | Märzen / Oktoberfest, Brown Ale, Porter, English Mild, Pumpkin (mer US-fenomen) |

## Workflow per anbefaling

Mirror av vin-workflow med øl-spesifikke avvik:

0. **Les kjernen** — denne fila (inkluderer BJCP-rammeverket) + `smaksprofil.md` (felles).
1. **Sjekk Untappd-historikk** — `data/untappd/checkins.csv`. Hva har han sjekket inn? Sortert på rating og dato (vekt nyere tyngre, men husk: han prøver mye nytt så lav rating på én ny stil ≠ permanent no-go).
2. **Stil-familie først** — identifiser hvilken familie forespørselen lander i, slå opp riktig `deep-knowledge/ol-*.md`.
3. **Sesong-sjekk** — er stilen i sesong? Hvis nei, foreslå alternativ eller forklar bevisst valg.
4. **Friskhet** — for hop-tunge stiler: ferskhet > alt annet. Foreslå fersk drop fra brukeren ikke har prøvd, eller hold seg til kjente fyldige malt-stiler.
5. **Kjøpskanal — betinget**:
   - Polet for sterkøl >4,7 % og spesialslipp → bruk `vinmonopolet.py` (samme tool, kategori "Øl")
   - Dagligvare (Meny, Joker) for lavere ABV — vi har ikke API; navngi konkret produkt + sannsynlig butikk
   - Tap room / bar — bare hvis det er konteksten
6. **Gi alternativer** — to-tre øl i ulike sesong/intensitets-spenn, rangert.
7. **Merk nytt vs. kjent**:
   - `[PRØVD]` – finnes i Untappd-historikken (oppgi rating + dato)
   - `[LIKNENDE]` – samme bryggeri/stil
   - `[NYTT]` – ukjent terreng for ham
8. **Forklar grundig** — stil-familie, hop/malt-profil, ABV/IBU, sesongkontekst, hvorfor det passer akkurat denne situasjonen.

## Ærlighet og anti-hallusinering

- Bryggerier åpner og legger ned. Sjekk konkrete viner mot WebSearch hvis usikker på status.
- Untappd-rating fra brukeren er signal, men "alt"-utforskeren har mer støy enn en kjenner-profil. Vekt nyere tungere, og se etter gjentakelse, ikke enkelt-ratings.
- Ikke foreslå et spesifikt slipp (juleøl 2024, fresh-hop 2025) hvis du ikke kan verifisere at det er i salg nå.
- Friskhet-data på Polet er begrenset — Polet oppgir ikke produksjonsdato i søke-API. Anta at sterkøl er friskere enn 6 mnd, men flag det som anslag.

## Cross-referansering med vin-systemet

- Smaksprofil er **felles**. Brukeren har én smak — øl-preferanser oppdateres i `smaksprofil.md` under sin egen seksjon.
- Servering-kjemi og parring-kjemi er **felles fag** — `deep-knowledge/servering-og-lagring.md` har tilberedningsmetode-tabellen som gjelder også for øl.
- WSET-vokabular (`wset_l2_sat.md`) overlapper delvis (frukt, krydder, eik, mineral) — men hop-aroma og malt-karakter krever ekstra ord (harpiks, citrus rind, gress, biscuit, ristet, mørk sjokolade, "barnyard funk").

## Øl-rammeverk (BJCP, skalaer, taksonomi, glass)

> Nøytral fag-referanse: ABV, IBU, SRM, BJCP-stilkategorier, glassvalg, serveringstemperatur, hop-/malt-/gjær-taksonomi.

### De fire kvantitative aksene

**ABV (Alcohol By Volume).** Volumprosent etanol. Direkte sammenlignbart med vin.

| Spenn | Karakter | Eksempler |
|---|---|---|
| 0,0–0,5 % | Alkoholfri | NA Pale Ale, NA Stout |
| 0,5–3,5 % | Session / lav | Berliner Weisse, Mild, Radler, Gose |
| 3,5–5,5 % | Standard | Pilsner, Helles, Pale Ale, Stout |
| 5,5–8,0 % | Sterkøl | IPA, Tripel, Imperial Pilsner, Doppelbock |
| 8,0–11 % | Imperial / Strong | DIPA, Imperial Stout, Belgian Strong, Barleywine |
| 11–15+ % | Extreme / BA | BA Imperial Stout, Eisbock, Quadrupel, Barleywine |

**Norsk implikasjon:** Skjeringspunktet 4,7 % bestemmer salgskanal. Over 4,7 % → Polet og sterkøl-utvalg. Under 4,7 % → dagligvare. Mange craft-stiler ligger akkurat over (5,0–6,5 %), så Polet er hovedkanalen for craft.

**IBU (International Bitterness Units).** Måler iso-α-syrer fra hop. Logaritmisk i opplevelse — forskjellen 20→40 IBU er hørbar, 80→100 mindre.

| Spenn | Opplevelse | Stilfølge |
|---|---|---|
| 5–15 | Nær umerkbar bitterhet | Hefeweizen, Witbier, Berliner Weisse, Sweet Stout |
| 15–25 | Subtil balanse | Helles, Kölsch, English Mild, Brown Ale |
| 25–40 | Tydelig men ikke dominerende | Pilsner, Pale Ale, Saison, Porter |
| 40–60 | Bittert, balansert mot malt | West Coast IPA klassisk, ESB, Dry Stout |
| 60–90 | Aggresivt bittert | DIPA klassisk, Imperial IPA |
| 90+ | Ekstremt bittert (mest teoretisk) | "Triple IPA", utgått trend |

**Viktig:** NEIPA og moderne DIPA bruker ofte sen-tilsetting / whirlpool / dry-hop som gir høy aroma men lav målt IBU. En NEIPA kan ha 35 IBU men oppfattes nesten ikke-bitter pga hop-aromakompleks som maskerer bitterhet. IBU alene er ikke nok — kombiner med stil-kontekst.

**SRM (Standard Reference Method) — farge.** Skala fra ~2 (halmgul) til ~40+ (svart). Approksimativ konvertering: SRM × 1,97 ≈ EBC.

| SRM | Beskrivelse | Stiler |
|---|---|---|
| 2–4 | Halm til lys gul | Pilsner, Helles, Witbier, Berliner Weisse |
| 4–7 | Gylden | Kölsch, Pale Ale, IPA klassisk |
| 7–14 | Rav til kobber | Märzen, ESB, Brown Ale, Saison |
| 14–22 | Mørk kobber til brun | English Brown, Dunkel, Bock, Doppelbock |
| 22–35 | Mørk brun til svart-brun | Porter, Stout, Schwarzbier |
| 35+ | Helt ugjennomtrengelig svart | Imperial Stout, BA Stout |

Farge predikerer ikke direkte smak (Schwarzbier er svart men lett, Imperial Stout er svart og fyldig), men korrelerer med maltprofil.

**Stamvørter og restsukker (OG/FG).** OG (Original Gravity) er sukkerinnholdet før gjæring, FG etterpå. Forskjellen → ABV. FG forteller om ølet er tørt eller sukker-restende:

- FG 1,000–1,010 = svært tørr (Saison, vill-fermentert øl)
- FG 1,010–1,018 = standard
- FG 1,018–1,030 = søtt / fyldig (Imperial Stout, Doppelbock, Sweet Stout)
- FG 1,030+ = veldig restsukker (BA Imperial Stout, Eisbock)

De fleste etiketter oppgir bare ABV og IBU. OG/FG finnes ofte på bryggeriens nettside eller Untappd-detaljer.

### BJCP 2021 stil-taksonomi (forenklet til 9 praktiske familier)

Den offisielle 2021-guiden har 34 hovedkategorier:

1. **Standard amerikansk lager (Cat 1)** — American Light Lager, American Lager, Cream Ale, American Wheat Beer. Sjelden i craft-spennet, mest industrielt.
2. **Internasjonal lager (Cat 2)** — International Pale/Amber/Dark Lager. Sommer-grillmat, lett.
3. **Tysk lager (Cat 3, 4, 5, 7, 8, 9)** — Munich Helles, Festbier, Pilsner (DE+CZ), Märzen, Dunkel, Schwarzbier, Bock, Doppelbock, Eisbock. Klassikere, sesong (Märzen høst, Bock vår, Doppelbock vinter).
4. **Tysk hvete (Cat 10)** — Weissbier (Hefeweizen), Dunkelweizen, Weizenbock. Sommer, frokost-klassikere, schnitzel.
5. **Britisk og irsk ale (Cat 11, 13, 14, 15, 16, 17)** — Ordinary/Best Bitter, ESB, English Mild, English Brown, Porter, Irish Stout, Sweet/Oatmeal/Foreign Extra/Imperial Stout, Old Ale, Barleywine. Vinter-pub-stemning, parring til stekt rødt kjøtt og pub-mat.
6. **Belgisk og fransk (Cat 23, 24, 25, 26)** — Witbier, Belgian Pale, Bière de Garde, Saison, Belgian Tripel/Dubbel/Strong Dark/Golden Strong, Quadrupel. Finstemt parring, mat-vin-erstatter.
7. **Sur og vill (Cat 23B–F, 27, 28)** — Berliner Weisse, Gose, Lambic, Gueuze, Fruit Lambic, Flanders Red, Flanders Brown / Oud Bruin, Wild Ale, American Brett. Apéritif, sjømat, modne oster.
8. **Amerikanske ales og IPA (Cat 12, 18, 19, 20, 21, 22, B-categories)** — Blonde Ale, American Pale Ale, American Amber/Brown/Porter/Stout, IPA (West Coast, English, Black, Brown, Red, Rye, White, Brut, NEIPA, Session, DIPA), Imperial IPA. Craft-hjertet.
9. **Fruktede, krydrede, røkte, eksperimentelle (Cat 29–34)** — Fruit Beer, Spice/Herb/Vegetable Beer, Smoked Beer (Rauchbier), Wood-Aged Beer, Specialty Beer.

Se BJCP 2021 PDF i `data/reference/bjcp_2021.pdf` (bjcp.org/bjcp-style-guidelines).

### Hop-taksonomi (aromakategorier)

- **Klassiske noble (Europa):** Saaz (CZ, Pilsner), Hallertau Mittelfrüh (DE, Helles/Märzen), Tettnang, Spalt (DE), Styrian Goldings (SI, Saison). Karakter: gress, urter, lett krydret, svært subtil.
- **Britiske:** East Kent Goldings, Fuggles, Challenger, Target, Bramling Cross. Karakter: jord, te, ribsblader, mild krydret.
- **Amerikanske C-hops (Pacific Northwest):** Cascade, Centennial, Citra, Chinook, Columbus, Crystal, Comet. Karakter: grapefruit, pinje, lett tropisk.
- **Moderne tropiske:** Mosaic, Galaxy (AU), Nelson Sauvin (NZ), Motueka, Riwaka, Sabro, Idaho 7, Strata, Azacca. Karakter: passion frukt, mango, ananas, white wine grape, kokos (Sabro).
- **Spesielle:** Simcoe (pinje + katt-pee, polariserende), Amarillo (appelsin), El Dorado (steinfrukt), Cryo / Lupulin Powder (konsentrerte oljer).

Når bryggeriene lister hops på etiketten — sjekk om de er biotransformerte (NEIPA-teknikk: hops + aktiv gjær = nye smaker som ikke finnes i hops alene). Biotransformasjon gir karakteristiske hvitt-vin/tropisk-eksotisk-aromer som er signatur for NEIPA.

### Malt-taksonomi (lys → mørk)

| Malt | Bidrag | Stiler |
|---|---|---|
| Pilsner / Pale | Base, lett brød | Alle |
| Munich | Brød, lett karamell | Helles, Märzen, Bock |
| Wien | Honning, brød | Märzen, amber |
| Karamell / Crystal | Karamell, sødme | Brown, ESB, Bock, Imperial Stout |
| Spesial-B | Rosin, tørket frukt | Belgian Dubbel, Quadrupel |
| Sjokolade-malt | Sjokolade, kakao | Porter, Stout |
| Roasted Barley | Brent kaffe, bitter | Irish Stout, Foreign Extra |
| Black Patent | Aske, ekstrem mørk | Schwarzbier, Black IPA |
| Røkt malt | Røyk (bøk eller torv) | Rauchbier, Smoked Porter |

### Gjær-familier

| Familie | Stiler | Karakter |
|---|---|---|
| **Saccharomyces cerevisiae** (alegjær) | Ale, IPA, Stout, Saison | Variabel — fra rene (US-05) til ester-frukt (English ale) til kryddernellik/banan (Hefeweizen) |
| **S. pastorianus** (lagergjær) | Pilsner, Helles, Bock | Rene, lite ester, kjølig gjæring 8–13 °C |
| **Brettanomyces bruxellensis / claussenii** | Lambic, Wild Ale, Saison med Brett | "Funk" — gård, hest, lær, ananas, tropisk |
| **Lactobacillus** | Berliner Weisse, Gose, Sour Stout | Melkesyre — sitron, yoghurt, friskhet |
| **Pediococcus** | Lambic blend, Flanders Red | Brettende-funk og melkesyre — også diacetyl (smør) i tidlig fase |

### Glassvalg

| Glasstype | Stiler | Hvorfor |
|---|---|---|
| **Tulipan** | NEIPA, IPA, Belgian, Saison, Stout standard | Konsentrerer aroma, holder skum, allroundsvinner |
| **Snifter / Tasting glass** | Imperial Stout, Barleywine, BA-stiler, Quad | Liten åpning, intensiv aroma, varmer mellom hender |
| **Pilsner / Pokal** | Pilsner, Helles, Kölsch (Stange-variant) | Høyt, smalt, viser farge og bobler, holder kjølig |
| **Weizen-glass** | Hefeweizen, Dunkelweizen | Bred topp for skumvolum, smal bunn for stigning |
| **Pint / Nonic** | English ales, Stout, brown | Praktisk, klassisk pub-format |
| **Goblet / Chalice** | Trappist (Chimay, Westvleteren, La Trappe) | Bredere åpning slipper aroma og bobler |
| **Stemless / standard øl-glass** | Lager, lette IPA i avslappet kontekst | OK for hverdag, ikke optimalt |

**Praktisk minimum hjemme:** 4–6 tulipaner (universal craft), 2–4 snifters (for sterke mørke), eventuelt 2 Weizen og 2 Pilsner-glass. Som med vin: form > merkenavn.

### Serveringstemperatur per stil (utvidet)

Bruker tommelfingerreglene i § "Servering – temperatur og glass" øverst som lommekort; her er stil-for-stil:

| Stil | Temp | Notat |
|---|---|---|
| Pilsner / Helles / lyse lager | 4–6 °C | Klassisk "kald øl" — ikke iskaldt eller du mister malt-aroma |
| Hefeweizen / Witbier | 5–7 °C | Aromakompleks åpner ved 7 °C |
| Pale Ale / IPA klassisk | 6–8 °C | Som hvitvin |
| NEIPA / DDH | 7–9 °C | For kald = aroma låses, men ikke over 10 °C |
| Saison / Belgian Pale | 8–10 °C | Som hvit Burgund |
| Stout / Porter standard | 8–12 °C | Som rosé |
| Brown Ale / Bock | 10–12 °C | Som lett rødvin |
| Imperial Stout / Barleywine | 10–14 °C | Som fyldig rødvin |
| BA-stiler | 12–16 °C | Som modent rødvin — alkohol bærer aroma |
| Lambic / Gueuze | 8–10 °C | Som tørr Riesling Spätlese |

### Servering-praktisk

- **Helling:** tilt glasset 45°, hell sakte til glasset er halvfullt, rett opp og fortsett — gir 2–3 cm skum (perfekt for å frigjøre aroma).
- **Ikke fris-glasset** — kalde glass mister hop-aroma og kan brekke ved temperatursjokk fra varmt øl.
- **Skum er aroma-leverandør** — ikke unngå det. Skum slipper flyktige forbindelser kontinuerlig.
- **Mørke flasker > klare.** Lys (særlig UV) skuner øl i sekunder gjennom klart eller grønt glass via 3-MBT-reaksjon. Boks er beste UV-vern.
- **Boks vs flaske:** Boks vinner på UV og oksygenoverføring (lavere). Smaksmessig ingen forskjell hvis presset på flaske er likt.

### Kilder

- BJCP 2021 Style Guidelines (bjcp.org/bjcp-style-guidelines)
- Garrett Oliver, *The Oxford Companion to Beer* (2011)
- Randy Mosher, *Tasting Beer* (2nd ed, 2017)
- John Palmer, *How to Brew* (4th ed)
- Brewers Association style guidelines (parallell til BJCP)

---

## Filer du har tilgang til (øl-spesifikt)

| Fil | Innhold | Når lese |
|---|---|---|
| `knowledge/cicerone.md` (denne) | Kjerne for øl + BJCP-rammeverk (skalaer, hop/malt/gjær, glass) | Hver øl-forespørsel |
| `knowledge/smaksprofil.md` | Felles smaksprofil – også med øl-seksjon | Hver anbefaling |
| `deep-knowledge/ol-*.md` | Stilfamilie-deep-dives | On-demand per forespørsel |
| `data/untappd/checkins.csv` | Brukerens 90 check-ins fra Untappd | Hver anbefaling |
| `tools/untappd_stats.py` | Auto-derivér statistikk (kommer parallelt med profile_stats.py) | Etter ny eksport |
