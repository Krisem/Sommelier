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

## 2026-08-31 – Bær skillet fra der det er kjent, ikke utled det fra utseendet
**Hva skjedde:** Da blindsonene ble skrevet om fra engelsk til norsk, trengte `_blindspot_hit` å vite hvilke needles som var auto-deriverte «<Land> <Kategori>» (matches eksakt) og hvilke som var kuratert prosa (matches som substring). Jeg avgjorde det på needelens FORM: ender den på en kategori, er den sammensatt. «Aromatisk hvitvin» ender også på en kategori, ble lest som land «Aromatisk», og spesifisitets-regelen fjernet dermed region-treffet til sju italienske musserende.
**Hvorfor det var feil:** Informasjonen fantes allerede — needelen kom fra én av to navngitte seksjoner i `smaksprofil.md` — men jeg kastet den ved parsing og gjettet den tilbake senere. Et heuristikk-basert gjenkall av noe som var kjent eksakt er alltid et tap, og det feiler stille.
**Hva jeg gjør annerledes nå:** Når to ting skal behandles ulikt, bær skillet fra der det er kjent (her: `rules["blindspots_land_kategori"]` fra parsingen). Utleder du det fra utseendet senere, gjetter du. Fanget fordi jeg diffet klassifiseringen av hele katalogen før og etter — 137 endrede varer der jeg forventet 126, og de 11 ekstra var funnet.

## 2026-08-31 – Et vokabular-bytte kan innføre en feil den gamle formen skjulte
**Hva skjedde:** Blindsonene gikk fra «United States White Wine» til «USA Hvitvin». Substring-matchingen som hadde fungert på den engelske formen ville med den norske stemplet 15 hvitviner fra Spania, Portugal, Østerrike, Italia, New Zealand og Argentina som «USA Hvitvin» — «USA» er tre bokstaver og finnes inni «Usatges», «Sausal», «Sousa» og «Susana».
**Hvorfor det var feil å ikke se det først:** Den engelske formen hadde fire ledd og skjulte risikoen bak kravet om at alle måtte finnes. Jeg antok at et vokabular-bytte var nøytralt for matche-logikken. Det er det ikke: kortere tokens er farligere tokens.
**Hva jeg gjør annerledes nå:** Ved bytte av vokabular, mål den gamle og den nye matche-veien mot hele datagrunnlaget og se på DIFFEN, ikke bare på at den nye virker. Her ga det 15 konkrete rader, som ble testen.

## 2026-08-31 – Grønn av feil grunn, i begge retninger
**Hva skjedde:** To ganger samme dag. (1) En test for «nettverksbom faller tilbake på snapshotet» passerte en mutasjon som fjernet fallback-en — den traff en tidligere gren (`if not wine_name`) og nådde aldri koden den skulle teste. (2) Da `active_only` ble snudd til default, falt fem filtertester fordi fixture-radene manglet `status` — de testet altså pris- og navnefiltre på rader som ble borte av en helt annen grunn.
**Hvorfor det er samme feil:** En test kan være grønn fordi koden virker, eller fordi den aldri kom dit. Og en fixture som mangler et felt produksjonsdata alltid har, tester noe annet enn den later som.
**Hva jeg gjør annerledes nå:** Muter alltid — men muter det NØYAKTIGE uttrykket testen påstår noe om, og sjekk at det er DEN testen som faller. Fixtures skal ligne produksjonsrader på de feltene koden faktisk leser.

## 2026-08-31 – Timeouten var kortere enn siden, og drift-vernet meldte feil årsak
**Hva skjedde:** Aperitif-sveipen avbrøt på side 222 etter 220 siders arbeid med «svarte ikke på 4 forsøk». Jeg antok rate-limiting. Sidene svarte 200 på tre forsøk rett etterpå — de tar bare 0,4–12 sekunder, mens `_http_get` har 15 sekunders default-timeout.
**Hvorfor det var feil:** Jeg gjenbrukte en timeout kalibrert for produktsider på et helt annet arbeid (390 kB listesider), og lot drift-vernet rapportere «svarer ikke» om noe som i virkeligheten var «svarer for sakte for MIN grense». Feilmeldingen pekte utover, mot serveren, når årsaken lå i mitt eget kall.
**Hva jeg gjør annerledes nå:** Mål responstiden FØR du setter en grense på den, og la den som starter en lang jobb eie sin egen timeout. Og: et vern som kaster to timers arbeid trenger mellomlagring, ellers er kostnaden ved å være forsiktig høyere enn feilen det verner mot.

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

