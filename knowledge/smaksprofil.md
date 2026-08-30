# Min smaksprofil

> **LEVENDE DOKUMENT.** Dette er den autoritative kilden til hva Kristoffer liker, ikke liker, og hva som er bevist vs hypotese.
>
> **Sist oppdatert:** 2026-08-30
> **Datagrunnlag:** Vivino-eksport (182 rader, 117 med rating; 12 års historikk). Auto-derivert blokk er generert 2026-07-02 — kjør `tools/profile_stats.py` etter neste Vivino-sync.
>
> ## Oppdaterings-trigger (Claude må følge disse)
>
> Filen skal oppdateres umiddelbart når:
> 1. **Brukeren bekrefter ny preferanse** – legg til i "Druer du vet du liker" eller "Regioner du dras mot". Hvis blindspot bekreftet, oppdater "Blindspots".
> 2. **Brukeren rapporterer dårlig opplevelse** – spesifikk vin → "No-go-liste"; mønster → "Druer/regioner som har bommet".
> 3. **Klokke-profil hentet for en topp-rated vin** – legg til i tabellen under "Klokke-profil for topp-viner".
> 4. **Ny Vivino-eksport** – re-analyser mønstre, oppdater snitt og sterke trender. Vekt nyere ratings tyngre.
>
> ## Vekting-prinsipper
> - Nyere ratings (siste 2 år) vekter dobbelt så mye som eldre
> - Én rating er ikke et mønster – krever 2-3 datapunkter for å oppgradere til "bekreftet"
> - Bekreftede mønstre kan bli "antakelser" igjen hvis ny data motbeviser dem

<!-- BEGIN AUTO-DERIVED (profile_stats.py) -->
## Auto-derivert statistikk

> Generert 2026-08-30 av `tools/profile_stats.py`. Ikke rediger manuelt – kjør scriptet på nytt etter Vivino-eksport.
> Grunnlag: 122 ratede viner, snitt 3.82.
> Nyere ratings (2024-01-01+): 35 viner, snitt 3.99.
> Eldre ratings (før 2024): 86 viner, snitt 3.76.

### Per vintype

| Kategori | N | Snitt | Snitt 2024+ |
|---|---|---|---|
| Red Wine | 67 | 3.79 | 4.02 |
| Sparkling | 23 | 4.03 | 4.23 |
| White Wine | 20 | 3.88 | 3.82 |
| Rosé Wine | 10 | 3.30 | 3.75 |
| Dessert Wine | 1 | 4.50 | – |
| Fortified Wine | 1 | 4.50 | – |

### Per land (topp etter N)

| Kategori | N | Snitt | Snitt 2024+ |
|---|---|---|---|
| Italy | 41 | 3.84 | 3.84 |
| France | 35 | 3.60 | 4.04 |
| Spain | 12 | 3.83 | 3.97 |
| Germany | 8 | 3.88 | 3.92 |
| United States | 6 | 3.87 | 4.00 |
| Argentina | 5 | 3.66 | 4.15 |
| United Kingdom | 3 | 4.27 | 4.27 |
| South Africa | 3 | 4.20 | 4.30 |
| Portugal | 2 | 4.50 | – |
| Austria | 2 | 4.25 | 4.00 |

### Per regional stil (n ≥ 2)

| Kategori | N | Snitt | Snitt 2024+ |
|---|---|---|---|
| French Champagne | 10 | 3.91 | 4.40 |
| Italian Ripasso | 6 | 4.03 | 3.70 |
| Italian Barbera | 6 | 3.90 | 3.80 |
| Spanish Rioja Red | 6 | 3.90 | 3.95 |
| Northern Italy Red | 6 | 3.33 | – |
| German Riesling | 5 | 3.82 | 3.80 |
| Southern Italy Red | 4 | 4.05 | 4.07 |
| Northern Italy Rosé | 4 | 3.88 | 3.50 |
| French Crémant | 4 | 3.88 | – |
| Tuscan Red | 4 | 3.75 | – |
| Provence Rosé | 4 | 2.38 | – |
| English Sparkling | 3 | 4.27 | 4.27 |
| Italian Amarone | 3 | 4.13 | 4.20 |
| Burgundy Red | 3 | 3.27 | 3.80 |
| Southern Rhône Red | 3 | 3.00 | – |
| Jura White | 2 | 4.25 | 4.10 |
| Argentinian Malbec | 2 | 4.15 | 4.15 |
| German Spätburgunder | 2 | 4.05 | 4.05 |
| Californian Santa Barbara County Chardonnay White | 2 | 4.00 | 4.00 |
| Californian Zinfandel | 2 | 4.00 | – |

### Bekreftede mønstre (n ≥ 3, snitt ≥ 4.0)

- **Italian Ripasso** – n=6, snitt 4.03, nyere 3.70
- **Southern Italy Red** – n=4, snitt 4.05, nyere 4.07
- **English Sparkling** – n=3, snitt 4.27, nyere 4.27
- **Italian Amarone** – n=3, snitt 4.13, nyere 4.20

### Bekymringer (n ≥ 3, snitt < 3.3)

- **Provence Rosé** – n=4, snitt 2.38
- **Burgundy Red** – n=3, snitt 3.27
- **Southern Rhône Red** – n=3, snitt 3.00

### Blindspots (kategori-kombinasjoner med n ≤ 2)

