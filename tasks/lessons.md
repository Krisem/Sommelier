# Lessons learned

> **Korreksjoner og lærdom over tid.** Dette er én av to filer i feedback-løkken:
>
> - **`lessons.md`** (denne) – sommelier-feil og prosess-lærdom (f.eks. "ikke anbefal X uten å sjekke Y")
> - **`../knowledge/smaksprofil.md`** – brukerens preferanser (hva han liker, hva han ikke liker, blindspots)
>
> Når brukeren korrigerer noe: avgjør om det er en regel-lærdom (her) eller en preferanse-justering (smaksprofil). Begge kan oppdateres samtidig hvis relevant.

Format:
```
## YYYY-MM-DD – kort tittel
**Hva skjedde:** ...
**Hvorfor det var feil:** ...
**Hva jeg gjør annerledes nå:** ...
```

---

## 2026-05-12 – Bruk vmpws, ikke det "offisielle" APIet
**Hva skjedde:** Førsteversjon brukte `apis.vinmonopolet.no/products/v0` (subscription-key). Det returnerer kun varenummer + kortnavn – ubrukelig for anbefalinger.
**Hvorfor det var feil:** "Open"-tieren er låst. Stock-endepunktet er for wholesalere (404 ellers).
**Hva jeg gjør annerledes nå:** Bruk alltid `https://www.vinmonopolet.no/vmpws/v2/vmp/products/search`. Klokker skrapes fra produktsidens HTML, ikke fra APIet. Se `tools/vinmonopolet.py`.

_(2026-05-12 – Off-dry tysk hvitt: migrert til `knowledge/smaksprofil.md` som bekreftet preferanse.)_

## 2026-05-12 – Polet-oppslag skal være betinget, ikke automatisk
**Hva skjedde:** Workflow step 5 ble skrevet som om Polet alltid skulle sjekkes for hver anbefaling.
**Hvorfor det var feil:** Brukeren peker på at scenarier som restaurant-vinliste (bilde), valg mellom flasker han eier, og rene fagspørsmål ikke trenger Polet-oppslag i det hele tatt. Vinen er ofte ikke i Polets sortiment (restaurant), eller han skal ikke kjøpe noe nytt. Polet-oppslag forskyver fokus fra vurdering til verifisering, og bryter samtaleflyt.
**Hva jeg gjør annerledes nå:** Følg den betingede regelen i `CLAUDE.md` step 5. JA ved kjøp, value-spørsmål, similarity-søk, eller smak ved føling. NEI ved restaurant-vinliste, valg mellom eksisterende flasker, eller fagspørsmål. I tvil – spør "skal du kjøpe eller har du den?".

## 2026-05-12 – Vokse klokke-profil-tabellen som biprodukt
**Hva skjedde:** Tabellen "Klokke-profil for topp-viner" i `smaksprofil.md` hadde bare én oppføring etter første runde – for liten ankermasse til at klokke-baserte sammenligninger var presise.
**Hvorfor det var feil:** Jeg behandlet tabellen som noe brukeren skulle fylle. Den vokser ikke uten arbeid.
**Hva jeg gjør annerledes nå:** Hver gang jeg henter klokker for en vin brukeren har ratet 4.5+ – uansett om grunnen var anbefaling, value-sjekk eller similarity-søk – legger jeg profilen til tabellen automatisk. Klokker akkumuleres som biprodukt av legitime søk, ikke som forced lookups.
