# Data Sources

## Critical note on SWITRS coordinate fields

Use `POINT_X` (longitude) and `POINT_Y` (latitude) in datum WGS84 (EPSG:4326), then reproject
to EPSG:2230 for all distance and buffer math. Do not use `LATITUDE`/`LONGITUDE`.

`POINT_X`/`POINT_Y` contain SafeTREC street/intersection geocoded coordinates with
approximately 96–97% coverage. `LATITUDE`/`LONGITUDE` contain officer-reported GPS
coordinates with approximately 44% coverage and heavy freeway bias. Using the wrong field
was the source of a critical data-quality error in early milestones of this project; see the
decisions log for full details.

Records with missing `POINT_X`/`POINT_Y` (approximately 3–4%) are excluded.

---

## Crash records — SWITRS via TIMS (required, login-gated, manual download)

**Source:** Statewide Integrated Traffic Records System (SWITRS), distributed via the
Transportation Injury Mapping System (TIMS) at UC Berkeley SafeTREC.

**Access:** https://tims.berkeley.edu — free account; password is emailed immediately upon
registration.

**Query used:** City of San Diego, 2015-01-01 to 2024-12-31; download Crashes, Parties, and
Victims tables (linked by `CASE_ID`).

**Storage:** `data/raw/switrs/<YYYYMMDD>/{crashes,parties,victims}.csv`

**KSI definition:** `COLLISION_SEVERITY ∈ {1 (fatal), 2 (severe injury)}`.

**Surface-street filter:** Records with `STATE_HIGHWAY_INDICATOR = Y` are excluded. These
records geocode to freeway segments rather than surface intersections and are not relevant
to intersection-level emergence prediction.

**Citation:** When publishing, cite TIMS and SafeTREC (UC Berkeley) per the portal's terms.

**Manual download required:** SWITRS data cannot be redistributed; researchers must obtain
their own export from TIMS. Row and feature counts for the version used in this study are
recorded in the project manifest files under `data/raw/switrs/<date>/manifest.json`.

---

## Road network — OpenStreetMap via OSMnx (automated, no login required)

**Source:** OpenStreetMap contributors, accessed via the OSMnx Python library.

**Query:** `place="San Diego, California, USA"`, `network_type="drive"`, `simplify=True`.

**Vintage used in feature window:** Network snapshot dated 2026 (current OSM). Graph topology
(node connectivity) is treated as static; only endogenous infrastructure attributes (signal
presence, speed limits, bike lanes) require a historical snapshot.

**Storage:** `data/raw/osm/<YYYYMMDD>/sandiego_drive.graphml` plus a `manifest.json` with
fetch date, node count, edge count, and sha256.

**Infrastructure attributes (endogenous features):** Signal presence, stop-sign presence,
speed limits, and bike lane presence use a historical OSM snapshot dated 2022-12-31
(verified run) / 2023-12-31 (forward run), obtained via the Overpass Attic API
(`overpass.kumi.systems` or `overpass-api.de`). This prevents leakage of post-feature-window
infrastructure changes into the feature set.

---

## Spatial blocking — data.sandiego.gov (automated, no login required)

**Community Planning Districts:**
City of San Diego Open Data portal.
Used to form spatial blocks for grouped k-fold cross-validation.
Storage: `data/raw/cpa/<YYYYMMDD>/community_planning_districts.geojson`.

**City boundary:**
City of San Diego Open Data portal.
Used for candidate set spatial filter (surface streets within city limits).

---

## Infrastructure data — OpenStreetMap history snapshots

Signal presence, stop sign presence, speed limits, and bike lane presence are sourced from
the Overpass Attic API using the 2022-12-31 temporal filter (verified run) and 2023-12-31
(forward run). Coverage is approximately 40%
for signals, 35% for stop signs, and 34% for bike lanes. Missing values carry explicit
`<feature>_missing` indicator columns in the feature table.

## Transit stops — MTS GTFS (automated, no login required)

**Source:** San Diego Metropolitan Transit System (MTS) General Transit Feed Specification
(GTFS) public feed.

**Used for:** `transit_proximity` binary indicator (within 200 m of any bus or rail stop).
Coverage is approximately 100% (all candidates can be evaluated).

## Terrain — USGS 3DEP 1 m DEM (automated, no login required)

**Source:** U.S. Geological Survey 3D Elevation Program, 1-meter digital elevation model,
accessed via the `py3dep` Python library.

**Used for:** `slope_pct` (percent grade at each intersection node). Coverage approximately
60% in the version used for this study; missing values carry an explicit `slope_pct_missing`
indicator.

---

## Data conventions

Raw data is treated as immutable. Each source is stored under
`data/raw/<source>/<YYYYMMDD>/` with a `manifest.json` recording the source URL, fetch date,
row or feature count, and sha256 checksum. Raw data is not committed to version control.
Processed intermediates are stored in `data/proc/` (GeoParquet). Model panels and score
files are stored in `data/model/`.
