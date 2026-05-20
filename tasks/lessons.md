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

## 2026-05-20 – Gjettet drueblanding i stedet for å sjekke
**Hva skjedde:** OMA Piemonte Rosso 3L — parseren returnerte "Barbera 90 prosent". Jeg skrev "90 % Barbera + (sannsynligvis Nebbiolo/Dolcetto)" uten å åpne HTML-en. Faktisk blanding: 90 % Barbera + 5 % Dolcetto + 5 % Nebbiolo. Brukeren spurte hvorfor jeg ikke hadde sjekket.
**Hvorfor det var feil:** To feil samtidig. (1) Parser-bug: `re.search` på `aria-label="... \d+ prosent"` returnerer kun første match — alle blendinger ble kuttet til hoveddrue. (2) Selv når output-en ser "rar" ut (90 % uten resten oppgitt), skrev jeg "sannsynligvis X" i stedet for å verifisere mot kilden. Det er hallusinasjon kamuflert som hedging.
**Hva jeg gjør annerledes nå:** Hvis et drue-felt ender på "X prosent" der X < 100, er det per definisjon en blanding — sjekk produktsiden selv (curl/grep aria-label) før jeg gjetter. Fix: `re.findall` i `parse_product_html` slik at alle druer i blandingen returneres. La til dette som sjekkpunkt: prosent-sum skal være 100 eller blanding er ufullstendig.

## 2026-05-12 – Bruk vmpws, ikke det "offisielle" APIet
**Hva skjedde:** Førsteversjon brukte `apis.vinmonopolet.no/products/v0` (subscription-key). Det returnerer kun varenummer + kortnavn – ubrukelig for anbefalinger.
**Hvorfor det var feil:** "Open"-tieren er låst. Stock-endepunktet er for wholesalere (404 ellers).
**Hva jeg gjør annerledes nå:** Bruk alltid `https://www.vinmonopolet.no/vmpws/v2/vmp/products/search`. Klokker skrapes fra produktsidens HTML, ikke fra APIet. Se `tools/vinmonopolet.py`.

_(2026-05-12 – Off-dry tysk hvitt: migrert til `knowledge/smaksprofil.md` som bekreftet preferanse.)_

## 2026-05-12 – Polet-oppslag skal være betinget, ikke automatisk
**Hva skjedde:** Workflow step 5 ble skrevet som om Polet alltid skulle sjekkes for hver anbefaling.
**Hvorfor det var feil:** Brukeren peker på at scenarier som restaurant-vinliste (bilde), valg mellom flasker han eier, og rene fagspørsmål ikke trenger Polet-oppslag i det hele tatt. Vinen er ofte ikke i Polets sortiment (restaurant), eller han skal ikke kjøpe noe nytt. Polet-oppslag forskyver fokus fra vurdering til verifisering, og bryter samtaleflyt.
**Hva jeg gjør annerledes nå:** Følg den betingede regelen i `CLAUDE.md` step 5. JA ved kjøp, value-spørsmål, similarity-søk, eller smak ved føling. NEI ved restaurant-vinliste, valg mellom eksisterende flasker, eller fagspørsmål. I tvil – spør "skal du kjøpe eller har du den?".

## 2026-05-12 – Betinget presisering, ikke blanket "vin eller øl?"
**Hva skjedde:** Etter at øl-systemet ble likestilt med vin-systemet er det ikke gitt hvilket fag brukeren vil ha anbefaling fra. Et tidlig instinkt var "spør alltid om vin eller øl først".
**Hvorfor det var feil:** Friction-tungt. Mange forespørsler har et åpenbart svar (osso buco → vin-territorium, etter joggetur → øl-territorium). Å spørre hver gang ville bryte samtaleflyt.
**Hva jeg gjør annerledes nå:** Følg den betingede regelen i `CLAUDE.md` (seksjonen "Presisering – vin eller øl?"). Gå direkte ved klart lean. Spør én rask oppfølger ved ekte tvetydighet (pizza, BBQ, sushi, hverdagsmiddag, brunch). Foreslå begge fag side om side kun når situasjonen reelt støtter det.

