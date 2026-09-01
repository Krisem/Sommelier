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

## Status: n=7 (2026-08-31)

Første diktering: Talisker 10 (4,25), Lagavulin 16 (4,00), Nikka Coffey Grain (4,50),
Laphroaig 10 (4,00), Glenmorangie Quinta Ruban 14 (3,75), Highland Park 12 (4,25),
Balvenie DoubleWood 12 (4,25).

Spredningen er smal — SD 0,23, seks av sju mellom 4,00 og 4,50 — og **bunnen er tom.** Det
mest verdifulle neste bidraget er flasker han *ikke* likte, ikke flere han likte.

## Felter

| Felt | Merknad |
|---|---|
| `varenummer` | Polets varenr. Tomt hvis flasken ikke føres i Norge |
| `navn`, `destilleri` | Slås opp mot Aperitif/Polet — han trenger bare å huske omtrentlig |
| `rating` | 1,00–5,00, kvart-trinn. Punktum som desimalskilletegn (fila er komma-separert) |
| `dato` | ISO. Når raden ble skrevet |
| `drukket_dato` | ISO, **eller grovere** — `2026-11` eller `2026-vinter` er gyldig. Se under |
| `anledning` | Ett ord med understrek: `kald_høstdag`, `sen_vår`, `etter_middag`, `med_venner` |
| `land`, `region` | Polets `district` der den finnes |
| `juridisk_kategori` | Scotch single malt, bourbon, irsk pot still, … — se `knowledge/whisky.md` |
| `abv` | Fra Polets produktside |
| `alder` | **Tomt = NAS, og tomt er informasjon.** Ikke gjett |
| `torv` | ja / nei / lett / ukjent. «ukjent» er et gyldig svar. Utled fra Polets Røyk-klokke der den finnes, og si fra i chat når verdien ikke er Polet-målt |
| `fattype` | ex-bourbon, oloroso, PX, virgin oak, … |
| `pris`, `notat` | Notat valgfritt |

## `dato` og `drukket_dato` er ikke det samme — og det var en ekte feil

De sju første radene ble skrevet med `dato = 2026-08-31`, dikteringsdatoen, fordi feltet
opprinnelig var definert som «når den ble ratet». Den definisjonen var for trang: Kristoffer
påpekte 2026-08-31 at **når** og **i hvilken situasjon** han drakk noe er en del av dommen, ikke
metadata rundt den — torv treffer på en kald høstdag, Highland Park sent på våren.

Derfor er `drukket_dato` og `anledning` egne felter, og `dato` er redusert til det den alltid
var: når raden ble skrevet. **De sju første radene har begge nye felter tomme** — den konteksten
er ikke rekonstruerbar uten at han husker den, og det er bedre at feltet står tomt enn at det
fylles med dikteringsdatoen én gang til.

Grov presisjon er nok. `2026-11` eller `2026-vinter` bærer sesongsignalet like godt som en
eksakt dato, og en tvungen ISO-dato ville invitert til å gjette.

## Hvorfor ikke en rating-app

Se [ADR-033](../../docs/ARCHITECTURE.md#adr-033-kontekst-fanges-i-dikteringen-ikke-i-en-app).
Kort: Untappd *var* den appen, fanget dato og sted automatisk, og døde likevel — og av 75
stedsmerkede check-ins var 72 «Untappd at Home», så stedsfeltet fanget ingenting.

## Før noen bygger en modell på denne fila

Tier-stigen spenner 0,65 poeng mens SD på brukerens egne ratinger er 0,61. Ved n=3 per bøtte er
95 % KI ±0,69 — bredere enn hele stigen. **Det trengs ~84 ratinger** før en fit-modell kan si
noe. Til da: ingen tier, ingen fit-score, ingen «du vil like denne».

**Og en advarsel til: sesong ser ut til å styre *valg*, ikke *karakter*.** Målt på de 89
ølratingene endrer median-ABV seg fra 6,5 % i kalde måneder til 5,4 % i varme, mens snittratingen
står stille (3,41 mot 3,37) og sterke øl scorer likt året rundt (3,51 mot 3,55). Hvis det holder
for whisky, vil en modell som bare ser karakterer aldri finne sesongmønsteret — det ligger i hva
han strekker seg etter, ikke i hva han gir. Derav `anledning`.
