# Vinmonopolets rammeverk

> Polets eget system for å beskrive og kategorisere vin. Hyllelapper, nettbutikk
> og rådgivning bygger på dette. Hvis Claude snakker samme språk som
> klokker/stiler/matfarger, blir anbefalinger lett å verifisere mot hyllelappen
> og lett å diskutere med polet-ansatte.
>
> Kilder: vinmonopolet.no/fag/artikler (hentet mai 2026)

## 1. Klokkene (smaksprofil per produkt)

Hver vin på Polet er gradert på 4–7 klokker, skala **1–12**. Klokkene viser
ikke kvalitet – bare hvor tydelig en egenskap er.

### Smaksklokker som alltid finnes på vin

| Klokke | Hva den måler | Hva som driver verdien |
|---|---|---|
| **Fylde** | Vekt og rikhet i munnen | Alkohol, glycerol, tannin, smakskonsentrasjon, fatlagring |
| **Friskhet** | Forfriskende syrlighet | Mengde og type syre (vinsyre, eplesyre, melkesyre) |
| **Garvestoffer** (tannin) | Tørrende/snerpende munnfølelse | Tannin fra drueskall/-kjerner og fat |
| **Sødme** | Tydelig søtsmak | Restsukker (kun angitt på hvit + musserende; rødvin antas tørr) |

### Aroma-klokker (når relevant)

| Klokke | Hva den måler |
|---|---|
| **Frukt** | Hvor tydelig fruktpreg vinen har |
| **Krydder og urter** | Krydder- og urtearomaer |
| **Fat** | Fatlagring (vanilje, røkt tre, kokos) |
| **Røyk** | Røykpreg (spesielt fra fat eller terroir) |

### Praktisk: hvordan tolke klokkene

- **Fylde 1–4**: Lett (Beaujolais, Pinot Grigio)
- **Fylde 5–8**: Medium (Chianti, Mâcon)
- **Fylde 9–12**: Fyldig (Amarone, fatlagret Chardonnay)
- **Friskhet 9+ på rødvin**: Syrlig (Barbera, Sangiovese, Nebbiolo)
- **Garvestoff 8+**: Markant struktur (ung Barolo, Cabernet, Tannat)
- **Sødme 1–3**: Tørt. **4–6**: Halvtørt. **7+**: Halvsøtt/søtt

### Eksempel: Brukerens topp-Barbera

Fenocchio Barbera d'Alba Superiore 2023 (4.6):
- Fylde 8, Friskhet 9, Garvestoff 7
- 13,5% alkohol, <3 g/l sukker, 6,2 g/l syre
- Stil: "Frisk og fruktig"

→ Dette er fingeravtrykket Claude skal lete etter når brukeren ber om "noe lignende".

---

## 2. Vinstilene (10 stiler for rødvin og 10 for hvitvin)

Polet klassifiserer alle tørre viner inn i én stil. Stilen beregnes automatisk
fra drue, område, klima og klokker.

### Rødvinsstiler

| Stil | Kjennetegn | Eksempler | Passer til |
|---|---|---|---|
| **Frisk og fruktig** | Lett-medium, høy syre, lite tannin | Barbera, Pinot noir, Gamay, Valpolicella, Zweigelt | Pasta, pizza, tapas, kylling |
| **Fruktig og mild** | Medium fylde, lav-medium syre, moderat tannin | Merlot, lett Chianti, Carmenère | Lett kjøtt, pasta med kjøttsaus |
| **Fruktig og rik** | Fyldig, frukt-dominert, varmere klima | Malbec, Zinfandel, Primitivo, Shiraz fra varmt klima | Vilt, gryteretter, soppretter |
| **Frisk og bærpreget** | Kjølig klima, høy syre, rødbærspreg | Pinot noir Burgund, kjølig-klima Cab Franc | Lette kjøttretter, fugl |
| **Sval og krydret** | Medium-fyldig, krydret, ofte fatpreget | Cabernet Sauvignon, Bordeaux, Chianti Classico Riserva | Biff, lam, hardost |
| **Fruktig og fast** | Tannisk, ung, mørkbærspreget | Ung Nebbiolo, Aglianico, ung Cab/Bordeaux | Kraftig kjøtt, grillet biff |
| **Modent og kompleks** | Lagret, tertiære aromaer (lær, sopp, krutt) | Eldre Burgund, Brunello, eldre Bordeaux/Rioja | Vilt, sopp, trøffel |
| **Fyldig og krydret** | Fyldig, mørkbær, pepper, lakris | Syrah/Shiraz, Châteauneuf-du-Pape, Sicilia rødvin | Biff, gryter, krydret kjøtt |
| **Konsentrert og rik** | Høy alkohol, fyldig, fatpreg, tørket frukt | Amarone, Ripasso, Rioja Reserva, Priorat | BBQ, finnbiff, kjøtt med portvinsaus |
| **Søte og halvsøte** | Restsukker, ofte fortified | Recioto, søt Madeira, søt Lambrusco | Dessert, blåmuggost |

### Hvitvinsstiler

