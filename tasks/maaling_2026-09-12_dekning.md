# Måling: kritiker-score-dekning (2026-09-12)

**Oppdrag:** utvide kritiker-score-dekningen slik at `recommend`s default-rangering
får reell orden. **Utfall: sveipen ble ikke kjørt.** Målingen viser at dekningen
ikke mangler data — den mangler en ledning. Se «Beslutning» nederst.

Alle tall under er målt i denne økta, med kommandoen som produserte dem.
Katalogsnapshot: `data/polet/` (11 dager gammelt ifølge `recommend`-headeren).
Aperitif-snapshot: `data/aperitif/meta.json`, `generated_at: 2026-08-31T14:48:25`.

---

## 1. Dekning i dag — to kilder, ikke én

`knowledge/scores/` er **håndkuratert DN-materiale** (6 filer, 409 unike viner).
`data/aperitif/scores.ndjson` er **sveipet** (15 672 rader, 557 sider, 2026-08-31).
`tools/recommend.py:237` `_kritiker()` leser **kun den første**.

| kategori | aktive | `knowledge/scores` | aperitif-snapshot | aperitif % |
|---|---|---|---|---|
| Rødvin | 11 580 | 21 | 5 965 | 51,5 |
| Hvitvin | 8 035 | 92 | 4 903 | 61,0 |
| Musserende vin | 2 640 | 102 | 1 547 | 58,6 |
| Rosévin | 664 | 121 | 391 | 58,9 |

3-liters-utsnittet — spørsmålet som utløste oppdraget:

| utsnitt | n | `knowledge/scores` | aperitif-snapshot |
|---|---|---|---|
| 3 l aktive rødvin | 269 | **0** | **160** |
| 3 l kartong (…06) | 211 | **0** | **156** (74 %) |

Kontrollrader (validerer at «0» er et funn og ikke et ødelagt instrument):

```
KONTROLL knowledge 5518401 -> 91.0  Bruno Paillard Première Cuvée Brut
KONTROLL aperitif 10037906 -> 84    La Huella 2024          (3 l kartong)
KONTROLL aperitif 10059006 -> 83    Giacosa Fratelli Barbera (3 l kartong)
KONTROLL aperitif 10094106 -> 86    Bibi Graetz Rosso Toscana (3 l kartong)
```

**Instrumentfeil funnet og rettet under målingen.** Første forsøk leste kategori
via `p["mainCategory"]` og ga **0 rødviner** på en katalog med 11 580. Katalogens
nøkkel er `main_category` (snake_case). En negativ telling validert mot en kjent
positiv rad avdekket det; uten den kontrollen hadde hele tabellen vært null.

Kommandoen bak tabellene (`python3 - <<'EOF'` fra repo-rot):

```python
import json, sys
sys.path.insert(0, ".")
from tools import polet_store, scores
kat = polet_store.read_catalog()
def kat_navn(p):
    v = p.get("main_category")
    return (v.get("name") if isinstance(v, dict) else v) or ""
def volum(p):
    v = p.get("volume"); return v.get("value") if isinstance(v, dict) else v
def varenr(p): return str(p.get("code") or "")
idx = scores.index()
ap = {}
with open("data/aperitif/scores.ndjson") as f:
    for ln in f:
        r = json.loads(ln); ap[r["polet_id"]] = r["score"]
for navn in ("Rødvin", "Hvitvin", "Musserende vin", "Rosévin"):
    akt = [p for p in kat if kat_navn(p) == navn and polet_store.is_active(p)]
    nk = sum(1 for p in akt if varenr(p) in idx)
    na = sum(1 for p in akt if varenr(p) in ap)
    print(f"{navn:16} {len(akt):6} {nk:5} {na:6} {100*na/len(akt):5.1f}%")
rod = [p for p in kat if kat_navn(p) == "Rødvin" and polet_store.is_active(p)]
for merke, sett in (("3 l", [p for p in rod if volum(p) == 300]),
                    ("3 l kartong", [p for p in rod if volum(p) == 300 and varenr(p)[-2:] == "06"])):
    print(merke, len(sett),
          sum(1 for p in sett if varenr(p) in idx),
          sum(1 for p in sett if varenr(p) in ap))
```

---

## 2. `11 956` og `284` er ikke foreldet — de teller noe annet

Briefen, `tools/recommend.py:32`, `tasks/todo.md:30` og `docs/ARCHITECTURE.md:452`
sier «21 av **11 956 aktive** rødviner» og «0 av **284** på 3 liter». Målt:

```
rødvin aktive         : 11 580      3 l aktive       : 269
rødvin kommer_snart   :    376      3 l kommer_snart :  15
sum                   : 11 956      sum              : 284
```

Tallene stemmer eksakt — men de inkluderer `kommer_snart`, som ADR-030 nettopp
sier **ikke** er kjøpbare. Ordet «aktive» i de fire dokumentene er derfor feil,
ikke tallet. `polet_store.is_active()` og `is_kommer_snart()` er disjunkte.

```sh
grep -rn "11956\|11 956" --include="*.py" --include="*.md" .
# tasks/todo.md:30 · tasks/maaling_2026-08-31.md:30 · tools/recommend.py:32
# tools/recommend.py:417 · docs/ARCHITECTURE.md:452 · docs/ARCHITECTURE.md:464
```

`tools/recommend.py:417` har tallet **hardkodet** i sorterings-headeren
(`f"kritiker-score desc (21/11956 dekning), "`), så headeren lyver i to ledd:
feil populasjonsdefinisjon, og et tall som ikke regnes ut fra dataene.
Eier: hovedtråden.

`docs/ARCHITECTURE.md:452` sier «**før** dekningssveipen samme dag» — den setningen
forutsetter en sveip som ikke ble kjørt, og må rettes. Eier: hovedtråden.

---

## 3. Projeksjon for full sveip — ikke relevant, og derfor ikke kjørt

Briefens punkt 2-3 (kostnad per vin på 30 viner, så projeksjon) forutsetter en
per-vin-sveip mot en kilde. Den forutsetningen bærer ikke:

1. **`refresh_aperitif.py` er ikke per vin.** Den sveiper Pollistens listesider
   (30 rader per side, 557 sider) og skriver til `data/aperitif/`, **ikke** til
   `knowledge/scores/`. Det finnes ingen «treffrate per vin» å måle.
2. **Den sveipen er allerede kjørt.** `data/aperitif/meta.json`: 557 sider,
   16 614 rader med poeng, 15 672 skrevet, 2026-08-31 — 12 dager gammel.
   Å kjøre den på nytt ville kostet ~2 timer og flyttet dekningen ~0.
3. **`knowledge/scores/` kan ikke sveipes.** Det er seks DN-artikler lagt inn for
   hånd. Det finnes ingen kilde å hente nummer 7 fra maskinelt.

**Ingen nettverkskall ble gjort i denne økta.** Throttling er urørt.

---

## 4. Kryssjekk (før)

```
python3 -m tools.recommend --kategori rødvin --volum-min 2.9 --volum-maks 3.1 \
    --emballasje kartong --antall 5
REC_EXIT=0
```

```
5 av 226 treff  ·  sortert: kritiker-score desc (21/11956 dekning), literpris asc som tie-break
snapshot 11 dager gammelt

 1. Cast. de Liria Bobal Shiraz  [14916506]   340 kr · 113 kr/l
    value: akseptabelt — Akseptabelt. Aperitif 82/100. pris i 46. percentil ...
 2. Black Tower Smooth Red       [18948906]   350 kr · 117 kr/l   value: usikkert
 3. Wine for Home                [18751106]   379 kr · 126 kr/l   value: usikkert
 4. Grande Real                  [16916206]   380 kr · 127 kr/l   value: usikkert
 5. Gato Negro Cabernet 2025     [295306]     380 kr · 127 kr/l   value: usikkert
```

**Det finnes ingen «etter» — sveipen ble ikke kjørt.** Kravet står uoppfylt med
vilje, ikke ved forglemmelse.

Merk rad 1: `value`-linja viser alt **«Aperitif 82/100»**. Poenget er hentet, vist
og forkastet i samme kjøring — rangeringen leser det ikke. Radene 2-5 er de nest
billigste av 226, uten noe kvalitetssignal i det hele tatt.

---

## 5. Konsekvensen av å koble til snapshotet — målt

`data/aperitif/meta.json` advarer selv: `prisbias`, Spearman(poeng, pris) =
+0,65 (whisky) / +0,80 (DN-vin), «høyest score ≈ dyrest». Målt på det utsnittet
dette faktisk gjelder (3 l kartong rødvin, n=156 med poeng):

