# Runbook: oppdatere Vivino-ratings (Playwright-MCP)

**Standardløsning** når Kristoffer ber om «oppdater Vivino / de siste vinene jeg har ratet».
Vivino har ingen offentlig eksport-API, så vi skraper den **innloggede** profil-feeden med
Playwright-MCP og legger de nye vinene inn i `data/vivino/full_wine_list.csv`.

> Alternativet er GDPR-eksporten (Innstillinger → last ned dine data → ZIP på e-post).
> Den er mest komplett, men manuell. Denne runbooken er den raske, repeterbare veien.

## Forutsetning: innlogget browser

Playwright-MCP kjører en lokal, synlig Chromium. Profilen `vivino.com/users/kristoffers4`
laster offentlig, **men egne stjerne-ratings vises bare når du er innlogget**.

1. `browser_navigate` → `https://www.vivino.com/users/kristoffers4`
2. Hvis siden redirecter til `/login`: be Kristoffer logge inn i det åpne vinduet, og vent
   til han sier fra. (Aldri be om passord — han logger inn selv.)

## Steg 1 — skrap feeden

På den innloggede profilsiden, kjør denne via `browser_evaluate`. Egen rating er kodet som
`<i class="icon-N-pct">` (N = fyllprosent per stjerne) inne i `.activity-rating .rating.rating-xs`.
Aktivitetslenka bærer et `title`-attributt med **eksakt UTC-tidsstempel** — bruk det, ikke den
relative teksten («27 days ago»). CSV-ens `Scan date` er UTC (verifisert 2026-08-30: Hattingley
Rosé-aktiviteten står som `Mon, Jun 8th at 17:50:03 UTC`, CSV-raden som `2026-06-08 17:50:03`).

```js
() => {
  const pct = (el) => {
    let s = 0;
    el.querySelectorAll('i[class*="icon-"][class*="-pct"]').forEach(i => {
      const m = i.className.match(/icon-(\d+)-pct/); if (m) s += +m[1];
    });
    return Math.round(s) / 100;
  };
  const seen = new Set(), rows = [];
  document.querySelectorAll('div').forEach(b => {
    const link = b.querySelector('a[href*="/w/"]');
    const rEl = b.querySelector('.activity-rating .rating.rating-xs');
    if (!link || !rEl || b.querySelectorAll('a[href*="/w/"]').length > 4) return;
    if (b.querySelectorAll('.activity-rating .rating.rating-xs').length !== 1) return;
    const href = link.getAttribute('href');
    if (seen.has(href)) return; seen.add(href);
    const act = b.querySelector('a[href*="/activities/"]');
    rows.push({
      href,
      winery: (b.querySelector('a[href*="/wineries/"]')||{}).textContent?.trim() || null,
      year: (href.match(/year=(\d{4})/)||[])[1] || '',
      myRating: pct(rEl),
      exactTime: act ? act.getAttribute('title') : null,   // "Mon, Aug 3rd at 18:21:16 UTC"
      relative: act ? act.textContent.trim().replace(/\s+/g,' ') : null,
    });
  });
  return rows;
}
```

Feeden viser de ~10 nyeste. Trenger du eldre, klikk **"Show more"** (`browser_click` på
`button.btn-flow`) og kjør snippeten på nytt — det gir 20.

> **Gjør dette uansett, minst én gang.** Overlappet er kontrollen din: de eldre radene skal
> matche CSV-en på rating, desimal for desimal. Gjør de det, er skrapingen intakt, og en tom
> diff betyr «ingen nye ratinger». Gjør de det ikke, har DOM-en driftet — og da ser en brukket
> skraping ut nøyaktig som en tom diff. Uten denne kontrollen kan du ikke skille de to.

## Steg 2 — finn de nye

Sammenlign mot CSV-en (dedup skjer på `Winery + Wine name + Vintage`, diakritikk-uavhengig):

```bash
python3 -c "import csv,unicodedata as u
n=lambda s:''.join(c for c in u.normalize('NFD',(s or '').lower()) if u.category(c)!='Mn')
rows=list(csv.DictReader(open('data/vivino/full_wine_list.csv')))
have={(n(r['Winery']),n(r['Wine name']),(r['Vintage'] or 'N.V.')) for r in rows}
print('nyeste scan:', max(r['Scan date'] for r in rows if r['Scan date']))"
```

Alt eldre enn forrige `Scan date` er allerede inne. Bare viner som mangler skal legges til.

## Steg 3 — hent metadata per ny vin

Feeden mangler region/stil/label/vintage-id. For **hver ny** vin: `browser_navigate` til `href`
og hent alt fra sidens egen `"vintage":{…}`-JSON-blokk. **Ikke bruk løse regexer mot HTML-en.**
Den tidligere `html.match(/"year"\s*:\s*"?(\d{4})"?/)` traff `2025` på Land of Saints — en
årgangsløs oppføring — fordi treffet kom fra «Compare Vintages»-blokka lenger nede på siden.
Brace-match objektet i stedet:

```js
() => {
  const html = document.documentElement.innerHTML;
  const i = html.indexOf('"vintage":{');
  if (i < 0) return {error: 'ingen vintage-blokk — DOM-drift, inspiser siden'};
  const start = i + '"vintage":'.length;
  let d = 0, end = -1, inStr = false, esc = false;
  for (let j = start; j < html.length; j++) {
    const c = html[j];
    if (esc) { esc = false; continue; }
    if (c === '\\') { esc = true; continue; }
    if (c === '"') { inStr = !inStr; continue; }
    if (inStr) continue;
    if (c === '{') d++;
    else if (c === '}') { d--; if (d === 0) { end = j + 1; break; } }
  }
  let v;
  try { v = JSON.parse(html.slice(start, end)); } catch (e) { return {error: 'parse: ' + e.message}; }
  const w = v.wine || {};
  const facts = {};
  document.querySelectorAll('table tr').forEach(tr => {
    if (tr.children.length === 2) facts[tr.children[0].textContent.trim()] = tr.children[1].textContent.trim();
  });
  return {
    vintageId: v.id,                          // → Link to wine: /wines/<id>
    seoName: v.seo_name,                      // slutter på "-uv" = årgangsløs → Vintage "N.V."
    year: v.year || 'N.V.',                   // → Vintage
    avg: v.statistics?.ratings_average,       // → Average rating
    winery: w.winery?.name,                   // → Winery
    wineName: w.name,                         // → Wine name
    region: w.region?.name,                   // → Region (siste ledd, ikke hele stien)
    country: w.region?.country?.name,         // → Country
    style: w.style?.name,                     // → Regional wine style
    wineTypeId: w.type_id,                    // → Wine type, se tabell
    label: 'https:' + v.image?.location.replace('_pl_480x640.png', '_pb_x600.png'),
    facts,
  };
}
```

Wine type-id → CSV `Wine type`, med CSV-ens **eksakte** strenger:
`1=Red Wine, 2=White Wine, 3=Sparkling, 4=Rosé Wine, 7=Dessert Wine, 24=Fortified Wine`.
Merk «Wine»-suffikset på Rosé og Fortified — uten det brekker gruppering i `profile_stats.py`.
(Kun 1 og 2 er verifisert mot levende sider; de øvrige er lest ut av CSV-ens eksisterende verdier.)

**En `-uv`-oppføring er Vivinos årgangsløse aggregat** over alle årganger av vinen. Den skal inn
som `Vintage: N.V.`, men vær klar over at den ikke kan knyttes til en bestemt årgang — eller til
et Vinmonopol-varenummer. Noter det hvis vinen senere skal klokke-matches.

**Verifiser før du merger:**
- At hver label-URL faktisk laster. CORS blokkerer `fetch` mot `images.vivino.com`, så bruk
  `new Image()` med `onload`/`onerror`. Transformen `_pl_480x640.png` → `_pb_x600.png` gir samme
  form som DOM-ens `<img src>` og som radene forrige synk la inn.
- At hver `https://www.vivino.com/wines/<vintageId>` gir 200 og riktig sidetittel. Same-origin
  `fetch` fungerer mot `vivino.com`.

## Steg 4 — merge inn i CSV

Bygg én dict per ny vin med CSV-kolonnene og send som JSON til merge-helperen. Den legger
bare til det som ikke finnes fra før (idempotent — trygt å kjøre på nytt):

```bash
echo '[{"Winery":"Catena","Wine name":"The Trilogy Malbec","Vintage":"2024",
  "Region":"Mendoza","Country":"Argentina","Regional wine style":"Argentinian Malbec",
  "Average rating":"4.1","Scan date":"2026-06-28 12:00:00","Your rating":"4.1",
  "Wine type":"Red Wine","Link to wine":"https://www.vivino.com/wines/178746900",
  "Label image":"https://images.vivino.com/thumbs/....png"}]' \
  | python3 -m tools.vivino_sync -
```

- **Scan date**: bruk `exactTime` fra steg 1, konvertert til `YYYY-MM-DD HH:MM:SS`. Verdien er
  allerede UTC og skal **ikke** regnes om til norsk tid — CSV-en er UTC. Fall bare tilbake på
  omregning fra relativ dato hvis `title`-attributtet skulle forsvinne.
- Tomme kolonner (Your review, Personal Note, Drinking Window, Scan/Review Location) kan stå tomme.

## Steg 5 — regenerer statistikk

```bash
python3 tools/profile_stats.py
```

Oppdaterer managed blokk i `knowledge/smaksprofil.md` + `data/user_fit/v0.json`.
Sjekk deretter om nye ratings gir grunn til å oppdatere smaksprofilen manuelt (nye favoritter,
no-go, sterkere mønstre) — jf. CLAUDE.md § «Når ny Vivino-eksport kommer».

## Kjente begrensninger

- **Endret rating** på en vin som alt finnes → merges ikke (bare nye legges til). Sjeldent;
  rett manuelt hvis det skjer.
- **DOM-selektorer** (`icon-N-pct`, `.activity-rating`, `.rating-xs`) kan endres av Vivino.
  Bryter skrapet, inspiser ett rating-kort på nytt med `browser_evaluate` og oppdater snippeten.
- **Login-sesjon** utløper — krever ny manuell innlogging ved neste kjøring.
