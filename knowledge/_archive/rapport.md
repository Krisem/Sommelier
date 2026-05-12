# Stress-test-rapport: Digital Sommelier

> Status etter test av API, smaksprofil, og research
> Dato: 2026-05-12

## Sammendrag

Prosjektet er solid grunnlag, men har **én stor svakhet** (det offisielle Vinmonopolet-APIet er nesten ubrukelig) og **én stor mulighet** (det udokumenterte interne webshop-APIet er gull).

Resultat etter denne sesjonen: Vi bytter datakilde, legger til Vinmonopolets eget klokke-system som matching-rammeverk, og fikser to feil i førsteanalysen av profilen.

---

## 1. API-funn (kritisk)

### Det "offisielle" APIet (apis.vinmonopolet.no/products/v0)
**Bruk det IKKE.** "Open"-produktet du har subscription til returnerer *kun* productId + productShortName. Ingenting om pris, region, lager, druer eller smaksprofil. `accumulated-stock`-endepunktet returnerer 404 – det krever wholesaler-tilgang.

```bash
# Eksempel - alt du får:
GET /products/v0/details-normal?productId=11894701
→ {"productId":"11894701","productShortName":"Guy Charlemagne Brut Rosé"}
```

Dette er for begrenset til å bygge en sommelier-tjeneste på.

### Det reelle APIet: webshop-API (vmpws)
**Bruk dette i stedet.** Det er det samme APIet som vinmonopolet.no bruker, krever ingen nøkkel, og gir nesten alt vi trenger:

```bash
# Søk:
GET https://www.vinmonopolet.no/vmpws/v2/vmp/products/search?q=barbera&pageSize=20
```

Returnerer per produkt:
- `code` (varenummer), `name`, `price.value`
- `alcohol.value`, `volume.value`
- `main_category` (Rødvin/Hvitvin/...), `main_country`, `district`, `sub_District`
- `product_selection` (Basisutvalget/Bestillingsutvalget/...)
- `productAvailability` (lager/bestilling)
- `url` (relativ sti til produktsiden)

### Klokker, lukt, smak: må skrapes fra produktsiden
Smaksprofilen ligger **ikke** i søke-APIet, men i HTML-en på den enkelte produktsiden. Eksempel:

```bash
GET https://www.vinmonopolet.no/{url-fra-søket}
```

I HTML-en finnes:
- **Klokker**: Fylde, Friskhet, Garvestoffer, Sødme (skala 1–12)
- **Stil**: "Frisk og fruktig", "Fyldig og fruktig", etc. (10 stiler)
- **Lukt** (fritekst-beskrivelse fra Polets sensoriker)
- **Smak** (fritekst-beskrivelse)
- **Drueblanding** ("Barbera 100%", "Sangiovese 90%, Cabernet 10%")
- **Vinifikasjonsmetode**
- **Drikkeklarhet** ("Drikkeklar nå", "Kan lagres 5–10 år", etc.)
- **Alkohol, sukker, syre** (kjemiske g/l-verdier)

### Implikasjon for prosjektet
- Slett alt om `apis.vinmonopolet.no` og subscription-key i instruksjonene
- API-nøkkelen i `secrets.md` trengs ikke lenger – kan slettes
- Erstatt med: "Bruk vmpws-APIet (åpent), og skrape produktsiden for klokker"
- Det er et **rate limit** vi ikke har testet – vær konservativ (max ~30 søk/sesjon)

---

## 2. Smaksprofil-svakheter funnet i testing

### Feil i førsteversjon
Jeg påsto at "Spätlese halvtørr ikke fantes i historikken". **Det var feil.** Brukeren har faktisk:
- 4.0 Stephan Ehlen Erdener Treppchen Riesling Spätlese 2013 (sannsynligvis off-dry)
- 3.8 Hexamer Spätlese Trocken (tørr Spätlese)
- 4.1 Stephan Ehlen Auslese 2019 (søt)

→ Brukeren tolererer både tørt og halvtørt tysk hvitt. Profilen må oppdateres.

### Reelle blindspots
1. **Asiatisk mat** – ingen viner ratet sammen med asiatisk mat. Vi har ingen empirisk basis for å vite hvordan brukerens preferanser fungerer med chili/kokos/fiskesaus.
2. **New World rødvin generelt** – minimal data utenfor Italia/Frankrike/Tyskland
3. **Pinot Noir-mønstret er kaotisk** – fra 1.5 til 4.5, så vi kan ikke generalisere
4. **Hvitviner med tropisk/aromatisk profil** – nesten ingen erfaring (Viognier, Gewürztraminer, Torrontés mangler helt)
5. **Spanske rødviner** – kun 4 stk i hele datasettet, ingen klar mønster
6. **Naturvin/orange/biodynamisk** – fraværende, men kan være interessant

