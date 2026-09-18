# Model Improvement Plan

Status: **harness built and validated; no real-data results yet.** Every idea below is
implemented in `scripts/improvement_bakeoff.py` and evaluated under the same genuine
out-of-fold protocol the project already holds its headline numbers to. None of them
has been run against San Diego, because `data/raw/switrs/` is empty in this working
copy — SWITRS cannot be redistributed, so it has to be re-downloaded from TIMS first.
**Do not quote any figure from this document as a result.** The expected-effect column
is a prior, not a measurement.

## What has been verified (and what that does not mean)

The harness now runs end to end against a synthetic panel
(`scripts/make_synthetic_panel.py`) built to match the real one's schema and its
*difficulty*: ~26k candidates, ~360 positives at ≥1 KSI and ~22 at ≥2, and a
persistence baseline that lands at recall@500 ≈ 0.19 against the real panel's 0.161.

Confirmed working:

- All eight arms execute on both the random and spatial splits.
- The synthetic panel **reproduces the project's central qualitative finding**: the
  persistence baseline (0.189) beats the tuned XGBoost model (0.164) at recall@500.
  That is a meaningful check on the generator — it was calibrated on the baseline's
  recall alone, and the model-loses-to-baseline result fell out rather than being
  fitted.
- The paired bootstrap produces CIs roughly ±0.03 wide, against the ±0.21-wide
  marginal intervals the project currently reports. `tests/test_improvement_harness.py`
  asserts this gap rather than assuming it.
- **Leak detection works.** Putting the label into the feature matrix drives recall
  above 0.9, and a stacked-window panel scored without intersection grouping is
  measurably optimistic against the grouped version. Both are pinned by tests.

What this explicitly does **not** establish:

- **No synthetic number says anything about San Diego.** The per-arm deltas in
  `results/improvement_bakeoff_synthetic.json` are properties of the generator.
- The corridor arm cannot be fairly assessed on synthetic data at all: in the
  generator, spatial structure enters only through `exposure`, which the crash-count
  features already capture, so corridor features have nothing extra to find *by
  construction*. Its real test needs real data.
- `monotone` scoring below baseline on synthetic is not evidence against monotonic
  constraints; it reflects generator-specific feature shapes.

The honest summary: the measuring instrument is built and calibrated. Nothing has
been measured.

---

## The diagnosis

The project has already done the work that rules out the easy explanations, and the
answer it produced is worth stating plainly:

- **Architecture is not the bottleneck.** `results/model_bakeoff_oof_results.json`
  compared XGBoost (frozen and freshly nested-CV-tuned), Random Forest, and a PyTorch
  MLP on identical OOF folds. Tuned XGBoost matched frozen XGBoost to four decimal
  places (ρ 0.1279 vs. 0.1279). Random Forest matched both. The MLP was materially
  worse. When four different function classes land on the same number, the ceiling is
  in the data, not the estimator.
- **The features are not independent of each other.** All 20 live features in
  `docs/FEATURE_CATALOG.md` Groups 1–2 are computed from one source: the crash point
  stream inside a 76.2 m buffer. `crashes_36mo`, `crashes_72mo`, `ewma_crashes`,
  `distinct_crash_days_72mo`, `emergence_velocity`, `momentum_ratio` and
  `crash_trend_slope` are, to a first approximation, seven different smoothings of the
  same underlying count. That is exactly why a two-term persistence baseline ties the
  tuned model at the ≥2-KSI threshold: there is nothing in the feature matrix that the
  baseline is not already using.
- **n = 21 is the binding constraint on *detecting* improvement.** At the primary
  threshold the bootstrap CI on recall@500 spans [28.6%, 71.4%]. Any change that moves
  recall by one or two sites is invisible inside that interval. This is why so many of
  the project's comparisons come back "tied" — not because nothing works, but because
  the measurement cannot resolve it.

So "drastically improve" reduces to two things, in this order: **get more label signal
per unit of evaluation noise**, and **add information the crash stream does not already
contain**. Items are ranked by that framing, not by sophistication.

---

## The 12 candidates, evaluated

Effect estimates are on OOF Spearman ρ and recall@500 at the ≥1-KSI threshold, which is
where the project has already shown the model has a real edge and where n = 378 makes an
effect measurable. "Tradeoff" is the honest cost, including costs to the project's
credibility, not just compute.

### Tier 1 — do these; large expected effect, no methodological tradeoff