## 2026-06-13 – Ikke avskriv lett Chardonnay for tidlig
**Hva skjedde:** Jeg vurderte Famille Morel Les Pierres Dorées (Beaujolais Blanc) som "trolig litt tynn og uinteressant" for brukerens profil, med argumentet at han foretrekker mineralsk-stramt (Jura, Riesling GG). Brukeren ga den 4.1 — godt over forventet.
**Hvorfor det var feil:** Jeg overekstrapolerte "du liker struktur" til "du liker ikke lett hvitvin". Beaujolais kalkstein-Chardonnay fra biodynamisk produsent kan ha tekstur og presisjon selv uten Jura-fylde. Én datatype (stilpreferanse) trumfet ikke den faktiske vinen.
**Hva jeg gjør annerledes nå:** Ikke diskvalifiser lettere Chardonnay-stiler fra et godt sted (Pierres Dorées, Mâcon, Chablis) uten konkret info om vinen. Vurder produsent og driftsform. Beaujolais Blanc ≠ generisk light white.

## 2026-05-14 – Dokumentér WHY, ikke bare WHAT, ved arkitekturvalg
**Hva skjedde:** Etter en stor audit/refactor-økt hadde vi mange designvalg uten dokumentert begrunnelse. Det ville gjort neste audit unødvendig dyr — vi ville måtte re-derivere konteksten for hvert valg.
**Hvorfor det er en risiko:** Uten Why-dokumentasjon vil neste refactor enten (a) gjenta gammel feil fordi grunnen ble glemt, eller (b) blokkere på trygg endring fordi ingen vet hvorfor den nåværende formen ble valgt.
**Hva jeg gjør annerledes nå:** Hver substantiell beslutning får en ADR i `docs/ARCHITECTURE.md` med Status / Kontekst / Beslutning / Konsekvenser / Alternativer vurdert. Mindre beslutninger får en linje i denne lessons-fila. README peker til ARCHITECTURE for design-spørsmål.

## 2026-07-02 – «Ikke på hylle» ≠ «utilgjengelig» (Polet Bestillingsutvalget)
**Hva skjedde:** Jeg konkluderte i utforskningsplanen at «Australia er tynt» fordi en subagent-sveip bare fant hylle-lagerførte viner, og kjølig-klima-shiraz var utsolgt der. Kristoffer utfordret: er det tynt fordi han har drukket lite, eller fordi jeg researchet dårlig? Live-sjekk viste 217 kjøpbare australske rødviner (52 kjølig-klima) – de beste lå i **Bestillingsutvalget** (bestillbare), ikke på hylle.
**Hvorfor det var feil:** (1) Jeg gjorde en subagents delvise sveip om til en konklusjon uten å verifisere. (2) Jeg likestilte «ikke på butikkhylle / Utgått i søk» med «utilgjengelig» – men Bestillingsutvalget er fullt kjøpbart. Brudd på elegance-sjekk spørsmål 3 (failure modes: filterboble/silent gap).
**Hva jeg gjør annerledes nå:** Før jeg kaller en kategori «tynn/utilgjengelig»: spør Polets vmpws-API (`/vmpws/v2/vmp/products/search?query=:relevance:mainCategory:rødvin:mainCountry:<kode>&fields=FULL`, virker fra browser-sidekontekst) og tell `buyable:true` på tvers av product_selection (Basis + Bestilling), ikke bare hylle-lager. Skill alltid «ikke rated i historikken» (ekte datablindsone) fra «ikke lett tilgjengelig» (ofte research-artefakt).