### Det som virker ekstremt godt
Test 2 var det beste resultatet: Brukerens topp-Barbera (4.6) finnes på Polet for **205 kr**. Slike treff er hva tjenesten lever av.

---

## 3. Mangler i prosjekt-kunnskapen

### Anbefalt å legge til (utover det vi allerede har):

**A. Vinmonopolets eget rammeverk (KRITISK)**
- Klokke-system (1-12 for fylde/friskhet/garvestoff/sødme)
- 10 vinstiler for rødvin og 10 for hvitvin (Polets klassifikasjon)
- "Matfarger" (grønn/rød/gul/brun) – Polets matparing-system
- Last opp som `vinmonopolet_rammeverk.md` – jeg kan lage denne

Hvorfor: Brukeren handler på Polet. Polet sorterer etter klokker. Hvis vi snakker samme språk som hyllelappene, blir anbefalinger lettere å verifisere.

**B. Norske grossister og importører (relevant)**
Mange viner kommer fra de samme få importørene (Moestue, Solera, Vinarius, Best Cellars). Hvis vi vet hvilke importører som leverer hva, kan vi forutsi stil.

**C. Druekompendium (medium relevans)**
WSET-SAT-pdfen er bra, men en kort "drue-profiler" med fokus på druer brukeren liker (Barbera, Nebbiolo, Riesling, Sangiovese, Tannat, Corvina-blend) hadde vært nyttig. Kan genereres.

**D. Årgangsguide (allerede har vi The Wine Society 2024)**
Tilstrekkelig for nå. Oppdater årlig.

### Anbefalt å IKKE legge til
- Jamie Goode "Science of Wine" – for dypt for behovet, ville okkupert mye kontekst uten å gjøre svar bedre. Bedre å web-søke for spesifikke spørsmål.
- Wine Folly aroma wheels – brukeren har Vivino-historikk som er rikere enn et generisk hjul
- Robert Parker-charten – betalingsmur, gammel data

---

## 4. Konkrete oppdateringer som trengs

### `smaksprofil.md` – tre korreksjoner:
1. Fjern påstanden om at off-dry/halvtørr ikke er testet – det ER testet, og bruker liker det
2. Legg til kjemisk-faktisk fingeravtrykk av topp-ratede viner (alkohol, syre, klokker) når vi har det
3. Legg til eksplisitt "blindspot"-seksjon: asiatisk mat, naturvin, varmt klima New World

### Prosjektinstruksjoner – endringer:
1. Slett Vinmonopolet-API-nøkkel-referansen – bruk vmpws
2. Legg til instruks om å hente klokke-data fra produktside ved seriøse anbefalinger
3. Legg til instruks om å koble brukerens topp-viner til klokke-verdier, og søke etter lignende profiler

### `secrets.md`
**Slett – ikke lenger nødvendig.** Vinmonopolets webshop-API krever ingen autentisering. (Rull også API-nøkkelen i Polets dev-portal siden den ble eksponert i chatten.)

---

## 5. Hvor bra treffer profilen?

**Test-resultater (skala: ⬛ feil / 🟨 sånn passe / 🟩 treffsikkert):**

| Test | Resultat |
|---|---|
| Barbera under 250 kr | 🟩 Fant 2 gode alternativer, inkl. brukerens 4.6 til 205 kr |
| Osso buco-paring | 🟩 Italiensk-fokus stemmer, riktige druer foreslått |
| Etna Rosso-utvidelse | 🟩 8 alternativer på Polet, alle relevante |
| Champagne under 500 kr | 🟩 12 alternativer funnet, varierte produsenter |
| Thai grønn curry | 🟨 Klassisk regel sier off-dry Riesling – brukeren har spist det (4.0+ på Spätlese), men ingen testing mot asiatisk mat |
| Pinot Noir utenfor Burgund | 🟨 Erfaringsdata er sprikende (1.5 til 4.5), så ingen klar retning |

**Verdivurdering:** Profilen treffer ~80% når brukeren spør om noe som ligger i komfort-sonen (italiensk, tysk hvit, Champagne). Sliter når vi går utenfor (asiatisk mat, New World, naturvin). Det er greit – vi merker [NYTT] og bygger data over tid.

---

## 6. Anbefalte neste steg

1. **Generer `vinmonopolet_rammeverk.md`** – klokker + stiler + matfarger
2. **Oppdater prosjektinstruksjoner** – fjern broken API, legg til vmpws + produktside-skraping
3. **Slett secrets.md** og rull API-nøkkelen
4. **Korriger smaksprofil.md** – Spätlese-feilen + blindspot-seksjon
5. **Test med tre reelle scenarier** etter at det er oppdatert
