# Sommelier

Personlig digital sommelier OG cicerone som Claude Code-prosjekt. Anbefaler både vin og øl basert på Vivino- og Untappd-historikk + felles smaksprofil, parrer drikke til mat med kjemisk presisjon, henter klokker/pris fra Vinmonopolet, og lærer av tilbakemeldinger over tid.

## Hva systemet kan

**Anbefale**
- Foreslå **vin og øl** ut fra dokumenterte preferanser (Vivino + Untappd + felles smaksprofil) – med eksplisitt merking av `[PRØVD]`, `[LIKNENDE]` eller `[NYTT]`.
- Verifisere mot Polet (pris, lager, klokker, drueblanding, stil for både vin og øl) – betinget, ikke automatisk: bare ved kjøp, value-spørsmål, eller når klokker faktisk hjelper.
- Finne lignende viner via klokke-profil-similarity (euklidsk avstand på fylde/friskhet/garvestoff).
- Be om presisering ("vin eller øl?") kun ved ekte tvetydighet — gå direkte når lean er åpenbar.

**Vurdere**
- Velge mellom to flasker du allerede eier eller har på en restaurant-/bar-meny – uten Polet-støy.
- Vurdere value og drikkevindu mot norsk pris- og vintage-realisme (vin) / friskhets-realisme (øl).
- Parre vin OG øl til mat med kjemisk presisjon – inkludert *tilberedningsmetode* (rå/dampet/stekt/grillet/braisert/røkt/friert) som egen dimensjon for begge fag.
- Sesongbevissthet for øl (juleøl november, fersk-hop september, lyse stiler sommer).

**Lære – kontinuerlig over tid**
- Hver ny Vivino-rating mater modellen: kjør `profile_stats.py` etter eksport, og auto-blokken i `smaksprofil.md` regenereres.
- Hver ny Untappd-rating mater modellen: kjør `untappd_stats.py` etter ny scrape, og en parallell øl-blokk i `smaksprofil.md` regenereres med stilfamilier, ABV-spenn, sesongmønster og topp/bunn.
- Når du sier "den vinen/ølet var glimrende" eller "ikke foreslå den igjen" – Claude oppdaterer `smaksprofil.md` umiddelbart. Smaksprofilen er et felles, levende dokument for vin og øl.
- Korreksjoner av Claudes resonnement havner i `tasks/lessons.md`, slik at samme feil ikke gjentas.
- Klokke-profiler for topp-rated viner (4.5+) akkumuleres automatisk i `smaksprofil.md` som biprodukt av legitime søk.
- Nyere ratings vektes tyngre enn eldre (smaken modnes).

**Faglig dybde**
- **Vin: WSET Level 3-nivå** referansestoff per region, lastet on-demand.
- **Øl: Cicerone Level 2/3-nivå** referansestoff per stilfamilie, lastet on-demand.
- Servering, dekantering, lagring, glass, parring-kjemi i parallelle oppslagsfiler for vin og øl.

## Struktur

```
.
├── CLAUDE.md                          autoloaded instruksjon for Claude
│
├── knowledge/                         alltid lastet
│   ├── sommelier.md                   vin-kjerne: drueprofiler, parring-lover, workflow
│   ├── cicerone.md                    øl-kjerne: tre akser, stilfamilier, friskhet, workflow
│   ├── smaksprofil.md                 felles profil + auto-derivert vin- og øl-statistikk
│   ├── vinmonopolet_rammeverk.md      klokker, stiler, matfarger
│   ├── ol_rammeverk.md                BJCP, ABV/IBU/SRM, hop/malt/gjær-taksonomi, glass
│   ├── wset_l2_sat.md                 WSET tasting-vokabular
│   └── _archive/                      historiske notater
│
├── deep-knowledge/                    on-demand
│   ├── INDEX.md                       trigger-ord → fil-oppslag
│   │
│   ├── (vin – WSET L3)
│   ├── italia.md, frankrike.md, tyskland.md, spania.md, portugal.md, …
│   ├── champagne-musserende.md, naturvin-orange.md, aromatisk-hvit.md
│   ├── new-world.md, pinot-noir.md, ovrige-regioner.md
│   ├── servering-og-lagring.md        vin-kjemi + tilberedningsmetode-tabell
│   ├── norsk-marked.md                vin-importører, vintage, drikkevindu, Polet
│   │
│   ├── (øl – Cicerone L2/3)
│   ├── ol-hopdominert.md              IPA, NEIPA, DDH, DIPA, Pale, Session, Cold IPA
│   ├── ol-belgisk.md                  Saison, Witbier, Tripel, Dubbel, Quad, Trappist
│   ├── ol-tysk-tjekkisk.md            Pilsner, Helles, Märzen, Bock, Schwarz, Hefeweizen
│   ├── ol-maltdominert.md             Brown, Porter, Stout, Imperial, BA, Barleywine
│   ├── ol-sur-vill.md                 Lambic, Gueuze, Flanders, Berliner, Gose, Wild Ale
│   ├── ol-servering-parring.md        øl-kjemi + parring-kjemi + tilberedning
│   └── ol-norge-norden.md             norske/nordiske bryggerier, Polet-rytme, kåringer
│
├── data/
│   ├── vivino/                        Vivino-eksport (CSV) – 172 viner, 104 ratet
│   ├── untappd/checkins.csv           Untappd-scrape (90 check-ins, 2019–2026)
│   └── reference/                     PDF-er (Food&Wine, Zoecklein, TWS Vintage)
│
├── tools/
│   ├── vinmonopolet.py                Polet-API + diskcache + klokke-similarity (vin OG øl)
│   ├── profile_stats.py               auto-derivér vin-statistikk fra Vivino-CSV
│   ├── untappd_stats.py               auto-derivér øl-statistikk fra Untappd-CSV
│   └── aroma_wheel.html               D3-sunburst med Davis/Noble-hjul
│
└── tasks/
    ├── todo.md                        aktive oppgaver
    └── lessons.md                     læring fra korreksjoner (vin og øl)
```

