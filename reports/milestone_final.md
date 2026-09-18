# Results of Record

**Model:** E — XGBoost Tweedie regression on crash history (20) + road infrastructure (21) +
spatial-neighbor structure (6), trained on the candidate set below the City's 5-crash screen.
Full narrative: `../README.md` and `../docs/HYPOTHESIS.md`.

---

## 1. Verified run (primary result)

**Feature window 2016–2021 → label window 2022–2024 | 25,699 candidates below the City screen,
City of San Diego.** Every figure is genuine 5-fold out-of-fold scoring: each candidate is scored
by a fold that never saw its label.

- **Spearman ρ (OOF):** 0.121 (random) / 0.122 (spatial). Persistence baseline (rank by crash
  count and trend): 0.101.
- **Operating threshold: any-KSI (≥1), 276 positives.** Recall@K, top-500: 39 sites / 40 events.
- **Model vs. baseline (top-500, any-KSI, prevented harm at 30% effectiveness):** +$7.8M random /
  +$10.9M spatial. E beats the baseline on both splits — the first model in the project to do so.
- **Economics (top-500):** $62M prevented, net $59M after ~$3.2M program cost (90% HSIP),
  **BCR ~19:1**. 100% incremental to the City, which catches $0 of these sites.
- **Feature sets:** crash-only ranks *below* the baseline; road infrastructure and spatial-neighbor
  structure move the model above it. Spatial features hold up under the region-holdout split.
- **Severe threshold (≥2 KSI):** no signal. 8–9 positives, and a raw crash-count baseline catches
  more of them. The product is injury-crash emergence.
- **Leakage audit:** 9/9 pass. **Geocoding:** POINT_X/POINT_Y throughout.

## 2. Prospective 2025 (forward run)

**Feature window 2016–2024 → label window 2025–2027 | 25,034 candidates below the City screen.**
The verified model, fit once and never retrained, scored the forward candidates predict-only against
true 2025 outcomes it never saw.

| K | sites | events | recall | lift vs. random |
|---|---|---|---|---|
| 100 | 2 | 2 | 3.2% | 8.1x |
| 200 | 2 | 2 | 3.2% | 4.0x |
| **500** | **9** | **10** | **14.5%** | **7.3x** |
| 1000 | 14 | 15 | 22.6% | 5.7x |
| 2000 | 24 | 25 | 38.7% | 4.8x |

62 any-KSI sites / 63 events in the pool (2025 partial). The 7.3x lift at top-500 matches the
verified run — the model generalizes to a year outside its training window. 2026–2027 labels
complete the window; the numbers are provisional until then.

---

## 3. Validated vs. pending

**Validated:** verified-run OOF ranking and recall@K (both splits); E beats the persistence
baseline on both splits at any-KSI; spatial features survive the region-holdout split; prospective
2025 replicates the 7.3x lift out-of-sample; leakage audit 9/9; POINT_X/POINT_Y geocoding.

**Pending:** 2026–2027 label completion (needed to confirm E's edge over the baseline on the
forward window and to say anything at the severe threshold); whether E's edge survives after
controlling for exposure/AADT; engineering effectiveness at treated sites.

---

## 4. Next steps

1. **Exposure / AADT.** The strongest spatial features track traffic volume; adding measured AADT
   as a rate offset separates dangerous design from high exposure. Largest expected effect.
2. **Verify block size ≫ 400 m** so the spatial-neighbor features carry no residual leakage across
   the region-holdout folds.
3. **Re-run on 2026–2027 labels** when released: `python -m src.features.build_spatial_features`
   for the new window, then `notebooks/forward_inference.ipynb`. The deployed model stays frozen on
   the verified window; only candidate scoring and truth labels change.
4. **Outreach** with the injury-crash shortlist (`docs/OUTREACH.md`); it is the list the City's
   5-crash screen cannot produce.

---

## 5. Evaluation methodology

**Recall@K is a full-population figure.** Every candidate is scored by a fold that never trained on
it, and recall is computed across the whole population — not on a single held-out slice, which can
show misleadingly high recall by chance.

**Out-of-fold scoring.** For both the random-stratified and spatial-block splits, the panel is
divided into 5 folds; each fold is scored by a model fit on the other four. Every candidate gets one
prediction from a model that never saw its label. Hyperparameters are frozen (tuned once on
crash-only), not re-tuned per fold.

**Candidate set is the City of San Diego, below its screen.** Intersections inside the City boundary
with fewer than 5 crashes in the feature window (`docs/DECISIONS.md` D18, D11).

**Forward run vs. live dashboard.** The forward run is a prospective prediction: scores locked on
data through 2024, outcomes checked as they arrive. A deployed model may instead be fit on all
resolved historical data — there is no future label to leak when scoring intersections whose
outcomes have not happened. The OOF evaluation governs how much confidence to place in the accuracy,
not what the model predicts.

**SWITRS sources.**

| Run | Primary | Secondary | Feature window | Label window |
|---|---|---|---|---|
| Verified | 20260608 (2015–2024) | — | 2016–2021 | 2022–2024 |
| Forward | 20260608 (2015–2024) | 20260615 (2025, dedup on CASE_ID) | 2016–2024 | 2025–2027 |

2015 records serve only `years_since_last_crash` burn-in. All STATE_HWY_IND='Y' crashes are excluded.

**Tests use synthetic data.** `tests/` exercises pipeline logic on synthetic panels; tests that load
real artifacts are marked `integration` and skip when absent. No test result is evidence of model
performance on real data.

---

## 6. File index

| File | Role |
|---|---|
| `src/features/build_spatial_features.py` | Spatial-neighbor feature builder |
| `notebooks/corrected_retrain.ipynb` | A/D/E bake-off on the corrected candidate set |
| `notebooks/forward_inference.ipynb` | Train E, score 2025–2027 |
| `data/model/verified_model_input.parquet` | Consolidated verified training input |
| `data/model/forward_model_input.parquet` | Consolidated forward scoring input |
| `data/model/verified_run/` | Verified run panel, features, OOF scores |
| `data/model/forward_run/` | Forward run panel, features |
| `reports/verified_canonical_numbers.json` | Canonical figures (superseded by the E run above) |
| `results/model_bakeoff_oof_results.json` | Architecture comparison (XGBoost/RF/MLP/FT-Transformer) |
| `dashboard/public/data/` | Dashboard GeoJSON |
