# Sommelier – kjernekompetanse (lean)

> Dette er kjerneprinsippene + drueprofiler + pointer-system. Alltid lastet i context.
>
> **For dybde:** les fil i `deep-knowledge/` – WSET L3-nivå referanse (klima, jord, viti, vinifisering, lover, marked, klassiske produsenter).
>
> **For bruker-spesifikt:** [smaksprofil.md](smaksprofil.md) er det levende dokumentet. Oppdateres fra Vivino-dumps og feedback. Deep-knowledge er nøytral fagreferanse – ingen bruker-spesifikke referanser der.

## Innhold

1. Arkitektur og oppslag (når lese hva)
2. Drueprofiler – kjernedruene
3. Servering – kjerneregler
4. Matparing – de ti lovene
5. Klassiske vinmordere
6. Anti-hallusinerings-sjekkliste
7. Feedback-løkken: hvordan smaksprofil og lessons oppdateres
8. Deep-knowledge oppslag

---

## 1. Arkitektur og oppslag

```
DATA       →  data/vivino/*.csv             (objektive fakta, kan re-eksporteres)
KNOWLEDGE  →  knowledge/*.md                (alltid lastet, kjerne + bruker-syntese)
DEEP       →  deep-knowledge/*.md           (on-demand, nøytral fagreferanse på L3-nivå)
```

| Når | Les |
|---|---|
| Alltid (workflow steg 0-1) | `smaksprofil.md`, `vinmonopolet_rammeverk.md`, denne fila |
| Presise tasting-notater | `wset_l2_sat.md` |
| Anbefaling i en spesifikk region | `deep-knowledge/<region>.md` |
| Servering/lagring i detalj | `deep-knowledge/servering-og-lagring.md` |
| Klassisk parring i detalj | `deep-knowledge/servering-og-lagring.md` (matparing-seksjonen) |
| Polet-praktisk (importør, lansering, vintage, value) | `deep-knowledge/norsk-marked.md` |

**Regel for context-økonomi:** ikke les hele `deep-knowledge/` uoppfordret. Les én fil per anbefaling, eller bruk `grep` for å trekke ut spesifikke produsenter/druer.

---

## 2. Drueprofiler – kjernedruene

Brukerens bevisste preferanser + adjacents å utforske. For region-spesifikke uttrykk: se deep-knowledge-fil.

### Druer brukeren har bevist

| Drue | Klassisk profil | Polet-klokker (typisk) | Hovedregioner | Deep-dive |
|---|---|---|---|---|
| **Barbera** | Surkirsebær, blå plomme, fiol, lakris. Lav tannin, høy syre | Fylde 7–9 / Friskhet 10–11 / Garvestoff 4–6 | Piemonte (Alba, Asti, Nizza) | italia.md |
| **Nebbiolo** | Tjære, rose, kirsebær, lær, anis, jern, trøffel (eldre) | Fylde 9–10 / Friskhet 9–10 / Garvestoff 11–12 | Piemonte (Barolo, Barbaresco, Roero, Alto Piemonte) + Valtellina | italia.md |
| **Sangiovese (Chianti)** | Surkirsebær, granateple, rosmarin, oregano, lær, sigarboks | Fylde 7–9 / Friskhet 9–10 / Garvestoff 8–10 | Toscana (Chianti Classico) | italia.md |
| **Sangiovese (Brunello)** | Mørk kirsebær, blackberry, lær, tjære, balsamico | Fylde 9–10 / Friskhet 8–9 / Garvestoff 10–11 | Montalcino | italia.md |
| **Corvina/Rondinella-blend** | Surkirsebær (Valpo); rosin, fiken, sjokolade (Amarone) | Basis 6/9/5, Ripasso 9/8/8, Amarone 11/7/9 | Valpolicella (Veneto) | italia.md |
| **Riesling** | Eple, lime, fersken, petroleum med alder. Høy syre, terroir-transparent | Tørr 7/11/–, Spätlese off-dry 6/11/– | Mosel/Rheingau/Pfalz/Nahe, Alsace, Austria, Clare/Eden | tyskland.md / frankrike.md |
| **Chardonnay** | Kameleon. Steinfrukt + hassel + eik (Burgund); mineralsk + sitrus (Chablis/Jura) | Chablis 6/9/–, Burgund Premier+ 8/8/– | Burgund, Jura, Champagne, kjølig New World | frankrike.md |
| **Tannat** | Massiv tannin, blackberry, lær, krydder | Fylde 10 / Friskhet 7 / Garvestoff 11–12 | Madiran (Frankrike), Uruguay | frankrike.md / new-world.md |
| **Pinot Noir** | Rød kirsebær, jord, sopp, blod-appelsin | Burgund Village 6/9/5, Premier+ 7/9/6 | Burgund, Tyskland, Oregon, Central Otago, Sonoma Coast | pinot-noir.md |