- Italy White Wine (n=1)
- Austria White Wine (n=1)
- Lebanon Red Wine (n=1)
- France Dessert Wine (n=1)
- Portugal Red Wine (n=1)
- Uruguay Red Wine (n=1)
- Chile Red Wine (n=1)
- New Zealand White Wine (n=1)
- Austria Sparkling (n=1)
- Spain Sparkling (n=1)
- Portugal Fortified Wine (n=1)
- South Africa Rosé Wine (n=1)
- Greece Rosé Wine (n=1)
- Germany Red Wine (n=2)
- United States White Wine (n=2)

### Topp 5 ratede viner

- 4.7 – Bollinger Special Cuvée Brut Aÿ Champagne N.V.
- 4.6 – Giacomo Fenocchio Barbera d'Alba Superiore 2019
- 4.5 – Vincent Girardin Bourgogne Terroir Noble 2010
- 4.5 – Fratta Pasini Valpolicella Superiore Ripasso 2009
- 4.5 – Taylor's Chip Dry White Port

### Bunn 5 ratede viner

- 1.0 – Domaine de Sulauze Pomponette Coteaux d'Aix-en-Provence Rosé 2015
- 1.5 – Labouré-Roi Pinot Noir Bourgogne 2013
- 2.0 – Domaine de la Janasse Côtes du Rhône Rouge 2015
- 2.0 – Miraval Côtes de Provence Rosé 2014
- 2.5 – Francisco Gomez Eco Rojo 2014

<!-- END AUTO-DERIVED -->

<!-- BEGIN AUTO-DERIVED-BEER (untappd_stats.py) -->
## Auto-derivert øl-statistikk (Untappd)

> Generert 2026-08-30 av `tools/untappd_stats.py`. Ikke rediger manuelt – kjør på nytt etter ny Untappd-scrape.
> Grunnlag: 89 ratede check-ins, snitt 3.39.
> Mangfold: 65 unike bryggerier, 58 unike stiler, 20 stilfamilier.
> Stildiversitet: 65.2% av check-ins er nye stiler – svært utforskende.
> Nyere (2024+): 43 check-ins, snitt 3.36.
> Eldre (før 2024): 46 check-ins, snitt 3.42.

### Per stilfamilie

| Stilfamilie | N | Snitt | Snitt 2024+ |
|---|---|---|---|
| Belgian Strong / Trappist | 11 | 3.50 | 3.43 |
| Brown / Mild / Bitter | 11 | 3.36 | 3.75 |
| Stout (standard) | 9 | 3.61 | 3.75 |
| Annet / uklassifisert | 9 | 3.31 | 3.50 |
| Pilsner | 8 | 2.97 | 2.95 |
| Helles / Lager | 6 | 3.08 | 3.10 |
| Porter / Baltic Porter | 5 | 3.75 | 3.88 |
| Witbier / Belgian Pale | 5 | 3.35 | 3.17 |
| Lambic / Gueuze / Wild | 4 | 3.88 | 4.25 |
| NEIPA / Hazy IPA | 4 | 3.31 | 3.08 |
| Saison / Farmhouse | 4 | 3.00 | 3.50 |
| Bock / Doppelbock / Eisbock | 3 | 3.33 | 3.38 |
| Sur (Berliner / Gose / Sour) | 2 | 4.00 | 4.00 |
| IPA (standard) | 2 | 3.50 | 3.50 |
| Märzen / Festbier / Vienna | 1 | 4.00 | – |
| Barleywine / Old Ale / Wee Heavy | 1 | 3.75 | 3.75 |
| Kölsch / Altbier | 1 | 3.75 | – |
| Schwarzbier / Dunkel | 1 | 3.50 | – |
| Rauchbier / Smoked | 1 | 3.00 | 3.00 |
| Fruit / Spice / Specialty | 1 | 2.50 | 2.50 |

### Per ABV-spenn

| ABV | N | Snitt |
|---|---|---|
| 4–5,5 % (standard) | 32 | 3.20 |
| 5,5–7 % (sterkøl) | 21 | 3.46 |
| 7–9 % (DIPA/Tripel-range) | 19 | 3.37 |
| 9–11 % (Imperial/Quad) | 11 | 3.59 |
| 11+ % (BA / Extreme) | 6 | 3.88 |

### Bekreftede preferanser (n ≥ 2, snitt ≥ 3.8)

- **Lambic / Gueuze / Wild** – n=4, snitt 3.88, nyere 4.25
- **Sur (Berliner / Gose / Sour)** – n=2, snitt 4.00, nyere 4.00

### Bekymringer (n ≥ 2, snitt < 3.2)

- **Pilsner** – n=8, snitt 2.97
- **Helles / Lager** – n=6, snitt 3.08
- **Saison / Farmhouse** – n=4, snitt 3.00

### Blindspots (familier med n ≤ 1)

- Märzen / Festbier / Vienna
- Barleywine / Old Ale / Wee Heavy
- Kölsch / Altbier
- Schwarzbier / Dunkel
- Rauchbier / Smoked
- Fruit / Spice / Specialty

### Sesong-mønster (snitt rating per måned)

| Måned | N | Snitt |
|---|---|---|
| Jan | 10 | 3.73 |
| Feb | 4 | 3.62 |
| Mar | 6 | 3.42 |
| Apr | 4 | 3.88 |
| Mai | 1 | 2.00 |
| Jun | 4 | 3.50 |
| Jul | 17 | 3.32 |
| Aug | 2 | 3.62 |
| Sep | 8 | 3.25 |
| Okt | 11 | 3.52 |
| Nov | 7 | 3.36 |
| Des | 15 | 3.07 |

### Topp 8 ratede ølene

