# Sommelier

Personlig digital sommelier som Claude Code-prosjekt. Anbefaler vin basert på Vivino-historikk + smaksprofil, parrer vin til mat, henter klokker/pris fra Vinmonopolet, og lærer av tilbakemeldinger.

## Hva systemet kan

**Anbefale**
- Foreslå viner ut fra dokumenterte preferanser (Vivino + smaksprofil) – med eksplisitt merking av `[PRØVD]`, `[LIKNENDE]` eller `[NYTT]`.
- Verifisere mot Polet (pris, lager, klokker, drueblanding, stil) – betinget, ikke automatisk: bare ved kjøp, value-spørsmål, eller når klokker faktisk hjelper.
- Finne lignende viner via klokke-profil-similarity (euklidsk avstand på fylde/friskhet/garvestoff).

**Vurdere**
- Velge mellom to viner du allerede eier eller har på en restaurant-vinliste – uten Polet-støy.
- Vurdere value og drikkevindu mot norsk pris- og vintage-realisme.
- Parre vin til mat med kjemisk presisjon – inkludert *tilberedningsmetode* (rå/dampet/stekt/grillet/braisert/røkt/friert) som egen dimensjon.

**Lære – kontinuerlig over tid**
- Hver ny Vivino-rating mater modellen: kjør `profile_stats.py` etter eksport, og auto-blokken i `smaksprofil.md` regenereres med ferske mønstre, snitt og blindspots.
- Når du sier "den vinen var glimrende" eller "ikke foreslå den igjen" – Claude oppdaterer `smaksprofil.md` umiddelbart (ny favoritt, ny no-go, eller bekreftet mønster). Smaksprofilen er et levende dokument, ikke en statisk fil.
- Korreksjoner av Claudes resonnement havner i `tasks/lessons.md`, slik at samme feil ikke gjentas.
- Klokke-profiler for topp-rated viner (4.5+) akkumuleres automatisk i `smaksprofil.md` som biprodukt av legitime søk – ankermassen for similarity-søk vokser uten ekstra arbeid.
- Nyere ratings vektes tyngre enn eldre (smaken modnes – snitt før 2018 = 3.67, etter 2024 = 3.89).

**Faglig dybde**
- WSET Level 3-nivå referansestoff per region, lastet on-demand.
- Servering, dekantering, lagring, glass, parring-kjemi i én oppslagsfil.

## Struktur

```
.
├── CLAUDE.md                          autoloaded instruksjon for Claude
│
├── knowledge/                         alltid lastet
│   ├── sommelier.md                   kjerne: drueprofiler, parring-lover, workflow
│   ├── smaksprofil.md                 personlig profil + auto-derivert statistikk
│   ├── vinmonopolet_rammeverk.md      klokker, stiler, matfarger
│   ├── wset_l2_sat.md                 WSET tasting-vokabular
│   └── _archive/                      historiske notater
│
├── deep-knowledge/                    on-demand (WSET L3)
│   ├── INDEX.md                       trigger-ord → fil-oppslag
│   ├── italia.md, frankrike.md, …     region-filer
│   ├── servering-og-lagring.md        temperatur, dekanter, glass, parring-kjemi, tilberedning
│   └── norsk-marked.md                importører, vintage, drikkevindu, Polet-strategi
│
├── data/
│   ├── vivino/                        Vivino-eksport (CSV)
│   └── reference/                     PDF-er (Food&Wine, Zoecklein, TWS Vintage)
│
├── tools/
│   ├── vinmonopolet.py                Polet-API + diskcache + klokke-similarity
│   ├── profile_stats.py               auto-derivér statistikk fra Vivino-CSV
│   └── aroma_wheel.html               D3-sunburst med Davis/Noble-hjul
│
└── tasks/
    ├── todo.md                        aktive oppgaver
    └── lessons.md                     læring fra korreksjoner
```

## Bruk

Start Claude Code i denne mappa – `CLAUDE.md` lastes automatisk. Skriv f.eks.:

- "Foreslå en rødvin under 300 kr til lasagne i kveld"
- "Hva drikker jeg til osso buco på torsdag?"
- "Jeg liker Etna Rosso – hva annet bør jeg prøve?"
- "Er denne verdt 450 kr?" + lenke/navn
- "Velg mellom disse to flaskene jeg har"  *(bilde / navn – ingen Polet-oppslag)*
- "Vurder denne vinkartet"  *(bilde fra restaurant)*

## Kommandolinje

```bash
# Auto-derivér smaksprofil-statistikk etter ny Vivino-eksport
python3 tools/profile_stats.py

# Smoke-test Polet-tilkobling
python3 tools/vinmonopolet.py

# Klokke-profil similarity – fra Python
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

**Hvis Polet endrer HTML-struktur:**
Regex-mønstrene i `tools/vinmonopolet.py` (`get_product_details`) må justeres. Test med:
```bash
python3 tools/vinmonopolet.py
```