## 2026-07-04 – Spesifikt pol nevnt → MÅ verifisere lager i akkurat den butikken før anbefaling
**Hva skjedde:** Kristoffer ba om ett øl til en ostetallerken «som de har inne på polet på Røa». Repo-snapshotet er kun vin (ingen øl), så jeg anbefalte Boon Oude Geuze ut fra profil + generell sortimentskunnskap uten å sjekke Røa. Boon var ikke inne på Røa. Først etter det åpnet jeg polet.no live og fant at Røa faktisk hadde **3 Fonteinen Oude Geuze** (varenr 10945401, 5 stk) og Lindemans Oude Kriek Cuvée René (10202401) — begge bedre svar enn gjettet.
**Hvorfor det var feil:** Når brukeren navngir en konkret butikk, er «er den inne der?» selve premisset for spørsmålet — ikke en detalj som kan hedges. Å anbefale noe som «vanligvis føres» er verdiløst hvis han står på Røa og hylla er tom. Jeg lot fravær av øl i snapshotet bli en unnskyldning for å gjette i stedet for å bruke live-veien jeg faktisk hadde (Playwright mot vmpws).
**Hva jeg gjør annerledes nå:** Nevner brukeren et spesifikt pol (øl ELLER vin), er butikk-lager en HARD forutsetning: verifiser at anbefalingen er kjøpbar i akkurat den butikken *før* jeg nevner den. Oppskrift: finn store-ID (`/vmpws/v2/vmp/stores?fields=FULL&pageSize=500`, filtrer på navn) → søk med `...:availableInStores:<storeId>` og les `storesAvailability` per produkt. Snapshotet er wine-only og har ikke butikk-lager — for butikk-spesifikke spørsmål (og all øl) må jeg gå live via Playwright/vmpws, ikke gjette fra sortimentskunnskap. Aldri presenter en kandidat for et navngitt pol uten bekreftet lager der.

---

## 2026-08-29 – Anbefalte på klokke-likhet; klokkene skiller ikke kraft

**Hva skjedde:** Vespa Barbera 3 l (5280806) ble anbefalt. Kristoffer fant den for lett og ville
ha noe kraftigere – særlig relevant høst/vinter. Vinen har *identiske* klokker med hans høyest
ratede rødvin, Fenocchio Barbera d'Alba Superiore (4.6): Fylde 8, Friskhet 9, Garvestoffer 7,
samme stilmerkelapp «Frisk og fruktig», samme drue. Klokke-similarity pekte altså rett på den.

**Hvorfor det var feil:** Klokkene måler sensorisk profil, ikke konsentrasjon, fatpreg eller
kvalitetsnivå. To viner kan være 8/9/7 og likevel være 273 og 163 kr/L, Superiore med 6 mnd fat
+ 6 mnd flaske mot ren ståltank uten lagring. Jeg behandlet klokke-likhet som om den var
kvalitets- eller kraftlikhet. Den er verken.

**Hva jeg gjør annerledes nå:**
- Klokker brukes til å finne **stil-slektninger**, aldri til å rangere kraft eller kvalitet.
- Når han ber om «kraftigere»: les `metode` og `stil` i details (fat, appassimento, ripasso,
  lang gjæring), bruk appellasjonsnivå (Superiore/Riserva/DOCG > generisk regional DOC), og se på
  **literpris** – i lavprisenden er den en reell konsentrasjonsindikator.
- På 3 l spesielt: nesten alt ligger 145–200 kr/L og er bygget lett og lettdrukket. Vil han ha
  kropp der, bytt stilfamilie (appassimento, ripasso, Primitivo, Nero d'Avola, Aglianico,
  Montepulciano) framfor å lete etter en kraftigere utgave av en lett drue.
- **Ikke kjemp mot druen.** Barbera er syrerik og lett-til-middels i kropp per konstruksjon. At
  han elsker Barbera (4.6) og samtidig avviste denne er ikke en selvmotsigelse – det er formatet
  og kvalitetsnivået som skiller.

---

## 2026-08-29 – Defaultet til «noe han liker» i stedet for å utfordre briefen

**Hva skjedde:** Kristoffer påpekte at «jeg trenger en flaske rødvin» ikke burde gi en anbefaling
basert på hva han erfaringsmessig liker, men et returspørsmål om hva han faktisk er ute etter.

**Hvorfor det var feil:** En vag brief har mange gyldige svar, og «trygt valg fra historikken» er
bare ett av dem – ofte det som bommer på situasjonen. Vespa Barbera-bommen samme dag var like mye
en brief-svikt som en modellsvikt: klokke-similarity pekte rett, men ingen hadde spurt om han ville
ha noe kraftig. Å hoppe rett til anbefaling føles hjelpsomt og er det motsatte.