- 4.5 – Omer Vander Ghinste VanderGhinste Roodbruin (Sour - Flanders Oud Bruin) 5.5%
- 4.5 – Buxton Brewery THE BEER (Stout - Imperial / Double Pastry) 11.0%
- 4.2 – Samuel Smith Organic Chocolate Stout (Stout - Other) 5.0%
- 4.2 – BOXCAR Triple Dark Mild (Mild - Dark) 9.0%
- 4.2 – Brouwerij Het Anker Gouden Carolus Cuvée van de Keizer Imperial Dark (Belgian Strong Dark Ale) 11.0%
- 4.2 – Brouwerij Mort Subite Lambic Kriek (Lambic - Kriek) 4.0%
- 4.0 – Brouwerij der Trappisten van Westmalle Westmalle Trappist Tripel (Belgian Tripel) 9.5%
- 4.0 – LERVIG HOLIDAY HAZE (Pale Ale - New England / Hazy) 4.7%

### Bunn 8 ratede ølene

- 2.0 – Abbaye de Maredsous Maredsous Triple / Tripel (Belgian Tripel) 10.0%
- 2.0 – Coop Norge Pokal Lys Pilsner (Pilsner - Other) 4.5%
- 2.2 – Færder Mikrobryggeri Gull (Belgian Dubbel) 8.0%
- 2.2 – Fuller's Griffin Brewery London Pride (Bitter - Session / Ordinary) 4.1%
- 2.2 – Wettre Bryggeri AS Passion Silly Saison (Farmhouse Ale - Saison) 4.7%
- 2.5 – Færder Mikrobryggeri Myrra (Spiced / Herbed Beer) 6.5%
- 2.5 – Sabeco Bia Saigon Export Premium (Lager - Pale) 4.8%
- 2.8 – Frydenlund Bryggerier Juicy IPA (IPA - New England / Hazy) 4.6%

### Mest besøkte bryggerier (n ≥ 2)

| Bryggeri | N | Snitt | Snitt 2024+ |
|---|---|---|---|
| Nøgne Ø | 7 | 3.43 | 3.56 |
| Samuel Smith | 3 | 3.92 | – |
| Små Vesen | 3 | 3.42 | – |
| Fjordfolk Mikrobryggeri | 3 | 3.33 | – |
| Frydenlund Bryggerier | 3 | 2.92 | 2.75 |
| Færder Mikrobryggeri | 3 | 2.58 | 2.58 |
| BOXCAR | 2 | 4.00 | – |
| LERVIG | 2 | 3.88 | 3.75 |
| Omer Vander Ghinste | 2 | 3.88 | – |
| Brouwerij St. Bernardus | 2 | 3.75 | – |

<!-- END AUTO-DERIVED-BEER -->

## Datagrunnlag (kort)

- Aktivt Vivino-bruk siden ~2014, med ratings spredt over 12 år
- 122 ratede viner, snitt 3.82
- Tyngdepunkt: rødvin (67), musserende (23), hvitvin (20), rosé (10)
- **Smaken har modnet:** snitt før 2018 = 3.67, etter 2024 = 3.89 → enten har du blitt bedre på å velge, eller du har blitt mer raus med høyere ratings. Sannsynligvis litt av begge.

## Generelt

- **Erfaringsnivå:** Mellomnivå – over et tiår med jevn dokumentasjon, men ingen formell utdanning
- **Tilnærming til pris:** Value-fokusert. Ikke fast pristak – men forventer at en vin leverer for det den koster. Eksempel: 200 kr som overrasker positivt er bedre enn 600 kr som bare er "grei".

  Konsekvens for Claude:
  - Ikke spør om budsjett hver gang – foreslå value-vinner i ulike prisklasser
  - Når jeg ber om "en hverdagsvin" → 150–300 kr-spennet
  - Når jeg ber om "noe godt til middag" → 250–500 kr
  - Når jeg ber om "noe spesielt" → 500+, men forklar hvorfor det er verdt det
  - Flag dårlig value uavhengig av prisklasse

## Stilpreferanser

### Kontekst-avhengig syrepreferanse (bekreftet 2026-07-02)

**Kristoffer foretrekker mer syre til mat enn til solo-drikking om kvelden.** Egenobservasjon på Catena Paraje Altamira (frisk høyde-Malbec): god solo, men «enda bedre til mat».

- **Fagbakgrunn:** Høy syre virker best med mat – den kutter fett, matcher syre i retten og friskner opp ganen mellom biter; solo kan samme syre oppleves skarpere/mindre balansert. Klassisk enologi, men her *personlig bekreftet* som noe han faktisk merker og vektlegger.
- **Slik brukes det i anbefalinger:**
  - **Til mat / matparing:** push friskhet oppover – Friskhet 8+ er en styrke, ikke en risiko (Granítico 10, Barbera 9, høyde-viner). Jo rikere/fetere rett, jo mer syre tåler og ønsker han.
  - **Solo «noe til kvelden» uten mat:** len mot litt rundere, mer fruktdrevet profil – Friskhet 6–8, litt mer fylde/glyserol – framfor de mest sylskarpe. Ikke velg bort syre, men ikke maksimér den.
  - Spør ev. kort «til mat eller solo?» når en høy-syre-kandidat vurderes og konteksten er uklar.

### «Kraftigere» kan IKKE søkes på Fylde-klokka (funn 2026-08-29, n=1)

**Observasjon.** Kristoffer prøvde **Vespa Barbera 3 l** (varenr 5280806, 489,90 kr) på anbefaling og fant den **for lett** – ønsket mer kraft i smaken. Særlig relevant høst/vinter.

**Funnet som gjør dette interessant.** Vinen har *identisk* klokke-profil med hans høyest ratede rødvin:

