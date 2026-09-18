# Key Design Decisions

This document records the decisions made during the project, including the ones that
changed from the original research design. The goal is full transparency: what changed,
when, and why.

> **Current state:** the deployed model is **E** — crash history + road infrastructure +
> spatial-neighbor structure — on the candidate set **below the City's 5-crash screen**
> (`crashes_feat < 5`, **D18**). Earlier entries describe superseded choices (the `KSI_feat < 2`
> candidate screen, the ≥2-KSI operating threshold, the crash-only model); they are kept as the
> record, not the current design. Results: `../README.md`, `HYPOTHESIS.md`.

---

## D1 — Primary modeling target: Tweedie count regression, not binary classification

**Original design:** binary classification on ≥2 KSI.

**What changed:** the corrected candidate set (after the geocoding fix in D4) produced only
22 intersections with ≥2 KSI in the label window. That's well below the ~300-positive floor
needed for a binary classifier to be reliable.

**Decision:** switch the primary target to the continuous three-year KSI count, modeled with
Tweedie regression (XGBoost `objective=reg:tweedie`). Binary thresholds (≥1 KSI and ≥2 KSI)
stay in as evaluation operating points for recall@K, just not as the training target.

**Why Tweedie:** crash counts at individual intersections are sparse, zero-inflated, and
right-skewed. Tweedie handles the large zero-mass and the rare high-count sites without
needing a separate hurdle-model stage.

---

## D2 — Buffer radius: 76.2 m (250 US survey feet)

**Original design:** 30 m buffer.

**What changed:** a parameter sweep from 30–100 m showed positive coverage growing with
radius. The SafeTREC geocoder offsets crash coordinates slightly from the intersection
center, and a 30 m buffer misses many crashes because of that snap-to-node behavior.

**Decision:** adopt 76.2 m (the SafeTREC standard intersection influence radius) as the
primary buffer. The 30 m version stayed in as a sensitivity check.

The buffer was chosen on Spearman ρ grounds before recall@K existed as a metric, so the
choice isn't circular with the recall numbers reported elsewhere in this project.

---

## D3 — Surface streets only, trunk roads included

**Decision:** exclude OSMnx edge types `motorway` and `motorway_link` (freeway mainline and
on/off-ramps) from the candidate set. Freeway KSI crashes are segment-level events that
geocode to highway nodes, not intersection nodes.

Trunk roads (arterials like major boulevards) were borderline. A sensitivity check showed
including them didn't meaningfully change Spearman ρ or recall@K, so they stayed in the
final candidate set.

---

## D4 — Geocoding field correction: POINT_X/POINT_Y, not LATITUDE/LONGITUDE

**Original implementation:** used SWITRS `LATITUDE`/`LONGITUDE` (officer-reported GPS).

**What changed:** `LATITUDE`/`LONGITUDE` has only ~44% coverage and is heavily skewed
toward freeway locations (~98.5% of populated records geocode to freeway nodes). The right
field is `POINT_X`/`POINT_Y`, which carries SafeTREC street-intersection geocoded
coordinates with ~96% coverage and basically no freeway skew.

**Impact:** every Milestone 1 and Milestone 2 numeric result was superseded by this fix.
The candidate set, feature distributions, and model results all changed materially. Only
Milestone 3a and later results are valid.

**Implementation:** `POINT_X`/`POINT_Y` are in WGS84 (EPSG:4326), reprojected to EPSG:2230
(California State Plane Zone VI) for buffer and distance math.

---

## D5 — Ablation protocol: frozen hyperparameters (Protocol A, not Protocol B)

**Original ablation (M3b, Protocol B):** re-ran Optuna at every feature-set step, selected
on Tweedie deviance, then reported Spearman ρ. That produced a confounded result: adding
infrastructure features sometimes improved deviance while reducing Spearman ρ at the same
time, giving false negatives depending on which metric you looked at.

**Correct ablation (Protocol A):** tune hyperparameters once on the crash-only feature set
(Set A), freeze them, and reuse them unchanged for every other feature set (B, C, D). The
only thing that changes between sets is the feature matrix, so any apparent lift or loss
can be attributed to the features themselves rather than to re-tuning noise.

**Result under Protocol A:** adding road geometry, signals, or the full infrastructure
feature group shows no statistically distinguishable effect on Spearman ρ relative to
crash-only, at the sample size this project has (22 positives at the ≥2-KSI threshold). See
D8 for the full writeup.

---

## D6 — Verified run vs. forward run, and how the model is evaluated

**Verified run (2016–2021 features → 2022–2024 labels):** the scientific result. Ground
truth is complete for this window. The model is XGBoost Tweedie regression on 20 crash-
history features, with hyperparameters chosen by nested cross-validation, evaluated with
genuine 5-fold out-of-fold (OOF) scoring: every reported prediction comes from a fold that
never saw that row during training.

