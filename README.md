# Predicting Intersection KSI Emergence in San Diego

A crash-history-based model that identifies which San Diego surface-street intersections
are most likely to become severe-injury (KSI: killed or seriously injured) sites within
three years, before they accumulate any severe-crash history.

**Bottom line:** a top-500 shortlist built from crash records alone catches about 48% of
the intersections that go on to become severe-crash sites (10 of 21 on the random split,
9 of 21 on the spatial split), sites San Diego's current review process can't identify at
all. The estimated benefit-cost ratio is about 9.6:1 after federal HSIP funding at that
threshold, and closer to 40:1 at the broader any-injury threshold. A prospective test
against unseen 2025 outcomes recovered 24 of 108 future KSI sites at K=500 (11.6x random),
so the model generalizes past its training window.

A simple, no-ML baseline (just rank intersections by recent crash count and trend) gets
the exact same result at the severe-emergence threshold. The model's clearest validated
edge over that baseline shows up at the broader any-injury threshold. Both numbers are
reported below, honestly, because that comparison is the whole point: the city isn't doing
either one today, and even the simple version would be a real improvement.

> **Note on scope:** the candidate set is restricted to intersections actually inside City
> of San Diego limits (26,423 surface intersections). See `docs/DECISIONS.md` D11 for the
> full candidate-set definition.

---

## The problem

Traffic safety investment is almost entirely reactive. San Diego's annual review flags
intersections with five or more prior crashes, about 14 locations a year. By definition,
intersections trending toward danger but without crash history yet are invisible to that
screen. This project asks whether we can predict which currently-clean intersections will
become KSI sites within three years, using only crash records the city already collects.

---

## Key results

**Verified run: 2016-2021 features → 2022-2024 KSI outcomes | 26,423 candidates, City of San Diego only**

Model: XGBoost Tweedie regression on 20 crash-history features, hyperparameters chosen by
nested cross-validation. Every number below comes from genuine 5-fold out-of-fold scoring:
each prediction is made by a model that never saw that row's label during training. That's
the standard we hold every number in this project to, not just this one.

Spearman ρ: **0.128** (random split) / **0.131** (spatial split). A no-fitting persistence
baseline (rank by recent crash count and trend) scores **0.133**, still slightly ahead,
statistically tied with the tuned model given how few positives there are. Read the
recall@K tables below with that in mind.

### Primary threshold — ≥2 KSI: 21 confirmed emergent sites

| Shortlist | Sites found (random / spatial split) | Recall | Persistence baseline | vs. city (0%) |
|---|---|---|---|---|
| Top 50 | 1 / 1 | 4.8% | 3/21 (14.3%) | 0% → 4.8% |
| Top 100 | 3 / 1 | 4.8-14.3% | 4/21 (19.0%) | 0% → 5-14% |
| Top 200 | 5 / 5 | 23.8% | 6/21 (28.6%) | 0% → 24% |
| **Top 500** | **10 / 9** | **42.9-47.6%** | **10/21 (47.6%)** | **0% → 43-48%** |
| Top 1,000 | 16 / 15 | 71.4-76.2% | 13/21 (61.9%) | 0% → 71-76% |

95% bootstrap CI on recall@500: [28.6%, 71.4%] (random split) / [23.8%, 61.9%] (spatial
split), wide because there are only 21 positives total. **The persistence baseline ties the
tuned model exactly on the random split at top-500** (10/21 both); on the spatial split the
baseline edges ahead (10/21 vs. the model's 9/21). This threshold doesn't show an
ML-specific advantage at this sample size, and we'd rather say that plainly than oversell
it.

20 KSI events were caught in the model's top-500 on the random split (same as the baseline,
an exact tie there); 18 on the spatial split. Harm at those caught sites: about $103.5M
(random split) / $93.2M (spatial split) (FHWA-SA-25-021, 2024 dollars, fatal share 24.3%,
measured directly from raw SWITRS crashes in the 2022-2024 label window). Prevented at 30%
treatment effectiveness: about $31.1M (random) / $27.9M (spatial). City program cost after
90% HSIP federal funding: about $3.2M (a program-cost assumption, not something this
analysis verifies). **BCR: about 9.6:1 (random) / 8.7:1 (spatial)**, vs. the baseline's
9.6:1.

### Secondary threshold — ≥1 KSI: 378 sites

| Shortlist | Sites found | Recall | Persistence baseline |
|---|---|---|---|
| Top 200 | 27 (random) / 30 (spatial) | 7.1-7.9% | 27/378 (7.1%, ties random) |
| **Top 500** | **74 (random) / 71 (spatial)** | **18.8-19.6%** | **61/378 (16.1%)** |
| Top 1,000 | 128 (random) / 123 (spatial) | 32.5-33.9% | 114/378 (30.2%) |

The model has a consistent edge over the baseline at K=500 and K=1000; at K=200 the random
split exactly ties the baseline (27/378 both), so the edge isn't universal at every K, but
it is real and the largest gap in the project at the K that matters operationally (top-500).