| | kr/L | Fylde | Friskhet | Garvestoffer | Polets stil |
|---|---|---|---|---|---|
| Fenocchio Barbera d'Alba Superiore – **4.6** | **273** | 8 | 9 | 7 | Frisk og fruktig |
| Vespa Barbera 3 l – **«for lett»** | **163** | 8 | 9 | 7 | Frisk og fruktig |

Samme drue (Barbera 100 %), samme klokker, samme stilmerkelapp – motsatt dom. **Klokkene diskriminerer altså ikke mellom hans beste rødvin og en han avviste.** Å søke «Fylde 9+» for å finne noe kraftigere ville vært feil svar, og ville dessuten sortert bort Fenocchio.

**Hva som faktisk skiller dem:**
- **Pris per liter: 273 vs 163.** I den nedre enden korrelerer konsentrasjon med literpris – lavere avling, mer seleksjon.
- **Appellasjon:** *Barbera d'Alba Superiore* (strammere avlingskrav + lagringskrav) vs generisk *Piemonte Barbera*.
- **Fat og modning:** Fenocchio har 6 mnd fatlagring + 6 mnd flaskemodning. Vespa er ren ståltank, 6–7 dagers gjæring, ingen lagring. Det er her «kraften» ligger – tekstur og lagringspreg, ikke fylde-tall.

**Slik brukes det i anbefalinger:**
1. **Ikke bruk Fylde alene når han ber om «kraftigere».** Klokka måler noe annet enn det han opplever.
2. **Les `metode`- og `stil`-feltet i details** – fatlagring, appassimento, ripasso, lang gjæring er signalene.
3. **Bruk appellasjonsnivå som proxy:** Superiore/Riserva/DOCG over generisk regional DOC.
4. **Literpris er en reell indikator i lavprisenden**, særlig på 3 l der nesten alt ligger 145–200 kr/L.
5. **Ikke kjemp mot druen.** Barbera er konstitusjonelt syrerik og lett-til-middels i kropp – det er stilen. Vil han ha kropp, bytt drue/stil, ikke bare produsent: appassimento, ripasso, Primitivo, Nero d'Avola, Aglianico, Montepulciano. Det stemmer med profilen hans allerede (Ripasso 4.5, Amarone 4.2 × 2, «struktur og modenhet»).

**Forbehold:** n=1. Per vektingsprinsippene er dette en **hypotese**, ikke et bekreftet mønster – og det motsier ikke at han elsker Barbera (topp-rødvinen hans *er* en Barbera). Signalet gjelder format og kvalitetsnivå, ikke druen. Bekreftes eller avkreftes ved neste kartong.

### Rødvin (klart hovedkategorien – 67 viner, snitt 3.79)

**Sterke mønstre i dataene:**

- **Italia er hjemmebanen din** – 41 av 122 ratede viner er italienske, og topp-rødvinen er Barbera d'Alba (4.6).
- **Du elsker viner med struktur og modenhet:**
  - Ripasso/Amarone gjentas (4.5 Valpolicella Ripasso, 4.2 Amarone × 2 nylig)
    - **Ripasso er ikke gjenbekreftet** (funn 2026-08-30). Fem av de seks Ripasso-ratingene er fra 2014–2015, deretter elleve år uten én eneste. Den ene moderne dataen — Antiche Terre Venete Valpolicella Ripasso, **3.7** den 2026-07-21 — er den svakeste av de seks. Produsenten er ratet før, med **4.0** i 2014, men det er en *annen* årgang og en annen Vivino-oppføring (2012-årgangen, `/wines/2360530`, mot den årgangsløse `/wines/1532847`) — to viner ti år fra hverandre, ikke én vin vurdert ned. Spriket mellom dem er ikke et funn og trenger ingen forklaring. Mønsteret er ikke dødt — n=6, snitt 4.03, og Fratta Pasini 2009 står fortsatt på 4.5 — men det er gammelt, og det som taler mot å lese det som gjenbekreftet er elleve års opphold med den ferskeste dataen som svakest. Vekt det ned til det er testet på nytt.
    - Amarone i samme kulepunkt er derimot **gjenbekreftet**: n=3, snitt 4.13, hvorav to ratinger fra 2025 med snitt 4.20. De to stilene skal ikke leses som ett mønster lenger.
  - Barbera, Nebbiolo, Sangiovese-baserte stiler scorer høyt
- **Du trives med moderat til høy syre:** Barbera, Nebbiolo og Sangiovese-druer er alle syrlige – du har 4.0+ på flere
- **Burgund er ujevnt for deg:**
  - 4.5 Vincent Girardin Bourgogne 2010 – topp
  - 1.5 Labouré-Roi Bourgogne 2013 – din laveste rating av rødvin
  - 3.8 Vincent Girardin Bourgogne Pinot Noir 2023 – mer ordinært
  - **Antakelse:** Du trenger seriøs Burgund for å bli imponert. Generisk billig Bourgogne treffer ikke. Bedre å bruke 400+ på Burgund enn 200, eller hoppe over og velge annen Pinot.

**Antatte preferanser (basert på mønstre):**
- Fruktig vs. jordpreget: **midt på til jordpreget** (Ripasso/Amarone/Nebbiolo-spor)
- Lett vs. fyldig: **medium til fyldig** (Amarone-kjærlighet, ingen lette Beaujolais-favoritter)
- Tannin: **medium til mye** – tåler struktur
- Eik: **moderat til tydelig** – Amarone og Ripasso har det
- Syre: **medium til høy** – Barbera/Sangiovese-vinklingen
- Restsødme: **ikke avklart – test og lær.** Du har scoret høyt på både Amarone (litt glycerolrik fylde) og knusktørr Barbera. Antakelse: tørt er trygt, men du har ikke aversjon mot dybde og fylde.
- **Baden Spätburgunder fungerer:** Florian Philipp Reicholzheimer 2022 → 4.2 (2026-06-13, restaurant, til tørrmodnet ytrefilet). Fyller blindspot for tysk rødvin — mer kropp og mørk frukt enn typisk Burgund-Pinot. Verdt å utforske videre.

