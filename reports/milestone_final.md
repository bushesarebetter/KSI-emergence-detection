# Milestone Final — Project Wrap-Up

**Date:** 2026-06-14
**Status:** RESEARCH COMPLETE

---

## 1. Project Status

### Verified Run (primary scientific result)

**Feature window: 2016-2021 → Label window: 2022-2024 | 81,007 candidates**

This is the fully validated result and is the basis for all paper claims.

- **Spearman ρ:** 0.175 (random) / 0.169 (spatial). CI-separated above persistence baseline (0.085/0.108). Both splits.
- **22 confirmed emergent sites** (≥2 KSI in label window).
- **Recall@K (verified run, ≥2 KSI threshold):**

| K | Hits | Recall | Lift |
|---|---|---|---|
| 50 | 5/22 | 22.7% | 368× |
| 100 | 6/22 | 27.3% | 221× |
| 200 | 8/22 | 36.4% | 147× |
| 500 | 13/22 | 59.1% | 96× |
| 1,000 | 17/22 | 77.3% | 63× |

- **BCR (top-500, ≥2 threshold, 30% treatment effectiveness): ~13:1**
- **Sufficiency null (Protocol A):** CONFIRMED. All three infrastructure feature groups reduce Spearman rank correlation vs crash-only under frozen hyperparameters. Crash history alone is sufficient.
- **Leakage audit:** 9/9 PASS.
- **Geocoding correction:** verified — POINT_X/POINT_Y used throughout.

### Forward Run (operational prediction)

**Feature window: 2016-2023 → Label window: 2024-2026 | 80,736 candidates**

Most current operational prediction. Dashboard is live on this run. 2024 labels are complete and provide partial prospective validation.

- **Spearman ρ:** 0.0948 (random) / 0.1084 (spatial). Lower than verified run — expected, as only one year of the three-year label window is complete.
- **Emergent sites ≥2 KSI:** 0 (insufficient label data — two complete years required for ≥2 threshold).
- **Sites ≥1 KSI (2024 data):** 118.
- **Recall@K (forward run, ≥1 KSI, 2024 data only):**

| K | Hits | Recall | Lift |
|---|---|---|---|
| 50 | 7/118 | 5.9% | 96× |
| 100 | 14/118 | 11.9% | 96× |
| 200 | 20/118 | 16.9% | 68× |
| 500 | 28/118 | 23.7% | 38× |
| 1,000 | 43/118 | 36.4% | 29× |

### Dashboard

Live on the forward run. GeoJSON exported to `dashboard/public/data/`. Vintage badge updated: "Forward run | 2016-2023 features | Predicting 2024-2026".

### Claims Audit

Clean. All figures sourced from `reports/verified_canonical_numbers.json`. Number provenance tracked in `reports/claims_audit.csv`.

---

## 2. What Has Been Validated vs What Is Pending

### Validated

- **Spearman ρ** (random and spatial splits, verified run): 0.175 / 0.169, CI-separated from persistence baseline.
- **Full-ranking recall@K** (verified run, all 81,007 candidates): 59.1% of 22 emergent sites in top-500.
- **Sufficiency null** (Protocol A, frozen hyperparameters): infrastructure features do not add independent signal at 76.2m intersection resolution.
- **All leakage audit checks (A1-A9):** 9/9 green on both pipeline runs.
- **Geocoding correction:** POINT_X/POINT_Y verified as the correct coordinate source; LATITUDE/LONGITUDE confirmed as freeway-biased and rejected.
- **Coordinate-bug correction:** M1/M2 results were freeway-contaminated; all published figures use the corrected M2.5+ pipeline.

### Pending

- **True prospective validation:** Compare forward-run top-500 against 2025-2027 SWITRS outcomes when available. This is the study's strongest prospective test.
- **2025-2026 label completion:** The ≥2 KSI threshold on the forward run cannot be evaluated until 2025 and 2026 SWITRS data are released (~early 2027 and 2028 respectively).
- **Engineering effectiveness:** Whether intervention at flagged sites reduces subsequent KSI outcomes. Requires tracking which sites receive treatment and their 2028+ outcomes.