**Hva jeg gjør annerledes nå:** Se «Utfordre vage briefer» i `CLAUDE.md`. Kort: 2–3 spørsmål i ÉN
melding (mat/solo, lett/kraftig, hverdag/anledning), alltid med et default han kan si ja til, aldri
om det briefen allerede besvarer. Ett presist spørsmål slår tre generiske.

---

## 2026-08-30 – Handlet på en filesing som var 20 sekunder gammel

**Hva skjedde:** Under en sveip med fem parallelle agenter grep-et jeg `smaksprofil.md`, så seks
foreldede tall, og skrev et skript for å rette dem. Da skriptet kjørte, hadde D-agenten allerede
rettet alle seks. Skriptets `assert s.count(old) == 1` feilet på første substitusjon og avbrøt før
`open(p,'w')` – ingen skade. Med en blind `sed`-erstatning hadde jeg ikke oppdaget det i det hele
tatt, og med en «rett nye tall til enda nyere»-logikk kunne jeg ha korrumpert fila.

Samme dag: D fikk tom liste fra Vivino-skrapingen fordi E hadde navigert den **delte** Chromium-
instansen til vinmonopolet.no. Symptomet var identisk med «ingen nye ratinger».

**Hvorfor det var feil:** Jeg hadde selv skrevet ned regelen om å re-lese artefaktet og notere
revisjonen før man låser noe til et tall – og brøt den i samme sesjon. En lesning er et
øyeblikksbilde, ikke en tilstand. Med parallelle agenter er vinduet mellom lesning og skriving
sekunder, ikke minutter. Og jeg hadde serialisert D og E på browseren, men brøt serialiseringen
selv da jeg ga D en verifiseringsoppgave mens E fortsatt kjørte.

**Hva jeg gjør annerledes nå:**
- Skriv aldri en erstatning uten `assert count == 1` på det gamle innholdet. Skriptet skal
  nekte å kjøre hvis verden har endret seg, ikke gjette. Dette er billig og fanget feilen her.
- Sjekk md5 + mtime rett før skriving, ikke bare rett etter at en agent meldte seg ferdig.
- «Alt gjort» fra en agent er en påstand om intensjon, ikke om filtilstand – verifiser, men
  verifiser *rett før* du handler, ikke ett tur-retur tidligere.
- Én delt ressurs (browser, database, ekstern API) = én agent om gangen. Serialiseringen gjelder
  også de små tilleggsoppgavene jeg selv deler ut underveis.

---

## 2026-08-30 – Kjørte et dokumentert skript for å teste det, og muterte ekte data

**Hva skjedde:** Jeg oppdaget at to av fire kommandoer `CLAUDE.md` dokumenterer var ødelagte, fikset
importfeilen, og verifiserte ved å **kjøre dem**. Én av dem – `tools/seed_polet_store.py` – leser
`~/.cache/sommelier/` og skriver katalogen via `upsert_products`. Den la inn en rad fra mai-cachen
(`3187405`, `fetched_at: 2026-05-20`) i `data/polet/catalog.ndjson` mens en agent var midt i en
2–3 timers sveip mot samme fil.

**Den fremmede raden var det minste av skaden, og jeg oppdaget resten først i gjennomgangen før
commit — to timer senere.** `upsert_products` erstatter raden i sin helhet, så kjøringen slettet
også **`clock_buckets` fra 61 rødvinsrader** (to av dem står i klokke-tabellen i `smaksprofil.md`)
og overskrev **fire details-filer med eldre mai-data** — `fetched_at` gikk bakover og `url` byttet
fra relativ til absolutt form. Ingen av delene ga feilmelding, ingen test falt, og diffen så ut som
et normalt datasett i bevegelse blant 27 000 rader. Agenten oppdaget den fremmede raden, mistenkte en parallell skriver
og stoppet for å varsle – berettiget, siden `_write_catalog` er read-modify-write og to skrivere
gir stille tap.

Min første hypotese var at testsuiten skrev til ekte data (jeg hadde kjørt `pytest` mange ganger).
Den var feil: `tests/test_polet_store.py` har en autouse-fixture som peker `POLET_DIR` mot `tmp_path`.
Riktig svar lå i `git show HEAD:...` – raden fantes ikke i HEAD, og `seed_polet_store` stempler
`fetched_at` med cache-filas mtime.