### Adjacents brukeren bør utforske

| Drue | Hvorfor | Region/produsent å starte med | Deep-dive |
|---|---|---|---|
| **Aglianico** | Sør-Italias Nebbiolo – tannin, syre, vulkansk struktur | Elena Fucci Titolo, Mastroberardino Radici Taurasi | italia.md |
| **Nerello Mascalese** | Etna-druen – mellom Pinot Noir og Nebbiolo | Graci, Girolamo Russo, Terre Nere | italia.md |
| **Carricante** | Italias mest mineralske hvit – Chablis-aktig | Benanti Pietramarina (Etna Bianco Superiore) | italia.md |
| **Mencía** | Bierzo – Burgund-elegance + nord-Rhône-mineralitet | Raúl Pérez, Descendientes de J. Palacios | spania.md |
| **Godello** | Galicias mineralske hvit, bro fra Albariño | Rafael Palacios Louro do Bolo / As Sortes | spania.md |
| **Xinomavro** | Hellas' "Nebbiolo" – syre, tannin, fiol, tjære | Thymiopoulos Naoussa, Kir-Yianni Ramnista | ovrige-regioner.md |
| **Assyrtiko** | Vulkansk salt-mineralsk hvit fra Santorini | Sigalas, Argyros, Gaia Wild Ferment | ovrige-regioner.md |
| **Furmint (tørr)** | Tokaj-mineralitet – Burgund-aktig på vulkan | István Szepsy, Oremus Mandolás | ovrige-regioner.md |
| **Trousseau / Poulsard** | Lett, parfymert rødt fra Jura | Stéphane Tissot, Domaine de la Tournelle | frankrike.md |
| **Blaufränkisch (Lemberger)** | Strukturert østerriksk rødvin – Nebbiolo-slektning | Moric, Uwe Schiefer, Heinrich | ovrige-regioner.md |
| **Schioppettino / Pignolo** | Friulis peppra, tanniske rødviner | Ronchi di Cialla, Moschioni | italia.md |
| **Chenin Blanc (tørt)** | Strukturert hvit, lagringsdyktig | Domaine Huet (Vouvray), Joly (Savennières), Sadie (Swartland) | frankrike.md |
| **Baga** | Bairradas "atlantiske Nebbiolo" | Luís Pato, Filipa Pato, Niepoort-prosjektet | portugal.md |

---

## 3. Servering – kjerneregler

For dybde (alle vinstiler, glass-merker, dekantering per vin, kjeller-betingelser): se `deep-knowledge/servering-og-lagring.md`.

### Temperatur-hovedregler (norsk leilighet 21–22°C)

| Stil | Temp | Praktisk |
|---|---|---|
| Søt dessertvin | 5–7°C | Rett fra kjøleskap |
| Champagne ung | 6–8°C | Standard kjøleskap |
| Champagne kompleks (vintage, BdB modent NV) | 8–10°C | 15 min ut av kjøleskap |
| Frisk hvit (Pinot Grigio, Muscadet) | 7–9°C | Standard |
| Mineralsk hvit (Chablis, Sancerre, Albariño) | 9–11°C | 5 min ut |
| Fyldig hvit (Burgund Premier+, Jura) | 10–12°C | 10–15 min ut |
| Off-dry hvit (Mosel Spätlese) | 8–10°C | Standard |
| Rosé | 8–12°C | Provence kald, Tavel lett varm |
| Lette røde (Beaujolais cru, kjølig Pinot) | 12–14°C | 20 min i kjøleskap |
| Medium røde (Barbera, Sangiovese) | 14–16°C | "Kjeller"-temperatur |
| Fyldige røde (Bordeaux, Barolo, Amarone) | 16–18°C | 30 min i kjøleskap |

