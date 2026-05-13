# Score-database

Bruker-kuratert database over vinanmeldelser fra eksterne kilder
(DN, magasiner, vinklubber, brukerens egne smaksnotater).
Leses av `tools/scores.py` og brukes som høyeste-prioritets kvalitetssignal
i `tools/value_score.py` — over Aperitif og Vivino.

## Skjema

Hver fil i denne mappen er én kilde. Filnavn = kilde-slug. Format:

```markdown
---
kilde: <kilde-navn>
test: <tema/test-navn>
dato: YYYY-MM-DD
forfattere: <navn> (<initialer>), ...
skala: <skala-beskrivelse>
url: <lenke>
antall_viner: <N>
---

# <Overskrift>

> Kort kontekst.

## <Seksjon>

### [<score>] <Vinnavn> — Varenummer <varenr>
- **Produsent:** <navn>, <region>, <land>
- **Pris:** <NNN.NN> kr
- **Utvalg:** <Basis/Bestillings/Tilleggs/Parti>
- **Importør:** <navn>
- **Anmelder:** <navn>
- **Notat:** <smaksnotat>
```

**Kritiske felt for parsing:** `Varenummer <NN>` i overskrift, score i firkant-parentes
`[NN]`, og `- **Score:** NN` ELLER score-en i overskriften.

`tools/scores.py` indekserer **alle** `*.md` i denne mappen automatisk.
Filer som ikke følger skjemaet ignoreres stille.

## Hvordan legge til en ny kilde

1. Opprett `knowledge/scores/<kilde-slug>.md`
2. Følg skjemaet over. Frontmatter er valgfri men anbefalt.
3. Hver vin skal ha overskrift med `Varenummer <NN>` slik at den kan
   slås opp.
4. Kjør `python3 -c "from tools.scores import index; print(len(index()))"`
   for å verifisere at parsing fungerer.

## Skala-konvertering

Når vi sammenligner scores fra ulike kilder bruker `value_score.py`:

| Kilde-skala | Konvertering |
|---|---|
| 0-100 (DN, Aperitif, Parker, Suckling) | Brukes direkte |
| 1-5 (Vivino) | Multipliseres med 20 |
| 1-20 (Jancis Robinson) | Multipliseres med 5 |
| 1-6 stjerner | Multipliseres med 16.67 |

## Eksisterende kilder

| Fil | Kilde | Tema | Viner |
|---|---|---|---|
| `dn_maislipp_rose_2026.md` | DN/Merete Bø + Else Navn | Maislipp rosé 2026 | 170 |

## Prioritering i value_score

`tools/value_score.py` sjekker kilder i denne rekkefølgen:
1. **knowledge/scores/** (denne databasen) — høyeste tillit
2. **Aperitif.no** — faglig norsk vurdering
3. **Vivino** — crowd-rating

Når flere kilder gir score for samme vin, vises alle, men databasens score
brukes som primær.