**Hvorfor det var feil:** «Virker kommandoen?» og «hva gjør kommandoen?» er to forskjellige spørsmål,
og jeg svarte på det første ved å utløse det andre. Et skript med `upsert`, `seed`, `write`, `sync`
eller `refresh` i navnet er ikke en smoke-test – det er en mutasjon. At det står i dokumentasjonen
gjør det ikke trygt å kjøre; det gjør det bare dokumentert.

**Hva jeg gjør annerledes nå:**
- **Diff alltid mot `HEAD` før commit når flere skrivere har vært i en datafil.** «Filen er endret»
  sier ingenting; `git show HEAD:<fil>` og en felt-for-felt-sammenligning sier hva som forsvant.
  Det var slik de 61 radene ble funnet, og de ville ellers blitt committet som et tap ingen så.
- **Les hva et skript gjør før du kjører det for å teste at det kjører.** `grep -n "write\|upsert\|
  save\|unlink\|rmtree"` tar sekunder. `--help`/`--dry-run` først der det finnes.
- Verifiser importfeil med `python3 -c "import tools.X"` eller `py_compile`, ikke ved å kjøre `main()`.
- **Når du eier en delt ressurs ut til en agent, gjelder det deg selv også.** Jeg hadde nettopp
  skrevet at `data/polet/` var E sitt område, og skrev så dit selv en time senere.
- Ved fremmed skriving i en fil: `git show HEAD:<fil>` først for å avgjøre om raden er ny, og se på
  metadata-stempelet (her `fetched_at`) – det navngir ofte kilden.

---

## 2026-08-30 – «Grønn av feil grunn» var sesjonens mest gjentatte feil (3 instanser)

**Hva skjedde:** Tre ganger på én dag så en kontroll frisk ut mens den ikke kontrollerte noe:

1. **Blindspot-regelen fyrte 422 ganger** og virket derfor i drift. Treffene kom fra tre land av
   femten – Portugal, Chile, Uruguay – utelukkende fordi de staves likt på norsk og engelsk, pluss
   én tysk vin med ordet «Germany» i merkenavnet. 367 andre tyske viner fikk ingenting.
2. **En mutasjon som fjernet landoversettelsen overlevde testsuiten.** Assertions om at blindspot
   fyrer for Tyskland og Spania ble oppfylt av *kuratert prosa* som aldri rørte landtabellen.
3. **Unntakslista `UTEN_VARER` var foreldet** og undertrykte sjekken for fire regler. Sveipen hadde
   gitt alle fire varer; lista fortsatte å tie.

Beslektet: 291 tester var grønne gjennom seks reelle bugs, fordi de testet logikk på små fixtures
og ikke oppførsel ved katalogskala.

**Hvorfor det skjer:** Et treffantall, en bestått test og en tom feilliste er alle *fravær av
alarm*. Fravær av alarm er ikke bevis for at alarmen virker. Feilen er alltid stille, og den
overlever nettopp fordi den ser ut som suksess.

**Hva jeg gjør annerledes nå:**
- **Valider på fordeling, ikke på antall.** «422 treff» sier ingenting; «422 treff fordelt på 3 av
  15 land» sier alt. Samme for tiers, regler, kategorier.
- **Muteringstest hver fiks:** gjeninnfør feilen og krev at testen faller. En test som ikke faller
  på den gjeninnførte buggen, tester ikke buggen. (Fanget 15/15 til slutt i user_fit, 5 i
  value_score, 7 i vinmonopolet.)
- **Velg testdata som bare kan bestå av riktig grunn.** En libanesisk rødvin uten prosa bak seg kan
  kun treffe via landtabellen; en tysk vin kunne treffe via tre veier og beviste ingenting.
- **Unntakslister skal være selv-utløpende.** En oppføring som ikke lenger gjelder, skal feile
  testen og tvinges fjernet. Et unntak som ikke kan utløpe er en permanent blindsone med
  vennlig navn.
- **Skriv skalainvarianter, ikke tall.** `sample_size >= 0.9 * len(populasjon)` overlever at
  datasettet tidobles; `sample_size == 50` bekrefter buggen.
- **En kontroll som ikke rikker seg når du forventer at den skal, er et funn.** En uendret
  sanity-sjekk avslørte at en regelendring bare hadde landet i den ene av to kodeveier.

