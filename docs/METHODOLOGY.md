# Methodology

## Candidate Set Construction

The unit of analysis is a single intersection, defined as a canonical node in the City of San
Diego drivable road graph derived from OpenStreetMap (via OSMnx), restricted to surface
streets. Nodes whose incident edges are classified as `motorway` or `motorway_link` (freeway
mainline and on/off-ramps) are excluded, because freeway KSI events are segment-level, not
intersection-level, and geocode differently from urban intersection crashes. Nodes are merged
within 10 meters to eliminate near-duplicates arising from OSMnx graph simplification.

To restrict the model to intersections without existing KSI exposure — the population of
interest for proactive intervention — we removed any intersection in the top decile of
feature-window KSI density and any intersection with two or more KSI crashes in the feature
window. This exclusion is by design: the candidate set collapses to nodes with approximately
zero KSI history, which forces signal to come from all-severity crash counts and temporal
patterns rather than past KSI incidents. The result is a candidate set of 81,007 surface
intersections for the original verified run.

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

The forward run shifts both windows forward (features 2016–2023, labels 2024–2026)
to generate the most current actionable ranking. 2024 label outcomes are now complete;
2025–2026 will be available when the next SWITRS export is released (~early 2027).

## Tweedie Regression Model

The primary modeling target is the three-year KSI count in the label window, modeled as a
rate via Tweedie regression (XGBoost with `objective=reg:tweedie`). The Tweedie distribution
is appropriate for this target because KSI counts at individual intersections are sparse,
right-skewed, and include a large mass at zero. The variance power (approximately 1.12) was
tuned via Optuna on the crash-only feature set and then frozen for all subsequent experiments.

We considered binary classification (label ≥ 2 KSI) as the primary target in the original
research design, but the pre-registered adequacy floor of approximately 300 positives was not
met (the corrected candidate set produced 22 sites with ≥2 KSI, well below the floor). Per
the pre-registered fallback, the primary target was switched to the count/rate. Binary
thresholds (≥1 KSI and ≥2 KSI) are retained as secondary readouts; the ≥2-KSI threshold
is used only for the recall@K evaluation operating point.

## Geocoding Correction

An important correction was applied between Milestone 2 and Milestone 3a. Early runs used
the SWITRS `LATITUDE`/`LONGITUDE` fields, which contain officer-reported GPS coordinates
with only approximately 44% coverage and approximately 98.5% freeway bias. The correct
field is `POINT_X`/`POINT_Y`, which provides SafeTREC street-intersection geocoded
coordinates with approximately 96–97% coverage and negligible freeway skew. All Milestone 1
and Milestone 2 numeric results were superseded by this correction; only Milestone 3a and
later results are considered valid.

## Frozen-Parameter Ablation Protocol (Protocol A)

To test whether built-environment features (road geometry, traffic signals, bike lanes, etc.)
add independent predictive signal beyond crash history, we designed a one-variable-at-a-time
ablation in which the XGBoost hyperparameters are frozen to the values tuned on the
crash-only model. This is Protocol A. It eliminates hyperparameter confounding that corrupted
an earlier ablation (Protocol B, M3b): when Optuna re-tunes hyperparameters at each step
against Tweedie deviance while reporting Spearman rank correlation, adding features that
improve deviance can paradoxically reduce Spearman, producing false negatives.

Protocol A tests four cumulative feature sets: A (crash history only, 20 features), B (A plus
road geometry and class), C (A plus signals and stop signs), and D (A plus all infrastructure).
Each set is fit with identical hyperparameters; any variation would indicate a protocol
violation. Spearman rank correlation between predicted count and actual label-window KSI count
is the primary metric, evaluated under both a random 80/20 split and a spatial-block grouped
k-fold with k=5 folds.

## Evaluation Metrics

We use two primary evaluation frameworks. Spearman rank correlation (predicted rate vs.
actual KSI count) measures the model's ability to rank intersections by risk. It is
scale-invariant, robust to the count distribution's heavy tail, and directly relevant to the
operational use case of generating a ranked shortlist.

Recall@K measures the fraction of true emergent sites (≥2 KSI in the label window) that
appear in the model's top-K ranked intersections. This metric is operationally concrete: an
agency deploying this model as a prioritization tool wants to know how many of the
subsequently dangerous sites would be captured by inspecting a shortlist of K intersections.
We report recall@K for K ∈ {50, 100, 200, 500, 1000} with bootstrap 95% confidence intervals
obtained by resampling the 22-positive evaluation set with replacement. With only 22 positives,
the CIs are wide by construction and should be read as directional evidence rather than
precise estimates.

Spatial blocking uses Community Planning Area polygons to form five approximately equal-area
folds. The gap between random-split and spatial-split metrics quantifies the degree of
spatial autocorrelation inflation in the random-split estimate.

All bootstrap CIs are computed with 1,000 resamples.

## Spatial Resolution and Buffer Sensitivity

Crashes are assigned to intersections using a nearest-within-buffer rule with a 76.2 m (250
US survey feet) radius in EPSG:2230 (California State Plane Zone VI). This buffer was widened
from an initial 30 m after a parameter sweep showed that positive coverage grew substantially
with radius, and because the SafeTREC geocoder systematically offsets crash coordinates a
short distance from the intersection center. A 30 m sensitivity run (applying the locked model
to features re-computed at 30 m) confirmed that full-population recall@200 is equivalent at
both buffer sizes (8/22, 36.4%), while recall@500 favors the 76.2 m buffer (13/22, 59.1%).
The 76.2 m choice is grounded in the original Spearman optimization (D2 in the decisions
log), not in recall@K.
