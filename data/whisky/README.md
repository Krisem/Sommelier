# Whisky-ratinger

**Kristoffer dikterer i chat, Claude skriver raden.** Han skal ikke redigere denne fila.
Ølkanalen døde nettopp fordi innføring var manuelt filarbeid — siste Untappd-check-in er
2026-01-16, og 29 check-ins i 2025 ble til 1 i 2026.

En linje i chat holder, i vilkårlig rekkefølge:

> Lagavulin 16 – 4,5, røyk og tørr avslutning
> Jameson – 2,75, kjedelig
> Nikka From The Barrel – 4,25

**Skalaen er 5-punkt med kvart-trinn** (1,00–5,00), samme som Vivino og Untappd. Tersklene i
`beer_fit.py` og `user_fit` er kalibrert på den, så en annen skala ødelegger sammenlignbarheten.

**Notat er valgfritt.** Fritekst ble skrevet 4 av 211 ganger (1,9 %) på vin og øl, så karakteren
må klare seg alene. Et manglende notat skal aldri stoppe en flaske fra å bli registrert.

## Felter

| Felt | Merknad |
|---|---|
| `varenummer` | Polets varenr. Tomt hvis flasken ikke føres i Norge |
| `navn`, `destilleri` | Slås opp mot Aperitif/Polet — han trenger bare å huske omtrentlig |
| `rating` | 1,00–5,00, kvart-trinn |
| `dato` | ISO. Når den ble ratet, ikke når flasken ble kjøpt |
| `juridisk_kategori` | Scotch single malt, bourbon, irsk pot still, … — se `knowledge/whisky.md` |
| `alder` | **Tomt = NAS, og tomt er informasjon.** Ikke gjett |
| `torv` | ja / nei / lett / ukjent. «ukjent» er et gyldig svar |
| `fattype` | ex-bourbon, oloroso, PX, virgin oak, … |

## Før noen bygger en modell på denne fila

Tier-stigen spenner 0,65 poeng mens SD på brukerens egne ratinger er 0,61. Ved n=3 per bøtte er
95 % KI ±0,69 — bredere enn hele stigen. **Det trengs ~84 ratinger** før en fit-modell kan si
noe. Til da: ingen tier, ingen fit-score, ingen «du vil like denne».
