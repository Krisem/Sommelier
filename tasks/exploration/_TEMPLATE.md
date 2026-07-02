# <Frontier-navn> – utforskningsplan

> Formål: løse en blindsone ikke ved å *stryke* den, men ved å teste en konkret
> hypotese med ekte flasker fra Vinmonopolet. Oppdateres etter hvert som viner rates.
> Opprettet ÅÅÅÅ-MM-DD. Kilde-seksjon i [`knowledge/smaksprofil.md`](../../knowledge/smaksprofil.md) § «<blindsone>».
>
> <!-- Kopiér denne fila til tasks/exploration/<navn>.md og fyll ut. Slett HTML-kommentarene når du er ferdig. -->

## Hypotesen

<!-- Én skarp, falsifiserbar påstand om hva brukeren liker/ikke liker i denne kategorien.
     Formulér den så den KAN brekke – ellers er den ikke en hypotese. -->

**Målprofil (klokker):** Fylde X–Y · Friskhet Z+ · Garvestoff A–B · alk %-sone · tørrhet · eik-nivå.
<!-- Oversett hypotesen til søkbare Vinmonopolet-klokker + evt. druer/regioner. -->

**Ankere fra egen historikk:**
<!-- Konkrete viner fra full_wine_list.csv som støtter (og kontrasterer) hypotesen.
     Oppgi rating, klokker, årgang, kort hvorfor. Ta med minst én KONTRAST (svakere score)
     som markerer hvor hypotesen slutter å gjelde. -->
- 4.x <Vin> — <klokker>, <alk>, <kort note>
- *Kontrast (svakere):* 3.x <Vin> — <hvorfor den bommet>

<!-- Valgfritt: viktig kontekst (mat vs solo, sesong, temperatur) som farger tolkningen. -->

---

## Starter-flight – kjøp disse først (rangert)

<!-- 3–4 viner som tester KJERNEN av hypotesen med best value/treffsannsynlighet.
     Rangér etter treffsannsynlighet. Merk hver med [PRØVD]/[LIKNENDE]/[NYTT] (+ [USA] ved behov).
     Oppgi varenr, ca. pris, klokker, alk, hvorfor akkurat denne, og matforslag. -->

1. **<Vin>** (varenr xxxxx, ~pris kr) — `[LIKNENDE/NYTT]`
   Klokker **x/x/x**, alk %. <Hvorfor dette tester kjernen.> Til mat: <…>
2. …
3. …

---

## Full liste (verifisert på Vinmonopolet)

<!-- Bredere kandidatliste, gjerne gruppert per land/region/stil-akse. ALLE må være verifisert
     kjøpbare på Polet (butikk- eller bestillingsutvalg) på dato for opprettelse – noter datoen.
     Marker klokker som *sjekk* der de ikke er verifisert. «Rolle» = hva vinen tester i flighten
     (kjerne-blink, stretch/grensetest, value, mat-vin, …). -->

### <Land / region / akse>

| Vin | Varenr | Klokker | Alk | Ca. pris | Rolle |
|---|---|---|---|---|---|
| <Vin> | xxxxx | x/x/x | % | pris | <rolle> |

---

## Slik leser vi resultatene

<!-- Hva bekrefter hypotesen? Hva brekker den? Knytt hver GRENSETEST-vin til hva et lavt/høyt
     resultat vil bety. Dette gjør flighten til et eksperiment, ikke bare en handleliste. -->

Hypotesen holder hvis kjerne-flighten lander ~4.0+.
Grensene testes av:
- **<grensetest-vin>** → hvis den scorer lavt/høyt: <hva det betyr>.

## Tracking (fyll inn etter smaking)

<!-- Én rad per vin etter hvert som den rates. -->

| Vin | Kjøpt | Rating | Solo/mat | Notat |
|---|---|---|---|---|
| | | | | |

Etter hver rating: oppdater denne tabellen + hypotese-seksjonen i smaksprofil.md, og legg vinen i
full_wine_list.csv (via `tools/vivino_sync.py`) så den teller i statistikken.