**These numbers are stated below as last corrected (D11, D15); see those entries for what
superseded earlier versions of this section.**

Spearman ρ = **0.128** (random split) / **0.131** (spatial split). A no-fitting persistence
baseline (rank by recent crash count and trend) scores **0.133**, still slightly ahead,
statistically the same as the tuned model given n=21 positives. At the ≥2-KSI threshold,
recall@500 is **10/21 (47.6%)** on the random split, ties the baseline; **9/21 (42.9%)** on
the spatial split, the baseline edges ahead there. At the ≥1-KSI threshold the model shows a
real, consistent edge over the baseline: **74/378 (19.6%)** random split / **71/378 (18.8%)**
spatial split, vs. the baseline's 61/378 (16.1%). Full numbers and methodology in
`scripts/refit_verified_run_oof.py` and `results/oof_verified_run_results.json`.

The honest framing: crash-history trend is a real, useful signal, and a one-line heuristic
captures it just as well at the severe (≥2-KSI) threshold. The tuned model's clearest
validated contribution is at the broader (≥1-KSI) threshold.

**Forward run (2016–2024 features → 2025–2027 labels):** the operational prediction.
Feature window extends through 2024 to include the most recent available crash history.
Label window is 2025–2027; 2025 is complete, 2026–2027 are pending. Spearman ρ = **0.069**
(random) / **0.068** (spatial), again tied with the persistence baseline (0.072). Treat all
forward-run numbers as provisional: only one of three label years is in, and there are only
2 positives at the ≥2-KSI threshold so far, too few for that threshold to mean anything yet.
recall@500 at the ≥1-KSI threshold (108 positives): 18.5% random split / 21.3% spatial
split, vs. the baseline's 22.2% (baseline edges ahead here). Full numbers in
`results/oof_forward_run_results.json`.

The live dashboard's predictions are unaffected by any of this: the deployed model is
correctly fit on all available historical data, since there's no future label to leak when
scoring intersections whose outcomes haven't happened yet. The evaluation methodology above
only governs how confident we should be in the model's *claimed accuracy*, not what it
predicts.

---

## D7 — Candidate exclusion: zero prior KSI history required

Any intersection with two or more KSI crashes in the feature window is excluded from the
candidate set. This is the definitional core of the task: predicting which currently-clean
sites will become dangerous, not re-ranking sites that are already known hotspots. The
excluded sites are exactly the ones the city's current reactive review already catches.

**Consequence:** the city's annual ≥5-crash review cannot, by construction, identify any
site in this candidate set. The comparison "city finds 0 of the eventual emergent sites,
the model finds 10 of 21" is definitional, not a claim about the city's process being
poorly run.

---

## D8 — Infrastructure features: a real, consistent signal once the candidate set was fixed

