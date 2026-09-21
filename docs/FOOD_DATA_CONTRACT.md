# Food-safety site: the export contract

The second site (`food-dashboard/`) ranks San Diego retail food facilities by how likely
the County's next routine inspection is to find a major violation. The site is built; the
model is not. This document is the boundary between them: what the pipeline must write to
`food-dashboard/public/data/`, in enough detail that the site needs no change when the
real export lands. A sample export in exactly this shape is written by
`scripts/food/make_sample_export.py`; `npm run check` in `food-dashboard/` fails the build
when an export breaks the contract.

## Sources

- **Candidate universe.** "Food Facility Permits", San Diego County open data portal,
  dataset `c5ez-ufrd` (public domain, monthly): about 15,900 permits with record id, name,
  business type, address, city, permit status and coordinates. `scripts/food/fetch_facilities.py`
  downloads it. Active retail permits inside the City of San Diego are the candidates;
  the export's `candidates` count is the number scored.
- **Inspection history.** SD Food Info, the County's published inspection results
  (routine, reinspection and complaint visits, with score, grade and the numbered items
  cited). Collecting it is the pipeline's job; the County has no bulk download, so the
  collection method and date go in `meta.source`.
- **Nothing else.** No reviews, no social media, no owner names. The site shows the
  County's record and a prediction; anything beyond the record is out of scope.

## `facilities.geojson`

A FeatureCollection of Point features, one per exported place, 1,000 at most. Every
feature carries:

| property | type | meaning |
|---|---|---|
| `rank` | int | 1..N, contiguous, 1 is highest predicted risk |
| `facility_id` | string | the County's record id (`PR…`) |
| `name` | string | as on the permit |
| `address` | string | street, city, state, zip |
| `facility_type` | enum | `restaurant`, `market`, `mobile`, `bar`, `school`, `bakery`, `caterer`, `other` |
| `risk_category` | int or null | the County's 1, 2 or 3 (routine inspections a year) |
| `council_district` | int or null | City of San Diego council district; null outside the City |
| `percentile` | number | 100 × (1 − (rank − 1) / candidates) |
| `score` | number, optional | the model's probability, 0 to 1 |
| `last_inspection` | object | the last entry of `inspections`, repeated for convenience |
| `inspections` | array | last five years, oldest first; see below |
| `violations` | array | every item cited in the 36 months before the last visit, at most 60; see below |
| `shap_features` | array | top five signals, strongest first; see below |
| `is_known_positive` | bool | once the label window has data: a major violation at the next routine inspection |
| `oof_rank` | int or null | the rank at which the place was scored, for the catch statistics |

An inspection: `{ "date": "2026-07-11", "type": "routine" | "reinspection" | "complaint",
"score": 84 | null, "grade": "A" | "B" | "C" | null, "major": 2, "minor": 5, "closed": false }`.
Complaint visits carry no score. `grade` follows the County's bands (A 90 to 100, B 80 to 89,
C below 80). `closed` is true when the visit ended in a closure order.

A violation: `{ "date": "2026-07-11", "code": "7", "theme": "temperature", "severity": "major" | "minor",
"description": "…" }` (`description` optional). `code` is the numbered item on the California retail food inspection
report; `theme` groups those items:

| theme | report items |
|---|---|
| `temperature` | 7, 8, 9, 10, 11 |
| `handwashing` | 5, 6 |
| `vermin` | 23 |
| `sanitizing` | 14, 33, 34, 39 |
| `storage` | 26, 27, 30 |
| `hygiene` | 2, 3, 4, 25 |
| `equipment` | 35, 36, 38 |
| `plumbing` | 21, 22, 40 |
| `labeling` | 32, 47, 48 |
| `other` | everything else |

A signal: `{ "feature_name": "theme_temperature", "display_label": "temperature cited 3 times",
"raw_value": 3, "shap_value": 0.41 }`. `display_label` must use the vocabulary below; the
site's plain-language rewrites read it, and the export check fails when more than a tenth of
the labels fall outside it.

## Signal vocabulary

| label pattern | example |
|---|---|
| `Last routine score N` | Last routine score 84 |
| `Grade X at last inspection` | Grade B at last inspection |
| `N major violation(s) in the last M inspections` | 2 major violations in the last 3 inspections |
| `<theme> cited N time(s)` | temperature cited 3 times |
| `Closed by the County YYYY` | Closed by the County 2025 |
| `Reinspection required N time(s)` | Reinspection required 2 times |
| `Risk category N` | Risk category 3 |
| `Facility type: <type>` | Facility type: mobile |
| `Score falling: A to B` / `Score rising: A to B` | Score falling: 96 to 84 |
| `N month(s) since last inspection` | 7 months since last inspection |
| `N complaint(s) in M year(s)` | 2 complaints in 2 years |
| `Neighbours' average score N` | Neighbours' average score 88 |
| `Change of ownership YYYY` | Change of ownership 2025 |
| `N seats` | 120 seats |

A new feature needs a new line here and a rewrite in `src/lib/signals.js` before it ships.

## `meta.json`

```json
{
  "sample": false,
  "model": "xgboost-classifier v1",
  "run": "forward_2026Q3",
  "generated": "2026-10-01",
  "candidates": 8213,
  "label": "at least one major violation at the next routine inspection",
  "label_window": "2026-10-01 to 2027-09-30",
  "inspections_through": "2026-09-15",
  "catch": { "50": { "caught": 0, "total": 0 } },
  "source": { "name": "SD Food Info, collected 2026-09-16", "url": "https://www.sandiegocounty.gov/content/sdc/deh/fhd/ffis.html" }
}
```

`catch` is empty (`{}`) until the label window has data; the site then says "not yet
scored" everywhere a figure would go. Once scored, `catch[K].caught` is how many of the
`total` positives sat in the top K, and must not fall as K grows. `sample: true` puts a
notice on every page and must never be set on a real export; the check also refuses a
non-sample export that contains a place named "Sample …".

## What the site does with it

- Rank, tier colour and the map from `rank`; filters from `facility_type`,
  `council_district`, and the themes in `violations` and `shap_features`.
- "The record" from `inspections` (`src/lib/inspections.js`): last score and grade, majors
  and minors in the 36 months before the last visit, closures, reinspections, trend.
- "What inspectors found" from `violations`, grouped by theme.
- "If you eat here" from the themes with a major finding or two findings, from closures,
  from a last grade of B or C, and from repeat reinspections (`src/lib/advice.js`).
- "Why the model ranked it here" from `shap_features` through the vocabulary above.
- "What a rank is worth" from `meta.catch` (`src/lib/tiers.js`).
