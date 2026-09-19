# Predicting Intersection KSI Emergence in San Diego

Ranks the intersections San Diego's safety program isn't watching by how likely they are to
become killed-or-seriously-injured (KSI) crash sites within three years, so the City can treat
them before the harm happens.

## The problem

San Diego's safety program is reactive. Its High Crash List flags intersections that already carry
**≥5 reported crashes**, about 14 sites a year. Intersections trending toward danger but still under
that bar are invisible to it. This project predicts which of those **City-invisible** intersections —
fewer than 5 crashes — will emerge as KSI sites within three years, from crash records the City
already collects, road infrastructure, and corridor context.

## The model

XGBoost Tweedie regression on 47 features: crash history (20), road infrastructure (21), and
**spatial-neighbor structure** (6 — local crash pressure, proximity to the City's ≥5-crash sites,
grid density). Trained only on the 25,699 candidate intersections below the City's screen. All results are **out-of-fold**

## Results

A **top-500 shortlist** of City-ignored intersections:

| Metric | Value |
|---|---|
| Future KSI sites caught | **39 / 276** (40 events) |
| Concentration vs. random | **7.3x** |
| Prevented societal harm (30% treatment effectiveness) | **$62M** |
| Net of program cost (~$3.2M after 90% HSIP) | **$59M** — **BCR ~19:1** |
| Incremental to the City | **100%** — its 5-crash screen catches $0 of these sites |

The spatial-neighbor features make this the first model in the project to beat a no-ML persistence
baseline (rank by crash count and trend) on **both** cross-validation splits, by $6–11M prevented
harm. Infrastructure and corridor context carry the signal: once the sites the City already flags
are removed, crash counts alone stop discriminating.


**Prospective 2025 (predict-only).** Fit once and never retrained, the model scored a fresh
2016–2024 candidate cohort against true 2025 outcomes it never saw. Top-500: **9 sites / 10 events,
7.3x random** — the same concentration as the verified run, on a year outside the training window.

The edge over the baseline is small — a few events on 40 — and consistent rather than decisive. At
the severe (≥2 KSI) threshold the model has no signal: 8–9 positives, and a raw crash-count baseline
catches more of them. The product is **injury-crash emergence**. Full argument, evidence, and limits:
[`docs/HYPOTHESIS.md`](docs/HYPOTHESIS.md).

## Reproducing

```bash
conda env create -f environment.yml && conda activate sdhs
# Download a SWITRS export to data/raw/switrs/<YYYYMMDD>/  (see docs/DATA_SOURCES.md)
python -m src.ingest.run
python -m src.gis.build_spine
python -m src.labels.build_panel                 # candidate_screen: city  (<5-crash eligibility)
python -m src.features.build_crash_emergence
python -m src.features.build_spatial_features    # crash pressure, hotspot proximity, grid density
python -m src.model.fit_frozen
python scripts/restrict_candidates_to_city_limits.py
python scripts/refit_verified_run_oof.py         # genuine out-of-fold scoring
make test
```

Colab notebooks for the corrected bake-off and the 2025–2027 forward run are in `notebooks/`.

## Dashboard & mobile

Interactive map (React + Google Maps with a deck.gl overlay, Street View, council-district filters):

```bash
cd dashboard && npm install && npm run dev
```

Needs a Google Maps API key — see `dashboard/docs/SETUP.md`; deployment in `docs/HOSTING_RENDER.md`.
An Expo / React Native mobile scaffold lives in `mobile/`.

## Docs

[`docs/HYPOTHESIS.md`](docs/HYPOTHESIS.md) (claim, evidence, limits) · `docs/METHODOLOGY.md` (windows,
model, evaluation) · `docs/DECISIONS.md` (design decisions, incl. **D18** candidate-set definition) ·
`docs/FEATURE_CATALOG.md` · `docs/DATA_SOURCES.md` · `docs/OUTREACH.md`.

## Data

Crash data: SWITRS via TIMS (tims.berkeley.edu — free account, not redistributable). Road network:
OpenStreetMap via OSMnx. Coordinates use `POINT_X`/`POINT_Y` (SafeTREC-geocoded); see
`docs/DATA_SOURCES.md`.

## Citation & license

MIT License (see `LICENSE`). Cite: Pendharkar, A. (2026), *Predicting KSI Intersection Emergence in
San Diego Using Crash-History Gradient Boosting*.