```
Spearman(aperitif-poeng, pris) = +0,52
pris i utsnittet: min 340 · median 500 · maks 780 kr

TOPP 5 ETTER APERITIF-SCORE          TOPP 5 ETTER LITERPRIS ASC (i dag)
 88p  670 kr  223 kr/l  Valli Unite   82p  340 kr  113 kr/l  Cast. de Liria
 88p  780 kr  260 kr/l  Massolino      –   350 kr  117 kr/l  Black Tower
 87p  540 kr  180 kr/l  Askaneli       –   379 kr  126 kr/l  Wine for Home
 87p  550 kr  183 kr/l  Thymiopoulos   –   380 kr  127 kr/l  Grande Real
 87p  600 kr  200 kr/l  Cuilleron      –   380 kr  127 kr/l  Gato Negro
```

Prisbiasen er **reell**: +0,52, og alle fem toppradene ligger over medianen
(500 kr) — én av dem på taket (780 kr). Det er altså ikke en mild effekt, det er
den øvre halvdelen med taket inkludert.

**Men det er den rangeringen spørsmålet ba om.** «Kraftig rødvin» oversettes i
CLAUDE.md til appellasjonsnivå og literpris, og dagens default gir i stedet de fem
billigste — fire av dem uten noe kvalitetssignal i det hele tatt. Utsnittet er
prisbegrenset (340-780 kr), så konsekvensen er avgrenset **her**. På et bredt søk
uten volumfilter er den **ikke målt**, og bør måles før dette gjøres til global
default.

---

## Beslutning — til hovedtråden

Dekningen mangler ikke data. `tools/recommend.py:237`:

```python
def _kritiker(varenr: str) -> Optional[float]:
    from tools import scores
    e = scores.best_score(varenr)
    return e["score"] if e else None
```

`tools/aperitif.py:132` `snapshot_score(polet_id)` finnes, er offline (ingen HTTP),
og er matchet på varenummer — ikke på navnelikhet. `tools/value_score.py:155`
`_combine_quality()` har alt presedensen: *«Kuratert > Aperitif (faglig) > Vivino
(crowd)»*. Å la `_kritiker()` falle tilbake på snapshotet anvender en **allerede
vedtatt** presedens på et andre kallsted — det endrer ingen vekting og ingen
`user_fit`-regel.

| | tiltak | dekning 3 l kartong | kostnad |
|---|---|---|---|
| **A** | `_kritiker()` faller tilbake på `aperitif.snapshot_score()` | 0/211 → **156/211** | ingen nettverk; ~4 linjer i fil hovedtråden eier |
| **B** | kjør `refresh_aperitif.py` på nytt | 156/211 → **156/211** (± drift) | ~2 t nettverk; svarer på ferskhet, ikke på dette |
| **C** | status quo | 0/211 | ingen; headeren fortsetter å love en orden den ikke har |

**Anbefaling: A**, og deretter at headeren i `recommend.py:417` regner dekningen
ut fra dataene i stedet for å bære `21/11956` hardkodet.

**Det som ville fått meg til å skifte:** at toppen etter aperitif-poeng la seg på
pristaket. Målt ligger alle fem toppradene over medianen (500 kr) og én på taket
(780 kr) — betingelsen er altså **delvis** innfridd, ikke avvist. Grunnen til at
anbefalingen står likevel: utsnittet er prisbegrenset til 340-780 kr, og
alternativet er de fem billigste uten kvalitetssignal. På et bredt søk uten
volumfilter er prisbiasen **ikke målt**, og A bør ikke gjøres til global default
før den er det.

Jeg eier ikke `tools/recommend.py` og har ikke rørt den.

---

## Status

- `python3 -m pytest -q` → `564 passed in 23.99s`, `PYTEST_EXIT=0` (urørt kode).
- Ingen filer endret utenom denne. Ingen nettverkskall. Ingen `git add`.
- **Uferdig:** prisbias på bredt katalogsøk uten volumfilter (`ANTATT` uavklart).
- **Defekter til hovedtråden:** (1) «aktive» om 11 956/284 i fire dokumenter,
  (2) hardkodet `21/11956` i `recommend.py:417`, (3) `ARCHITECTURE.md:452`s
  «før dekningssveipen samme dag» viser til en sveip som ikke ble kjørt.

---

# DEL 2: A gjennomført med prissone-lås (2026-09-12, samme økt)

Hovedtråden avgjorde A med prissone-lås og ga meg `tools/recommend.py` +
`tests/test_recommend.py`. Registeret hadde alt svaret: `ARCHITECTURE.md:988`
— «prissone-lås er en FORUTSETNING for å bruke disse poengene til rangering».