### Hvitvin (20 viner, snitt 3.88 – overraskende høyt)

**Sterke mønstre:**
- **Tysk Riesling er en favoritt** – 4.5 Fritz Haag Brauneberger GG, men også svakheter (2.7 Schloss Vollrads)
- **Off-dry/halvtørt fungerer faktisk:** 4.0 Stephan Ehlen Spätlese (off-dry), 4.1 Auslese (søt). Du tåler restsødme i tysk hvitvin når den er balansert av syre. Ikke avskriv off-dry-stilene.
- **Jura-Chardonnay treffer deg** – 4.4 og 4.1 på Rolet, to forskjellige årganger
- **Cloudy Bay 4.5** – men dette er en 2015-rating. Smaken har modnet siden da, så ikke vekt denne tungt.
- **Sør-Rhône hvit fungerer ikke** – 3.0 og 3.2 på Lirac Blanc fra Ségriés, to årganger på rad
- **Beaujolais Blanc (Chardonnay) kan funke:** Famille Morel Les Pierres Dorées 2024 → 4.1 (2026-06-13, restaurant). Biodynamisk kalkstein-Chardonnay. Overrasket positivt — lett og frisk, men med nok substans. Ikke avskriv lettere Chardonnay-stiler for tidlig.

**Antatte preferanser:**
- Stil: **mineralsk og strukturert** (GG-Riesling, Jura-Chardonnay), men også **god til off-dry tysk** (Spätlese)
- Eik: **moderat – ikke smør-bomber** (Jura-vinifisering, ikke California-style)
- Syre: **høy** (Riesling-preferansen er tydelig)
- Aromatisk vs. diskret: **trolig diskret – mineralsk profil dominerer (GG-Riesling, Jura). Den ene aromatiske favoritten (Cloudy Bay) er gammel rating. Test forsiktig med aromatiske.**

### Musserende (23 viner, snitt 4.03 – din høyeste kategori!)

- Du elsker Champagne, men også Cava (4.5 Juvé & Camps) og Crémant
- 4.5 Vve Fourny Blanc de Blancs Premier Cru = solid Chardonnay-basert Champagne
- Du har tre Champagner i kjelleren – musserende er åpenbart viktig for deg
- **Bernard Pitois Brut Réserve → 4.4** (2026-06-13, restaurant). NM-stil, frisk og mineralsk. Bekrefter Champagne-mønsteret.

### Rosé (10 viner, snitt 3.30 – sliter mest)

- **Provence-rosé har skuffet flere ganger:** 1.0, 2.0, 2.5, 4.0 – stor varians
- **Italiensk nebbiolo-rosé fra Piemonte fungerer:** 4.5 Ioppa, 4.0 Cantalupo
- **Antakelse (vekt høyt):** Du trives bedre med fyldigere, mer strukturerte roséer enn lyse Provence-stiler. Foreslå nebbiolo-rosé, italiensk rosato, eller mørkere Bandol-stil framfor klassisk blek Provence.

### Andre kategorier
- **Dessertvin:** 1 vin (Sauternes 4.5) – for lite data
- **Hetvin/fortified:** 1 vin (Chip Dry White Port 4.5) – for lite data
- **Orange/natur:** Ingen i dataene. Ukjent terreng – kan foreslås som [NYTT] i passende situasjon.

## Klokke-profil for topp-viner (Vinmonopolets system)

Når Claude finner viner med kjent klokke-profil, søk etter lignende.