| # | Change | Why it should work here | Tradeoff |
|---|---|---|---|
| **1** | **Evaluate with repeated CV + paired bootstrap on the difference** | Current `bootstrap_recall_ci` in `refit_verified_run_oof.py` resamples positive *positions* against one fixed ranking. It captures which positives you drew, but not refit variance, and it never pairs model against baseline on the same resample. Repeated 5-fold over 10 seeds plus a paired bootstrap of Δrecall cuts the variance you are fighting and tests the question you actually care about ("is the model better than the baseline", not "what is each one's CI"). | None. Strictly more information from the same fits. Costs ~10× compute on a model that fits in seconds. **Do this first — everything below is unmeasurable without it.** |
| **2** | **Train on the county panel, evaluate on the city subset** | D11 restricted candidates to 26,423 City-of-San-Diego intersections. That restriction is correct for *deployment* (the city can only treat its own intersections) but it was applied to *training* too, and the original panel had 81,007 candidates. Fitting on the full county and scoring only the city subset is ~3× the positives at zero leakage cost, provided the county rows outside the city are never scored. | Requires that county-wide features are built to the same standard. Spatial CV must group by block so a county fold cannot straddle the city boundary. No credibility cost — the evaluation set is unchanged. |
| **3** | **Stack multiple overlapping time windows (temporal augmentation)** | One panel exists today: 2016–21 features → 2022–24 labels. The same pipeline can emit 2015–17→2018–20, 2016–18→2019–21, 2017–19→2020–22. Each adds a fresh set of positives from the same intersections under different conditions, which is the single cheapest way to multiply n. | The same intersection appears in several rows, so rows are not independent: CV **must** group by `intersection_id`, or OOF scores leak across windows and every number inflates. That is a real trap, and the harness enforces it. COVID (2020–21) distorts one window; include `covid_period_share` as a control. |
| **4** | **Add exposure (AADT / traffic volume) and model it as an offset** | This is the largest known gap, and the feature catalog already admits it: `crash_rate_per_MEV_72mo` is listed as *deferred — needs exposure/ADT*. Without exposure, crash counts conflate "busy" with "dangerous", and the model spends its capacity rediscovering traffic volume. Every Highway Safety Manual SPF uses AADT for exactly this reason. Enter it as `log(AADT)` offset in the Tweedie/Poisson objective, not as a plain feature, so the model predicts *rate*. | Coverage. Caltrans and SANDAG counts are dense on arterials and sparse on local streets, so a large share of the 26k candidates need imputation plus a `aadt_missing` flag. Genuinely new information though, and static (not endogenous). |
| **5** | **Corridor / neighbourhood features** | Group 9 in the catalog is deferred, and it is the biggest free win left. KSI risk is spatially autocorrelated along corridors: a node with clean history 100 m from three bad nodes on the same arterial is not the same risk as an isolated clean node. Distance-decay crash kernels over neighbours, counts on the parent OSM way, and 1-hop graph neighbour statistics are all computable **from data already in the repo** — no new source, no new licence. | Must respect the same crash wall (`feature_cutoff_date`), and neighbour features must be built from training-window crashes only. Adds a leakage surface the audit needs a new check for. |

### Tier 2 — strong candidates, small honest caveats

| # | Change | Why it should work here | Tradeoff |
|---|---|---|---|
| **6** | **Two-stage decomposition: frequency × conditional severity** | Stop asking one model to learn a 21-positive signal. Stage A predicts total crash count (thousands of positives, easily learnable). Stage B predicts P(KSI \| crash) from severity-relevant covariates. Rank by their product. This is the standard actuarial frequency-severity split and it routes almost all the estimation into the dense part of the problem. | Stage B is where the sparsity moves, not disappears; it needs severity-discriminative features (speed, geometry, ped/bike mix) to beat a constant. If B degenerates to a constant, you have re-derived the persistence baseline — which is itself a clean, publishable negative result. |
| **7** | **Harm-weighted continuous target** | Replace the `KSI_label` count with FHWA-weighted harm (fatal 15.99M, severe 1.71M, other-injury and PDO at their own costs). Turns a near-degenerate integer target into a continuous one with far more distinct values, and it aligns training with the BCR objective the project already reports. | Changes what the headline number means, so it needs its own row in the results tables rather than silently replacing the existing one. The weights are FHWA's, so they are defensible. |
| **8** | **Rank-average ensemble of model + persistence baseline** | The model and the baseline tie on aggregate but are not identical rankings — they disagree about *which* sites. When two rankings of similar quality disagree, their rank-average usually beats both. Two lines of code. | Almost none. Slightly harder to explain in a paper than a single model, and it makes "the model beats the baseline" a muddier claim since the baseline is now inside the model. |
| **9** | **Census/ACS and land-use context (Group 8)** | Genuinely independent information, free from the Census API: population and employment density, vehicle availability, commute mode share, zoning mix, alcohol-outlet and school proximity. These predict exposure and vulnerable-user presence, neither of which the crash stream captures. | Block-group resolution is coarse relative to a 76.2 m intersection buffer. Also carries an equity dimension that must be handled deliberately — a model that ranks low-income areas higher needs to be presented as *where harm concentrates*, not as a targeting tool. Worth doing, worth doing carefully. |

