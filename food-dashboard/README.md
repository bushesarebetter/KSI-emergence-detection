# San Diego Food Safety Risk

The second site in this repository. It ranks San Diego restaurants, markets and food
trucks by how likely the County's next routine inspection is to find a major violation,
and shows each place's inspection scores, what inspectors found, and what a customer can
look for. Same stack and design as the intersection site in `dashboard/`: Vite, React,
Tailwind, Google Maps with a deck.gl overlay, no router, installable.

**State: built on a sample export.** The model does not exist yet. Every place shown is
invented by `scripts/food/make_sample_export.py`, `meta.json` says `"sample": true`, and a
notice sits on every page. The real export must follow [docs/FOOD_DATA_CONTRACT.md](../docs/FOOD_DATA_CONTRACT.md);
drop it into `public/data/` and the notice disappears.

## Run it

```
cp .env.example .env        # add the Google Maps key and Map ID
npm install
npm run dev                 # http://localhost:5173
npm test                    # node --test tests/*.test.mjs
npm run check               # the export against the contract
npm run build
```

The Google key can be the intersection site's key with this site's domain added to its
referrer list; it needs the Maps JavaScript, Street View, Places (New) and Geocoding APIs.
Hosting is the same as the first site (docs/HOSTING_RENDER.md), with the build directory
`food-dashboard/dist` and the same rewrite rule.

## Pages

- `/` the front page: the claim, a search, the top three, the caveat
- `/map` the application: map, filters (shortlist size, kind of place, what inspectors
  found, district), "Near an address", the ranked table with CSV download, and the detail
  panel; a phone gets its own shell
- `/place/N` one place as a page, for printing, embedding and sharing
- `/privacy` privacy and terms

## Where things are

- `src/site.js` everything about the place and the regulator; another county changes this
  file and its export
- `src/lib/inspections.js` what a record says, computed once
- `src/lib/advice.js` "If you eat here", from the record
- `src/lib/signals.js` the export's signal vocabulary in plain words
- `src/lib/filters.js`, `search.js`, `format.js`, `tiers.js`, `ask.js` filters, search, CSV,
  what a rank is worth, citations
- `scripts/check-export.mjs` the contract check that CI runs
- `../scripts/food/make_sample_export.py` the sample; `../scripts/food/fetch_facilities.py`
  the County's permit list, the candidate universe

## Design

AVOID.md at the repository root governs both sites. In practice here: warm paper, ink,
one risk ramp; hairlines instead of cards; no gradients, shadows on everything, emojis,
icon packs, rounded corners or pastel; a real product on the front page; a custom 404; a
title, description and share card per page; a favicon set; robots and a sitemap; a
cookie note, a privacy page and terms; loading states and form error states; mobile
breakpoints with a sticky mobile button; no em dashes in copy.