84 KSI events caught in the top-500 on the random split (80 on the spatial split, 71 for the
baseline). Harm at those sites: about $434.8M random / $414.1M spatial. Prevented at 30%
effectiveness: about $130.4M / $124.2M. **BCR: about 40.4:1 (random) / 38.5:1 (spatial)**,
vs. the baseline's 34.2:1.

### How the model compares to simpler alternatives

We ran a full architecture comparison (`scripts/model_bakeoff_oof.py`,
`results/model_bakeoff_oof_results.json`): the persistence baseline against XGBoost (both
the original hyperparameters and a freshly nested-CV-tuned version), a Random Forest, and a
small PyTorch MLP neural network (Tweedie-deviance loss, up to 100 epochs with early
stopping), all on the same genuine out-of-fold protocol, on both crash-only and
infrastructure-augmented feature sets.

What we found:
- The neural network was consistently the weakest model, sometimes badly (recall@500 as
  low as 1-4 out of 21 in some configurations). With only 21 positive examples, there's
  nowhere near enough data for a network with that many parameters to learn anything
  stable, no matter how it's regularized.
- Random Forest performed about the same as XGBoost.
- A freshly nested-CV-tuned XGBoost on crash-only features performed about the same as the
  frozen Protocol-A hyperparameters used for the headline numbers above (Spearman 0.1279
  vs. 0.1279 random split, recall@500 within a site or two either way). Re-tuning didn't
  buy anything; the model reported above stays the frozen Protocol-A version, for
  consistency with every other comparison in this project (see `docs/DECISIONS.md` D16).
- No architecture we tried clearly and reliably beats the persistence baseline at the
  severe (≥2-KSI) threshold. Crash-history trend is a real signal, and a one-line heuristic
  captures all of it there. The model's validated value-add is real, but it's concentrated
  at the broader (≥1-KSI) threshold, not the severe one.

### Does infrastructure data help?

We tested road geometry, signal/sign presence, and the full infrastructure feature set
against crash-only, all with the same frozen-hyperparameter Protocol A design used for
every feature-set comparison in this project (`scripts/refit_protocol_a_oof.py`).

| Feature set | Spearman ρ (random) | Spearman ρ (spatial) | Δ vs. crash-only |
|---|---|---|---|
| A: crash-only | 0.128 | 0.131 | — |
| B: + road geometry | 0.148 | 0.150 | +0.020 |
| C: + signals | 0.134 | 0.135 | +0.006 |
| D: + all infrastructure | 0.149 | 0.150 | +0.021 |

B and D show a **consistent** positive delta on both splits, similar in size on each, worth
taking seriously. recall@500 (≥2-KSI) moves from 10/21 to 11-12/21 with infrastructure
features included.

We're stopping short of recommending infrastructure data as a requirement, though. n=21
positives is still a small sample, the same regime that's made every comparison in this
project noisy, and a real-looking signal at this size can still firm up or fade as more
label data arrives (the forward run will add 2025-2026 outcomes). The model we report above
stays the simpler crash-only one; this finding is flagged as a promising lead for follow-up
work, not baked into the headline claim.

A leakage-free predict-only check against the 2025 forward-run outcome
(`scripts/predict_protocol_a_forward.py`, see `docs/DECISIONS.md` D17) does **not** replicate
this lift. Spearman deltas vs. crash-only are small and negative there (B −0.014, C −0.006,
D −0.015). With only 108 partial-year positives this isn't strong evidence infra data hurts
either; it just means the verified run's infra-helps finding hasn't yet replicated
out-of-sample.

### Prospective 2025 evaluation

The verified-run model was fit once on 2016-2021 features → 2022-2024 labels and never
retrained. It was applied via predict-only scoring to a fresh candidate cohort (intersections
with no KSI history through 2024, restricted to the City of San Diego) using 2016-2024
features, the most current data available, and scored against true 2025 KSI outcomes it
never saw during training or fitting of any kind. This is the cleanest possible test: the
labels it's being checked against didn't exist anywhere when the model was trained, and the
model was never refit to include them. Results at the ≥1-KSI threshold (108 positives in
26,045 candidates):

| K    | Hits | Recall | 95% CI         | Lift vs. random |
|------|------|--------|----------------|------------------|
| 200  | 9    | 8.3%   | [3.7%, 13.9%]  | 10.9x            |
| **500**  | **24**   | **22.2%** | **[14.8%, 30.6%]** | **11.6x**      |
| 1000 | 38   | 35.2%  | [26.8%, 45.4%] | 9.2x            |

The random baseline is computed against the true City of San Diego candidate set (26,045
candidates). Source data: `results/recall_evaluation.json`. These are the same numbers
quoted for the forward run below; see that section for why they're the same artifact.

---

## Repository structure

