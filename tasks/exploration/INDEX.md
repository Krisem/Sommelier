# Utforsknings-frontier – oversikt over åpne blindsoner

> Systematisk angrep på brukerens blindsoner. Autoritativ liste over selve blindsonene ligger i
> [`knowledge/smaksprofil.md`](../../knowledge/smaksprofil.md) § Blindspots – denne fila er *arbeidslaget*:
> hvordan vi løser dem, ikke bare at de finnes.

## Hva er en «frontier»?

En frontier er en blindsone vi angriper aktivt i stedet for å bare flagge `[NYTT]` og gå videre.
Hver frontier har en falsifiserbar hypotese om hva brukeren liker i kategorien, og en kuratert
flight av ekte flasker fra Vinmonopolet som tester den. Blindsonen løses ikke ved å *stryke* den,
men ved å samle ratings til mønsteret er klart.

## Arbeidsflyt

1. **Hypotese** – formuler én skarp, falsifiserbar påstand + målprofil (klokker) og ankere fra historikken.
2. **Verifisert flight på Polet** – kurater 3–4 kjerne-viner + en bredere liste, alle sjekket kjøpbare på Vinmonopolet.
3. **Rate** – smak, noter solo vs mat, før inn i flight-filas tracking-tabell.
4. **Oppdater** – juster hypotese-seksjonen i `smaksprofil.md`, oppdater tracking, og legg vinen i
   `full_wine_list.csv` (via `tools/vivino_sync.py`) så den teller i statistikken.

Ny frontier startes ved å kopiere [`_TEMPLATE.md`](_TEMPLATE.md) → `tasks/exploration/<navn>.md`.

## Frontiers

| Frontier | Status | Hypotese / spørsmål | Flight |
|---|---|---|---|
| New World rødvin | `aktiv` | Liker frisk, høyde-/kjølig-preget, strukturert og savory New World-rødvin – ikke den syltete, høy-alkohol, eik-tunge varmklima-stereotypien. (2 ratings 4.1/4.2, flight klar) | [`newworld.md`](newworld.md) |
| Aromatisk hvitvin | `planlagt` | Passer aromatiske druer (Viognier, Gewürztraminer, Torrontés) ham, eller trumfer syre-/mineralpreferansen den parfymerte stilen? | ikke opprettet ennå |
| Spanske rødviner | `planlagt` | Finnes det et mønster i spansk rødt (Rioja/Ribera/Bierzo/Priorat)? Kun 4 viner ratet i dag – for tynt til å konkludere. | ikke opprettet ennå |
| Pinot Noir generelt | `planlagt` | Hva skiller Pinot han elsker fra Pinot han hater? Stor varians (1.5–4.5) – er det region, pris, modenhet eller stil som avgjør? | ikke opprettet ennå |
| Naturvin / orange / hudkontakt | `planlagt` | Fungerer hudkontakt/naturvin for ham, eller kolliderer stilen med preferansen for renhet og struktur? Fraværende i datasettet. | ikke opprettet ennå |
| Asiatisk mat (paring) | `planlagt` | Hvilke viner (og øl) parrer best til thai/indisk/kinesisk? Ingen ratinger sammen med asiatisk mat i dag. | ikke opprettet ennå |

**Statuskoder:** `aktiv` = flight klar, ratings pågår · `delvis` = noen ratings, mønster ikke klart · `planlagt` = blindsone identifisert, flight ikke bygget ennå.

> **Verifikasjon (ikke en frontier):** [`scenario_test_2026-08-30.md`](scenario_test_2026-08-30.md) — tre reelle scenarier kjørt mot det utvidede snapshotet (ADR-024). Katalogen ble klart bedre; seks bugs i lesesiden, rangert.
