# Feature Catalog

Status legend: **[done]** implemented & validated on the corrected panel ·
**[planned]** designed, built in its milestone · **[deferred]** later milestone.

All features are computed on **feature-window data only** (< `feature_cutoff_date` =
2022-01-01) unless a separate temporal wall is noted. Attach to `intersection_id`; carry a
`*_missing` flag where a source field is absent.

## TWO temporal-validity walls (read before adding features)

1. **Crash wall** (`feature_cutoff_date = 2022-01-01`): no crash dated on/after may inform
   any feature. Enforced by the leakage audit.
2. **Infrastructure wall** (NEW, M3b): OSM/SanGIS describe infrastructure *as of the pull
   date (2026)*. Features must reflect ≤ 2021. Treat as:
   - **Static / safe:** geometry, edge/leg count, functional class, slope/grade, road
     class: assume time-invariant; current values are fine.
   - **Endogenous / risky:** traffic signals, stop control, bike lanes, speed limits: these
     are often installed *as countermeasures to* the crashes being predicted. Use a
     **historical OSM snapshot as of 2021-12-31** (Overpass attic data), or run an
     exclusion-sensitivity check. Using 2026 values as 2016–2021 features is leakage.

## Group 1 — Crash history (all-severity)  [done]

Computed on **all-severity** crashes (KSI-specific versions are ~zero-variance on the
candidate set — see DECISIONS.md D1). In buffer (76.2 m), feature window:
`crashes_36mo`, `crashes_72mo`, `ped_crashes_72mo`, `bike_crashes_72mo`, `broadside_72mo`,
`left_turn_72mo`, `dui_72mo`, `night_72mo`, `ped_row_violation_72mo`,
`years_since_last_crash`, `distinct_crash_days_72mo`, `worst_severity_72mo`.
**Dropped (logged, zero-variance on candidates):** `ksi_72mo`, `years_since_last_ksi`.
**Deferred (need exposure/ADT):** `crash_rate_per_MEV_72mo`, `ksi_rate_per_MEV_72mo`.

## Group 2 — Emergence / temporal trend  [done]

Computed on all-severity crash density over the feature window:
`crash_trend_slope` (Theil–Sen), `emergence_velocity`, `emergence_acceleration`,
`mann_kendall_tau`, `changepoint_prob`, `ewma_crashes`, `momentum_ratio`,
`covid_period_share`.

## Group 3 — Intersection geometry  [done: M3b]

`edge_count` (approach legs), `lane_count`, `approach_asymmetry`, `intersection_type`.
Source: OSM current graphml (static — safe). Coverage: `lane_count` 34.3%; others 100%.
Missing flag: `lane_count_missing`.

## Group 4 — Signal / stop control  [done: M3b, ENDOGENOUS — 2021 vintage]

`signal_present` (3.6% candidates positive), `stop_control` (9.5% positive).
Source: Overpass attic API snapshot @ 2021-12-31. Both 100% defined (binary 0/1).
Missing flags: `signal_present_missing`, `stop_control_missing`.

## Group 5 — Roadway environment  [done: M3b]

`functional_class` [static, 100% coverage], `freeway_proximity` [static binary, 100%],
`speed_limit` [endogenous: 4.8% from 2021 OSM vintage; 95.2% gap-filled from 2026 OSM;
total coverage 19.5%; flagged `speed_limit_vintage`=0/2/3, `speed_limit_missing`].
Source: OSM graphml (static) + Overpass attic 2021 (speed_limit).

## Group 6 — Active transport  [done: M3b, partly ENDOGENOUS]

`bike_lane_present` (2.1% candidates, 2021 vintage), `transit_proximity` (29.7% within
400 m, MTS GTFS current feed ≈ static), `transit_prox_m` (continuous distance).
Source: Overpass attic 2021 (bike lanes) + MTS GTFS download (stops).
Missing flags: `bike_lane_missing`, `transit_prox_missing`.

## Group 7 — Terrain  [done: M3b, partial — slope 60.1% coverage]

`slope_pct` (rise/run × 100, mean=4.93%, sd=26.95%), `slope_pct_missing`.
Source: USGS 3DEP 1m DEM via py3dep (static — safe), returned in EPSG:5070 (Albers metres).
Coverage: 48,693/81,007 nodes (60.1%), measured against the county-wide candidate set;
pending re-measurement against the corrected 26,423-candidate City-of-San-Diego-only set.
A supplemental terrain-only ablation is run separately from the primary ablation panel.

## Group 8 — Demographics / land use  [deferred]

ACS-derived context (population/employment density, equity indicators), land-use mix.
Source: ACS (`census`/`pygris`), SanGIS zoning.

## Group 9 — Spatial-neighbor structure  [done]

Summarize the area around each intersection over the feature window
(`src/features/build_spatial_features.py`): `nbr_crashes_150m`, `nbr_crashes_400m` (local crash
pressure), `nbr_ksi_400m`, `n_hotspots_400m` and `dist_nearest_hotspot_m` (adjacency and
proximity to the City's ≥5-crash sites), `node_density_400m` (grid density). Feature-window
crashes only. These carry the strongest univariate signal on the candidate set (AUC 0.74–0.79)
and lift the model above the persistence baseline; the lift survives the region-holdout split,
so it is corridor signal rather than spatial autocorrelation. GraphSAGE and higher-order graph
features remain deferred.

## Modeling discipline

Positives are scarce (276 any-KSI on the verified candidate set). Keep the feature count
disciplined; prefer group-level comparison over a kitchen-sink model; strong regularization;
rely on spatial-block CV to expose overfitting. A feature group earns inclusion only by showing
**incremental Tweedie Spearman lift over crash-only in both splits**, with bootstrap CIs.
Crash-only ranks below the persistence baseline; infrastructure (Groups 3–7) and spatial
structure (Group 9) are what move the model above it.