### Tier 3 — cheap, do them while you are in there

| # | Change | Why | Tradeoff |
|---|---|---|---|
| **10** | **Monotonic constraints** | XGBoost `monotone_constraints` on features whose direction is known a priori (more recent crashes → higher risk, longer since last crash → lower). In a 21-positive regime this is free variance reduction, and it prevents the visibly silly non-monotonicities that undermine a model in front of a traffic engineer. | Wrong if a constraint is wrong. Only apply where the direction is genuinely certain. |
| **11** | **Rank-learning objective (`rank:pairwise` / `rank:ndcg`)** | The model is evaluated on recall@K but trained on Tweedie deviance. XGBoost can optimise the ranking directly, which is metric-aligned. | With 21 positives a pairwise objective can overfit the top of the list badly. Cheap to test, must not be adopted without OOF proof on both splits. |
| **12** | **Isotonic calibration of the output score** | Does not change the ranking at all, so it cannot improve recall@K. Worth it only because a calibrated "expected KSI count" is far more defensible to a city engineer than an arbitrary score. | Zero ranking benefit. Purely a communication improvement — listed so it is not mistaken for a performance one. |

---

## What was considered and rejected

- **Deep learning of any kind (GNN, sequence model, transformer).** Already tested and
  already lost: `scripts/nn_sequence_bakeoff.py` and the MLP arm of the bakeoff both
  underperformed, with recall@500 as low as 1–4 of 21. 21 positives will not support it,
  and a GraphSAGE model would fail for the same reason. The corridor features in #5 are
  the right way to capture graph structure at this sample size.
- **More hyperparameter search.** Already answered: fresh nested-CV tuning reproduced the
  frozen parameters to four decimals. There is nothing left in that direction.
- **SMOTE / synthetic minority oversampling.** Interpolating between 21 real KSI sites
  manufactures intersections that do not exist, and with spatial data the synthetic points
  land in geographically meaningless places. It would inflate CV scores and degrade the
  forward run. Not worth the credibility risk.

---

## Execution order

0. **Get SWITRS.** Download the TIMS export into `data/raw/switrs/<YYYYMMDD>/` per
   `docs/DATA_SOURCES.md` and run the pipeline in README.md. Everything below is
   blocked on this and nothing else. Until then, `make synthetic_check` exercises the
   machinery without it.
1. ~~**#1 evaluation harness**~~ — **done.** Repeated CV plus the paired bootstrap is
   implemented in `scripts/improvement_bakeoff.py` and covered by
   `tests/test_improvement_harness.py`. Run it against the real panel first, before
   any other change, to establish the reference numbers everything else is compared to:
   `python scripts/improvement_bakeoff.py --arms current,baseline --threshold 1`
2. **#2 county training** and **#3 window stacking** — these attack n directly and need no
   new data source. Run them together; both are pure re-partitions of data you already have.
3. **#5 corridor features** — best information-per-effort of any new feature, no new licence.
4. **#4 exposure/AADT** — biggest single expected effect, but gated on acquiring and
   imputing the counts.
5. **#6–#9** in whatever order the data lands.
6. **#10–#12** as cleanup before writing up.

Adoption rule, unchanged from `docs/FEATURE_CATALOG.md`: a change earns its place only if
it shows **incremental lift on both the random and the spatial split**, with the paired
bootstrap from #1 excluding zero, **and** it does not degrade the forward run. The infra
feature-set finding is the cautionary example — a clean, consistent +0.02 on both verified
splits that did not replicate on 2025 data. Hold every item on this list to that standard.
