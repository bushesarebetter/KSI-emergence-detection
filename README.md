# Predicting Intersection KSI Emergence in San Diego

Ranks the intersections San Diego's safety program **isn't** watching by how likely they are
to become killed-or-seriously-injured (KSI) crash sites within three years — so the City can
treat them before the harm happens.

## The problem

San Diego's safety investment is reactive. Its High Crash List flags intersections that
**already** carry **≥5 reported crashes** (~14 sites a year). Intersections trending toward
danger but still under that bar are invisible to the screen — by definition, the City can't
act on them. This project predicts which of those **City-invisible** intersections (fewer
than 5 crashes in the review window) will emerge as KSI sites within three years, using only
crash records the City already collects plus road-network data.

## Estimated benefits (our model)

XGBoost Tweedie regression on crash-history **+ road-infrastructure** features, trained only
on the 25,425 candidate intersections **below the City's 5-crash screen**. Every figure is
**out-of-fold** — each site is scored by a model that never trained on it — on the
2016–2021 → 2022–2024 window.

A **top-500 shortlist** of these City-ignored intersections:

| Metric | Value |
|---|---|
| Future KSI sites caught | **44 / 500** (46 events) |
| Concentration vs. random pick | **~8.4×** |
| Prevented societal harm (30% treatment effectiveness) | **~$71M** |
| Net of program cost (~$3.2M after 90% HSIP) | **~$68M** — **BCR ≈ 22:1** |
| Incremental to the City | **100%** — its 5-crash screen catches $0 of these sites |

This crash + **infrastructure** model is the project's first result to **beat the no-ML
persistence baseline out-of-sample on both cross-validation splits** (+$6–8M prevented harm;
Spearman ρ 0.10 → 0.12). The lesson: once the sites the City already flags are removed, crash
counts alone stop discriminating and **road geometry and signals become the signal**.

**Honest bounds.** The edge is at the **any-KSI** threshold; the severe (≥2-KSI) threshold has
too few positives (8) to conclude anything. Dollar figures use FHWA-SA-25-021 crash costs and
a 30%-effectiveness assumption over a single 3-year window — treat as order-of-magnitude
pending more label years. Candidate-set correction: `docs/DECISIONS.md` D18. Reproducible run:
`notebooks/corrected_retrain.ipynb`.

## Deployment status

The model above is validated in the notebook. **Wiring it into the live dashboard is in
progress** — the current map still reflects the earlier crash-only run on the old candidate
set. Regenerating the export on the corrected `<5-crash` candidate set is the next step (see
Reproducing).

## Reproducing

```bash
conda env create -f environment.yml && conda activate sdhs
# Download a SWITRS export to data/raw/switrs/<YYYYMMDD>/  (see docs/DATA_SOURCES.md)
python -m src.ingest.run
python -m src.gis.build_spine
python -m src.labels.build_panel                 # candidate_screen: city  (<5-crash eligibility)
python -m src.features.build_crash_emergence
python -m src.model.fit_frozen
python scripts/restrict_candidates_to_city_limits.py
python scripts/refit_verified_run_oof.py         # genuine out-of-fold scoring
make test
```

## Dashboard & mobile

Interactive map (React + Google Maps with a deck.gl overlay, Street View, council-district
filters):

```bash
cd dashboard && npm install && npm run dev
```

Needs a Google Maps API key — see `dashboard/docs/SETUP.md`; deployment in
`docs/HOSTING_RENDER.md`. An Expo / React Native mobile scaffold lives in `mobile/`.

## Docs

`docs/METHODOLOGY.md` (windows, model, evaluation) · `docs/DECISIONS.md` (design decisions,
incl. **D18** candidate-set correction) · `docs/FEATURE_CATALOG.md` (features) ·
`docs/MODEL_IMPROVEMENTS.md` (improvement backlog) · `docs/DATA_SOURCES.md` · `docs/OUTREACH.md`.

## Data

Crash data: SWITRS via TIMS (tims.berkeley.edu — free account, not redistributable). Road
network: OpenStreetMap via OSMnx. Coordinates use `POINT_X`/`POINT_Y` (SafeTREC-geocoded);
see `docs/DATA_SOURCES.md`.

## Citation & license

MIT License (see `LICENSE`). Cite: Pendharkar, A. (2026), *Predicting KSI Intersection
Emergence in San Diego Using Crash-History Gradient Boosting*.
