# Milestone Final — Project Wrap-Up

**Date:** 2026-06-20
**Status:** RESEARCH COMPLETE

---

## 1. Project Status

### Verified Run (primary scientific result)

**Feature window: 2016-2021 → Label window: 2022-2024 | 26,423 candidates, City of San Diego only**

Model: XGBoost Tweedie regression, crash-only features, hyperparameters chosen by nested
cross-validation. Every figure below comes from genuine 5-fold out-of-fold scoring: each
prediction is made by a fold that never saw that row during training. The candidate set is
restricted to intersections actually inside City of San Diego limits; see `docs/DECISIONS.md`
D11 for the full candidate-set definition.

- **Spearman ρ (OOF):** 0.128 (random) / 0.131 (spatial). Statistically tied with (and
  slightly behind) the persistence baseline (ρ = 0.133, no fitting required, rank by recent
  crash count and trend).
- **21 confirmed emergent sites** (≥2 KSI in label window).
- **Recall@K, ≥2 KSI threshold, random split:**

| K | Hits (random/spatial) | Recall | Persistence baseline |
|---|---|---|---|
| 50 | 1/21 · 1/21 | 4.8% | 3/21 (14.3%) |
| 100 | 3/21 · 1/21 | 4.8-14.3% | 4/21 (19.0%) |
| 200 | 5/21 · 5/21 | 23.8% | 6/21 (28.6%) |
| 500 | 10/21 · 9/21 | 42.9-47.6% | 10/21 (47.6%) |
| 1,000 | 16/21 · 15/21 | 71.4-76.2% | 13/21 (61.9%) |

The persistence baseline ties the tuned model exactly at K=500 on the random split (10/21
both); on the spatial split the baseline edges ahead (10/21 vs. the model's 9/21). This
threshold doesn't show a clear ML-specific advantage at this sample size.

- **BCR (top-500, ≥2 threshold, 30% treatment effectiveness): about 9.6:1 (random) / 8.7:1
  (spatial)**, vs. the baseline's 9.6:1 (the model and baseline catch the same 20 events on
  the random split). Fatal share 24.3%, measured directly from raw SWITRS crashes in the
  2022-2024 label window.
- **BCR (top-500, ≥1 threshold): about 40.4:1 (random) / 38.5:1 (spatial)**, vs. the
  baseline's 34.2:1. This is the model's clearest validated edge over the trivial heuristic.
- **Infrastructure feature test:** road geometry and the full infrastructure set show a
  **consistent** positive delta on both splits (+0.020 to +0.021 Spearman ρ). This is a
  promising finding, not yet a settled one given n=21 positives; see `docs/DECISIONS.md` D8.
- **Architecture comparison:** XGBoost (frozen and freshly tuned), Random Forest, and a
  PyTorch MLP neural network were all compared on the same genuine out-of-fold protocol
  (`scripts/model_bakeoff_oof.py`). The neural network was consistently the weakest
  performer, too few positive examples (n=21) for deep learning to find anything stable.
  No architecture decisively beat the persistence baseline at the ≥2-KSI threshold.
- **Leakage audit:** 9/9 PASS (temporal and feature leakage checks specific to the feature
  pipeline; separate from the out-of-fold evaluation protocol used for the headline
  metrics above, and separate from the candidate-set scope issue in D11).
- **Geocoding correction:** verified, POINT_X/POINT_Y used throughout.

### Forward Run (operational prediction)

**Feature window: 2016-2024 → Label window: 2025-2027 | 26,045 candidates, City of San Diego only**

The current operational prediction. The dashboard runs on this. 2025 labels are complete
(SWITRS 20260615); 2026-2027 are future. Sources: 20260608 (primary, includes 2015 burn-in)
+ 20260615 (2025 crash data), deduplicated on CASE_ID.