---

## 3. Forward-Run Results (from pipeline output)

**Panel:** 80,736 candidates | 0 emergent (≥2 KSI, partial) | 118 (≥1 KSI, 2024 only)

**Protocol A (frozen M3a hyperparameters):**

| Set | Random ρ | Spatial ρ | Lift (R) | Lift (S) |
|---|---|---|---|---|
| A_crash_only | 0.0948 | 0.1084 | — | — |
| B_road_geometry | 0.0497 | 0.0570 | -0.0451 | -0.0514 |
| C_signals | 0.0750 | 0.0856 | -0.0198 | -0.0228 |
| D_all_infra | 0.0537 | 0.0594 | -0.0410 | -0.0490 |

Verdict: NULL CONFIRMED. Best set: A_crash_only. Consistent with verified-run Protocol A result.

**Recall@K (forward run, ≥1 KSI threshold, 2024 data only):**

| K | Hits | Recall | Lift |
|---|---|---|---|
| 50 | 7/118 | 5.9% | 96× |
| 100 | 14/118 | 11.9% | 96× |
| 200 | 20/118 | 16.9% | 68× |
| 500 | 28/118 | 23.7% | 38× |
| 1,000 | 43/118 | 36.4% | 29× |

**Dashboard export (forward run):**
- 80,736 candidates | 0 emergent (≥2) | 118 (≥1)
- Recall@200 (≥1 KSI): 16.9% (68× random)
- Unnamed intersections: 0
- Nodes outside district polygons in top-1000: 127

---

## 4. Recommended Next Steps (non-modeling)

**a. Submit TMLR paper using verified-run results.**
Lead claim: crash-history-only model detects emerging KSI hotspots at previously-clean
intersections with CI-separated rank signal (Spearman ρ=0.175); recall@500=59% on 22
confirmed emergent sites; infrastructure features add no independent signal (sufficiency null).
Secondary: operational framing of the recall@K shortlist. Target: TMLR (no page limit, open access).

**b. Outreach to Vision Zero SD and UCSD TREDS.**
Emails and contacts in Notion > Outreach & Connections. Lead with the BCR (13:1) and the
city-comparison framing (0% vs 59% at top-500).

**c. Share dashboard with City Traffic Engineering as the pitch tool.**
The forward run is live and shows the 2016-2023 feature-trained rankings for the 2024-2026
prediction horizon. Offer to present alongside the verified-run validation numbers.

**d. When 2025 SWITRS data is released (~early 2027):**
Run `python scripts/compute_verified_numbers.py` to update the forward-run recall@K.
This is the prospective validation moment — the first time the forward-run top-500 can be
compared against actual outcomes. If the model performs at verified-run levels, the prospective
validation is complete.

**e. If city conducts engineering reviews at flagged sites:**
Track which sites receive treatment and compare 2028 outcomes — the study's strongest
possible validation. Document treatment type, date, and cost for BCR computation.

---

## 5. File Index

| File | Role |
|---|---|
| `data/model/model_scores.parquet` | Verified run scores (immutable — do not modify) |
| `data/model/frozen_scores.parquet` | Forward run scores (Set A–D, 80,736 candidates) |
| `data/model/xgb_tweedie.pkl` | Verified run model (M3a frozen hyperparameters) |
| `data/model/candidate_panel.parquet` | Forward run panel with 2024-2026 labels |
| `reports/verified_canonical_numbers.json` | All canonical figures, both runs |
| `reports/claims_audit.csv` | Number provenance audit |
| `reports/milestone4.md` | M4 Protocol A ablation + recall@K results |
| `dashboard/public/data/` | Forward run GeoJSON for live dashboard |
| `final_github/results/top500_verified_2022_2024.csv` | Validated top-500 (immutable) |
| `final_github/results/top500_forward_2024_2026.csv` | Forward run top-500 |
| `final_github/results/model_performance.json` | All metrics, all runs |
| `final_github/README.md` | Public-facing documentation |
