# Manual data downloads

Raw data is **immutable**: each download goes in its own dated snapshot folder
`data/raw/<source>/<YYYYMMDD>/` alongside a `manifest.json` (source URL, fetch date,
row/feature count, sha256). Nothing here is committed to git.

There is exactly **one hard blocker** that Claude Code cannot fetch on its own
(it is behind a free login). Everything else can be auto-fetched, but links are
listed so you can pre-stage them if you prefer.

---

## 1. REQUIRED — login-gated, you must download this

### TIMS / SWITRS geocoded crash data  →  data/raw/switrs/<YYYYMMDD>/
- Site: https://tims.berkeley.edu  (free account; password is emailed instantly)
- Tool: "SWITRS GIS Map" or "SWITRS Query & Map" → filter to **City of San Diego**,
  date range **2015-01-01 → 2024-12-31**, then "Download Raw Data".
- The download dialog offers three files — **download all three** (same CASE_ID key):
  - **Crashes**  → save as `crashes.csv`  (REQUIRED — carries COLLISION_SEVERITY + POINT_X/POINT_Y; this alone covers Milestone 1)
  - **Parties**  → save as `parties.csv`  (later milestones: DUI, party movement, vehicle type)
  - **Victims**  → save as `victims.csv`  (later milestones: ped/bike involvement, victim severity/age)
- Codebook / geocoding docs: https://tims.berkeley.edu (Help page)
- Acknowledgement is required when publishing (cite TIMS / SafeTREC, UC Berkeley).

> The Crashes file is the project's **label backbone**. The pipeline will not produce
> real labels without it.

---

## 2. OPTIONAL — Claude Code can auto-fetch these (no auth); links for pre-staging

### City of San Diego drivable road graph  →  data/raw/osm/<YYYYMMDD>/
- Pulled automatically via OSMnx (`place="San Diego, California, USA"`,
  `network_type="drive"`). Only stage a cached `sandiego_drive.graphml` here if you
  want a frozen snapshot or you're offline.

### Community Planning Districts (spatial-blocking units)  →  data/raw/cpa/<YYYYMMDD>/
- https://data.sandiego.gov/datasets/gis-community-planning-districts/
  Prefer **GeoJSON** (one file) over shapefile. Save as `community_planning_districts.geojson`.
  If absent, the splitter falls back to a ~2 km grid.

### City boundary (clip mask)  →  data/raw/cpa/<YYYYMMDD>/
- https://data.sandiego.gov/datasets/gis-city-boundary/
  Prefer **GeoJSON**. Save as `city_boundary.geojson`.

### SDPD collisions — NOT NEEDED if you have TIMS
- Was only a development stand-in. Skip unless you later want the optional
  SWITRS-vs-SDPD under-reporting check for the equity section, in which case:
  data/raw/sdpd/<YYYYMMDD>/  · https://data.sandiego.gov/datasets/police-collisions/
  + https://data.sandiego.gov/datasets/police-collisions-details/

---

## County scope probe (Milestone 2.5 — only if running the scope decision)

### TIMS / SWITRS — County of San Diego  →  data/raw/switrs_county/<YYYYMMDD>/
- Same site/account as the city pull: https://tims.berkeley.edu
- Re-run the query with **County = San Diego, City = (leave blank / All)**, same date
  range **2015-01-01 → 2024-12-31**, download all three files:
  - Crashes → `crashes.csv`   Parties → `parties.csv`   Victims → `victims.csv`
- This includes CHP-reported freeway/ramp KSI (flagged via `STATE_HIGHWAY_INDICATOR`);
  the probe filters those out for the surface-street count and reports their share.
- The county drivable graph is pulled automatically by OSMnx into
  `data/raw/osm_county/<YYYYMMDD>/` (large; may be clipped to the urbanized footprint).

---

## Later milestones (not needed for Milestone 1)
- SanGIS roads/zoning, bike facilities, transit GTFS (MTS), ACS demographics
  (`census`/`pygris`), DEM slope, FARS fatal anchor. See §1 Dataset Inventory in Notion.
- Optional Fig-1 overlay: San Diego Vision Zero **High Injury Network** layer
  (the design derives hotspot exclusion from the data itself, so this is cosmetic).
