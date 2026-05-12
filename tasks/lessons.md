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

## 2026-05-12 – Off-dry tysk hvitt fungerer for brukeren
**Hva skjedde:** Tidligere profil-utkast påsto at off-dry/halvtørt Riesling ikke var testet.
**Hvorfor det var feil:** Brukeren har 4.0 på Ehlen Spätlese (off-dry), 4.1 på Auslese (søt), 3.8 på Hexamer Spätlese Trocken.
**Hva jeg gjør annerledes nå:** Behandle tysk Spätlese (både tørt og off-dry) som en bekreftet preferanse, ikke en hypotese.