## 2026-05-12 – Subagent-bruk skal være eksplisitt, ikke implisitt
**Hva skjedde:** Ved store oppgaver (utbygging av øl-kunnskap til Cicerone L2/3-nivå) ville en ad hoc-tilnærming vært å gjøre alt selv sekvensielt, og det ville sprengt hovedkonteksten.
**Hvorfor det var feil:** Subagenter er sterke nettopp her — parallelle, fokuserte, kan WebSearch-grunne fakta, leverer ferdige filer. Men kun hvis de briefes grundig.
**Hva jeg gjør annerledes nå:** Følg subagent-regelen i `CLAUDE.md` (seksjonen "Bruk av subagenter"). Spawn parallelt ved 3+ uavhengige underoppgaver. Brief hvert prompt med: peke på eksisterende filer for tone, length-target, required sections, "DO NOT"-liste, WebSearch-grunning for ferske fakta, background-mode der det er meningsfull annet arbeid. Verifiser sluttprodukt — sub-summaries beskriver intensjon, ikke resultat.

## 2026-05-12 – Vokse klokke-profil-tabellen som biprodukt
**Hva skjedde:** Tabellen "Klokke-profil for topp-viner" i `smaksprofil.md` hadde bare én oppføring etter første runde – for liten ankermasse til at klokke-baserte sammenligninger var presise.
**Hvorfor det var feil:** Jeg behandlet tabellen som noe brukeren skulle fylle. Den vokser ikke uten arbeid.
**Hva jeg gjør annerledes nå:** Hver gang jeg henter klokker for en vin brukeren har ratet 4.5+ – uansett om grunnen var anbefaling, value-sjekk eller similarity-søk – legger jeg profilen til tabellen automatisk. Klokker akkumuleres som biprodukt av legitime søk, ikke som forced lookups.

## 2026-05-14 – Sjekk repo-state før du jobber, ikke etter
**Hva skjedde:** Jeg jobbet med en feilaktig antagelse om at en value-funksjonalitet ikke eksisterte i kodebasen, fordi jeg ikke hadde fetchet origin. Brukeren hadde merget inn `tools/scores.py`, `tools/value_score.py`, og hele `knowledge/scores/`-strukturen — jeg fant det først etter at jeg hadde foreslått (og delvis bygget) en parallell CSV-løsning.
**Hvorfor det var feil:** "Jeg har ikke sett denne koden" er ikke det samme som "denne koden finnes ikke". `git status -s -b` viser kun lokal divergens fra remote-tracking — ikke om remote har nyere commits enn du har fetchet.
**Hva jeg gjør annerledes nå:** Når brukeren refererer til funksjonalitet som "vi har lagt til X", kjør `git fetch && git log HEAD..origin/main --oneline` *før* jeg konkluderer om noe eksisterer eller ikke. Repo-state må verifiseres mot remote, ikke bare lokal arbeidskopi.

