# Sommelier

Personlig digital sommelier som Claude Code-prosjekt. Anbefaler vin basert på Vivino-historikk + smaksprofil, parrer vin til mat, og verifiserer alt mot Vinmonopolet.

## Struktur

```
.
├── CLAUDE.md                          autoloaded instruksjon for Claude
│
├── knowledge/                         evergreen kontekst
│   ├── sommelier.md                   sommelier-ekspertise (druer, regioner, servering, parring)
│   ├── smaksprofil.md                 personlig profil (oppdateres)
│   ├── vinmonopolet_rammeverk.md      klokker, stiler, matfarger
│   ├── wset_l2_sat.md                 WSET tasting-vokabular
│   └── _archive/                      historiske notater
│
├── data/
│   ├── vivino/                        Vivino-eksport (CSV)
│   └── reference/                     PDF-er (Food&Wine, Zoecklein, TWS Vintage)
│
├── tools/
│   └── vinmonopolet.py                vmpws-API helpers
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

## Re-eksport av Vivino

Last ned ny eksport fra Vivino og overskriv filene i `data/vivino/` (kolonnenavnene er stabile).

## Oppdatere helpers

`tools/vinmonopolet.py` snakker med Polets webshop-API (`vmpws/v2`). Hvis Polet endrer HTML-struktur, må regex-mønstrene i `get_product_details()` justeres. Test med:

```bash
cd "/Users/kristoffer/Claude Code/GitHub/Sommelier"
python3 tools/vinmonopolet.py
```
