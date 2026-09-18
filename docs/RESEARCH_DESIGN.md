# Research Design (locked)

Distilled from the Research Design Document. Runtime constants live in `../configs/config.yaml`.

> **Current candidate set (see `DECISIONS.md` D18):** candidates are City-of-San-Diego surface
> intersections **below the City's 5-crash screen** (`crashes_feat < 5`) — 25,699 in the verified
> run, 276 with ≥1 KSI in the label window. An earlier design used a `KSI_feat < 2` screen; D18
> replaced it with the City's actual threshold. Current results: `README.md`, `docs/HYPOTHESIS.md`.

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
  events, and they geocode differently. See DECISIONS.md on the coordinate bug.)

## Coordinate systems

- **EPSG:2230** (NAD83 / California State Plane Zone VI, US survey feet): all distance
  and buffer math.
- **EPSG:4326** (WGS84): mapping and the source CRS of crash coordinates.

## Influence area

**76.2 m radius** (= 250 US survey feet) around each node. KSI crashes are assigned to
their **nearest** node and counted only if within this radius (`nearest_within_buffer`).
(Originally 30 m; widened. See DECISIONS.md. The SafeTREC geocoder also offsets crashes
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

Keep node `i` iff `crashes_feat(i) < 5` — below the City's High Crash List screen (≥5
crashes). This is the population the City cannot act on: sites it has not yet flagged, so the
model cannot win by re-identifying the City's existing list. Signal comes from sub-threshold
crash counts and trend, road infrastructure, and spatial context, since KSI counts are ~zero
across the candidate set.

## Target

- **Model target:** 3-year KSI **count** `cᵢ = KSI_label(i)`, modeled as a rate via
  **Tweedie regression**.
- **Operating threshold:** binary `KSI_label ≥ 1` (any-KSI). The shortlist is scored on how
  many any-KSI sites it captures. Reported as "future injury-crash emergence".
- **Severe (`KSI_label ≥ 2`):** not a target. Too few positives, and a raw crash-count
  baseline catches more of them.

## Evaluation

- **Splits:** spatial-block grouped k-fold (k=5), holding out whole blocks (Community
  Planning Districts if available, else ~2 km grid), **plus** a random split. Report both;
  the random–spatial gap quantifies spatial-autocorrelation inflation.
- **Metrics:** Tweedie deviance, **Spearman ρ** (predicted rate vs actual count), recall@K and
  precision@K (K∈{50,100,200,500,1000}) on the any-KSI readout, decile calibration. All with
  **bootstrap 95% CIs** (1000 resamples).
- **Bar to beat:** the persistence baseline (rank by crash count and trend). Crash-only ranks
  below it; road infrastructure and spatial-neighbor features move the model above it.
- **Sample size:** the positive count keeps CIs wide. A modest edge that holds across both
  splits and both windows is the reportable result, not a single-split gap.

## Scope decision

**City of San Diego only.** County-wide scope was probed and declined (target rarity is
not solved by county scale, and infrastructure data harmonization across ~18 municipalities
is costly). See DECISIONS.md D11 for the implementation bug that, until 2026-06-20, caused
the candidate set to span the full county rather than enforcing this decision.
