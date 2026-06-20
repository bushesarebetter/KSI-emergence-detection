# Key Design Decisions

This document records the decisions made during the project, including the ones that
changed from the original research design. The goal is full transparency: what changed,
when, and why.

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

**These numbers are stated below as last corrected (D11); see D11 for the candidate-set fix
that superseded an earlier version of this section.**

Spearman ρ = **0.128** (random split) / **0.131** (spatial split). A no-fitting persistence
baseline (rank by recent crash count and trend) scores **0.133** — still slightly ahead,
statistically the same as the tuned model given n=21 positives. At the ≥2-KSI threshold,
recall@500 is **10/21 (47.6%)** on both splits, an exact tie with the baseline's 10/21. At
the ≥1-KSI threshold the model shows a real, consistent edge over the baseline: **75/378
(19.8%)** random split / **73/378 (19.3%)** spatial split, vs. the baseline's 61/378
(16.1%). Full numbers and methodology in `scripts/refit_verified_run_oof.py` and
`results/oof_verified_run_results.json`.

The honest framing: crash-history trend is a real, useful signal, and a one-line heuristic
captures it just as well at the severe (≥2-KSI) threshold. The tuned model's clearest
validated contribution is at the broader (≥1-KSI) threshold.

**Forward run (2016–2023 features → 2024–2026 labels):** the operational prediction.
Feature window extends through 2023 to include the first two full post-COVID traffic years.
Label window is 2024–2026; 2024 is complete, 2025–2026 are pending. Spearman ρ = **0.066**
(random) / **0.068** (spatial), again tied with the persistence baseline (0.072). Treat all
forward-run numbers as provisional: only one of three label years is in, and there are only
2 positives at the ≥2-KSI threshold so far, too few for that threshold to mean anything yet.
recall@500 at the ≥1-KSI threshold (108 positives): 19.4% random split / 22.2% spatial
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
$2,127M (≥1) — these numbers, unlike the recall-derived ones in D6, turn out to match the
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
named "SAN DIEGO"). The loader takes `union_all()` over **all 74 rows unconditionally** —
there was never a filter to the city-named rows. Of a random sample of 500 candidates, only
31% actually fell inside the true City of San Diego boundary.

**Why this didn't get caught by any of the model's own diagnostics:** the SWITRS crash data
feeding every feature and label was always correctly scoped to the city the whole time
(confirmed directly: 99.97% of crash records carry `JURIS` code 3711, San Diego PD, or the
matching CHP beat). So the ~68% of candidates outside true city limits had almost no real
crash history in this dataset — not because they're genuinely safe, but because the crash
data was never queried for them. The model mechanically scored them near zero. This showed
up as: (a) 21 of 22 confirmed emergent sites and 494 of the top-500 shortlist landing inside
San Diego anyway, which looked like a clean signal but was actually a measurement-coverage
artifact, and (b) a severely imbalanced spatial cross-validation fold (one fold held 67% of
all candidates, because Community Planning Area polygons — correctly scoped to the real
city, ~332 sq mi — don't cover the ~68% of candidates that were never really in the city).

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
  of the data — this was a direct symptom of the same bug, now resolved as a side effect.
- Spearman ρ rose from ~0.087 to **~0.13** across the board (model, baseline, and all
  feature sets) — a real increase in signal-to-noise once non-informative rows were removed
  from the pool, not the model getting better.
- recall@500 (≥2-KSI) is **unchanged in absolute terms** (10/21 vs. the prior 10/22) — the
  city's true candidate count and the true positive count moved together, so the headline
  "found roughly half the sites the city's process misses" claim survives intact.
- The infrastructure-features finding (D8) reversed from "no effect" to "consistent
  positive signal on both splits" — this was the most surprising result of the fix, and is
  flagged as a promising lead rather than a settled claim given the small sample.
- Dollar figures and BCRs were recomputed on the corrected population; see D10's note above
  for the final reconciliation.
