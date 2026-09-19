# Hypothesis

## Claim

Among San Diego surface intersections below the City's screening threshold — fewer than 5
reported crashes in the look-back window, invisible to the High Crash List — a gradient-boosted
model on crash-history, infrastructure, and spatial-neighbor features ranks sites so that a
top-K shortlist concentrates future 3-year KSI emergence about 7–8x above chance. It reaches
harm the City's reactive process cannot, at a benefit-cost ratio above 1.

## Mechanism

The City acts on accumulated crash volume (≥5 crashes), a lagging indicator: it cannot see a
site until harm has piled up. KSI emergence at a still-quiet intersection is predictable ahead
of that accumulation from three orthogonal signals — sub-threshold crash count and trend, road
design (geometry, signals, speed), and corridor context (proximity to dangerous sites). A ranked
shortlist of sub-threshold sites lets the City inspect and treat before the crashes happen.

## Evidence

- **Concentration replicates across two windows.** Verified out-of-fold (2016–21 features →
  2022–24 outcomes) and prospective 2025 (predict-only, never trained on) both concentrate future
  KSI ~7.3x above random at the top-500. The model generalizes to a year it never saw.
- **Infra + spatial beat the no-ML baseline.** On the candidate set below the City screen, the
  crash + infrastructure + spatial model (E) beats a persistence baseline (rank by crash count and
  trend) by $6–11M prevented harm on both cross-validation splits at the any-KSI threshold. The
  spatial features hold up under a region-holdout split, so the corridor signal is predictive
  rather than spatial autocorrelation.
- **Feature attribution confirms the mechanism.** SHAP on the E model splits the decision
  **53% road infrastructure / 32% crash history / 15% corridor.** The top drivers are recency of
  the last crash, road functional class (arterial vs. local), intersection geometry (legs, lanes),
  and transit proximity. On the <5-crash set crash history is flat, so road design carries the
  weight — the direct reason E beats a crash-count baseline the City's screen relies on. Much of
  that infrastructure weight is exposure by proxy (arterials carry more traffic), which is why
  measured AADT is the highest-value feature still missing.
- **Calibration holds.** Predicted KSI counts track observed counts at the top of the ranking.

## Limits

- **The model has no severe-threshold signal.** At ≥2 KSI there are 8–9 positives, and the model
  catches fewer of them than a raw crash-count baseline. The product is injury-crash emergence,
  not fatal.
- **The edge over the baseline is small.** A few events on 40. It is consistent across splits and
  windows, which is why it stands, and it is not separable from noise on any single split. E is the
  best model and it is not decisively better than a one-line heuristic.
- **The strongest features track exposure.** Neighbor crash pressure and hotspot proximity are
  largely traffic-volume proxies; part of the signal is that busy areas have more crashes.
  Separating dangerous design from high exposure needs ADT data the project does not yet have.
- **The dollar figures are illustrative.** Prevented harm at top-500 is $21–62M across a 10–30%
  treatment-effectiveness range; the ~20:1 BCR uses the optimistic 30% and a ~$6.4k/site spend the
  analysis does not verify. The program clears break-even while average treatment stays under
  ~$40–120k/site. The baseline carries a similar BCR, so the ratio measures the economics of crash
  prevention, not the model's contribution. And the City treats ~14 spot sites a year, so a 500-site
  program is only realistic as systemic low-cost treatment, not spot fixes.
- **The City already uses the main signal.** Road design (SHAP: 53% of the E decision — functional
  class, geometry, lanes) is what San Diego's Systemic Safety Analysis (SSARP, built with SafeTREC)
  screens on. The model's contribution over that program is a site-specific ranking on the
  sub-threshold population, not a new risk factor. "Fully incremental to the City" holds against the
  reactive ≥5-crash review, not against the systemic program.
- **The forward edge is unconfirmed.** Only the overall 7.3x lift replicated on 2025. Whether E
  specifically outperforms the baseline on the forward window waits on the complete 2025–2027 labels.

## Threats to the design

- **Positive counts are small** (276 verified, 62 forward-partial at ≥1). Confidence intervals are
  wide; the argument rests on cross-split and cross-window consistency, not single-split significance.
- **Residual spatial leakage.** The region-holdout split reduces neighbor leakage but does not
  eliminate it where a 400 m neighborhood straddles two blocks. Block sizes should be verified to be
  much larger than 400 m.
- **Cutoff circularity.** Eligibility (<5 crashes) and the features share the same window, so a
  4-crash site is both barely eligible and high-signal, creating edge effects near the threshold.
- **Researcher degrees of freedom.** Five feature sets × two splits × two thresholds × several
  radii were tried. The reported result is one cell and should be pre-registered before the forward
  window closes.

## What falsifies it

On the complete 2025–2027 window, the shortlist's recall drops toward random, or E's margin over
the baseline disappears.

## What strengthens it

Add exposure/ADT and show the edge survives after controlling for volume. Add label-years to raise
the positive count. Pre-register the forward test.
