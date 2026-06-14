# Dashboard Setup

## Prerequisites

- Node.js 20 or later
- Python 3.11 or later
- A free Mapbox account (mapbox.com) for map rendering

---

## 1. Get a Mapbox Token

1. Go to [mapbox.com](https://mapbox.com) and sign up or log in.
2. Navigate to **Account → Tokens**.
3. Copy your default public token (starts with `pk.`), or create a new one.

---

## 2. Set Your Mapbox Token

Copy the example env file and paste your token:

```bash
cp dashboard/.env.example dashboard/.env
```

Open `dashboard/.env` and replace the placeholder:

```
VITE_MAPBOX_TOKEN=pk.your_actual_token_here
```

---

## 3. Generate Sample Data

Run from the **repo root** (not from inside `dashboard/`):

### Windows

```powershell
python scripts/generate_sample_data.py
```

### macOS / Linux

```bash
python scripts/generate_sample_data.py
```

This writes two files:
- `dashboard/public/data/intersections.geojson`
- `dashboard/public/data/districts.json`

You should see:
```
Sample data written.
Intersections: 500 | Known emergents: 12 | Districts: 9
→ dashboard/public/data/intersections.geojson
→ dashboard/public/data/districts.json
```

---

## 4. Install Dependencies

```bash
cd dashboard
npm install
```

---

## 5. Start the Dev Server

```bash
npm run dev
```

The dashboard is available at [http://localhost:5173](http://localhost:5173).

Without a Mapbox token the map canvas will be blank, but the sidebar, table, and filter controls will all work.

---

## Using Real Model Data

Once you have scored predictions from the research pipeline, run:

```bash
python scripts/export_predictions.py \
  --panel data/model/frozen_scores.parquet \
  --names data/proc/intersection_names.csv
```

This overwrites the files in `dashboard/public/data/` with real data. See `dashboard/docs/DATA_FORMAT.md` for the expected schema.