```
intersection_project/
├── src/
│   ├── ingest/          crash + network ingestion
│   ├── gis/             node spine construction
│   ├── labels/          KSI label panel
│   ├── features/        20 crash-history features
│   ├── model/           Tweedie XGBoost + frozen-param ablation
│   ├── eval/            Spearman, recall@K, spatial CV
│   └── audit/           9-check leakage audit
├── scripts/
│   ├── compute_verified_numbers.py            canonical figures, both thresholds
│   ├── restrict_candidates_to_city_limits.py  restricts candidates to City of San Diego limits
│   ├── refit_verified_run_oof.py              genuine out-of-fold scoring, verified run
│   ├── predict_forward_run.py                 predict-only forward-run scoring (D17)
│   ├── refit_protocol_a_oof.py                infrastructure feature-set comparison
│   ├── model_bakeoff_oof.py                   architecture comparison (XGBoost/RF/MLP)
│   ├── build_export_panel_verified.py         dashboard export (--run verified|forward)
│   └── claims_audit.py                        number provenance audit
├── dashboard/           React + MapLibre interactive map
├── results/
│   ├── top500_verified_2022_2024.csv  verified-run top-500 (with became_emergent flag)
│   ├── top500_forward_2025_2027.csv   forward-run top-500 (2016-2024 features)
│   ├── model_performance.json         all metrics, both runs, both thresholds
│   ├── feature_importance.csv         SHAP top-15 with plain-English labels
│   ├── ablation_results.csv           infrastructure feature-set comparison
│   └── model_bakeoff_oof_results.json architecture comparison, full numbers
├── reports/
│   └── verified_canonical_numbers.json  source of truth for all headline figures
├── figures/
│   ├── shap_importance.png
│   └── shap_importance.pdf
├── docs/
│   ├── METHODOLOGY.md     candidate set, temporal windows, model, evaluation
│   ├── DATA_SOURCES.md    data access instructions, coordinate correction
│   ├── DECISIONS.md       key design decisions D1-D11
│   └── FEATURE_CATALOG.md all 20 crash-history features
├── configs/config.yaml   single source of runtime constants
├── tests/                pytest suite
├── environment.yml
└── Makefile
```

---

## Reproducing the results

```bash
conda env create -f environment.yml
conda activate sdhs
```

SWITRS data must be downloaded manually from TIMS (see `docs/DATA_SOURCES.md`).
Place the export in `data/raw/switrs/<YYYYMMDD>/`. Then:

```bash
python -m src.ingest.run
python -m src.gis.build_spine
python -m src.labels.build_panel
python -m src.features.build_crash_emergence
python -m src.model.fit_frozen
python scripts/restrict_candidates_to_city_limits.py
python scripts/refit_verified_run_oof.py
python scripts/compute_verified_numbers.py
```

All leakage audit checks run automatically before every model fit. Full test suite:

```bash
make test
```

---

## Forward-looking run (2025-2027)

The live map covers 2025-2027 for the 26,045 City-of-San-Diego candidates with no KSI
history through 2024. 2025 outcomes are complete; 2026-2027 will land when the next SWITRS
export is released. The forward-run top-500 is in `results/top500_forward_2025_2027.csv`.

**Methodology:** the deployed model is the verified-run model: fit once on 2016-2021
features → 2022-2024 labels, the project's one and only trained model. It's applied via
`.predict()` only to the current 2016-2024 forward-candidate features
(`scripts/predict_forward_run.py`), and it is **never retrained** on the forward candidates' own
KSI outcome — that outcome (the 2025 portion of the 2025-2027 window) is what the forward run
is being checked against, so the model never sees it during fitting. The forward run and the
"Prospective 2025 evaluation" above are therefore the same artifact —
recall@500 (≥1 KSI, 108 positives): **24/108 (22.2%, 11.6x random)**. recall@200: 9/108 (8.3%).
Treat every forward-run number as provisional: only one of the three label years (2025) is
complete, and with just 2 positives at the ≥2-KSI threshold so far, no recall figure at that
threshold means much yet. Full methodology notes: `docs/DECISIONS.md` D17.

---

## Dashboard

An interactive map of the 26,423 candidate intersections actually inside San Diego city
limits, with ranked shortlist layers, per-site crash history, SHAP signals, and Council
district filtering.

```bash
python scripts/build_export_panel_verified.py --run forward
cd dashboard && npm install && npm run dev
```

Open `http://localhost:5173`.

---

## Data

Crash data from SWITRS via TIMS (tims.berkeley.edu). Free account required; cannot be
redistributed. Road network from OpenStreetMap via OSMnx. See `docs/DATA_SOURCES.md` for
full access instructions and the geocoding correction (POINT_X/POINT_Y, not
LATITUDE/LONGITUDE).

---

## Citation

```bibtex
@misc{sd_ksi_emergence_2026,
  title  = {Predicting {KSI} Intersection Emergence in {San Diego}
            Using Crash-History Gradient Boosting},
  author = {Pendharkar, Ayan},
  year   = {2026},
  url    = {https://github.com/bushesarebetter/KSI-emergence-detection}
}
```

---

## License

MIT License. See `LICENSE`.