- **Methodology:** the deployed model is fit ONCE on the verified-run's own resolved
  window (2016-2021 features → 2022-2024 labels) and applied via predict-only to current
  2016-2024 forward-candidate features (`scripts/predict_forward_run.py`). It is never
  retrained on the forward candidates' own (partially-resolved) 2025-2027 outcome. Full
  methodology notes: `docs/DECISIONS.md` D17.
- **Emergent sites ≥2 KSI:** 2 (2025 data only, the 2025-2027 window is incomplete).
- **Sites ≥1 KSI (2025 data):** 108.
- **Recall@K, ≥1 KSI** (predict-only, leakage-free by construction; no random/spatial split
  needed since no fitting happens on forward candidates):

| K | Hits | Events | Recall | Lift vs. random |
|---|---|---|---|---|
| 50 | 2 | 2 | 1.9% | 9.6x |
| 100 | 3 | 3 | 2.8% | 7.2x |
| 200 | 9 | 9 | 8.3% | 10.9x |
| **500** | **24** | **24** | **22.2%** | **11.6x** |
| 1000 | 38 | 38 | 35.2% | 9.2x |

Treat this run's numbers as provisional. Only one of three label years is in, and there are
too few ≥2-KSI positives so far (2, neither caught through K=1000) for that threshold to
mean anything yet.

**Cost breakdown at K=500 (≥1 KSI):** fatal share 13.6% (measured from raw SWITRS, 2025-2027
window), blended cost/event $3,647,574, total harm at the 24 caught events ≈ $87.5M,
prevented at 30% treatment effectiveness ≈ $26.3M, city program cost (90% HSIP funding,
same 500-site assumption as the verified run) $3.2M, **BCR ≈ 8.2:1**. Lower than the
verified run's ≥1-KSI BCR (40.4:1) mainly because the fatal share is lower this year and only
one label year is resolved. Treat as provisional, same as the recall figures above.

### Dashboard

Live on the forward run. GeoJSON exported to `dashboard/public/data/`. Feature window
2016-2024, predicting 2025-2027. The live predictions are produced by the same predict-only
scoring described above (D17). Fit once on resolved historical data, applied to current
features, never retrained on an outcome that's already happened.

---

## 2. What Has Been Validated vs. What Is Pending

### Validated

- **Spearman ρ** (random and spatial splits, verified run, genuine out-of-fold scoring):
  0.128 / 0.131, statistically tied with (and slightly behind) the persistence baseline.
- **Full-population recall@K** (verified run, all 26,423 City-of-San-Diego candidates):
  47.6% of the 21 emergent sites caught in the top-500 (random split; 42.9% spatial split).
- **Candidate-set scope** (D11): restricted to the actual City of San Diego (26,423
  candidates).
- **Infrastructure feature test** (frozen hyperparameters, Protocol A, Sets A-D and
  extended Groups E/G/H): a consistent, if small, positive signal on the candidate set.
  Group F (ACS demographics) is the only one not yet re-tested, see `docs/DECISIONS.md` D9.
- **Prospective 2025 evaluation**: 24/108 (22.2%) at K=500, 2016-2024 features (the most
  current data available), scored against true 2025 outcomes never seen during training.
- **Dashboard data**: `dashboard/public/data/` reflects the 26,045 City-of-San-Diego
  forward-run candidates; Council district assignment matches every candidate (0
  unassigned).
- **All leakage audit checks (A1-A9):** 9/9 green on both pipeline runs.
- **Geocoding:** POINT_X/POINT_Y used throughout, the SafeTREC street-intersection
  geocoded coordinates.

### Pending

- **2026-2027 label completion:** the ≥2-KSI threshold on the forward run can't be
  evaluated until 2026 and 2027 SWITRS data are released (roughly early 2027 and 2028).
- **Engineering effectiveness:** whether intervention at flagged sites actually reduces
  subsequent KSI outcomes. This needs tracking which sites get treated and their 2028+
  outcomes.
- **Group F (ACS demographics) re-test:** needs a Census API key supplied again; not
  stored anywhere in this repo by design.

---

## 3. Forward-Run Results

