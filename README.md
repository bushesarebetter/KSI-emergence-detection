# Predicting Intersection KSI Emergence in San Diego

A crash-history-based model for identifying which San Diego surface-street intersections
are most likely to emerge as severe-injury (KSI: killed or seriously injured) sites over a
three-year horizon — before they accumulate any severe-crash history.

**Bottom line:** a top-500 shortlist built from crash records alone catches 59% of
subsequently emergent severe-crash sites (13/22) — sites San Diego's current review process
identifies zero of — with an estimated benefit-cost ratio of ~13:1 after federal HSIP funding.

---

## The problem

Traffic safety investment is almost entirely reactive. San Diego's annual review flags
intersections with five or more prior crashes (~14 locations per year). By definition,
intersections trending toward danger but with no crash history yet are invisible to this
screen. This project asks: can we predict which currently-clean intersections will become
KSI sites within three years, using only crash records the city already collects?

---

## Key results

**Verified run: 2016–2021 features → 2022–2024 KSI outcomes | 81,007 candidates**

Spearman ρ: **0.175** (random split) / **0.169** (spatial split).
Persistence baseline: 0.085 / 0.108. Both splits CI-separated.

### Primary threshold — ≥2 KSI: 22 confirmed emergent sites

| Shortlist | % of city | Sites found | Recall | vs city (0%) | vs random |
|---|---|---|---|---|---|
| Top 50 | 0.06% | 5 / 22 | 22.7% | 0% → 22.7% | 368× |
| Top 100 | 0.12% | 6 / 22 | 27.3% | 0% → 27.3% | 221× |
| Top 200 | 0.25% | 8 / 22 | 36.4% | 0% → 36.4% | 147× |
| **Top 500** | **0.62%** | **13 / 22** | **59.1%** | **0% → 59.1%** | **96×** |
| Top 1,000 | 1.23% | 17 / 22 | 77.3% | 0% → 77.3% | 63× |

44 KSI events across 22 sites. Total societal harm: **~$228M** (FHWA-SA-25-021, 2024 dollars).
Top-500 harm: ~$135M. Prevented at 30% treatment effectiveness: **~$40M**.
City program cost after HSIP federal funding (90%): **~$3.2M**. BCR: **~13:1**.

### Secondary threshold — ≥1 KSI: 389 sites

| Shortlist | Sites found | Recall | vs random |
|---|---|---|---|
| Top 200 | 49 / 389 | 12.6% | 51× |
| **Top 500** | **89 / 389** | **22.9%** | **37×** |
| Top 1,000 | 143 / 389 | 36.8% | 30× |

Total harm across 389 sites: **~$2.13B**. Top-500 catch: 89 sites, ~102 events, ~$529M
in concentrated harm. BCR at ≥1 threshold: **~50:1**.

The top-500 list is the same 500 intersections regardless of which threshold you evaluate
against. The 13 ≥2 sites in the top-500 are a subset of the 89 ≥1 sites.

### Sufficiency null

Under Protocol A (frozen hyperparameters, four feature sets), adding road geometry,
signals, and all infrastructure reduced Spearman rank correlation relative to crash-history
alone. **Crash records are sufficient; no infrastructure inventory is needed.**

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
│   ├── compute_verified_numbers.py   canonical figures, both thresholds
│   ├── build_export_panel_verified.py  dashboard export (--run verified|forward)
│   └── claims_audit.py               number provenance audit
├── dashboard/           React + MapLibre interactive map
├── results/
│   ├── top500_verified_2022_2024.csv  verified-run top-500 (with became_emergent flag)
│   ├── top500_forward_2024_2026.csv   forward-run top-500 (2016-2023 features)
│   ├── model_performance.json         all metrics, both runs, both thresholds
│   ├── feature_importance.csv         SHAP top-15 with plain-English labels
│   └── ablation_results.csv           Protocol A sufficiency-null results
├── reports/
│   ├── verified_canonical_numbers.json  source of truth for all headline figures
│   ├── claims_audit.csv                 number provenance audit output
│   └── milestone_final.md               final project status
├── figures/
│   ├── shap_importance.png
│   └── shap_importance.pdf
├── docs/
│   ├── METHODOLOGY.md    candidate set, temporal windows, model, evaluation
│   ├── DATA_SOURCES.md   data access instructions, coordinate correction
│   ├── DECISIONS.md      key design decisions D1–D8
│   └── FEATURE_CATALOG.md  all 20 crash-history features
├── configs/config.yaml   single source of runtime constants
├── tests/                62-test pytest suite
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
python -m src.eval.milestone4
python scripts/compute_verified_numbers.py
```

All 9 leakage audit checks run automatically before every model fit. All 62 tests:

```bash
make test
```

---

## Forward-looking run (2024–2026)

The model was retrained on 2016–2023 features (80,736 candidates) to produce a live
prediction for 2024–2026. 2024 label outcomes are now complete; 2025–2026 will be
available when the next SWITRS export is released (~early 2027). The forward-run top-500
is in `results/top500_forward_2024_2026.csv`. Full prospective evaluation is pending.

---

## Dashboard

An interactive map of all 81,007 candidate intersections with ranked shortlist layers,
per-site crash history, SHAP signals, and Council district filtering.

```bash
python scripts/build_export_panel_verified.py --run forward
cd dashboard && npm install && npm run dev
```

Open `http://localhost:5173`.

---

## Data

Crash data from SWITRS via TIMS (tims.berkeley.edu). Free account required; cannot be
redistributed. Road network from OpenStreetMap via OSMnx. See `docs/DATA_SOURCES.md` for
full access instructions and the critical geocoding correction (POINT_X/POINT_Y, not
LATITUDE/LONGITUDE).

---

## Citation

```bibtex
@misc{sd_ksi_emergence_2026,
  title  = {Predicting {KSI} Intersection Emergence in {San Diego}
            Using Crash-History Gradient Boosting},
  author = {[Authors]},
  year   = {2026},
  url    = {[GitHub URL]}
}
```

---

## License

MIT License. See `LICENSE`.
