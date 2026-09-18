# Dashboard Setup

## Prerequisites

- Node.js 20 or later
- Python 3.11 or later (only to regenerate the data files)
- A Google Cloud project with billing enabled, for the Maps JavaScript API

---

## 1. Get Google Maps credentials

The dashboard renders on the Google Maps JavaScript API with a deck.gl overlay for
the ranked intersection layer. You need two values.

### API key

1. <https://console.cloud.google.com/> → create a project.
2. Enable billing. Without it Maps serves degraded, watermarked tiles even inside
   the free allowance.
3. **APIs & Services → Library** → enable **Maps JavaScript API** and
   **Street View Static API**.
4. **Credentials → Create credentials → API key**.
5. Restrict it: **Application restrictions → Websites**, add
   `http://localhost:5173/*` and your deployed domain. Then **API restrictions →
   Restrict key** to the two APIs above.

### Map ID

Vector rendering requires a Map ID, and the dark theme is attached to it — the
`styles` option on `google.maps.Map` is ignored whenever a `mapId` is set.

1. **Google Maps Platform → Map Management → Create Map ID**.
2. Map type **JavaScript**, rendering **Vector**.
3. Create a Map style based on "Dark" and associate it with the Map ID.

Without a Map ID the app falls back to `DEMO_MAP_ID`, which works for local
development but is watermarked and rate-limited.

---

## 2. Configure the environment

```bash
cp dashboard/.env.example dashboard/.env
```

Then edit `dashboard/.env`:

```
VITE_GOOGLE_MAPS_API_KEY=AIza...your_key
VITE_GOOGLE_MAPS_MAP_ID=8e0a97af9386fef
```

Vite inlines these at build time, so restart the dev server after changing them.

---

## 3. Generate data

Run from the **repo root**, not from inside `dashboard/`:

```bash
python scripts/generate_sample_data.py
```

This writes `dashboard/public/data/intersections.geojson` and
`dashboard/public/data/districts.json`.

Both files are committed to the repository, so if you only want to run the UI you
can skip this step entirely — the real model export is already there.

---

## 4. Install and run

```bash
cd dashboard
npm install
npm run dev
```

Open <http://localhost:5173>.

Without a valid API key the map area shows an explicit error panel naming the
missing variable; the sidebar, ranked table, filters, and detail panel all still
work, so most UI development does not need a key.

---

## Using real model output

Once the research pipeline has produced scored predictions:

```bash
python scripts/build_export_panel_verified.py --run forward
```

This overwrites the files in `dashboard/public/data/`. See
`dashboard/docs/DATA_FORMAT.md` for the expected schema.

---

## Deploying

See `docs/HOSTING_RENDER.md` in the repo root for the full Render deployment
walkthrough, including the exact build settings, rewrite rule, cache headers, and
Google Cloud cost controls.