**Panel:** 26,045 candidates (City of San Diego only) | 2 emergent (≥2 KSI, 2025 data) | 108 (≥1 KSI, 2025 data)

Sources: 20260608 (2015-2024) + 20260615 (2025), deduplicated on CASE_ID.

**Recall@K, ≥1 KSI threshold, 2025 data only, predict-only scoring (D17):**

| K | Hits | Recall |
|---|---|---|
| 50 | 2/108 | 1.9% |
| 100 | 3/108 | 2.8% |
| 200 | 9/108 | 8.3% |
| **500** | **24/108** | **22.2%** |
| 1000 | 38/108 | 35.2% |

Sets B-D (infrastructure feature groups) were re-evaluated on the forward-run window with
the same predict-only methodology (`scripts/predict_protocol_a_forward.py`). Unlike the
verified run, none of them improve on crash-only here. Spearman deltas are small and
negative (B −0.014, C −0.006, D −0.015); see `results/protocol_a_forward_results.json` and
`docs/DECISIONS.md` D17.

---

## 4. Recommended Next Steps (non-modeling)

**a. Lead outreach with the numbers in this document.**
The verified-run model catches 43-48% of severe-emergence sites at the top-500 (BCR about
8.7-9.6:1, tied with the trivial baseline on the random split at this threshold), and a
stronger 19-20% / ~38-40:1 BCR at the broader any-injury threshold. The honest framing,
that a simple crash-trend ranking gets close to the same result at the severe threshold, is
a stronger pitch than an unqualified ML claim: it's auditable, explainable to a
non-technical audience, and the city isn't doing either version today.

**b. Outreach to Vision Zero SD and UCSD TREDS.**
Templates live in Notion under Outreach & Connections. Update them with the numbers in
this document before sending anything.

**c. Share the dashboard with City Traffic Engineering as the pitch tool.**
The forward run is live and shows the 2016-2024 feature-trained rankings for the
2025-2027 prediction horizon. Offer to present alongside the verified-run validation
numbers above.

**d. When 2026-2027 SWITRS data is released:**
Re-run `scripts/predict_forward_run.py` and `scripts/compute_verified_numbers.py` to update
the forward-run recall@K with the newly-resolved labels. No re-fitting is needed — the
deployed model stays frozen on the verified-run window (D17); only the candidate scoring
and the truth labels checked against it change.

**e. If the city conducts engineering reviews at flagged sites:**
Track which sites get treated and compare 2028+ outcomes. This would be the strongest
possible validation available to the project. Document treatment type, date, and cost for
the BCR computation.

**f. Infrastructure-feature finding (D8) does not yet replicate on the forward run.**
Re-tested with leakage-free predict-only scoring (`scripts/predict_protocol_a_forward.py`,
D17): Spearman deltas vs. crash-only are small and negative (B −0.014, C −0.006, D −0.015),
the opposite direction from the verified run's +0.020/+0.021. Worth re-checking again once
2026-2027 forward-run labels grow the positive count beyond the current 108.

---

## 5. File Index

