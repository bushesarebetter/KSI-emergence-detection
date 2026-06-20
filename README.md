# Predicting Intersection KSI Emergence in San Diego

A crash-history-based model that identifies which San Diego surface-street intersections
are most likely to become severe-injury (KSI: killed or seriously injured) sites within
three years, before they accumulate any severe-crash history.

**Bottom line:** a top-500 shortlist built from crash records alone catches about 48% of
the intersections that go on to become severe-crash sites (10 of 21), sites San Diego's
current review process can't identify at all. The estimated benefit-cost ratio is about
9.7:1 after federal HSIP funding at that threshold, and closer to 40:1 at the broader
any-injury threshold. A prospective test against unseen 2025 outcomes recovered 26 of 112
future KSI sites at K=500 (12x random), so the model generalizes past its training window.

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
| Top 50 | 2 / 1 | 4.8-9.5% | 3/21 (14.3%) | 0% → 5-10% |
| Top 100 | 2 / 1 | 4.8-9.5% | 4/21 (19.0%) | 0% → 5-10% |
| Top 200 | 5 / 5 | 23.8% | 6/21 (28.6%) | 0% → 24% |
| **Top 500** | **10 / 10** | **47.6%** | **10/21 (47.6%)** | **0% → 48%** |
| Top 1,000 | 14 / 13 | 61.9-66.7% | 13/21 (61.9%) | 0% → 62-67% |

95% bootstrap CI on recall@500: [28.6%, 71.4%] (random split), wide because there are only
21 positives total. **The persistence baseline ties the tuned model exactly at top-500**
(10/21 both), and beats it at every K below that. This threshold doesn't show an
ML-specific advantage at this sample size, and we'd rather say that plainly than oversell
it.

20 KSI events were caught in the model's top-500 (same for both splits and the baseline, an
exact tie all around at this threshold). Harm at those caught sites: about $103.5M
(FHWA-SA-25-021, 2024 dollars, fatal share 24.3%, measured directly from raw SWITRS crashes
in the 2022-2024 label window). Prevented at 30% treatment effectiveness: about $31.1M.
City program cost after 90% HSIP federal funding: about $3.2M (a program-cost assumption,
not something this analysis verifies). **BCR: about 9.7:1.**

### Secondary threshold — ≥1 KSI: 378 sites

| Shortlist | Sites found | Recall | Persistence baseline |
|---|---|---|---|
| Top 200 | 29 (random) | 7.7% | 27/378 (7.1%) |
| **Top 500** | **75 (random) / 73 (spatial)** | **19.3-19.8%** | **61/378 (16.1%)** |
| Top 1,000 | 128 (random) | 33.9% | 114/378 (30.2%) |

Here the model has a real, consistent edge over the baseline at every K shown. This is the
clearest evidence in the whole project that the model adds value beyond the trivial
heuristic.

85 KSI events caught in the top-500 (random split; 83 on the spatial split, 71 for the
baseline). Harm at those sites: about $440M random / $430M spatial. Prevented at 30%
effectiveness: about $132.0M / $128.9M. **BCR: about 41.2:1 (random) / 40.3:1 (spatial)**,
vs. the baseline's 34.4:1.

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
- A freshly nested-CV-tuned XGBoost on crash-only features was the most consistently
  competitive setup, and it's the model reported above.
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

### Prospective 2025 evaluation

The verified-run model was applied to a fresh candidate cohort (intersections with no KSI
history through 2024, restricted to the City of San Diego) using 2016-2024 features, the
most current data available, and scored against true 2025 KSI outcomes it never saw during
training. This is the cleanest possible test: the labels it's being checked against didn't
exist anywhere when the model was trained. Results at the ≥1-KSI threshold (108 positives in
26,045 candidates):

| K    | Hits | Recall | 95% CI         | Lift vs. random |
|------|------|--------|----------------|------------------|
| 200  | 9    | 8.3%   | [3.7%, 13.9%]  | 10.9x            |
| **500**  | **24**   | **22.2%** | **[14.8%, 30.6%]** | **11.6x**      |
| 1000 | 38   | 35.2%  | [26.8%, 45.4%] | 9.2x            |

The random baseline is computed against the true City of San Diego candidate set (26,045
candidates). Source data: `results/recall_evaluation.json`.

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
│   ├── refit_forward_run_oof.py               genuine out-of-fold scoring, forward run
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

The model was retrained on 2016-2024 features (26,045 City-of-San-Diego candidates) for a
live prediction covering 2025-2027. 2025 outcomes are complete; 2026-2027 will land when
the next SWITRS export is released. The forward-run top-500 is in
`results/top500_forward_2025_2027.csv`.

Spearman ρ: **0.066** (random split) / **0.068** (spatial split), against a persistence
baseline of 0.072, the same tied-or-trailing pattern as the verified run. recall@500 at the
≥1-KSI threshold (108 positives): 21/108 (19.4%, random split) / 24/108 (22.2%, spatial
split), vs. the baseline's 24/108 (the baseline ties or edges ahead here too). Treat every
forward-run number as provisional: only one of the three label years is complete, and with
just 2 positives at the ≥2-KSI threshold so far, no recall figure at that threshold means
much yet.

The live map predictions don't depend on any of the evaluation methodology above: the
deployed model is fit on all available historical data, which is correct, because there's
no future label to leak when scoring intersections whose outcomes haven't happened yet.
The out-of-fold scoring only governs how confident we should be in the model's claimed
accuracy, not what it predicts day to day.

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