| Vin | Rating | Fylde | Friskhet | Tannin | Sødme | Stil |
|---|---|---|---|---|---|---|
| Fenocchio Barbera d'Alba Sup. 2023 | 4.6 | 8/12 | 9/12 | 7/12 | <3 g/l | Frisk og fruktig |
| Thymiopoulos Rosé de Xinomavro 2024 | — (foreslått) | 7/12 | 8/12 | — | <3 g/l | Strukturert rosé, Nebbiolo-aktig |
| Hattingley Valley English Sparkling 2014 | 4.0 | — | — | — | — | Engelsk traditional method (ikke-rosé) |
| Hattingley Valley Rosé 2021 | — (foreslått) | 7/12 | 10/12 | — | 5,2 g/l | Engelsk traditional method rosé |
| Catena Zapata Paraje Altamira Malbec 2024 | 4.2 | 8/12 | 7/12 | 7/12 | 3,6 g/l | Uco Valley høyde-Malbec, floral/savory, diskret eik |
| **Vespa Barbera 3 l** (varenr 5280806) | **avvist – «for lett»** | 8/12 | 9/12 | 7/12 | <3 g/l | Ustøttet ankerpunkt: identiske klokker med Fenocchio 4.6, motsatt dom |
| Ch. Kefraya Les Bretèches (8136501) `[≠ 2016→2023]` | 4.5 | 9/12 | 8/12 | 6/12 | <3 g/l | Krydret og sødmefull |
| Vincent Girardin Terroir Noble Bourgogne (9111501) `[≠ 2010→2024]` | 4.5 | 7/12 | 8/12 | 7/12 | <3 g/l | Frisk og fruktig — **motsigelse A** |
| Valpantena Amarone della Valpolicella (4612201) `[? →2023]` | 4.2 | 10/12 | 8/12 | 8/12 | 4,7 g/l | Krydret og sødmefull |
| Patria Femina Etna Rosso (19716901) `[? →2025]` | 4.1 | 8/12 | 8/12 | 8/12 | <3 g/l | Frisk og fruktig — **motsigelse C** |
| Carpineto Dogajolo Rosso (1788401) `[≠ 2016→2023]` | 4.0 | 8/12 | 9/12 | 8/12 | <3 g/l | Fast og fruktig — **motsigelse B** |
| Castellani Filicheto Vino Nobile, 3 l (8299106) `[≠ 2013→2022]` | 4.0 | 7/12 | 7/12 | 7/12 | 8,1 g/l | Fast og fruktig (ratet på flaske, klokker fra 3 l) |
| Ch. de Ségriès Lirac Rouge (3133501) `[≠ 2014→2023]` | 4.0 | 9/12 | 8/12 | 8/12 | <3 g/l | Fyldig og saftig — **motsigelse D** |
| Antiche Terre Venete Valpolicella Ripasso (5220001) `[≠ 2012→2022]` | 4.0 | 8/12 | 7/12 | 7/12 | 5 g/l | Krydret og sødmefull (SKU-usikkerhet, se note 3) |
| Borgogno No Name (701401) `[≠ 2011→2023]` | 4.0 | 9/12 | 9/12 | 10/12 | <3 g/l | Fast og fruktig, Nebbiolo 100 % — høyeste tannin i settet |
| Castelmondo Valpolicella Ripasso Superiore (11186901) `[≠ 2017→2023]` | 3.9 | 8/12 | 8/12 | 6/12 | 4,1 g/l | Krydret og sødmefull — **motsigelse E** |
| Vincent Girardin Bourgogne Pinot Noir (9111501) `[≠ 2023→2024]` | 3.8 | 7/12 | 8/12 | 7/12 | <3 g/l | Samme varenummer som 4.5-raden over — **motsigelse A** |
| Pietro di Campo Silenzio Barbera (1208701) `[≠ 2012→2024]` | 3.8 | 7/12 | 9/12 | 7/12 | 5 g/l | Frisk og fruktig |
| Weinert Carrascal (3240401) `[≠ 2013→2022]` | 3.5 | 9/12 | 8/12 | 8/12 | <3 g/l | Fyldig og saftig — **motsigelse D** |
| Vajra Langhe Rosso (3123601) `[≠ 2016→2025]` | 3.5 | 7/12 | 8/12 | 8/12 | <3 g/l | Fast og fruktig |
| Campo Viejo Reserva (344401) `[≠ 2009→2018]` | 3.5 | 8/12 | 8/12 | 6/12 | <3 g/l | Utviklet og nyansert — **motsigelse E** |
| Bread & Butter Pinot Noir (11018401) `[? →2020]` | 3.2 | 7/12 | 7/12 | 5/12 | 7 g/l | Frisk og fruktig — laveste tannin i settet |
| Villa Antinori Rosso (279201) `[≠ 2015→2024]` | 3.0 | 8/12 | 9/12 | 8/12 | <3 g/l | Fast og fruktig — **motsigelse B** |
| Chapoutier Belleruche Côtes du Rhône, 3 l (9348706) `[≠ 2013→2024]` | 3.0 | 8/12 | 8/12 | 8/12 | <3 g/l | Fyldig og saftig — **motsigelse C** |
| **Dom. de la Janasse Côtes du Rhône (3241501)** `[≠ 2015→2024]` | **2.0** | 8/12 | 8/12 | 8/12 | <3 g/l | Negativt anker: laveste rødvins-rating i settet, midt i klokke-skyen — **motsigelse C** |

*(Tabellen utvides etter hvert som Claude slår opp viner i bekjent-historikken)*

**Årgangsmerking:** `[≠ a→b]` = ratingen gjelder årgang *a*, klokkene er lest fra årgang *b* i Polet-snapshotet — **ikke** samme flaske. `[? →b]` = Vivino-oppføringen mangler årgang, klokkene er fra årgang *b*. **Ingen av de 19 nye radene har klokker fra den årgangen som faktisk ble ratet** (snapshotet fører dagens årganger; avstanden rated årgang → snapshot-årgang er 1–14 år). Det er en reell svakhet ved hele tabellen, ikke en detalj.

**Noter:**
1. Alle klokke-verdier er lest direkte fra `data/polet/details/<varenr>.json`. Ingen er estimert. Manglende dimensjon vises som `—`.
2. Fenocchio-raden øverst er verifisert mot varenr **759901** (Fylde 8 / Friskhet 9 / Garvestoffer 7 — stemmer). Snapshotet fører nå **2024**-årgangen, og Vivino-ratingen 4.6 gjelder **2019** — «2023» i radetiketten er altså ikke årgangen klokkene kommer fra.
3. Antiche Terre Venete fører **to** Ripasso-SKU-er i katalogen (5220001 til 169,90 og 17228201 til 315,-). Bare 5220001 har details. Hvilken av dem 4.0-ratingen fra 2012 gjelder, er ukjent. **Oppdatert 2026-08-30:** spørsmålet er smalere enn noten antyder. **4.0-ratingen kan ikke tilhøre noen av SKU-ene** — den gjelder 2012-årgangen (Vivino `/wines/2360530`), mens begge varenumrene fører **2022**. Det som faktisk er i spill er en *nyere* rating på samme vinnavn: **3.7**, ratet 2026-07-21 — men den er en årgangsløs Vivino-aggregat-entitet (`/wines/1532847`, `seo_name` slutter på `-uv`), så den har ingen årgang å knytte til et varenummer heller. De to ratingene er altså to ulike viner, ikke én vin over tid.
   Details for 17228201 er nå hentet. Drueblanding, årgang, alkohol, sukker og syre er **identiske** med 5220001, mens klokkene avviker: **Fylde 10 / Friskhet 7 / Garvestoffer 5** mot 5220001s **8 / 7 / 7**. Alt som kommer fra produsent og lab er likt; alt som kommer fra Polets sensoriske panel spriker. Det er forenlig både med to panelrunder på samme vin og med to beslektede cuvéer. Feltet som ville avgjort det, `metode`, mangler på 17228201 (5220001 har «vinifikasjon etter ripasso-metoden…»). Spørsmålet står altså fortsatt åpent — men nå med data i stedet for antagelser.