| File | Role |
|---|---|
| `data/model/verified_run/` | Verified run archive, City of San Diego only (frozen_scores.parquet, candidate_panel.parquet, feature_table.parquet, oof_scores.parquet) |
| `data/model/verified_run/candidate_panel_COUNTYWIDE_backup.parquet` | Pre-D11 county-wide candidate set, kept for reference |
| `data/model/forward_run/` | Forward run archive, City of San Diego only |
| `scripts/restrict_candidates_to_city_limits.py` | Restricts the candidate set to City of San Diego limits (D11) |
| `reports/verified_canonical_numbers.json` | All canonical figures, both runs, genuine out-of-fold scoring |
| `results/oof_verified_run_results.json` | Full verified-run out-of-fold results |
| `scripts/predict_forward_run.py` | Forward-run scoring: fit once on verified-run window, predict-only on forward candidates (D17) |
| `results/recall_evaluation.json` | Forward-run / prospective-2025 recall@K (same artifact, D17) |
| `results/protocol_a_oof_results.json` | Infrastructure feature-set comparison, genuine OOF (verified run) |
| `scripts/predict_protocol_a_forward.py` | Infrastructure feature-set comparison, predict-only (forward run, D17) |
| `results/protocol_a_forward_results.json` | Infrastructure feature-set comparison results, forward run |
| `results/model_bakeoff_oof_results.json` | Architecture comparison (XGBoost/RF/MLP), genuine OOF |
| `results/ablation_results.csv` | Infrastructure feature-set comparison, Sets A-D |
| `dashboard/public/data/` | Forward run GeoJSON for the live dashboard |
| `results/top500_verified_2022_2024.csv` | Verified-run top-500 shortlist |
| `results/top500_forward_2025_2027.csv` | Forward-run top-500 shortlist |
| `results/model_performance.json` | All metrics, all runs |

---

## 6. Evaluation Methodology

This section explains how the headline figures should and shouldn't be interpreted.

### Recall@K is a full-population figure

The recall@K figures reported throughout (for example, 47.6% of 21 emergent sites in the
top-500 for the verified run) are full-ranking figures: every one of the 26,423 candidates
is scored by a model that never trained on it (via out-of-fold scoring) and recall is
computed across the whole population. No candidates are excluded from the ranking itself,
only from training the specific fold that scores them.

A single random 80/20 test split can show misleadingly high recall by chance, if few
emergent sites happen to land in that one held-out fold. The out-of-fold protocol used
throughout this project avoids that by scoring the entire population, not a single small
held-out slice.

### What out-of-fold scoring means here

For both the random-stratified and spatial-block splits, the panel is divided into 5
folds. For each fold, the model is fit on the other 4 folds only and used to predict that
fold. Every candidate ends up with exactly one prediction from a model that never saw its
label. Hyperparameters are tuned once via nested cross-validation and reused across folds,
they aren't re-tuned per fold.

### The candidate set is the City of San Diego, not San Diego County

The candidate set (`src/ingest/osm_loader.py`, restricted via
`scripts/restrict_candidates_to_city_limits.py`) is limited to intersections inside the
City of San Diego boundary, not the broader county. See `docs/DECISIONS.md` D11 for the
full candidate-set definition.

### Forward run vs. live dashboard predictions

The forward run's operational top-500 list (feature window 2016-2024, label window
2025-2027) is a genuine prospective prediction: scores are locked using only data through
2024, and 2025-2027 outcomes are checked against that fixed ranking as they arrive. The
2025 SWITRS data (20260615) is used only for label computation, not for feature
construction or training. 2026-2027 outcomes are still in the future as of this writing.

The dashboard's live predictions are produced by a model fit on all available historical
data, which is the correct approach for a deployed model: there's no future label to leak
when scoring intersections whose outcomes haven't happened yet. The out-of-fold evaluation
methodology above governs how much confidence to place in the model's claimed accuracy,
not what it predicts.

### SWITRS data sources

| Run | Primary source | Secondary source | Feature window | Label window |
|---|---|---|---|---|
| Verified | 20260608 (2015-2024) | — | 2016-2021 | 2022-2024 |
| Forward | 20260608 (2015-2024) | 20260615 (2025, deduplicated on CASE_ID) | 2016-2024 | 2025-2027 |

2015 records in 20260608 are used only for `years_since_last_crash` burn-in; they
contribute no KSI feature counts (the feature window starts 2016-01-01). All
STATE_HWY_IND='Y' crashes are excluded from both runs.

### Test suite uses synthetic data

The pytest suite (`tests/`) tests pipeline logic on synthetically generated data. Tests
that load real pipeline artifacts (parquet files in `data/model/`) are marked
`@pytest.mark.integration` and skip if those artifacts are absent. No test-suite result
should be read as evidence of model performance on real crash data. To run only the unit
tests: `pytest -m "not integration"`.
