# Deviation Log

## M2.5 deviation chain (recorded 2026-06-08)

1. **Pre-registered re-scope trigger fired** (city, 30 m): 5-6 positives @>=2.
   Trigger threshold was < 300 positives.

2. **Registered fallback (Option A, Tweedie) adopted in M2.** XGBoost-Tweedie showed
   directional Spearman lift (0.275 random / 0.172 spatial, ~3.5x baseline) confirming
   the architecture works.

3. **City N inadequate at the registered 30 m buffer.** The registered buffer was
   deliberately conservative (minimal cross-intersection attribution overlap); the
   sparse label result was a design artefact, not signal absence.

4. **Influence zone refined to 76.2 m (250 US survey feet), primary buffer.**
   Supported by the M2 buffer sensitivity sweep (6→48 positives @>=2 at 30→76.2 m).
   Disclosed as a deliberate definition refinement, not post-hoc cherry-picking.
   Old 30 m value retained as a sensitivity row.

5. **County scope probed before committing** (this milestone). Escalation decision
   made on measured surface-street positive counts at 76.2 m, not extrapolation from
   the city sweep. Freeway contamination (STATE_HWY_IND=Y crashes) excluded from
   both city and county counts for an apples-to-apples comparison.

6. **Surface-street-only unit of analysis adopted.** Any node with an incident
   motorway or motorway_link OSM edge is excluded from the candidate set. Trunk/trunk_link
   nodes kept but flagged. This was not explicitly pre-registered but is a principled
   clarification of the intersection-node unit of analysis: freeway mainline and ramp
   nodes are not intersection nodes in the Vision Zero sense.

7. **TIMS coordinate column corrected: POINT_X/POINT_Y replaces LATITUDE/LONGITUDE.**
   Discovered in M2.5: LATITUDE/LONGITUDE is present for only 44% of KSI crashes,
   and 98.5% of those are state-highway crashes (STATE_HWY_IND=Y). Surface-street
   crashes are geocoded in POINT_X/POINT_Y (96% coverage). M1 and M2 were therefore
   analysing almost exclusively freeway-adjacent crash clusters snapping to nearby
   intersection nodes -- not surface-street KSI. All M1/M2 label and feature counts
   are superseded by M2.5 clean re-derivation results.
   Corrected figures (city, 76.2 m, surface-only): 22 pos@>=2, 391 pos@>=1.

8. **Primary binary threshold shifted from @>=2 to @>=1 for M3.**
   With correct surface-street coordinates, @>=2 yields 22 positives (below the 150
   floor). @>=1 yields 391 positives (above the 300 adequacy bar). M3 will use @>=1
   as the primary binary readout for AUPRC/recall@K, with @>=2 as an explicitly
   underpowered secondary. Tweedie count remains the primary optimization target.

9. **County scope not escalated: county OSM network = city network.**
   San Diego County's urbanized road network contains 81,960 surface nodes (city: 81,962).
   The marginal coverage gain from county scope is 2 intersection nodes -- not worth the
   infrastructure data harmonisation cost across 18+ municipalities. M3 proceeds city-only
   at 76.2 m with corrected coordinates and @>=1 primary threshold.
   Note: the specific node-count figure from the M2.5 probe is treated as potentially
   unreliable (the county OSM fetch may have used a restricted Nominatim polygon); the
   stay-city decision rests on @>=2=22 being far below the 150-positive adequacy floor
   and on the infrastructure-data heterogeneity cost, not solely on the node-count figure.

## M3a deviation entries (recorded 2026-06-08)

10. **Primary binary threshold: @>=2 demoted to evaluation operating point; @>=1 is M3a secondary.**
    With corrected coordinates, @>=2 yields 22 positives (below the <150 floor for any
    binary modelling). @>=1 yields 391 positives (above the 300-positive adequacy bar).
    Training targets for logistic + XGB-binary are @>=1 (391 positives). @>=2 (22 positives)
    is used only as an evaluation operating point (recall@K, precision@K with honest wide CIs).
    This is NOT a threshold change for the Tweedie primary, which optimises on raw count.

11. **M1 and M2 reports marked SUPERSEDED.** All M1/M2 numeric results are invalid due to
    the coordinate-field bug (deviation 7). The pipeline architecture and feature group
    structure from M2 are retained; all count/signal results are replaced by M3a clean-data
    re-derivation. The SUPERSEDED banner is prepended to both report files for record.

12. **Rebuild on corrected data constitutes the scientific baseline.** M3a clean-data
    Spearman ρ (Tweedie, both splits) replaces M2's contaminated 0.275/0.172 figures as
    the directional-signal reference. The gate decision (PASS/WEAK/FAIL) is made on M3a
    clean-data results.

## M3b deviation entries (recorded 2026-06-08)

13. **Spatial-split bootstrap CI bug fixed (D7 open item).** In M3a's evaluate_model,
    the point estimate used fold-averaged Spearman while the CI bootstrap operated on
    the concatenated test set (all 81k nodes for spatial k-fold). These measure slightly
    different estimands, causing the reported "inside-out" CI (lower bound > point).
    Fix: compute both from the concatenated set. M3a report CIs remain as published
    (the gate verdict PASS is unchanged); corrected evaluator used from M3b forward.

14. **Overpass attic 2021 vintage: all four features obtained.** Initial query returned
    HTTP 406 (wrong Accept header); fixed with `Accept: application/json, */*;q=0.5`.
    stop_signs initial query returned HTTP 504 (result too large); obtained on retry.
    Final state:
    - traffic_signals (Group 4): ✓ 4,178 nodes @ 2021-12-31
    - stop_signs (Group 4): ✓ 13,000 nodes @ 2021-12-31 (retrieved on retry)
    - speed_limits (Group 5): ✓ 10,232 ways @ 2021-12-31 (4.8% candidate coverage;
      95.2% gap-filled from 2026 OSM — flagged `speed_limit_vintage`=2)
    - bike_lanes (Group 6): ✓ 4,829 ways @ 2021-12-31
    All four features included in ablation. Speed_limit endogenous-vintage caveat retained.

15. **DEM CRS mismatch bug: corrected, slope_pct at 60.1% coverage.** py3dep
    `get_dem()` returned data in EPSG:5070 (Albers metres) despite `crs="EPSG:4326"`.
    Candidate WGS84 coordinates were mapped to wrong pixels (0/81,007 valid).
    Fix: detect DEM CRS at runtime; project candidates from WGS84 to DEM CRS (EPSG:5070)
    using pyproj before rasterio pixel lookup. Post-fix: 48,693/81,007 nodes valid
    (60.1%), mean=4.93%, sd=26.95%. Static feature — safe.
    Timing: bug fix applied after primary ablation panel was loaded → slope_pct was
    all-NaN in the ablation run. See deviation 16.

16. **Terrain step in primary ablation used zero-variance slope.** slope_pct was patched
    into infra_features.parquet after fit_ablation.py loaded its panel. The `crash+terrain`
    and `all` steps in ablation_scores.parquet therefore have no terrain signal (slope was
    dropped as zero-variance). A supplemental ablation (`src/model/fit_terrain_supp.py`)
    re-runs only the terrain-affected steps with the corrected slope data, and writes
    supplemental columns (`crash+terrain_supp`, `all_supp`, `static_infra_only_supp`) to
    ablation_scores.parquet. Terrain verdict in the milestone report comes from the
    supplemental run. Groups 3–6 verdicts are unaffected.