**"Romtemperatur" er en myte fra før sentralvarme.** I norsk leilighet skal nesten all rødvin kjøles 15–30 min før servering.

### Dekantering – fire scenarier

1. **Ung tannisk rødvin** (Barolo, Bordeaux Cru Classé, CdP, Brunello, Amarone): 1–4 timer i karaffel
2. **Eldre rødvin med sediment** (10+ år): hell forsiktig, 15–30 min lufting maks
3. **Lukket ung vin** ("dumb phase"): 30–60 min, prøve underveis
4. **IKKE dekanter:** Gammel Burgund/Mosel (10+), vintage Champagne 15+, lette røde

### Glass – minimum

- 6 universale tulipan-form (Riedel Veritas Universal eller ZALTO)
- 6 Champagne-tulipaner (ikke flutes – Champagne av kvalitet trenger volum)
- (Valgfritt) 2–4 Burgund-glass for Barolo/Amarone/aldret Pinot Noir

---

## 4. Matparing – de ti lovene

Glem "hvit til fisk, rød til kjøtt". Dette er prinsippene som faktisk gjelder:

1. **Vekt-match** – lett vin med lett mat, fyldig med fyldig
2. **Syre i mat trenger syre i vin** – vinaigrette, tomatsaus, sitrus
3. **Tannin trenger protein og fett** – biff binder tannin; tannin + fisk = metallsmak
4. **Fett trenger syre/tannin/bobler** – smørsaus + Chablis, fettribbe + Champagne
5. **Salt + søtt = magisk** – Sauternes/Roquefort, Port/Stilton, PX/sjokolade
6. **Salt gjør tannin mildere** – saltet biff tar ung Bordeaux bedre enn naken
7. **Umami senker fruktighet** – sopp/parmesan trenger tertiær vin eller ung fruktig
8. **Sukker i mat trenger mer sukker i vin** – dessert > vin = vinen smaker tørr/sur
9. **Chili + alkohol = brann** – jo høyere alkohol jo verre. Off-dry Riesling 8 % er trygt
10. **Eddik er vinens fiende** – krever vin med veldig høy syre og lavt tannin, eller drikk vann

For klassiske parringer per matrett: se `deep-knowledge/servering-og-lagring.md`.

---

## 5. Klassiske vinmordere

Mat som ødelegger nesten enhver vin – velg vinen med omhu eller drikk vann/øl:

- **Vinaigrette og syrlige dressinger** – eddik dominerer
- **Sterk sennep (Dijon ung)** – isothiocyanat dreper tannin
- **Chili** – jo sterkere jo verre; capsaicin forsterker alkohol-brenning
- **Asparges** – svovel-forbindelser gjør Sauvignon Blanc bitter
- **Råløk og rå hvitløk** – svovel-flyktig dominerer aromaer
- **Kapers, oliven, anchovis i mengde** – salt + bitter binder tannin
- **Rå ananas** – bromelain bryter ned proteiner inkludert vinens
- **Frisk mynte** – dominerer alle vinaromaer
- **Sjokolade mot tørr rødvin** – krever søt vin (Port, PX, Banyuls)
- **Tunfisk-sashimi/tartar** – jod reagerer med tannin → metallsmak

---

## 6. Anti-hallusinerings-sjekkliste

Før Claude leverer en anbefaling, sjekk:

- [ ] Vivino-historikk lest? (`data/vivino/full_wine_list.csv`)
- [ ] Smaksprofil konsultert? (`knowledge/smaksprofil.md` – blindspots, no-go)
- [ ] Relevant deep-knowledge-fil lest hvis anbefaling er region-spesifikk?
- [ ] Polet-tilgjengelighet verifisert via `tools/vinmonopolet.py`?
- [ ] Klokke-profil hentet hvis brukeren refererer til kjent vin?
- [ ] Produsentens rykte og stil konsistent med kontekst?
- [ ] Årgang relevant for regionen? (Bordeaux/Burgund/Champagne/Piemonte/Mosel = ja, varmt New World = mindre)

Hvis usikker: si "jeg vet ikke" eller "denne påstanden vil jeg verifisere først".

---

## 7. Feedback-løkken: hvordan smaksprofil og lessons oppdateres

Dette er **kritisk** for at systemet skal forbedres over tid. Smaksprofil og lessons er **levende dokumenter**.

### Når bruker korrigerer en anbefaling

