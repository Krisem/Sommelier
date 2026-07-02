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
`<i class="icon-N-pct">` (N = fyllprosent per stjerne) inne i `.activity-rating .rating.rating-xs`:

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
    const yr = href.match(/year=(\d{4})/);
    rows.push({
      href,
      winery: (b.querySelector('a[href*="/wineries/"]')||{}).textContent?.trim() || null,
      year: yr ? yr[1] : '',
      myRating: pct(rEl),
      when: (b.querySelector('a[href*="/activities/"]')||{}).textContent?.trim() || null,
    });
  });
  return rows;
}
```

Feeden viser de ~10 nyeste. Trenger du eldre (mange nye siden sist), klikk **"Show more"**
(`browser_click`) og kjør snippeten på nytt.

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

Feeden mangler region/stil/label/vintage-id. For **hver ny** vin: `browser_navigate` til
`href` og kjør:

```js
() => {
  const html = document.documentElement.innerHTML;
  const g = {};
  g.regionalStyle = (document.querySelector('a[href*="/wine-styles/"]')||{}).textContent?.trim() || null;
  g.label = (document.querySelector('img[src*="/labels/"], img[src*="thumbs"]')||{}).src || null;
  const vm = html.match(/"vintage"\s*:\s*\{[^}]*"id"\s*:\s*(\d+)/) || html.match(/\/wines\/(\d+)/);
  g.vintageId = vm ? vm[1] : null;                       // → Link to wine: /wines/<id>
  g.wineTypeId = (html.match(/"wine_type_id"\s*:\s*(\d+)/)||[])[1] || null;  // 1=Red 2=White 3=Sparkling 4=Rosé 7=Dessert 24=Fortified
  const facts = {};
  document.querySelectorAll('table tr').forEach(tr => {
    if (tr.children.length === 2) facts[tr.children[0].textContent.trim()] = tr.children[1].textContent.trim();
  });
  g.facts = facts;  // Region: "France / Bordeaux / Médoc" → Country=France, Region=siste ledd
  return g;
}
```

Wine type-id → CSV `Wine type`: `1=Red Wine, 2=White Wine, 3=Sparkling, 4=Rosé, 7=Dessert Wine, 24=Fortified`.

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

- **Scan date**: feeden gir kun relativ dato («4 days ago»). Regn om til `YYYY-MM-DD HH:MM:SS`
  fra dagens dato — dag-presisjon er godt nok (brukes bare til «vekt nyere høyere»). Noter at
  den er omtrentlig hvis det er tvil.
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
