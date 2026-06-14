# Research Design (locked)

Distilled from the Research Design Document. Runtime constants live in `../configs/config.yaml`.

## Question

Predict which **currently non-hotspot** intersections in the City of San Diego will
**emerge** as severe-injury (KSI) locations over a 3-year horizon, using only information
available before the horizon. The policy use is a ranked shortlist for proactive
Vision-Zero-style intervention at sites without a crash history that would already flag them.

## Unit of analysis

One row = one intersection = a canonical node in the City of San Diego **drivable** road
graph (OpenStreetMap, simplified), **surface-street only**.
- Near-duplicate nodes merged within **10 m**.
- `intersection_id` = stable hash of node coordinates rounded in EPSG:2230.
- **Surface-street filter:** exclude nodes whose incident edges are `motorway` /
  `motorway_link` (freeway mainline + ramps). `trunk`/`trunk_link` is a reported
  borderline class. (Rationale: freeway KSI are segment/ramp events, not intersection
  events, and they geocode differently — see DECISIONS.md on the coordinate bug.)

## Coordinate systems

- **EPSG:2230** (NAD83 / California State Plane Zone VI, US survey feet) — all distance
  and buffer math.
- **EPSG:4326** (WGS84) — mapping and the source CRS of crash coordinates.

## Influence area

**76.2 m radius** (= 250 US survey feet) around each node. KSI crashes are assigned to
their **nearest** node and counted only if within this radius (`nearest_within_buffer`).
(Originally 30 m; widened — see DECISIONS.md. The SafeTREC geocoder also offsets crashes
a short distance from the intersection, which a tight buffer would miss.)

## KSI definition

A collision with SWITRS `COLLISION_SEVERITY ∈ {1 (fatal), 2 (severe injury)}`.

## Time windows

- **Feature window:** 2016-01-01 → 2021-12-31 (2015 is burn-in for "time since" lookups).
- **Label window:** 2022-01-01 → 2024-12-31 (2025+ excluded as provisional/incomplete).
- **`feature_cutoff_date` = 2022-01-01.** Hard wall: nothing dated on/after may inform a
  feature or candidate eligibility. (Infrastructure features have a *separate* temporal
  wall — see FEATURE_CATALOG.md.)

## Candidate set (who is modeled)

Keep node `i` iff `KSI_feat(i) < 2` **AND** `i` is **not** in the top decile of
feature-window KSI density. This removes already-known hotspots so the model cannot win
by re-identifying the existing High Injury Network. In practice this collapses candidates
to nodes with ~zero feature-window KSI history, which is why crash-history *signal* must
come from **all-severity** crash counts/trends, not KSI counts (those are ~constant on
the candidate set).

## Target (re-scoped — see DECISIONS.md)

- **PRIMARY:** 3-year KSI **count** `cᵢ = KSI_label(i)`, modeled as a rate via
  **Tweedie/Poisson regression**. Uses all nonzero-count nodes (~389).
- **SECONDARY readout:** binary `KSI_label ≥ 1` (~389 positives). Reported honestly as
  "≥1 future KSI" — **not** "hotspot emergence".
- **EVALUATION operating point:** `KSI_label ≥ 2` (n≈22). Used only to measure whether the
  predicted ranking surfaces true emergent hotspots (recall@K / precision@K), with honest
  wide CIs. **Not** a training label.

The original design was binary ≥2 classification; the re-scope trigger (below the
~300-positive adequacy floor) moved the primary to the count/rate. See DECISIONS.md.

## Evaluation

- **Splits:** spatial-block grouped k-fold (k=5), holding out whole blocks (Community
  Planning Districts if available, else ~2 km grid), **plus** a random split. Report both;
  the random–spatial gap quantifies spatial-autocorrelation inflation.
- **Metrics:** Tweedie/Poisson deviance, **Spearman ρ** (predicted rate vs actual count)
  as the primary; AUPRC, recall@K (K∈{25,50,100}), precision@K on the binarized readouts;
  decile calibration. All with **bootstrap 95% CIs** (1000 resamples).
- **Bar to beat:** the all-severity-crash-density persistence baseline, and (from M3b on)
  the crash-only Tweedie model — infrastructure must show incremental lift over crash-only.
- **Honesty:** with ~22 ≥2-positives, expect wide CIs; overlapping CIs are not a win; an
  honest null/modest result is a valid, reportable finding.

## Scope decision

**City of San Diego only.** County-wide scope was probed and declined (target rarity is
not solved by county scale, and infrastructure data harmonization across ~18 municipalities
is costly). See DECISIONS.md.
