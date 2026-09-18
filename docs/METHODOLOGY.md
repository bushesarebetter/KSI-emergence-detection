# Methodology

## Candidate Set Construction

The unit of analysis is a single intersection, defined as a canonical node in the City of San
Diego drivable road graph derived from OpenStreetMap (via OSMnx), restricted to surface
streets. Nodes whose incident edges are classified as `motorway` or `motorway_link` (freeway
mainline and on/off-ramps) are excluded, because freeway KSI events are segment-level, not
intersection-level, and geocode differently from urban intersection crashes. Nodes are merged
within 10 meters to eliminate near-duplicates arising from OSMnx graph simplification.

The candidate set is the population the City's own process cannot act on: intersections below
its screening threshold. The City's High Crash List flags intersections with five or more
crashes, so every candidate here has fewer than five crashes in the feature window
(`crashes_feat < 5`) and is invisible to that screen. This yields 25,699 surface intersections
within City of San Diego limits for the verified run. Signal comes from sub-threshold crash
counts and trend, road infrastructure, and spatial context rather than past KSI incidents. See
`docs/DECISIONS.md` D18 for the candidate-set definition and D11 for the City-limits restriction.

## Temporal Windows

We use three temporal intervals. The burn-in window (2015) provides enough lookback for
computing "years since last crash" features without leaking label-period information. The
feature window (2016-01-01 to 2021-12-31) defines the observation period from which all
predictive features are computed. The label window (2022-01-01 to 2024-12-31) defines the
outcome period. A hard wall at the feature cutoff date (2022-01-01) ensures no information
dated on or after that date informs any feature or candidate eligibility decision.

Infrastructure features (signal presence, speed limits, bike lanes) carry a separate temporal
wall: we use an OSM history snapshot dated 2021-12-31 via the Overpass Attic API rather than
current OSM data, which would leak post-feature-window infrastructure changes.

The forward run shifts both windows forward (features 2016–2024, labels 2025–2027)
to generate the most current actionable ranking. 2025 label outcomes are now complete;
2026–2027 will be available as future SWITRS exports are released.

## Tweedie Regression Model

The primary modeling target is the three-year KSI count in the label window, modeled as a
rate via Tweedie regression (XGBoost with `objective=reg:tweedie`). The Tweedie distribution
is appropriate for this target because KSI counts at individual intersections are sparse,
right-skewed, and include a large mass at zero. The variance power (approximately 1.12) was
tuned via Optuna on the crash-only feature set and then frozen for all subsequent experiments.

The operating threshold is any-KSI (≥1): the model ranks intersections by predicted count and
the shortlist is scored on how many any-KSI sites it captures. The severe threshold (≥2 KSI)
has too few positives to model — a raw crash-count baseline catches more of them — so it is not
a target.

## Geocoding

Crashes are geocoded using the SWITRS `POINT_X`/`POINT_Y` fields, which provide SafeTREC
street-intersection geocoded coordinates with approximately 96–97% coverage and negligible
freeway skew.

## Frozen-Parameter Feature-Set Comparison

To attribute any lift to features rather than re-tuning, the XGBoost hyperparameters are frozen
to the values tuned on the crash-only set and held identical across every feature set. The
comparison is cumulative: A (crash history, 20 features), D (A plus road infrastructure, 21
features), E (D plus spatial-neighbor structure — local crash pressure, proximity to the City's
≥5-crash sites, grid density, 6 features). **E is the deployed model.** Crash-only ranks below a
persistence baseline; infrastructure and spatial context are what move it above the baseline.
Spearman rank correlation between predicted count and actual label-window KSI count is the
ranking metric, evaluated under both a random 80/20 split and a spatial-block grouped 5-fold.

## Evaluation Metrics

We use two primary evaluation frameworks. Spearman rank correlation (predicted rate vs.
actual KSI count) measures the model's ability to rank intersections by risk. It is
scale-invariant, robust to the count distribution's heavy tail, and directly relevant to the
operational use case of generating a ranked shortlist.

Recall@K measures the fraction of any-KSI emergent sites that appear in the model's top-K
ranked intersections. This metric is operationally concrete: an agency deploying the model as a
prioritization tool wants to know how many subsequently dangerous sites a shortlist of K
intersections captures. We report recall@K for K ∈ {50, 100, 200, 500, 1000} with bootstrap 95%
confidence intervals. The positive count (276 in the verified run) keeps the CIs wide, so
recall differences of a few sites are read as consistency across splits and windows rather than
single-split significance.

Spatial blocking uses Community Planning Area polygons to form five approximately equal-area
folds. The gap between random-split and spatial-split metrics quantifies the degree of
spatial autocorrelation inflation in the random-split estimate.

All bootstrap CIs are computed with 1,000 resamples.

## Spatial Resolution and Buffer Sensitivity

Crashes are assigned to intersections using a nearest-within-buffer rule with a 76.2 m (250
US survey feet) radius in EPSG:2230 (California State Plane Zone VI). A parameter sweep over 30-100 m showed
that positive coverage grows substantially with radius, because the SafeTREC geocoder
systematically offsets crash coordinates a short distance from the intersection center. A 30 m
sensitivity run (applying the locked
model to features re-computed at 30 m) showed recall@K in the same broad range at both
buffer sizes, with no consistent winner once evaluated on genuinely held-out data (see
D6/D8 in the decisions log for the held-out evaluation methodology). The 76.2 m choice is
grounded in the original Spearman optimization (D2 in the decisions log), not in recall@K.