→ Oppdater `tasks/lessons.md` umiddelbart med format:
```
## YYYY-MM-DD – kort tittel
**Hva skjedde:** ...
**Hvorfor det var feil:** ...
**Hva jeg gjør annerledes nå:** ...
```

### Når bruker bekrefter en ny preferanse

(f.eks. "jeg likte Mencía fra Bierzo, gjerne mer av det")

→ Oppdater `knowledge/smaksprofil.md`:
- Legg til drue/region i "Druer du vet du liker" eller "Regioner du dras mot"
- Hvis det fyller en blindspot, oppdater "Blindspots"-seksjonen

### Når bruker rapporterer dårlig opplevelse

→ Oppdater `knowledge/smaksprofil.md`:
- Legg til på "No-go-liste" hvis spesifikk vin
- Legg til på "Druer/regioner som har bommet" hvis et mønster

### Når ny Vivino-eksport kommer

1. Overskriv `data/vivino/full_wine_list.csv` (kolonnene er stabile)
2. Analyser nye ratings: er det noen nye mønstre? Nye favoritter? Bekreftede no-go?
3. Oppdater `knowledge/smaksprofil.md` med ev. nye sterke mønstre
4. Vekt nye ratings tyngre enn gamle (smaken modnes)

### Deep-knowledge er IKKE bruker-spesifikk

Filer i `deep-knowledge/` skal være nøytral fagreferanse. Ingen "brukerens 4.6", ingen "for deg", ingen no-go-lister. Hvis Claude oppdager bruker-spesifikke notater i deep-knowledge, **flytt dem til smaksprofil.md** og strip filen.

Forbindelsen mellom region-fakta og bruker-preferanse skjer på inferens-tid (Claude leser begge filer og syntetiserer).

---

## 8. Deep-knowledge oppslag

| Forespørsel inneholder | Les |
|---|---|
| Barbera, Nebbiolo, Barolo, Barbaresco, Amarone, Chianti, Brunello, Etna, Aglianico, italiensk | `deep-knowledge/italia.md` |
| Riesling, Mosel, Rheingau, Pfalz, Nahe, Spätburgunder, GG, Prädikat, tysk | `deep-knowledge/tyskland.md` |
| Champagne, Cava, Franciacorta, Crémant, Sekt, musserende, BdB, BdN | `deep-knowledge/champagne-musserende.md` |
| Burgund, Bourgogne, Bordeaux, Rhône, Loire, Jura, Alsace, Beaujolais, Madiran, Cahors, Bandol | `deep-knowledge/frankrike.md` |
| Rioja, Ribera, Priorat, Bierzo, Galicia, Sherry, Manzanilla, Mencía, Albariño, Godello | `deep-knowledge/spania.md` |
| Port, Douro, Dão, Bairrada, Madeira, Vinho Verde, Touriga, Baga | `deep-knowledge/portugal.md` |
| Naturvin, orange, lavinngrep, qvevri, amfora, Cornelissen, Radikon, Gravner | `deep-knowledge/naturvin-orange.md` |
| Gewürztraminer, Viognier, Torrontés, Muscat, aromatisk hvit | `deep-knowledge/aromatisk-hvit.md` |
| California, Oregon, Australia, New Zealand, Chile, Argentina, Sør-Afrika, Uruguay | `deep-knowledge/new-world.md` |
| Pinot Noir (på tvers av regioner / sammenligning) | `deep-knowledge/pinot-noir.md` |
| Hellas, Tokaj, Østerrike, Slovenia, Georgia, Lebanon, Sveits, Furmint, Xinomavro, Assyrtiko, Grüner Veltliner, Blaufränkisch | `deep-knowledge/ovrige-regioner.md` |
| Serveringstemperatur, glass, dekantering, lagring, vinkjøleskap, matparing-kjemi, klassiske parringer | `deep-knowledge/servering-og-lagring.md` |
| Importør, Vinmonopolet-utvalg, lanseringer, vintage-årganger, lagringsstrategi, Polet-perler, vinfeller | `deep-knowledge/norsk-marked.md` |

**Pro-tips:** for tverrgående spørsmål ("hva drikker jeg til osso buco?") les både region-fil (italia.md) OG `servering-og-lagring.md` (matparing). For "noe nytt jeg vil like" les `smaksprofil.md` først og synthesize fra adjacent-tabellen i seksjon 2.