## 2026-05-14 – LOGIC_VERSION i cache-nøkkel, ikke bare TTL
**Hva skjedde:** Innledende implementasjon av `compute_value_score`-cache hadde 7d TTL og nøkkel `(polet_id, vintage)`. Det betydde at hvis vi senere endret `_value_verdict`-algoritmen, ville cachen returnere gammel logikk i opptil en uke.
**Hvorfor det var feil:** TTL beskytter mot data-drift (priser/scorer endres). LOGIC_VERSION beskytter mot kode-drift (algoritmer endres). Disse er ortogonale.
**Hva jeg gjør annerledes nå:** Cache-nøkler for resultater som er funksjon av både input *og* logikk skal alltid prefikses med en `LOGIC_VERSION`-konstant. Bumping invaliderer alt manuelt. Se [ADR-004](../docs/ARCHITECTURE.md#adr-004-logic_version-i-value_score-cache-nøkkel).

## 2026-05-14 – Cache-flagg må være i nøkkel eller skippes
**Hva skjedde:** `compute_value_score(fetch_vivino=False)` skrev cache uten Vivino. Neste default-kall returnerte det stale halv-resultatet stille.
**Hvorfor det var feil:** Cache-nøkkelen ignorerte flaggene som styrer hvilke kilder som hentes. Eksperimentelle kall poisonet produksjons-cache.
**Hva jeg gjør annerledes nå:** Når en flagg-kombinasjon kan endre struktur på returverdien, må enten (a) flaggene være del av cache-nøkkelen, eller (b) ikke-default kombinasjoner skippe cache helt. Jeg valgte (b) — enklere, tryggere. Se [ADR-006](../docs/ARCHITECTURE.md#adr-006-cache-skippes-når-flagg-kombinasjon-er-ikke-default).

## 2026-05-14 – Throttle "mellom kall", ikke "før hvert kall"
**Hva skjedde:** `tools/aperitif.py` hadde `time.sleep(REQUEST_DELAY)` på toppen av `_http_get` — selv før det første kallet. Worst case ble 50 s for én vin-scan (5 kandidater × 1 s sleep + HTTP).
**Hvorfor det var feil:** Throttling skal beskytte ekstern tjeneste mot å bli hammet — det betyr "min tid mellom kall", ikke "minimum tid før hvert kall". Første kall trenger ingen throttle.
**Hva jeg gjør annerledes nå:** Spor `_LAST_HTTP_AT` globalt; sleep kun hvis `time.time() - _LAST_HTTP_AT < REQUEST_DELAY`. Se [ADR-008](../docs/ARCHITECTURE.md#adr-008-aperitif-throttle-som-min-mellom-modell-ikke-før-hver).

## 2026-05-14 – Fasett-API-verdier må være .code, ikke .name
**Hva skjedde:** Refactor av `_peer_percentile` til Polets Hybris fasett-API. Første forsøk brukte `mainCategory:Rødvin` (med stor R, fra `.name`-feltet) — returnerte 0 treff. Stille feil.
**Hvorfor det var feil:** Polets fasett-API matcher mot kode-verdier (lowercase, underscore), ikke visnings-navn. `Rødvin` ≠ `rødvin`.
**Hva jeg gjør annerledes nå:** Ved bruk av fasetter, hent alltid `product['main_category']['code']` (lowercase: `rødvin`, `musserende_vin`), aldri `name`. Dokumentert i `tools/vinmonopolet.py:search_with_facets` docstring og [ADR-009](../docs/ARCHITECTURE.md#adr-009-polet-fasett-api-i-_peer_percentile-ikke-3-fritekstsøk).

## 2026-05-14 – Innholds-baserte tester overlever refactors
**Hva skjedde:** En refactor som slettet `knowledge/ol_rammeverk.md` (innhold flyttet inn i `cicerone.md`) ville knust enhver test som hardkodet "BJCP må finnes i ol_rammeverk.md".
**Hvorfor det var feil:** Tester bør asserte på *innhold* (kontrakt), ikke filstruktur (implementasjon).
**Hva jeg gjør annerledes nå:** For knowledge-tester: søk på tvers av katalog ("BJCP finnes et sted i `knowledge/`"). Filnavn-baserte tester forbeholdt invariante filer (smaksprofil.md, sommelier.md, cicerone.md). Se [ADR-013](../docs/ARCHITECTURE.md#adr-013-innholds-baserte-tester-fil-agnostiske).

## 2026-05-14 – DRY-instinkt er feil i autoload-prompt
**Hva skjedde:** CLAUDE.md hadde vokst til 17 KB med duplikat-innhold fra `knowledge/sommelier.md` (workflow, deep-knowledge-tabell) og `knowledge/smaksprofil.md` (blindspots, pris-soner). Aggressive trim-forslag ville flytte duplikatet til "kanonisk kilde" og pek dit fra CLAUDE.md.
**Hvorfor det var delvis feil:** I LLM-workflows er ikke duplikasjon bare bortkastet plass. Synlighet i autoload-prompt påvirker faktisk oppførsel — hvis Claude hopper over workflow-step "les sommelier.md", er duplikatet load-bearing for korrekthet.
**Hva jeg gjør annerledes nå:** Trimme kun der den autoritative kilden alltid leses som del av workflow. Beholde duplikat der det er operasjonelt synlig (pris-soner, feedback-løkken-regler). DRY-prinsipp gjelder ikke ubetinget for instruksjons-prompts. Se [ADR-014](../docs/ARCHITECTURE.md#adr-014-claudemd-trimming--fjern-duplikat-behold-synlighet).

## 2026-05-14 – HTML-scraping må ha drift-vern
**Hva skjedde:** `tools/vinmonopolet.py` har 12+ regex over Polets DOM. Når Polet redesigner (sannsynlig <12 mnd), vil parsing returnere null/feil verdier *stille*.
**Hvorfor det er en risiko:** Stille feil er dyre å oppdage — brukeren ser bare at en anbefaling mangler klokker, og må gjette hvorfor.
**Hva jeg gjør annerledes nå:** Pin én rik HTML-fixture som drift-snapshot. 14 assertions mot kjente verdier. Når Polet endrer DOM, feiler pytest synlig med klar melding. Refresh-script dokumentert i fil. Se [ADR-011](../docs/ARCHITECTURE.md#adr-011-html-fixture-test-for-polet-drift). Tester offline, <1 s.

## 2026-05-14 – No-filter-bubble: tier er advarsel, ikke filter
**Hva skjedde:** Første integrasjon av user-fit-score (v0) hadde workflow-step "Filtrér ut `no_go` og merk `risky` eksplisitt", og demos rangerte tier-first før critic-score. Brukeren reagerte: "jeg ønsker ikke at vi skaper en boble der jeg ikke eksponeres for objektivt gode viner — jeg ønsker bare at de flagges som risky."
**Hvorfor det var feil:** Filter bubble er et veldokumentert recsys-anti-pattern. For en én-bruker-system uten kollektiv intelligens er det særlig alvorlig — smaksprofilen kan ikke utvides hvis høyt-scorede viner i blindspots aldri blir vist. Filter-instinktet kommer fra "reduser kognitiv last for brukeren", men det fjerner agency.
**Hva jeg gjør annerledes nå:** Default-rangering er kritiker-score, tier vises som merke. Tier-first-sortering aktiveres KUN ved eksplisitt brukerønske ("noe jeg garantert vil like", "trygge valg"). `risky` og `no_go` vises alltid med tydelig flagg, aldri skjules. Se [ADR-016](../docs/ARCHITECTURE.md#adr-016-no-filter-bubble-prinsippet-for-user-fit-score).

## 2026-05-14 – Dokumentér WHY, ikke bare WHAT, ved arkitekturvalg
**Hva skjedde:** Etter en stor audit/refactor-økt hadde vi mange designvalg uten dokumentert begrunnelse. Det ville gjort neste audit unødvendig dyr — vi ville måtte re-derivere konteksten for hvert valg.
**Hvorfor det er en risiko:** Uten Why-dokumentasjon vil neste refactor enten (a) gjenta gammel feil fordi grunnen ble glemt, eller (b) blokkere på trygg endring fordi ingen vet hvorfor den nåværende formen ble valgt.
**Hva jeg gjør annerledes nå:** Hver substantiell beslutning får en ADR i `docs/ARCHITECTURE.md` med Status / Kontekst / Beslutning / Konsekvenser / Alternativer vurdert. Mindre beslutninger får en linje i denne lessons-fila. README peker til ARCHITECTURE for design-spørsmål.