**Speilbildet, like viktig:** et NEGATIVT resultat fra et ukontrollert instrument er heller ikke et
funn. Samme dag rapporterte en agent «`data/polet/_meta.json` mangler → aldersmerkingen er blind»
som høyest prioriterte funn. Fila het `catalog_meta.json`; agenten hadde **gjettet filnavnet i
stedet for å slå opp konstanten**, og leste `FileNotFoundError` som bevis for at noe var galt med
systemet, når det var bevis for at noe var galt med spørsmålet. Verifiser instrumentet før du
rapporterer måleresultatet — i begge retninger. Det gjelder særlig ad-hoc-sjekker på siden av det
man tester nøye; det var der den slapp gjennom.

---

## 2026-08-30 – Skrivefunksjoner som bygger fra en mal, sletter alt utenfor malen

**Hva skjedde:** Tre varianter av samme feil dukket opp på én dag i `polet_store`:

1. `upsert_products` erstatter raden i sin helhet (`existing[code] = entry`) og tar dermed
   `clock_buckets` med seg. Rekkefølgen enumerering → prune → klokker er *påkrevd*, ikke en
   preferanse.
2. En `seed_polet_store`-kjøring utløste nettopp det og slettet klokkene på **61 rødviner** – usynlig,
   fordi radene ble *tommere* og ikke *færre*. En radtelling ga 14 081 → 14 082 og så uskyldig ut.
3. `_write_meta` bygde en fersk dict med tre nøkler, så ethvert katalogskriv ville slettet
   `category_completeness` – kompletthets-beviset bak teknisk gjeld #11, som ikke kan
   rekonstrueres uten å betale Polets timeskvote om igjen.

**Hvorfor det er samme feil:** alle tre bygger en ny struktur fra en fast mal i stedet for å flette
inn i den eksisterende. Malen er skrevet av den som eide feltet den gangen, og alt en senere
forfatter la til, forsvinner uten spor. Ingen av dem feiler; de bare glemmer.

**Hva jeg gjør annerledes nå:**
- **En skrivefunksjon som ikke eier hele strukturen, skal flette – ikke erstatte.** `_write_meta`
  leser nå eksisterende meta og oppdaterer kun sine tre avledede nøkler.
- **Ikke løs det med en hviteliste over kjente ekstra-felter.** Den brekker neste gang noen legger
  til et felt, altså nøyaktig feilen man prøver å fikse.
- **Bevart data må datere seg selv.** `completed_at` gjør en foreldet påstand synlig; en slettet
  påstand etterlater ingenting å oppdage.
- **Ved tap av felter: diff felt for felt, aldri radantall.** «Tommere» er usynlig for en telling.

---

## 2026-08-31 – Sju tall i egne planfiler og todo-poster viste seg feil ved etterprøving

**Hva skjedde:** Jeg sekvenserte restansen etter sveipen og etterprøvde hvert tall før jeg brukte
det. Sju av dem holdt ikke — alle fra dokumenter *dette prosjektet* hadde skrevet dagen før,
etter grundig research med QA-agent:

| Påstand | Faktisk |
|---|---|
| `v0.json` dekker 0,59 % av katalogen | **1,5 %** (409 av 27 402) |
| `full_wine_list.csv.bak` er tracket, konvensjonen er uklar | Ikke tracket. `*.bak` har ligget i `.gitignore` hele tiden |
| «Fase 2 av hvit/musserende/rosé: ~3–4 t, 13 625 produkter» | 13 625 var enumereringen, som var levert. Det som manglet var **942 details** |
| Aperitif-sveipen «skriver rett inn i `knowledge/scores/`-formatet» | Ville brutt ADR-003: `_combine_quality` rangerer den mappen over Aperitif, så 14 300 skrapede scorer hadde overkjørt 384 kuraterte |
| Aperitif-pagineringen | `?side=N` returnerer side 1 uansett. Fungerende form er `/pollisten/pollisten,7,<side>` |
| «Poeng t.o.m. ~side 475» | Poeng finnes t.o.m. minst side 540; slutter mellom 540 og 600 |
| «≈14 300 scorede varenumre» | Tak, ikke anslag: side 520 hadde 30 rader med poeng men 18 med varenummer |