This finding has moved twice. The original Protocol A comparison (in-sample) found
infrastructure features reduced Spearman ρ. Re-evaluated with genuine out-of-fold scoring
on the (at the time still bugged, county-wide) candidate set, the deltas were small,
inconsistent in sign between splits, and read as noise (D8 as originally written said "no
measurable effect either way"). After fixing the candidate-set scope bug (D11), the same
comparison on the corrected 26,423-candidate City-of-San-Diego-only set gives a
**materially different result**:

| Feature set | Spearman ρ (random) | Spearman ρ (spatial) | Δ vs. crash-only (random / spatial) |
|---|---|---|---|
| A: crash-only | 0.128 | 0.131 | — |
| B: + road geometry | 0.148 | 0.150 | +0.020 / +0.020 |
| C: + signals | 0.134 | 0.135 | +0.006 / +0.005 |
| D: + all infrastructure | 0.149 | 0.150 | +0.021 / +0.020 |

Unlike the earlier (bugged-data) result, **B and D now show a consistent positive delta on
both splits**, similar magnitude on each, not the random-up/spatial-down overfitting
signature seen before. That consistency is the main reason to take this more seriously than
the earlier "no effect" reading. recall@500 (≥2-KSI) moves from 10/21 (crash-only) to
11-12/21 with infrastructure features, depending on configuration.

---

**Practical implication, stated carefully:** this is a more promising signal than anything
seen before in this project, but it is still built on n=21 positives, the same small-sample
regime that has made every other comparison in this project noisy. Treat this as a lead
worth investigating further (e.g., once 2025-2026 forward-run labels are available and the
positive count grows), not as settled proof that infrastructure data is required. The model
*reported* in README/the deck is still the simpler crash-only one; this finding is flagged
separately rather than baked into the headline claim, because the gain is real-looking but
not yet large enough to justify the added data-collection burden with confidence.

recall@200's 95% CI lower bound (random split, ≥2-KSI threshold) clears random search by a
wide margin regardless of which feature set is used; the model is useful relative to random
search even at its simplest configuration.

---

## D9 — Extended ablation (Groups E–H, plus demographics): no robust lift, mixed signs

Re-run with genuine out-of-fold scoring (`scripts/refit_extended_ablation_oof.py`), frozen
Set-A hyperparameters, against the crash-only baseline (ρ = 0.087 random / 0.084 spatial):

| Group | Features | Δ random ρ | Δ spatial ρ | recall@500 (random/spatial) |
|---|---|---|---|---|
| E: ADT proxy (OSM maxspeed) | +3 | +0.003 | -0.007 | 9/22 · 10/22 |
| F: ACS demographics (Census 2022 5-yr) | +5 | +0.011 | -0.011 | 11/22 · 9/22 |
| G: pedestrian infrastructure | +4 | +0.000 | +0.000 | 8/22 · 10/22 |
| H: E + G | +7 | +0.003 | -0.006 | 10/22 · 9/22 |
| I: E + F + G combined | +12 | +0.012 | -0.008 | 12/22 · 9/22 |

**Pattern:** every group except G shows a small positive delta on the random split and a
small negative delta on the spatial split. That divergence is itself informative: the
spatial-block split is the stricter test for genuine generalization (it can't be fooled by
local spatial autocorrelation the way a random split can), so an apparent gain that
vanishes or reverses under spatial holdout looks more like noise fit to the random split
than a real signal. None of these deltas (0.000 to 0.012 in Spearman ρ, 1-3 sites out of 22
in recall@500) clear the noise floor at this sample size either way.

**Group G stays degenerate.** Overpass attic API queries for crosswalk and sidewalk data
failed again on this re-run (consistent with the original attempt), so those two features
are zero for every candidate. Only `has_ped_signal` is real, and it's highly collinear with
`signal_present` (already in Set D), which is why Group G ties the baseline exactly.

**Group F (ACS demographics) is now genuinely tested**, not skipped: a Census API key was
obtained and a geometry-download bug in `scripts/run_extended_ablation.py` (a malformed
TIGERweb query, fixed 2026-06-19) was blocking it even with a working key. With both fixed,
demographics show the largest single-group bump on the random split (+0.011) but a
negative one on the spatial split, the same overfitting-flavored pattern as the others.

**Revised conclusion (at the time):** no extended feature group, individually or combined,
showed a statistically robust improvement over crash-only on the data available then.

**Re-run on the corrected city-only candidate set (2026-06-20):** Groups E, G, and H were
re-tested (`scripts/refit_extended_ablation_oof.py`) against a freshly-derived crash-only
reference (ρ = 0.128 random / 0.131 spatial, not the stale county-wide constant the script
had been comparing against):

| Group | Δ random ρ | Δ spatial ρ | recall@500 (random/spatial) |
|---|---|---|---|
| E: ADT proxy | +0.0072 | +0.0068 | 10/21 · 9/21 |
| G: pedestrian infrastructure | -0.0001 | -0.0005 | 10/21 · 10/21 |
| H: E + G | +0.0072 | +0.0068 | 10/21 · 9/21 |

E and H now show a small but **consistent** positive delta on both splits, similar to the
B/D pattern in D8, though smaller in magnitude. G remains degenerate: Overpass crosswalk
and sidewalk queries failed again, so only `has_ped_signal` is real, and it's collinear
with `signal_present` already in Set D, hence the near-zero delta.

**Group F (ACS demographics) has not been re-tested on the corrected candidate set.** It
needs a Census API key supplied again (not stored anywhere in this repo, by design) plus a
working Overpass connection for G's full feature set. Treat Group F as unverified on the
current candidate set until that re-run happens.

**Revised conclusion:** consistent with D8, the small-infrastructure-group story is now
"small but consistently positive on both splits" rather than "no effect" or "pure noise."
None of these deltas are large enough to justify adding infrastructure data collection as
a requirement, but the direction is no longer ambiguous the way it was on the buggy
county-wide candidate set.

---

## D10 — Fatal-share figure was using the wrong run's window

The $228M/$2.13B total-harm figures and the BCR figures derived from them all depend on a
measured fatal-vs-serious split of KSI crashes (the FHWA fatal-crash cost is roughly 9x the
serious-injury cost, so this ratio matters a lot to the dollar totals). That split was being
read from `data/proc/ksi_label_crashes.parquet`.

**The bug:** that file is not archived per run. `src/labels/build_panel.py` overwrites it in
place every time it runs, for whichever label window that run used. By the time the
verified-run harm figures were computed during this audit, the file on disk reflected the
forward run's 2025 window (fatal share 14.5%), not the verified run's 2022-2024 window
(fatal share 24.3%, confirmed by filtering raw SWITRS directly). Every verified-run dollar
figure produced under the 14.5% assumption understated the true harm and the resulting BCRs
by roughly 35-40%.

**Fix:** `scripts/compute_verified_numbers.py` and `scripts/refit_verified_run_oof.py` now
compute fatal share directly from raw SWITRS, filtered to the specific label window being
evaluated, rather than trusting the shared mutable proc file. `compute_verified_numbers.py`
also previously computed a single fatal share and reused it for both the verified and
forward runs even though they cover different label windows; it now computes one per run.

**Corrected figures (verified run, top-500, county-wide candidate set, since superseded):**
≥2-KSI BCR ~9.7:1 (random split) / 10.7:1 (spatial split), up from the previously reported
~7.1:1/7.8:1. ≥1-KSI BCR ~39.3:1, up from ~28.7:1. Total population harm: $228M (≥2) /
$2,127M (≥1). These numbers, unlike the recall-derived ones in D6, turn out to match the
original pre-audit deck almost exactly, because total harm is a measured fact about
historical crashes, not a model output; only the *recall@K-derived* figures (which sites
the model catches) needed the leakage correction in D6. The fatal-share mixup was a
separate, independent error introduced while fixing the first one. **The candidate count
and several of these figures were superseded again by D11**, which restricted the
candidate set to the true City of San Diego; the fatal-share fix itself (24.3%, computed
from raw SWITRS filtered by date window) remains correct and unaffected by D11.

---

## D11 — Candidate set spanned all of San Diego County, not just the City of San Diego

This is the most consequential correction in the project. Every number published before
2026-06-20, including the ones in D6, D8, D9, and D10, was computed on a candidate set that
was not actually the City of San Diego.

**The bug:** `src/ingest/osm_loader.py` builds the road network (and therefore every
candidate intersection) from `data/raw/cpa/<date>/city_boundary.geojson`. That file
contains 74 separate polygons covering **all 18 incorporated cities in San Diego County
plus unincorporated county land** (confirmed: La Mesa, El Cajon, Chula Vista, Oceanside,
Escondido, Carlsbad, Encinitas, National City, Poway, Coronado, Vista, San Marcos, Santee,
Lemon Grove, Solana Beach, Imperial Beach, Del Mar, and "S.D. COUNTY," plus 7 rows actually
named "SAN DIEGO"). The loader takes `union_all()` over **all 74 rows unconditionally**.
There was never a filter to the city-named rows. Of a random sample of 500 candidates, only
31% actually fell inside the true City of San Diego boundary.

**Why this didn't get caught by any of the model's own diagnostics:** the SWITRS crash data
feeding every feature and label was always correctly scoped to the city the whole time
(confirmed directly: 99.97% of crash records carry `JURIS` code 3711, San Diego PD, or the
matching CHP beat). So the ~68% of candidates outside true city limits had almost no real
crash history in this dataset: not because they're genuinely safe, but because the crash
data was never queried for them. The model mechanically scored them near zero. This showed
up as: (a) 21 of 22 confirmed emergent sites and 494 of the top-500 shortlist landing inside
San Diego anyway, which looked like a clean signal but was actually a measurement-coverage
artifact, and (b) a severely imbalanced spatial cross-validation fold (one fold held 67% of
all candidates, because Community Planning Area polygons, correctly scoped to the real
city, ~332 sq mi, don't cover the ~68% of candidates that were never really in the city).

**A genuine regional analysis was considered and rejected.** A countywide version would
need a fresh SWITRS download scoped to the whole county (manual, TIMS-gated, unknown
turnaround time) and a full pipeline rebuild, for a result that a direct check showed
wouldn't actually be more compelling: the *recall* numbers (sites found / sites that exist)
barely move when restricting to the true city, only the "Nx better than random" multiplier
shrinks, because that multiplier's denominator was inflated by the same bug. The honest
fix was to restrict the candidate set, not to relabel the geographic scope.

**Fix:** `scripts/restrict_candidates_to_city_limits.py` filters `candidate_panel.parquet`
in both the `verified_run/` and `forward_run/` archives down to intersections that fall
inside the actual `SAN DIEGO`-named polygon (originals backed up to
`candidate_panel_COUNTYWIDE_backup.parquet`). Every OOF refit, ablation, and bake-off script
was re-run on the corrected data; every downstream document and report was updated.

**What changed:**
- Candidates: 81,007 → **26,423** (verified run), 80,618 → **26,045** (forward run)
- Emergent sites (≥2 KSI): 22 → **21** (one site, in Escondido, was never really a San
  Diego site)
- Spatial-block CV folds are now evenly sized (~5,300 each) instead of one fold holding 67%
  of the data. This was a direct symptom of the same bug, now resolved as a side effect.
- Spearman ρ rose from ~0.087 to **~0.13** across the board (model, baseline, and all
  feature sets), a real increase in signal-to-noise once non-informative rows were removed
  from the pool, not the model getting better.
- recall@500 (≥2-KSI) is **unchanged in absolute terms** (10/21 vs. the prior 10/22). The
  city's true candidate count and the true positive count moved together, so the headline
  "found roughly half the sites the city's process misses" claim survives intact.
- The infrastructure-features finding (D8) reversed from "no effect" to "consistent
  positive signal on both splits," the most surprising result of the fix, and is
  flagged as a promising lead rather than a settled claim given the small sample.
- Dollar figures and BCRs were recomputed on the corrected population; see D10's note above
  for the final reconciliation.

---

## D12 — Forward run window text was stale; archive timestamps were inconsistent

The forward run's intended window (`configs/config.yaml`) is features 2016-2024 → labels
2025-2027. The genuine OOF results (`results/oof_forward_run_results.json`) and
`reports/milestone_final.md` already reflected this window. `README.md`, however, still
described the forward run as "2016-2023 features... covering 2024-2026" (stale text from
before the window was last shifted forward).

**Separately:** `data/model/forward_run/feature_table.parquet` and `frozen_scores.parquet`
had an older timestamp than `candidate_panel.parquet`, meaning the archived feature table
and the archived labels weren't necessarily built in the same pipeline pass.

**Fix:** re-ran `src.labels.build_panel` and `src.features.build_crash_emergence` and
`src.model.fit_frozen` under the current config, re-archived all three files to
`data/model/forward_run/`, re-ran `restrict_candidates_to_city_limits.py`,
`refit_forward_run_oof.py`, `compute_verified_numbers.py`, and the dashboard export. Also
fixed an unrelated stale check in `compute_verified_numbers.py` that still validated the
verified run against 22 ≥2-KSI positives (the pre-D11 county-wide count) instead of 21.

**Result:** every genuine OOF number (Spearman ρ, recall@K) came back numerically identical
to what was already published. The forward-run model and labels were already built on the
correct window. Only the README prose and `results/top500_forward_2024_2026.csv` (renamed
to `top500_forward_2025_2027.csv` and regenerated from the OOF scores) were actually wrong.
The archive is now internally consistent (all three files from one pipeline pass) even
though the headline numbers didn't move.

---

## D13 — Infrastructure-feature lift (D8) replicates on the forward run

D8 found a small, consistent positive Spearman delta from infrastructure features (B, D)
on the verified run, once the candidate-set scope bug was fixed. Re-tested on the forward
run panel (2016-2024 features, 2025-only partial labels) with the same frozen hyperparameters,
genuine 5-fold OOF (`scripts/refit_protocol_a_forward_oof.py`):

| Set | Δ random ρ | Δ spatial ρ | recall@500 (≥1, random/spatial) |
|---|---|---|---|
| A: crash-only | — | — | 20/108 · 23/108 |
| B: + road geometry | +0.0101 | +0.0088 | 21/108 · 22/108 |
| C: + signals | +0.0019 | +0.0009 | 22/108 · 20/108 |
| D: + all infrastructure | +0.0101 | +0.0092 | 21/108 · 25/108 |

B and D show the same consistent-on-both-splits pattern as the verified run, proportionally
similar in size (~15% relative lift here vs. ~16% on the verified run). recall@500 movement
is small and mixed (a 1-2 site swing on 108 positives, noise-level), so this doesn't change
the operational shortlist yet, but the Spearman consistency across two independent runs is
real evidence the D8 lift isn't a one-dataset fluke. Still not strong enough to add an
infrastructure-data requirement to the reported model.

> **Superseded by D17.** The OOF procedure here retrained a fresh model on the forward
> panel's own (partially-resolved) 2025 label each time, which D17 established is the wrong
> methodology for the forward run. It should use the one frozen, never-retrained
> verified-run model applied via predict-only, like the deployed score. Re-tested with
> `scripts/predict_protocol_a_forward.py`: B and D no longer replicate the verified run's
> positive lift. Spearman deltas vs. crash-only are small and **negative**
> (B −0.0136, C −0.0060, D −0.0148). See D17 for the full numbers. This finding (D8 lift
> replicates on the forward run) should no longer be cited.

---

## D14 — Prospective 2025 evaluation was using a stale one-year-old feature cutoff

`scripts/run_recall_evaluation.py` builds a fresh prospective candidate cohort, scores it
with the frozen verified-run model, and checks against true 2025 KSI outcomes. Its window
was `feature_end = 2023-12-31`, `feature_cutoff_date = 2024-01-01`, left over from before
D12 corrected the forward run's window from 2016-2023 to 2016-2024. Nothing about this was a
leakage bug (2023 features are still cleanly before the 2025 label window), it just meant the
prospective check wasn't using the most current data available, one full year less than the
operational forward run uses for the same purpose.

**Fix:** bumped to `feature_end = 2024-12-31`, `feature_cutoff_date = 2025-01-01`. This makes
the prospective candidate cohort's eligibility screen and feature window identical to the
forward run's own (26,045 candidates, 108 positives at ≥1 KSI, 2 at ≥2, same population
exactly). Re-running gives recall@500 (≥1 KSI) = 24/108 (22.2%, 11.6× random, 95% CI
[14.8%, 30.6%]), down slightly from the prior 26/112 (23.2%, 12.1×) computed on the stale
2023-cutoff cohort. The direction of the change is expected: a stricter, more current
eligibility screen (excluding any site with KSI through 2024, not just through 2023) removes
a few already-risky sites from the denominator and a few resulting hits from the numerator;
it doesn't change the conclusion. Updated in `README.md`, `reports/milestone_final.md`, and
the Notion outreach materials.

---

## D15 — Verified-run recall@K hit counts didn't match the canonical OOF results file

A comprehensive audit (two independent reviews, one cross-checking every numeric claim
against source files, one auditing the pipeline code) found that the recall@K hit counts
quoted in `README.md`, `reports/milestone_final.md`, this file's own D6 section, and every
Notion outreach page (Project Writeup, Cost-Benefit Analysis, Pitch Deck, Outreach &
Connections) did not match `results/oof_verified_run_results.json`, the file every one of
them cites as its source. Spearman ρ was correct everywhere; only the recall@K hit counts,
and everything computed from them (harm, BCR), had drifted.

**Re-running `scripts/refit_verified_run_oof.py` reproduces the actual file deterministically**
(same code, same `random_state=42`, same candidate panel), confirming the published numbers
were stale relative to the current, correct, post-D11 verified-run archive. Not a one-off
typo, and not something this session introduced (the archive predates this session; the docs
were apparently never reconciled against it after some earlier rebuild).

**Corrected ≥2-KSI recall@500:** random 10/21 (47.6%, unchanged, still ties the persistence
baseline), **spatial 9/21 (42.9%, was published as 10/21; the baseline now edges ahead of
the model on this split, it does not tie it.** ≥2-KSI BCR: 9.6:1 random (was 9.7:1, minor) /
**8.7:1 spatial (was claimed tied at ~9.7:1)**.

**Corrected ≥1-KSI recall@500:** random 74/378 (19.6%, was published as 75/378) / spatial
71/378 (18.8%, was published as 73/378). ≥1-KSI BCR: 40.4:1 random (was 41.2:1) / 38.5:1
spatial (was 40.3:1). At K=200, the random split now exactly ties the baseline (27/378 both)
rather than showing a small edge (the published "29 (random)" was also wrong).

**Separate fix:** `scripts/refit_verified_run_oof.py` computed persistence-baseline scores
but never wrote the baseline's own recall@K into its JSON output. The baseline numbers in
every doc were being hand-computed separately (correctly, as it turned out) with no way to
spot-check them against the canonical file. Added a `persistence_baseline` block to the
script's output alongside `random`/`spatial`, so the file is now self-contained.

Updated: `README.md`, `reports/milestone_final.md`, this file's D6, and the Notion Project
Writeup, Cost-Benefit Analysis, Pitch Deck, and Outreach & Connections pages.

---

## D16 — Forward-run OOF script hardcoded a third, different hyperparameter set

The project's Protocol A discipline (D5) is to tune hyperparameters once on the crash-only
model, freeze them, and reuse them unchanged everywhere, so any difference between
comparisons is attributable to the data, not to re-tuning noise. Every OOF script follows
this by loading `data/model/frozen_params.json` directly: `refit_verified_run_oof.py`,
`refit_protocol_a_oof.py`, `refit_protocol_a_forward_oof.py`, `fit_frozen.py`.

`scripts/refit_forward_run_oof.py` was the one exception: it hardcoded a literal copy of a
hyperparameter dict, commented as coming from "the project's best model in the verified-run
bake-off (`results/final_chosen_model_oof.json`)." Three problems with this, found in a
comprehensive audit: (1) `results/final_chosen_model_oof.json` is itself just a saved copy
of `scripts/model_bakeoff_oof.py`'s "freshly nested-CV-tuned XGBoost" result, a one-off
architecture-comparison data point, not Protocol A's frozen model. (2) The hardcoded copy
in `refit_forward_run_oof.py` didn't even match that file correctly: three different
hyperparameter sets existed across the project (`frozen_params.json`: variance_power=1.12,
depth=3, n_estimators=171; the hardcoded copy: variance_power=1.59, depth=4, n_estimators=53;
`final_chosen_model_oof.json`: variance_power=1.46, depth=3, n_estimators=85), and none of
the three agreed. (3) Separately, `model_bakeoff_oof.py`'s "freshly tuned" XGBoost result
(used in the README's architecture-comparison narrative, which claims it "is the model
reported above") doesn't actually match what `refit_verified_run_oof.py` computes for the
verified-run headline numbers either — that script has always used the frozen Protocol-A
params, not the bake-off's fresh tune. The README's claim that the freshly-tuned model is
"the model reported" was never true of the actual headline-number-generating script.

**Fix:** `refit_forward_run_oof.py` now loads `frozen_params.json` directly, the same as
every other OOF script, eliminating the hardcoded copy and the drift risk permanently. The
architecture-comparison framing in README/Pitch Deck/Project Writeup was corrected to
describe the freshly-tuned XGBoost as one data point in the bake-off (it performs about the
same as the frozen model, Spearman 0.1279 vs. 0.1279 random on the verified run, recall
within a site or two), not as the model actually used for any headline number.

**Result, forward run (≥1 KSI, genuine OOF):** Spearman ρ random 0.0661 → **0.069**
(spatial unchanged at 0.068). recall@500: random 21/108 (19.4%) → **20/108 (18.5%)**,
spatial 24/108 (22.2%) → **23/108 (21.3%)**. The OOF-based hit/miss ring on the live
dashboard map dropped from 21 to **20 white rings**. The verified run's own headline numbers
were unaffected (it was already loading `frozen_params.json` correctly). This was purely a
forward-run and architecture-comparison-narrative fix. Updated: `README.md`,
`reports/milestone_final.md`, this file's D6, the Notion Project Writeup and Pitch Deck, and
`dashboard/src/FilterBar.jsx`'s static OOF lookup table.

---

## D17 — The forward run's live/deployed score was fit on the label it was being scored against

`src/model/fit_frozen.py` does `model.fit(X, y)` where `y = panel["KSI_label"]`. For the
verified run this is correct supervised training: 2016-2021 features → 2022-2024 labels,
both fully resolved well before "now," so fitting on `y` is legitimate historical training,
and OOF (D12, D16) exists only to get an unbiased *evaluation* of that legitimately-trained
model, not because the training itself is improper.

For the forward run, this was a real bug, not just an evaluation-bias issue. The forward
panel's `KSI_label` represents the 2025-2027 outcome, and because the project's "current
date" has moved past 2025, that portion of the label is now resolved and sitting in the
SWITRS export the panel was built from. `fit_frozen.py` doesn't distinguish "resolved
historical label, safe to train on" from "label being evaluated, must never touch it." It
just fits on whatever `KSI_label` is in the current panel. So every time the forward-run
pipeline was re-run, the production model was handed the real 2025 answer as its training
target, then immediately scored on those same rows. `reports/verified_canonical_numbers.json`
already had an `IN_SAMPLE_WARNING` flagging this for its own in-sample recall@K table, but
that warning didn't stop the *live dashboard* from using the same leakage-tainted score for
its actual displayed predictions. Only the JSON's own printed numbers were flagged, not the
deployed model behind the map.

Separately, `scripts/refit_forward_run_oof.py` (D16) did genuine 5-fold OOF specifically to
work around this: by holding each candidate's row out of whichever fold trained the model
scoring it, no single row could be "answered" by a model that had directly fit on it. That
made the *evaluation* numbers honest, but the live map still showed the leakage-tainted
in-sample rank, and the dashboard's hit/miss ring (`oof_rank`) had to be sourced from a
*third*, separately-fit OOF model just to get an honest signal: three different scores
(in-sample live rank, OOF random split, OOF spatial split) for what should have been one
number.

**Fix:** stop fitting on the forward panel's label entirely. `scripts/predict_forward_run.py`
fits the frozen Protocol-A crash-only model **once**, only on the verified-run's own resolved
window (`data/model/verified_run/{candidate_panel,feature_table}.parquet`, 2016-2021 features
→ 2022-2024 labels), then calls `.predict()`, never `.fit()`, on the current forward
candidates' 2016-2024 features. The forward panel's `KSI_label` is read only afterward, to
report recall@K; it is never passed to the model. This is the same approach
`scripts/run_recall_evaluation.py` ("prospective_2025") already used. The forward run and
the prospective evaluation are now the same artifact by construction, so they report
identical numbers: recall@500 (≥1 KSI) = 24/108 (22.2%), recall@200 = 9/108 (8.3%).


## D18 — Candidate eligibility used a KSI threshold, not the City's actual screen

The project's whole claim is that it surfaces future-severe intersections the City's
current process **can't see**. The City's process is the High Crash List: it reviews
intersections with **≥5 injury-or-fatal crashes** (SWITRS severity 1-4) in the review
window, ~14 sites/year (see README "The problem", `scripts/city_screen_overlap.py`).

But candidate eligibility in `src/labels/build_panel.py` defined "currently clean /
invisible to the City" as `KSI_feat < 2` (fewer than 2 *severe* crashes in history), plus a
top-decile-KSI-density drop. That is not the City's screen. It admits into the candidate
universe intersections that already have ≥5 total crashes — sites the City is *already
reviewing* — as long as they had 0 or 1 KSI specifically. Any future-KSI outcome the model
"found" at those sites was credit for finding something the City already flags, which
inflates every "sites the City can't identify at all" and incremental-BCR claim.

**Fix:** eligibility now screens on the City's own definition. `build_panel` counts all
feature-window crashes per node (`crashes_feat`; the crash extract is already restricted to
severity 1-4, so this equals the injury-or-fatal count) and keeps a node iff
`crashes_feat < candidate_city_screen_min` (=5). Config: `labels.candidate_screen: "city"`.
The old rule is preserved as `labels.candidate_screen: "ksi_legacy"` for one sensitivity row.
The top-decile-KSI drop is retired from the primary path (with KSI so sparse its 90th
percentile is 0, it never removed anything anyway).

**Impact (approximate, forward window 2016-2024→2025-2027, county-wide surface nodes; the
authoritative figure comes from re-running the verified pipeline):** of the candidate sites
the *old* rule kept, ~1,019 have ≥5 crashes and are dropped by the new rule — and those
dropped sites contain ~47 of the ~111 ≥1-KSI positive outcomes (≈42%). In other words a
large share of the model's headline "positives" sat at intersections the City already
screens. The corrected candidate universe is a slightly smaller set (~80.2k vs ~80.6k) with
correspondingly fewer positives to find, but every remaining positive is genuinely a site
the City's volume screen would miss. `scripts/city_screen_overlap.py` (verified run) is the
place this lands hardest and should be re-read against the new candidate set. Retag all
downstream artifacts (features → fit → OOF → canonical numbers → README) after regenerating
the panel.

Because no fitting happens on forward candidates at all, there's nothing left to hold out:
`refit_forward_run_oof.py`, `results/oof_forward_run_results.json`, and
`data/model/forward_run/oof_scores.parquet` were deleted rather than kept as dead weight.
`scripts/build_export_panel_verified.py`'s `add_oof_hit_flag` now sets `oof_rank = rank`
directly for the forward run (live rank and genuine rank are now the same number); the
verified run is unaffected and still sources `oof_rank` from genuine OOF, since its training
labels are legitimately historical.

`scripts/refit_protocol_a_forward_oof.py` (the B/C/D infrastructure-ablation comparison for
the forward run) had the same `model.fit(X, y)`-on-the-forward-panel pattern, just inside a
5-fold OOF loop instead of a single fit. The OOF loop did stop any individual row from being
scored by a model that had directly trained on that exact row, but it was still answering a
different question than the one this project now asks of the forward run: it retrained a
brand-new model on the freshest (partially-resolved) 2025 window each time, rather than
applying the one frozen, never-retrained verified-run model. Replaced with
`scripts/predict_protocol_a_forward.py`, which fits all 4 feature sets once on the
verified-run's resolved window and predicts-only on forward candidates, mirroring
`predict_forward_run.py`. Result (recall@500, ≥1 KSI, 108 positives): crash-only 24/108
(unchanged from the deployed model, as expected, since it's the same data and same fit), road-geometry
26/108, signals 25/108, all-infra 26/108. Spearman deltas vs. crash-only are small and
**negative** here (B −0.0136, C −0.0060, D −0.0148), the opposite direction from the
verified run's finding (D8/D13: B and D help, +0.020/+0.021). With only 108 (partial-year)
positives and a single label year, this isn't strong evidence infra data hurts the forward
run; it's a reminder that the verified run's infra-helps finding hasn't yet been replicated
out-of-sample and shouldn't be assumed to transfer. `refit_protocol_a_forward_oof.py` and
`results/protocol_a_forward_oof_results.json` were deleted.

Updated: `scripts/predict_forward_run.py` (new), `scripts/predict_protocol_a_forward.py`
(new), `scripts/compute_verified_numbers.py`, `scripts/build_export_panel_verified.py`,
`scripts/export_predictions.py` (unrelated rank/tie-break fix found in the same pass),
`dashboard/src/FilterBar.jsx`, `dashboard/src/MapLegend.jsx`, `dashboard/src/MapView.jsx`,
`README.md`, `tests/test_d11_d16_regressions.py`, `data/model/frozen_scores.parquet`,
`data/model/forward_run/frozen_scores.parquet`, `dashboard/public/data/intersections.geojson`,
`results/top500_forward_2025_2027.csv`.