4. Utelatt fra tabellen: viner der Vivino-oppføringen matchet en **annen** vin fra samme produsent (Marchesi di Barolo *Reis* vs *Ruvei*, Ricasoli *Brolio Chianti Classico* vs generisk Chianti, Ioppa *Rusin* rosé vs Colline Novaresi **rød**, Chakana *Estate* vs *Sobrenatural*) — produsent-treff er ikke vin-treff.

### Diskriminerer klokkene i det hele tatt? (n=20, målt 2026-08-30)

Nei — ikke på dette datagrunnlaget. Korrelasjonen mellom rating og hver enkelt klokke er ~0:

| Klokke | Korrelasjon med rating | Spredning i settet |
|---|---|---|
| Fylde | **+0,16** | 7–10 |
| Friskhet | **+0,09** | 7–9 |
| Garvestoffer | **−0,10** | 5–10 |

Verre: **hver eneste gruppe med identiske klokker spenner over ratingskalaen.**

- **Motsigelse A — samme varenummer, to dommer.** 9111501 Vincent Girardin Terroir Noble er ratet **4.5** (2010) og **3.8** (2023). Identiske klokker per definisjon; 0,7 poeng fra hverandre. Årgang/moden alder forklarer det klokkene ikke kan.
- **Motsigelse B — 8/9/8:** Carpineto Dogajolo **4.0** vs Villa Antinori **3.0**. Samme stilmerkelapp «Fast og fruktig», samme land, samme sukker.
- **Motsigelse C — 8/8/8 (den vanligste trippelen han har):** Patria Femina Etna Rosso **4.1**, Chapoutier Belleruche **3.0**, Janasse Côtes du Rhône **2.0**. Tre viner, identiske klokker, **2,1 poeng spenn**. Dette er den sterkeste enkeltobservasjonen i tabellen.
- **Motsigelse D — 9/8/8:** Ch. de Ségriès **4.0** vs Weinert Carrascal **3.5**.
- **Motsigelse E — 8/8/6:** Castelmondo Ripasso **3.9** vs Campo Viejo Reserva **3.5** (svakest av de fem).
- **Det opprinnelige ankeret — 8/9/7:** Fenocchio **4.6** vs Vespa Barbera 3 l **«for lett»**.

**Konsekvens.** Alle 6 klokke-gruppene i settet er selvmotsigende, og de tre klokkene forklarer til sammen nesten ingenting av ratingvariasjonen. Klokke-similarity er brukbar til **én ting**: å finne viner som *smaker i samme retning* (stil-slektninger). Den er ubrukelig til å forutsi om han vil like en vin, hvor kraftig den er, eller hvor god den er. Rangér på det som faktisk skilte i motsigelsene over — appellasjonsnivå, fat/metode, literpris, årgang og drue — og bruk klokkene bare som grovfilter. Se «Kraftigere kan IKKE søkes på Fylde-klokka».

> **Les tabellen med det negative ankeret i bånn.** Vespa-raden er ikke en topp-vin – den står der fordi den beviser at klokke-similarity alene er utilstrekkelig: to viner med identisk 8/9/7 fikk 4.6 og «for lett». Bruk klokkene til å finne *stil-slektninger*, ikke til å rangere kraft eller kvalitet. Se «Kraftigere kan IKKE søkes på Fylde-klokka» under Stilpreferanser.

## Blindspots (eksplisitt mangel på data)

Disse områdene har for lite eller ingen data til å gi sikre anbefalinger.
Claude bør markere [NYTT] og lavere konfidens:

- **Asiatisk mat** – ingen viner ratet sammen med thai, indisk, kinesisk osv.
- **Naturvin / orange / hudkontakt** – fraværende i datasettet
- **Aromatisk hvitvin** – Viognier, Gewürztraminer, Torrontés mangler helt
- **Spanske rødviner** – kun 4 viner, ingen klart mønster
- **Pinot Noir generelt** – stor varians (1.5 til 4.5), vanskelig å forutsi

### New World rødvin – under aktiv utforskning (oppgradert fra blindsone 2026-07-02)

**Hypotese (styrket, ikke bekreftet):** Du liker **frisk, høyde-/kjølig-preget, strukturert og savory** New World-rødvin – ikke den syltete, høy-alkohol, eik-tunge varmklima-stereotypien.

Evidens så langt:
- 4.2 Catena Zapata Paraje Altamira Malbec 2024 (Uco Valley høyde, 13,5 %, klokker 8/7/7, floral/savory, diskret eik)
- 4.1 Catena The Trilogy Malbec 2024 (høyde-Mendoza, friskere stil)
- *Kontrast:* 3.5 basis-Catena Malbec 2014 og 3.0 Chakana Bonarda 2014 – flatere/eldre, den varmere/rundere enden traff ikke like godt.