## Terskelen er målt, ikke valgt

Spennet er **rått maks/min** over kandidatsettets priser. Målt per kandidatsett:

| kandidatsett | rått spenn | utfall |
|---|---|---|
| rødvin 300-500 kr | 1,7x | LÅST |
| rødvin 150-250 kr | 1,7x | LÅST |
| rødvin 1,5 l kartong | 1,8x | LÅST |
| rødvin 3 l kartong | 2,3x | LÅST |
| — **terskel 4,0x** — | | |
| `--maks-pris 200` | 5,0x | ulåst |
| `--maks-pris 300` | 7,5x | ulåst |
| `--maks-pris 500` | 12,5x | ulåst |
| `--maks-pris 30000` | 737,2x | ulåst |
| all rødvin | 1371,2x | ulåst |

4,0 ligger i det målte tomrommet mellom 2,3 og 5,0.

```python
# kommandoen bak tabellen (fra repo-rot, python3 - <<'EOF')
import sys; sys.path.insert(0, ".")
from tools import polet_store
def pris(p):
    v = p.get("price"); return v.get("value") if isinstance(v, dict) else v
def raa(rader, merke):
    pr = sorted(x for x in (pris(p) for p in rader) if x)
    print(f"{merke:26} n={len(pr):5} rå {pr[0]:6.0f}-{pr[-1]:7.0f} = {pr[-1]/pr[0]:7.1f}x")
q = polet_store.query
raa(q(category="rødvin", min_price=300, max_price=500), "300-500 kr")
raa(q(category="rødvin"), "all rødvin")
raa(q(category="rødvin", max_price=30000), "maks-pris 30000")
```

## To avvik fra briefen, begge målt

**1. `--maks-pris` er IKKE en lås i seg selv.** Briefen sa «lås = brukeren har
satt `--maks-pris`, eller kandidatsettets eget prisspenn er smalt». Målt er det
første falskt: `--maks-pris 30000` gir **737x** spenn og ville lagt Mugnier
Musigny (21 750 kr) på topp — akkurat det låsen finnes for å hindre. Det målte
spennet **subsumerer** pristaket: et ekte tak snevrer settet av seg selv. Én
regel, som ikke kan lures. Konsekvens: et tak alene låser ikke, fordi gulvet på
40 kr står — sonen låses ved å feste begge ender (`--min-pris 150 --maks-pris
250` → 1,7x).

**2. Rått spenn, ikke persentiler.** Første utgave brukte p5-p95 «så én outlier
ikke definerer sonen». **Det var feil vern, og testen avslørte det:** med n=6
kastet p95 nettopp outlieren, så fem billige viner pluss én Musigny målte 1,5x
og **låste** — hvorpå Musigny gikk til topps. Persentilen skjulte raden som
betyr noe. Rått spenn kan ikke lures slik, og separasjonen er bredere
(2,3 → 5,0 mot 3,1 → 5,1). `test_poeng_er_ikke_noekkel_i_ulaast_sone` er
regresjonsvernet.

## Hva låsen gjør og ikke gjør

Den fjerner **ikke** prisbiasen — rho er +0,52 i 3-liters-sonen og topp 5 ligger
i 86. prispersentil der. Den binder **konsekvensen i kroner**: 540-780 kr i
stedet for 21 750. Det er påstanden, ikke mer.

## Kryssjekk før/etter

**3 l kartong — før:**
```
5 av 226 treff · sortert: kritiker-score desc (21/11956 dekning), literpris asc som tie-break
 1. Cast. de Liria Bobal Shiraz [14916506]  340 kr · 113 kr/l   (Aperitif 82/100, vist men ubrukt)
 2. Black Tower Smooth Red      [18948906]  350 kr · 117 kr/l   value: usikkert
 3. Wine for Home               [18751106]  379 kr · 126 kr/l   value: usikkert
 4. Grande Real                 [16916206]  380 kr · 127 kr/l   value: usikkert
 5. Gato Negro Cabernet 2025    [295306]    380 kr · 127 kr/l   value: usikkert
```