## Bruk

Start Claude Code i denne mappa – `CLAUDE.md` lastes automatisk. Skriv f.eks.:

**Vin**
- "Foreslå en rødvin under 300 kr til lasagne i kveld"
- "Hva drikker jeg til osso buco på torsdag?"
- "Jeg liker Etna Rosso – hva annet bør jeg prøve?"
- "Er denne verdt 450 kr?" + lenke/navn

**Øl**
- "Foreslå en IPA jeg ikke har prøvd"
- "Hva passer til Wienerschnitzel?"
- "Anbefal et juleøl i år"
- "Hva er forskjellen på West Coast og NEIPA?"

**Begge fag**
- "Hva drikker jeg til pizza i kveld?"  *(forventer "vin eller øl?"-oppfølger)*
- "Velg mellom disse to flaskene jeg har"  *(bilde / navn – ingen Polet-oppslag)*
- "Vurder dette vinkartet" eller "dette ølkartet"  *(bilde fra restaurant)*

## Kommandolinje

```bash
# Auto-derivér vin-statistikk etter ny Vivino-eksport
python3 tools/profile_stats.py

# Auto-derivér øl-statistikk etter ny Untappd-scrape
python3 tools/untappd_stats.py

# Smoke-test Polet-tilkobling (dekker både vin og øl)
python3 tools/vinmonopolet.py

# Klokke-profil similarity – fra Python (samme for øl: bare bytt kategori)
python3 -c "
from tools.vinmonopolet import find_similar_by_clocks
hits = find_similar_by_clocks(
    target_clocks={'Fylde': 8, 'Friskhet': 9, 'Garvestoffer': 7},
    queries=['Barbera d Alba', 'Dolcetto', 'Nebbiolo Langhe'],
    max_price=400,
    category='Rødvin',
    top_k=5,
)
for h in hits:
    print(h['distance'], h['product']['name'])
"

# Aroma-hjul – åpne i nettleser
open tools/aroma_wheel.html
```

## Cache

Polet-kall caches på disk i `~/.cache/sommelier/` (search 24t, details 7d). Mappa kan slettes når som helst for å resette. Reduserer både ventetid og rate-limit-risiko.

## Vedlikehold

**Etter ny Vivino-eksport:**
1. Overskriv `data/vivino/full_wine_list.csv` (kolonner er stabile).
2. Kjør `python3 tools/profile_stats.py` – auto-blokken i `smaksprofil.md` regenereres.
3. Be Claude om å gjennomgå mønstre – nye favoritter / no-go / oppdatert blindspots.

**Etter ny Untappd-scrape:**
1. Untappd har ingen åpen eksport — full historikk krever autentisert Playwright-scrape (Claude kan kjøre det). Etter at `data/untappd/checkins.csv` er oppdatert:
2. Kjør `python3 tools/untappd_stats.py` – øl-blokken i `smaksprofil.md` regenereres.
3. Be Claude om å gjennomgå nye stiler / bryggerier / sesongmønstre.

**Hvis Polet endrer HTML-struktur:**
Regex-mønstrene i `tools/vinmonopolet.py` (`get_product_details`) må justeres. Test med:
```bash
python3 tools/vinmonopolet.py
```
