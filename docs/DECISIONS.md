# Key Design Decisions

This document records the principal methodological decisions made during the project,
including decisions that deviated from the original research design. It is intended to
give reviewers full transparency into what changed, when, and why.

---

## D1 — Primary modeling target: Tweedie count regression (not binary classification)

**Original design:** binary ≥2 KSI classification.

**What changed:** the corrected candidate set (after the geocoding fix in D4) produced only
22 intersections with ≥2 KSI in the label window — well below the pre-registered adequacy
floor of approximately 300 positives needed for a reliable binary classifier.

**Decision:** switch the primary target to the continuous three-year KSI count, modeled via
Tweedie regression (XGBoost `objective=reg:tweedie`). Binary thresholds (≥1 KSI and ≥2 KSI)
are retained as evaluation operating points for recall@K.

**Why Tweedie:** count data at individual intersections is sparse, zero-inflated, and
right-skewed. Tweedie handles the large zero-mass and the rare high-count sites without
requiring a two-stage hurdle model.

---

## D2 — Buffer radius: 76.2 m (250 US survey feet)

**Original design:** 30 m buffer.

**What changed:** a parameter sweep from 30–100 m showed positive coverage growing
substantially with radius. The SafeTREC geocoder systematically offsets crash coordinates
a short distance from the intersection center (snap-to-node behavior), which a 30 m buffer
misses for many crashes.

**Decision:** adopt 76.2 m (the SafeTREC standard intersection influence radius) as the
primary buffer. The 30 m version was retained for sensitivity analysis.

**Sensitivity result:** full-population recall@200 is equivalent at both buffer sizes
(8/22, 36.4%). Recall@500 favors 76.2 m (13/22, 59.1%). The selection was made on
Spearman ρ grounds before recall@K was computed, so the recall result is not circular.

---

## D3 — Surface streets only; trunk roads included

**Decision:** exclude OSMnx edge types `motorway` and `motorway_link` (freeway mainline
and on/off-ramps) from the candidate set. Freeway KSI crashes are segment-level events
that geocode to highway nodes rather than intersection nodes.

**Trunk roads** (arterials such as major boulevards) were borderline. A sensitivity check
confirmed that including them did not substantially change Spearman ρ or recall@K.
They are included in the final candidate set.

---

## D4 — Geocoding field correction: POINT_X/POINT_Y not LATITUDE/LONGITUDE (critical)

**Original implementation:** used SWITRS `LATITUDE`/`LONGITUDE` fields (officer-reported
GPS coordinates).

**What changed:** discovered that `LATITUDE`/`LONGITUDE` has only ~44% coverage and is
heavily skewed toward freeway locations (~98.5% of populated records geocode to freeway
nodes). The correct field is `POINT_X` (longitude) / `POINT_Y` (latitude), which contains
SafeTREC street-intersection geocoded coordinates with ~96% coverage and negligible
freeway skew.

**Impact:** all Milestone 1 and Milestone 2 numeric results were superseded. The candidate
set, feature distributions, and model results all changed materially. Only Milestone 3a
and later results are considered valid.

**Implementation:** `POINT_X` and `POINT_Y` are in WGS84 (EPSG:4326). Reprojected to
EPSG:2230 (California State Plane Zone VI) for buffer and distance calculations.

---

## D5 — Ablation protocol: frozen hyperparameters (Protocol A, not Protocol B)

**Original ablation (M3b, Protocol B):** re-ran Optuna hyperparameter search at each
feature set step, selecting on Tweedie deviance, then reported Spearman ρ. This produced
a confounded result: adding infrastructure features sometimes improved deviance while
simultaneously reducing Spearman ρ, producing false negatives on opposite metrics from
the same feature addition.

**Correct ablation (M4, Protocol A):** hyperparameters are tuned once on the crash-only
feature set (Set A) and then frozen for all subsequent feature sets (B, C, D). The only
thing that changes across sets is the feature matrix. Any variation in hyperparameters
would indicate a protocol violation and is checked in the audit.

**Result under Protocol A:** all three infrastructure groups (road geometry, signals, all
infrastructure) reduced Spearman ρ relative to crash-only. The sufficiency null is
confirmed: crash history alone is sufficient at 76.2 m intersection resolution.

**Why infrastructure adds no signal:** at 76.2 m resolution, road geometry attributes
(lane count, edge count, signal presence) are nearly constant across comparable urban
intersections. The discriminating information is in crash timing and trajectory, not
physical attributes.

---

## D6 — Verified run vs forward run distinction

**Verified run (2016–2021 features → 2022–2024 labels):** the scientifically validated
result. Ground truth is complete. Spearman ρ = 0.175 (random) / 0.169 (spatial).
recall@500 = 13/22 (59%). All headline figures in external documents refer to this run.

**Forward run (2016–2023 features → 2024–2026 labels):** the operational prediction.
Feature window extended to include 2022 and 2023 (the first two full post-COVID traffic
years). Label window is 2024–2026; 2024 outcomes are now complete, 2025–2026 pending.
Full prospective evaluation available when 2025 SWITRS data is released (~early 2027).

**Why the forward run Spearman is lower (0.0948):** evaluated against a single-year
incomplete label window with 0 ≥2 KSI sites and only 118 ≥1 KSI sites in 2024 data.
This figure is not comparable to the verified run's 0.175 and will stabilize once
2025–2026 label data becomes available.

---

## D7 — Candidate exclusion: zero prior KSI history required

Any intersection with two or more KSI crashes in the feature window is excluded from the
candidate set. This is the definitional constraint for the emergence detection task: we
are predicting which currently-clean sites will become dangerous, not re-ranking existing
hotspots. The excluded sites are the ones the city's current reactive approach already
identifies.

**Consequence:** the city's annual ≥5-crash review cannot, by construction, identify any
site in our candidate set. The comparison "city finds 0/22, model finds 13/22" is
definitional, not contingent on the city's approach being poorly calibrated.

---

## D8 — Infrastructure sufficiency null: RESOLVED NEGATIVE

The pre-registered decision gate at Milestone 4 asked whether any infrastructure feature
set produced a CI-separated Spearman improvement over crash-only under Protocol A. The
answer is no: all three groups reduced Spearman. The null is confirmed.

**Practical implication:** the city does not need an infrastructure inventory to operate
this model. Crash records alone are sufficient for the ranked shortlist.