**3 l kartong — etter** (`EXIT=0`):
```
5 av 226 treff · sortert: kritiker-score desc (156/226 dekning, prissone låst: prisspenn 2.3x (340-780 kr)), literpris asc som tie-break
 1. Valli Unite 2022            [9382706]   670 kr · 223 kr/l  Aperitif 88/100 (godt kjøp)
 2. Massolino Langhe Rosso      [12309606]  780 kr · 260 kr/l  Aperitif 88/100 (godt kjøp)
 3. Askaneli Saperavi Qvevri    [16493506]  540 kr · 180 kr/l  Aperitif 87/100
 4. Thymiopoulos Xino-Maverick  [19171806]  550 kr · 183 kr/l  Aperitif 87/100
 5. Cuilleron Syrah             [19483006]  600 kr · 200 kr/l  Aperitif 87/100
```
Dekning i denne sonen: **0/226 → 156/226**. `value_score` dømmer uavhengig tre
av de fem som `godt_kjop` — ikke noe jeg har bygget inn.

**Bredt søk, ingen volumfilter — etter** (`EXIT=0`):
```
5 av 11956 treff · sortert: literpris asc — kritiker-score er IKKE nøkkel: prissonen er
ulåst (prisspenn 1371.2x > 4x (40-54712 kr)), og Spearman(poeng, pris) = +0.74, så rå
poeng ville rangert etter pris. Dekning 5972/11956. Snevre prisspennet inn under 4x med
--maks-pris/--min-pris for å låse sonen — et tak alene er ikke nok, gulvet på 40 kr står
(--maks-pris 300 gir 7,5x).
 1. Cast. de Liria Bobal Shiraz  340 kr · 113 kr/l
```
Musigny er ikke i toppen, og outputen sier hvorfor. Utfallet er **uendret** fra
før på bredt søk — det er meningen: låsen legger ingen ny orden der den ikke
kan forsvares.

## Mutasjonstest — vokter testene noe?

Hver mutasjon ble kjørt, fanget, og fila gjenopprettet bit-identisk
(`shasum` før/etter: `279f69a4…`).

| mutasjon | fanget av | utfall |
|---|---|---|
| `bruk_kritiker=True` alltid (låsen fjernet) | `test_poeng_er_ikke_noekkel_i_ulaast_sone` | `1 failed, 41 passed` |
| aperitif-fallbacken fjernet fra `_kritiker` | `test_kritiker_faller_tilbake_paa_aperitif_snapshot` | `1 failed, 41 passed` |
| dekningen hardkodet til `21/11956` | `test_headeren_navngir_aarsaken_i_begge_soner` + `test_dekningen_er_ikke_hardkodet` | `2 failed, 40 passed` |
| kildene byttet om (Aperitif sjekkes først) | `test_kuratert_score_slaar_aperitif` | `1 failed, 41 passed` |
| `max(begge kilder)` i stedet for presedens | `test_kuratert_score_slaar_aperitif` | `1 failed, 41 passed` |

Presedens-testen ble strammet underveis: Aperitif-poenget er nå satt **høyere**
(99) enn det kuraterte (91). Med et lavere tall bestod testen også en
`max(begge)`-implementasjon — som ikke er presedens, men en ny
sammenslåingsregel. Mutasjon 5 er beviset på at den nå fanger begge.

**En test som besto mutasjonen den var oppkalt etter.** `test_dekningen_er_ikke_hardkodet`
brukte først `katalog`-fixturen, som har 4 aktive rader → **ulåst** sone → traff
den ulåste header-grenen, som aldri bar det hardkodede tallet. Den voktet
ingenting. Flyttet til den låste sonen, og fanger nå mutasjonen (rad 3 over).

## Testene er nå hermetiske

`_kritiker()` leser `knowledge/scores/` og `data/aperitif/scores.ndjson` fra disk
via modul-cacher. Fixturens `10037906`/`10059006` er **ekte** varenumre med 84 og
83 poeng i snapshotet, så sorteringstestene ville målt datatilstand — de hadde
endret seg neste gang noen sveipet. Ny `kritiker`-fixture patcher `_kritiker` og
inngår i `katalog`, så alle 32 eksisterende tester er hermetiske. Samme feil som
subprocess-CLI-testene hadde.

## Rangeringsstien er offline — bevist

```
socket.socket = <kaster AssertionError>
→ LÅST sone, 226 kandidater rangert etter poeng — 0 nettverkskall
→ ULÅST sone, 11 956 kandidater, dekning telt på alle — 0 nettverkskall
EXIT=0
```

## Port

```
python3 -m pytest -q  →  574 passed in 28.29s
PYTEST_EXIT=0
```
Baseline var 564. +10 nye tester, 0 endret bortsett fra den ene svake som ble
flyttet til den låste grenen.