**Konsekvens for anbefalinger:** New World-rødvin skal ikke lenger flagges som ren blindsone. Foreslå aktivt langs frisk/høyde-aksen (mål: Fylde 7–9, Friskhet 7+, Tannin 6–8, 13–14 %, diskret-moderat eik). Vær fortsatt varsom med den varme, syltete, høy-eik-enden (Barossa-jam, billig varmklima-Cab) – det er der hypotesen kan brekke, og verdt å teste bevisst.

**Utforskningsplan:** se [`tasks/exploration/newworld.md`](../tasks/exploration/newworld.md) – kuratert flight på tvers av Argentina/Chile/Sør-Afrika/Australia for å kartlegge grensene. Oppdater denne seksjonen etter hvert som viner rates.

## Druer du vet du liker (utledet fra mønstre)

- **Barbera** (4.6 topp, flere 4.0+)
- **Nebbiolo** (både rødt og rosé)
- **Corvina/Rondinella-blend** (Ripasso, Amarone)
- **Riesling** (tysk, både tørr og søt)
- **Chardonnay** (Jura, Burgund, ikke for fet)
- **Sangiovese** (Chianti Classico, Vino Nobile)
- **Tannat** (Garzón 4.5)

## Druer/regioner som har bommet

- **Generisk Provence-rosé** (gjentakende skuffelse)
- **Sør-Rhône hvit** (to lave på Lirac Blanc)
- **Billig Burgund** (Labouré-Roi 1.5)
- **Argentinsk Bonarda** (3.0 Chakana)
- **Sauvignon Blanc:** Bare én i hele dataene (Cloudy Bay 4.5 fra 2015). Ukjent om dette er bevisst fravalg eller bare ikke prøvd. Ikke foreslå klassisk gress/stikkelsbær-SB uten å sjekke først; bedre å gå Sancerre/Pouilly-Fumé hvis SB skal med (mer mineralsk, matcher din hvitvin-profil).

## Regioner du dras mot (basert på frekvens og rating)

1. **Nord-Italia** (Piemonte, Veneto) – tyngdepunktet ditt
2. **Tyskland** (Mosel, Rheingau – Riesling)
3. **Champagne**
4. **Jura** (Chardonnay)

## Regioner verdt å utforske (mine forslag, vi diskuterer)

- **Etna (Sicilia)** – du ga 4.1 til Donnafugata Etna Rosso. Mer i denne stilen?
- **Galicia (Albariño)** – du ga 4.0 til Torres Pazo das Bruxas
- **Tyske GG-er bredere** – Spätburgunder, ikke bare Riesling
- **Mosel-Riesling Spätlese tørr** – du har mønster mot tysk hvitt med syre

## Aromaer/smaker du sannsynligvis liker

Utledet fra hva som dominerer toppen din:
- Mørke bær (Ripasso, Amarone)
- Krydder/lakris (Nebbiolo)
- Mineralsk/steinete (Riesling GG, Jura)
- Sitrus/grønt eple (musserende-favorittene)
- Tørket frukt/figen (Amarone)

Disse legges inn som arbeidshypotese – kan justeres etter hvert som vi tester.

## Aromaer/smaker som sannsynligvis ødelegger for deg

Kandidater basert på laveste ratings:
- Tynn, syrlig billig Pinot Noir (Labouré-Roi)
- Vannet Provence-rosé (Whispering Angel 2.5, Sulauze 1.0)
- Overoaket eller varmt-klimask hvitt (Lirac Blanc)

## Praktisk

Allergier, glass, dekanter, lagringsforhold: ikke avklart. Spør i situasjoner der det er kritisk (f.eks. "har du dekanter?" hvis jeg foreslår ung Barolo).

## Mat og drikkesituasjon

Avklares per spørsmål – det er en del av samtaleflyten. Når brukeren spør om en vin, antas det at:
- Mat ikke er gitt med mindre nevnt
- Anledning ikke er gitt med mindre nevnt
- Hvis det er uklart om vinen skal følge mat eller drikkes alene, spør én rask oppfølger

## Kjeller (dokumentert i Vivino)

- Alexandre Bonnet Grande Réserve Brut Champagne (1 fl)
- Pierre Peters Blanc de Blancs Le Mesnil-sur-Oger (1 fl)
- Vve Fourny & Fils Blanc de Blancs Vertus Premier Cru (1 fl)

→ Brukeren har også mye annen vin liggende som ikke er dokumentert i cellar-data. Anta ikke at det som er listet over er hele lageret. Spør om kontekst når det er relevant ("har du noe åpent allerede?").

## No-go-liste (konkrete viner)

- Domaine de Sulauze Pomponette Rosé (din eneste 1.0)
- Labouré-Roi Pinot Noir Bourgogne (1.5)
- Domaine de la Janasse Côtes du Rhône 2015 (2.0)
- Whispering Angel Rosé (2.5)
- Miraval Provence Rosé 2014 (2.0) – men ny årgang kan være annerledes
- Schloss Vollrads Riesling Kabinett Trocken 2014 (2.7)
- Francisco Gomez Eco Rojo 2014 (2.5)

## Notater til Claude

- **Vekt nyere ratings høyere:** Smaken min har endret seg fra 2014 til 2026
- **Gamle 4.5 fra 2014–2016 er ikke nødvendigvis fortsatt favoritter** – bekreft før du baserer mye på dem
- **Jeg vil ha grundige forklaringer** – ikke kutt på "hvorfor"
- **Marker alltid [PRØVD] / [LIKNENDE] / [NYTT]** når du anbefaler
- **Flagg amerikanske produkter med `[USA]`** når land = United States. Jeg ønsker å unngå dem, men vil bli eksponert med tydelig merking — aldri filtreres bort. Samme prinsipp som tier-flagg (no-filter-bubble, ADR-016).