| Stil | Kjennetegn | Eksempler | Passer til |
|---|---|---|---|
| **Frisk og fruktig** | Slank, sitruspreget, ståltank | Pinot Grigio, Vinho Verde, Petit Chablis, Muscadet | Reker, ceviche, lette salater |
| **Frisk og frodig** | God modning, fersken/aprikos, fortsatt frisk | Riesling Ortswein/GG, Chenin Blanc, Soave, Albariño | Fisk, kylling, svin |
| **Aromatisk** | Tropisk frukt, blomster, oljete tekstur | Gewürztraminer, Viognier, Torrontés, Muscat, Pinot Gris Alsace | Thai, kinesisk, indisk, gravlaks, rødkittost |
| **Rik og fyldig** | God fylde, fatpreg, gult eple, smør | Fatlagret Chardonnay (hvit Burgund), Pinot Blanc, Viura, hvit Rhône | Stekt mat, fløtesauser, smaksrike skalldyr |
| **Frisk og urtepreget** | Sauvignon Blanc-stil, grønt | Sancerre, NZ Sauvignon Blanc, Verdejo | Geitost, asparges, urteretter |
| **Sval og mineralsk** | Steinete, tørr, kjølig klima | Chablis, tørr tysk Riesling, Jura Chardonnay | Skalldyr, østers, sushi |
| **Modent og kompleks** | Lagret, oksidativ, nøtter | Eldre hvit Burgund, Hunter Valley Sémillon, Sherry | Trøffelretter, mature oster |
| **Rik og krydret** | Krydret, viskøs | Pinot Gris fra varmt klima, krydret Gewürz | Krydret asiatisk mat, paté |
| **Søte og halvsøte** | Restsødme | Spätlese, Auslese, Sauternes, Tokaji | Foie gras, blåmuggost, dessert |
| **Oransje / hudkontakt** | Hudkontakt, tannin i hvitvin | Naturvin, ramato Pinot Grigio | Krydret mat, fett kjøtt |

---

## 3. Matfarger (Vinmonopolets parings-rammeverk)

Polet deler all mat inn i fire "farger" basert på dominerende smak og tekstur.
Dette er et forenklet, men praktisk system.

| Matfarge | Karakter | Eksempler | Vin-prinsipp |
|---|---|---|---|
| **Grønn** | Lett, frisk, syrlig, vegetabilsk | Salater, reker, hvit fisk, asparges | Lett/medium hvit med god friskhet (Pinot Grigio, Sancerre, Albariño) |
| **Gul** | Smørrik, kremet, moderat fyldig | Kylling i fløtesaus, kalv, røkt fisk, brie | Fyldigere hvit (fatlagret Chardonnay, Viognier), eller lett rød |
| **Rød** | Saftig kjøtt, tomatbase, krydret | Pasta bolognese, lam, biff medium, pizza | Frisk-fruktig rødvin med struktur (Sangiovese, Barbera, Tempranillo) |
| **Brun** | Karamellisert, røkt, langtidskokt, intens | Gryter, BBQ, vilt, sopp, mørke sauser | Fyldig rødvin (Amarone, Shiraz, Cab, eller modne viner) |

## 4. Smaksinteraksjoner (Polets generelle prinsipper)

Hvordan mat påvirker vin – fra Vinmonopolets matfag:

| Mat-egenskap | Effekt på vin | Strategi |
|---|---|---|
| **Salt mat** | Vinen blir fruktigere, søtere, mindre frisk. Svært salt mat kan demper fruktigheten. | Frisk vin med tydelig frukt |
| **Syrlig mat** | Demper vinens syre, vinen blir fruktigere og søtere. Svært syrlig mat demper frukt. | Vin med høyere syre enn maten |
| **Sødmerik mat** | Vinen blir friskere, mindre søt og fruktig | Vin med minst like mye sødme som maten |
| **Umamirik mat** | Vinen blir mindre søt og fruktig | Vin med ekstra fruktighet, eller tertiær kompleksitet (fat, alder) |
| **Fet mat** | Vinen blir mindre frisk og fruktig, tannin dempes | Vin med god konsentrasjon, ofte syrlig eller tanninsk |
| **Sterk/krydret mat** | Vinen blir friskere, snerpende, mindre søt og fruktig | Lav alkohol, gjerne off-dry/halvtørt, lite tannin |

### Klassiske "vinfeller"
Disse smakene i mat overdøver vinen eller gjør tannin trå:
- Eddik (vinaigrette)
- Sterk sennep
- Chili
- Stor sødme (uten kompenserende sødme i vin)
- Rå løk

---

## 5. Drikkeklarhet (drikkevindu)

Polet merker viner med drikkeklarhet:
- **Drikkeklar nå**
- **Drikkeklar nå, men kan også lagres**
- **Vil utvikle seg ytterligere ved lagring**
- **Best etter X år**

Generelle tommelfingre Claude kan bruke:
- **Vanlig basisutvalg rødvin**: Drikk innen 2–3 år etter kjøp
- **Barolo, Brunello, Bordeaux Cru, Burgund Premier+**: Tåler 10–20 år
- **Amarone**: Topp drikkevindu 5–15 år etter høst
- **Riesling GG og Auslese**: Tåler 10+ år, blir bedre
- **Champagne Vintage**: Tåler 10–20 år; ikke-vintage drikkes ferskere

---

## 6. Polets utvalg-kategorier

Når du ser et produkt på Polet, er det merket med utvalg:

| Utvalg | Hva det betyr |
|---|---|
| **Basisutvalget** | Bredt utvalg, alltid tilgjengelig, finnes i kategori-1 og -2 butikker |
| **Bestillingsutvalget** | Må bestilles, leveres til butikk eller hjem |
| **Tilleggsutvalget** | Begrenset utvalg, kun i større butikker |
| **Testutvalget** | Nye produkter på prøve |
| **Partiutvalget** | Engangs-parti, forsvinner når det er tomt |

For en value-fokusert bruker: **Basisutvalget** er ofte best for hverdag (konsekvent tilgjengelig), **Bestillingsutvalget** for det spesielle (større utvalg, men må planlegges).