Tre av dem ville kostet reelt arbeid: `knowledge/scores/`-feilen hadde stille degradert
value_score-hierarkiet, pagineringsfeilen hadde gitt 560 identiske sider, og hvis sveipen hadde
gått til produktsidene i stedet for listeradene var det 25 000 kall i stedet for 560.

**Hvorfor det skjer:** Et dokument skrevet av en grundig prosess *føles* som en målt kilde, særlig
når det sier «alle tall er målt i repoet, ikke anslått» og har en QA-linje øverst. Men et tall
arver ikke tilliten fra prosessen som produserte det — det var korrekt mot en tilstand som
tallet selv ikke navngir, og tilstanden har flyttet seg. Fire av de sju var korrekte da de ble
skrevet; de tre andre var aldri korrekte.

Beslektet, og verdt å se sammen: dette er samme feilklasse som «grønn av feil grunn» (2026-08-30).
Der var det en kontroll som ikke kontrollerte; her er det et tall som ikke måler. Begge ser ut som
belegg.

**Hva jeg gjør annerledes nå:**

- **Mål tallet på nytt før du bygger på det, også når kilden er egen dokumentasjon fra i går.**
  Kostnaden er sekunder; de sju feilene tok under ti minutter å avdekke til sammen.
- **Sonder et eksternt format med 3–5 kall før du planlegger et sveip på hundrevis.** Hele
  pagineringsfeilen og radformat-funnet kom fra 13 forespørsler.
- **Et tall uten revisjon er en påstand, ikke en måling.** Skriv `catalog.ndjson`-md5 eller
  commit-SHA ved siden av tallet, ellers kan neste leser ikke vite om det gjelder.
- **Når et tall spriker, si det høyt i dokumentet** — ikke rett det stille. Alle sju står nå i
  `todo.md` med både den gamle og den nye verdien, fordi «hvorfor endret dette seg» er et
  legitimt spørsmål neste gang.

---

## 2026-08-31 – Gjentok mutasjons-feilen fra dagen før, på en kommando merket som «sjekk»

**Hva skjedde:** Som siste close-out-sjekk kjørte jeg de dokumenterte kommandoene i `CLAUDE.md` for
å bekrefte at de virker — presedensen var `e664747`, der to av fire feilet på import.
`python3 -m tools.beer_fit` **skriver**, og satte `generated_at` i `data/user_fit/beer_v0.json`
fra `2026-06-08` til `2026-08-31`. Klassifiseringen var bit-identisk; kun tidsstempelet flyttet seg.
Oppdaget umiddelbart via `git status`, og tilbakestilt.

**Hvorfor det var feil:** Untappds siste check-in er `2026-01-16`. Et ferskt `generated_at` på
uendret januar-data er en **falsk ferskhets-påstand** — det neste noen leser er «øl-modellen ble
regenerert 31. august», og da ser en død datakanal levende ut. Skaden er ikke tapte data, den er
et villedende metadatafelt.

Dette er nøyaktig lærdommen fra 2026-08-30 («Kjørte et dokumentert skript for å teste det, og
muterte ekte data»), gjentatt 24 timer senere. **Grunnen til at hukommelsen ikke holdt:** lærdommen
sa *at* det kunne skje, men ikke *hvilke* kommandoer som skriver. Kommandolista i `CLAUDE.md`
skilte ikke mellom «regenerér» og «smoke-test» på en måte som var synlig i det øyeblikket man
kopierer en linje.

**Hva jeg gjør annerledes nå — strukturelt, ikke ved å huske bedre:**

- **Kommandolista i `CLAUDE.md` er nå merket med ✍️** på hver kommando som skriver til sporede
  filer, med én linje som forklarer merket. `user_fit` og `eval_fit` har trygge lesevarianter
  (`<varenr>`-argumenter, `--stdout-only`), og de står nå eksplisitt ved siden av.
- **Vil du bekrefte at et skrivende skript «virker», importér det** — `importlib.import_module`
  fanger den faktiske feilklassen fra `e664747` (import-feil) uten å røre data.
- **`git status` etter enhver verifiseringsrunde**, ikke bare etter redigering. Det var det som
  fanget dette; uten den sjekken hadde tidsstempelet blitt committet i neste `git add`.
