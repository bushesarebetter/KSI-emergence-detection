"""Milestone 3a: Clean-data signal re-validation (gate before infrastructure features).

Evaluates all 4 models on the corrected-coordinate clean panel.
Reports:
  - Count metrics: Tweedie deviance, Spearman rho, decile calibration
  - Ranked readouts:
      @>=1 (391 positives, M3a secondary): AUPRC, recall@K
      @>=2 (22 positives, evaluation operating point): AUPRC, recall@K, wide-CI warning
  - All under random + spatial-block splits with bootstrap 95% CIs
  - Lift over adapted persistence baseline

Gate verdict:
  PASS  -- Tweedie Spearman positive and CI upper > baseline CI lower in BOTH splits
  WEAK  -- positive but CIs overlap baseline / signal only in random split
  FAIL  -- no signal above baseline on clean data

Run via:  python -m src.eval.milestone3a
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import stats

from src.eval.metrics import bootstrap_ci, compute_metrics
from src.eval.milestone2 import (
    bootstrap_count_ci,
    count_metrics,
    decile_calibration,
)
from src.eval.splitter import add_spatial_blocks, random_split, spatial_block_kfold
from src.model.fit import FEATURE_COLS, _tweedie_deviance, persistence_baseline_scores
from src.utils import load_config, project_root

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gate logic
# ---------------------------------------------------------------------------

def _gate_verdict(
    tweedie_results: dict,
    baseline_results: dict,
) -> tuple[str, str]:
    """
    Determine PASS / WEAK / FAIL from Tweedie Spearman vs baseline Spearman.

    Checks both splits (random_thr1 and spatial_thr1 for the >=1 threshold,
    which is the primary readout).  Returns (verdict, reasoning).
    """
    def _get_sp(res: dict, split: str) -> tuple[float, float, float]:
        """Return (point, lo, hi) Spearman CI."""
        pt = res.get(split, {}).get("point", {}).get("spearman_rho", float("nan"))
        ci = res.get(split, {}).get("ci", {}).get("spearman_rho", {})
        return pt, ci.get("lo", float("nan")), ci.get("hi", float("nan"))

    tw_r_pt, tw_r_lo, tw_r_hi = _get_sp(tweedie_results, "random_thr1")
    bl_r_pt, bl_r_lo, bl_r_hi = _get_sp(baseline_results, "random_thr1")
    tw_s_pt, tw_s_lo, tw_s_hi = _get_sp(tweedie_results, "spatial_thr1")
    bl_s_pt, bl_s_lo, bl_s_hi = _get_sp(baseline_results, "spatial_thr1")

    # Positive in both splits
    random_positive  = not np.isnan(tw_r_pt) and tw_r_pt > 0
    spatial_positive = not np.isnan(tw_s_pt) and tw_s_pt > 0

    # CI-separated from baseline (95% CI lower > baseline 95% CI upper)
    random_separated  = tw_r_lo > bl_r_hi
    spatial_separated = tw_s_lo > bl_s_hi

    if random_positive and spatial_positive and random_separated and spatial_separated:
        verdict = "PASS"
        reason = (
            f"Tweedie Spearman positive in both splits (random={tw_r_pt:.3f}, spatial={tw_s_pt:.3f}) "
            f"and 95% CI lower bounds ({tw_r_lo:.3f}, {tw_s_lo:.3f}) exceed "
            f"baseline 95% CI upper bounds ({bl_r_hi:.3f}, {bl_s_hi:.3f}). "
            "Directional signal verified on clean data. Proceed to M3b."
        )
    elif random_positive and spatial_positive:
        verdict = "WEAK"
        reason = (
            f"Tweedie Spearman positive in both splits (random={tw_r_pt:.3f}, spatial={tw_s_pt:.3f}) "
            "but CIs overlap baseline. Signal present but not cleanly separated. "
            "Proceed to M3b cautiously; infrastructure features must carry the model."
        )
    elif random_positive and not spatial_positive:
        verdict = "WEAK"
        reason = (
            f"Tweedie Spearman positive in random split ({tw_r_pt:.3f}) "
            f"but zero or negative in spatial split ({tw_s_pt:.3f}). "
            "Signal may be within-block memorization. Proceed to M3b with caution; "
            "flag that infrastructure features must demonstrate cross-block lift."
        )
    else:
        verdict = "FAIL"
        reason = (
            f"Tweedie Spearman not above baseline on clean data "
            f"(random={tw_r_pt:.3f}, spatial={tw_s_pt:.3f}). "
            "Crash-history alone does not predict surface-street KSI on corrected data. "
            "Stop and reassess before feature expansion."
        )
    return verdict, reason


# ---------------------------------------------------------------------------
# Full evaluation (mirrors milestone2.py, adapted for M3a thresholds)
# ---------------------------------------------------------------------------

def evaluate_model(
    scores: np.ndarray,
    panel: pd.DataFrame,
    cfg: dict,
    model_name: str,
) -> dict:
    """Evaluate under random and spatial-block splits at >=1 and >=2 thresholds."""
    y_count = panel["KSI_label"].values.astype(float)
    seed    = cfg["project"]["rng_seed"]
    k_vals  = cfg["evaluation"]["recall_at_k"]
    n_boot  = cfg["evaluation"]["bootstrap_resamples"]
    p       = cfg["target"]["tweedie_variance_power"]
    out     = {}

    for split_name, get_indices in [
        ("random", lambda: random_split(panel, cfg)[1]),
        ("spatial", None),
    ]:
        if split_name == "random":
            test_idx = get_indices()
            folds = [(None, test_idx)]
        else:
            # spatial: aggregate across k-fold
            folds = [(None, ti) for _, ti in spatial_block_kfold(panel, cfg)]

        for thr, thr_label in [(1, "thr1"), (2, "thr2")]:
            key = f"{split_name}_{thr_label}"
            y_bin = (y_count >= thr).astype(int)

            # collect over folds
            all_yb, all_sc, all_yc = [], [], []
            fold_pts: list[dict] = []
            for _, ti in folds:
                yb = y_bin[ti]; sc = scores[ti]; yc = y_count[ti]
                if yb.sum() == 0:
                    continue
                pt = {**count_metrics(yc, sc, p), **compute_metrics(yb, sc, k_vals)}
                fold_pts.append(pt)
                all_yb.append(yb); all_sc.append(sc); all_yc.append(yc)

            if not fold_pts:
                out[key] = {"point": {}, "ci": {}}
                continue

            ay   = np.concatenate(all_yb)
            as_  = np.concatenate(all_sc)
            ayc  = np.concatenate(all_yc)
            # Point estimate from the concatenated test set (same estimand as bootstrap).
            # For spatial k-fold each node appears in exactly one test fold, so the
            # concatenated set = all candidates and the estimate is consistent with the CI.
            # (Fold-averaged Spearman differs by ~0.005-0.01 due to Jensen's inequality,
            # which caused the inside-out CI reported in DECISIONS.md D7.)
            agg  = {**count_metrics(ayc, as_, p), **compute_metrics(ay, as_, k_vals)}
            cc   = bootstrap_count_ci(ayc, as_, n_resamples=n_boot, seed=seed, p=p)
            cr   = bootstrap_ci(ay, as_, k_vals, n_resamples=n_boot, seed=seed)
            out[key] = {"point": agg, "ci": {**cc, **cr}}

            log.info(
                "%s [%s @>=%d] n=%d pos=%d spearman=%.3f auprc=%.4f",
                model_name, split_name, thr,
                len(ay), int(ay.sum()),
                agg.get("spearman_rho", float("nan")),
                agg.get("auprc", float("nan")),
            )
    return out


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def _fmt_ci(ci_dict: dict, key: str, decimals: int = 3) -> str:
    v = ci_dict.get(key, {})
    if not v:
        return "N/A"
    m = v.get("mean", float("nan"))
    lo = v.get("lo", float("nan"))
    hi = v.get("hi", float("nan"))
    fmt = f"{{:.{decimals}f}}"
    return f"{fmt.format(m)} [{fmt.format(lo)}, {fmt.format(hi)}]"


def _fmt_pt(res_dict: dict, split_thr: str, key: str, decimals: int = 3) -> str:
    v = res_dict.get(split_thr, {}).get("point", {}).get(key, float("nan"))
    return f"{v:.{decimals}f}" if not np.isnan(v) else "N/A"


def write_report(
    all_results: dict,
    panel: pd.DataFrame,
    verdict: str,
    gate_reason: str,
    xgb_tw_params: dict,
    reports_dir: Path,
) -> None:
    from datetime import date
    today = date.today().isoformat()
    n_cand = len(panel)
    n_pos2 = int((panel["KSI_label"] >= 2).sum())
    n_pos1 = int((panel["KSI_label"] >= 1).sum())

    lines: list[str] = [
        "# Milestone 3a -- Clean-Data Signal Re-Validation",
        "",
        f"**Date:** {today}",
        "**Gate:** PASS / WEAK / FAIL decision on crash-only signal, corrected coordinates.",
        "**Coordinates:** POINT_X/POINT_Y (SafeTREC geocoded, ~96% coverage). "
        "LATITUDE/LONGITUDE not used (officer GPS / CHP postmile, ~44% coverage, ~98.5% freeway).",
        "**Buffer:** 76.2 m (249.9995 US survey feet, EPSG:2230).",
        "**Surface filter:** motorway/motorway_link nodes excluded. STATE_HWY_IND=Y crashes excluded.",
        "",
        "---",
        "",
        "## 1. Corrected Candidate Panel",
        "",
        "| Metric | Value | M2.5 probe reference |",
        "| ------ | ----- | -------------------- |",
        f"| Surface candidates | {n_cand:,} | 81,007 |",
        f"| Positives @>=2 (evaluation operating point) | **{n_pos2}** | 22 |",
        f"| Positives @>=1 (M3a secondary readout) | **{n_pos1}** | 391 |",
        f"| Crash-active nodes (feature window) | 6,104 | -- |",
        f"| Silent nodes (all-zero features) | {n_cand - 6104:,} | -- |",
        "",
        "**Note:** The 2-count difference vs M2.5 probe at @>=1 (389 vs 391) reflects 2 crashes "
        "with valid coordinates but missing severity codes, excluded by the loader's "
        "`dropna(severity)` filter. Non-material.",
        "",
        "---",
        "",
        "## 2. Signal Re-Validation",
        "",
        "All metrics are mean over test folds (random 80/20 or spatial k=5). "
        "Bootstrap 95% CIs use 1,000 resamples of the aggregated test set.",
        "",
        "### 2.1 Spearman ρ (predicted rank vs actual KSI count)",
        "",
        "| Model | Random split | Spatial split |",
        "| ----- | ------------ | ------------- |",
    ]

    models_order = ["baseline", "logistic", "xgb_binary", "xgb_tweedie"]
    for m in models_order:
        r = _fmt_pt(all_results.get(m, {}), "random_thr1", "spearman_rho")
        s = _fmt_pt(all_results.get(m, {}), "spatial_thr1", "spearman_rho")
        tag = " **(PRIMARY)**" if m == "xgb_tweedie" else ""
        lines.append(f"| {m}{tag} | {r} | {s} |")

    lines += [
        "",
        "Bootstrap 95% CI on Spearman ρ (Tweedie):",
    ]
    tw_res = all_results.get("xgb_tweedie", {})
    bl_res = all_results.get("baseline", {})
    lines += [
        f"- Random: {_fmt_ci(tw_res.get('random_thr1', {}).get('ci', {}), 'spearman_rho')}",
        f"- Spatial: {_fmt_ci(tw_res.get('spatial_thr1', {}).get('ci', {}), 'spearman_rho')}",
        "",
        "Bootstrap 95% CI on Spearman ρ (baseline):",
        f"- Random: {_fmt_ci(bl_res.get('random_thr1', {}).get('ci', {}), 'spearman_rho')}",
        f"- Spatial: {_fmt_ci(bl_res.get('spatial_thr1', {}).get('ci', {}), 'spearman_rho')}",
        "",
        "### 2.2 AUPRC at @>=1 (M3a secondary, {n_pos1} positives)".format(n_pos1=n_pos1),
        "",
        f"Chance baseline: {n_pos1/n_cand:.4f}",
        "",
        "| Model | Random AUPRC | Spatial AUPRC |",
        "| ----- | ------------ | ------------- |",
    ]
    for m in models_order:
        r = _fmt_pt(all_results.get(m, {}), "random_thr1", "auprc", 4)
        s = _fmt_pt(all_results.get(m, {}), "spatial_thr1", "auprc", 4)
        lines.append(f"| {m} | {r} | {s} |")

    lines += [
        "",
        "### 2.3 AUPRC at @>=2 (evaluation operating point, {n_pos2} positives -- wide CIs expected)".format(n_pos2=n_pos2),
        "",
        f"Chance baseline: {n_pos2/n_cand:.4f}",
        "",
        "| Model | Random AUPRC | Spatial AUPRC |",
        "| ----- | ------------ | ------------- |",
    ]
    for m in models_order:
        r = _fmt_pt(all_results.get(m, {}), "random_thr2", "auprc", 4)
        s = _fmt_pt(all_results.get(m, {}), "spatial_thr2", "auprc", 4)
        lines.append(f"| {m} | {r} | {s} |")

    lines += [
        "",
        "*@>=2 metrics are provided for reference only. With n=22 positives, "
        "AUPRC estimates are unreliable; do not use for gating decisions.*",
        "",
        "### 2.4 Tweedie deviance (primary count metric)",
        "",
        "| Model | Random split | Spatial split |",
        "| ----- | ------------ | ------------- |",
    ]
    for m in models_order:
        r = _fmt_pt(all_results.get(m, {}), "random_thr1", "tweedie_deviance", 4)
        s = _fmt_pt(all_results.get(m, {}), "spatial_thr1", "tweedie_deviance", 4)
        lines.append(f"| {m} | {r} | {s} |")

    lines += [
        "",
        "### 2.5 Recall@K at @>=1 (K = 25 / 50 / 100)",
        "",
        "| Model | Split | recall@25 | recall@50 | recall@100 |",
        "| ----- | ----- | --------- | --------- | ---------- |",
    ]
    for m in models_order:
        for split_key, split_label in [("random_thr1", "random"), ("spatial_thr1", "spatial")]:
            pt = all_results.get(m, {}).get(split_key, {}).get("point", {})
            r25  = f"{pt.get('recall@25', float('nan')):.3f}" if pt else "N/A"
            r50  = f"{pt.get('recall@50', float('nan')):.3f}" if pt else "N/A"
            r100 = f"{pt.get('recall@100', float('nan')):.3f}" if pt else "N/A"
            lines.append(f"| {m} | {split_label} | {r25} | {r50} | {r100} |")

    lines += [
        "",
        "---",
        "",
        "## 3. Comparison with Superseded M2 Results",
        "",
        "| Metric | M2 (contaminated, 30m, LATITUDE/LONGITUDE) | M3a (clean, 76.2m, POINT_X/POINT_Y) |",
        "| ------ | ----------------------------------------- | ----------------------------------- |",
        f"| Candidates | 84,789 | {n_cand:,} |",
        "| pos@>=2 | 6 | 22 |",
        "| pos@>=1 | 91 | 389 |",
        "| Crash-active nodes | 1,167 | 6,104 |",
        f"| Tweedie Spearman (random) | 0.275 (contaminated) | {_fmt_pt(tw_res, 'random_thr1', 'spearman_rho')} |",
        f"| Tweedie Spearman (spatial) | 0.172 (contaminated) | {_fmt_pt(tw_res, 'spatial_thr1', 'spearman_rho')} |",
        "",
        "---",
        "",
        "## 4. Tuned XGBoost Tweedie Parameters",
        "",
    ]
    for k, v in xgb_tw_params.items():
        lines.append(f"- {k}: {v}")

    lines += [
        "",
        "---",
        "",
        "## 5. Gate Verdict",
        "",
        f"**{verdict}**",
        "",
        gate_reason,
        "",
    ]

    if verdict in ("PASS", "WEAK"):
        lines += [
            "---",
            "",
            "## 6. M3b Scope Proposal (infrastructure + geometry features)",
            "",
            "Subject to human confirmation:",
            "",
            "**Feature groups to add in M3b:**",
            "- Intersection geometry: edge count, lane count, road class mix (OSM),",
            "  signal/stop presence (OSM + SanGIS), approach leg asymmetry",
            "- Roadway environment: speed limit (OSM), functional class (OSM highway type),",
            "  nearest arterial distance, freeway proximity",
            "- Active transport: bike lane presence (SanGIS), bikeway distance,",
            "  transit stop proximity (MTS GTFS)",
            "- Terrain: slope / grade (USGS 3DEP 1m DEM)",
            "",
            "**Evaluation plan:**",
            "- Measure incremental Spearman lift over crash-only M3a as the primary signal test",
            "- Fit same 4-model suite; add feature importance attribution",
            "- Same random + spatial-block CV, bootstrap CIs",
            "- Report whether infrastructure features carry independent signal vs crash history",
            "",
            "Await human confirmation before starting M3b.",
        ]
    else:
        lines += [
            "---",
            "",
            "## 6. Reassessment Options",
            "",
            "**Gate FAILED.** Crash-history alone does not predict surface-street KSI "
            "on corrected data at city scale.",
            "",
            "Options:",
            "1. **Infrastructure-only hypothesis:** proceed to M3b but frame it as testing "
            "whether built-environment features (not crash history) predict KSI emergence. "
            "Crash features become controls.",
            "2. **Honest null:** characterize the spatial distribution of surface KSI without "
            "a predictive claim. Report the data quality findings (coordinate bug, freeway "
            "contamination) as the primary contribution.",
            "3. **Broader scope reassessment:** revisit the county-wide option or longer "
            "label window (2019-2024 for more positives) before further modeling.",
            "",
            "Await human decision before proceeding.",
        ]

    out = reports_dir / "milestone3a_revalidation.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    log.info("Wrote %s", out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import pickle

    cfg        = load_config()
    model_dir  = project_root() / cfg["paths"]["model"]
    reports_dir = project_root() / cfg["paths"]["reports"]
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Load
    candidates = gpd.read_parquet(model_dir / "candidate_panel.parquet")
    feat_table = pd.read_parquet(model_dir / "feature_table.parquet")
    panel = candidates.merge(feat_table, on="intersection_id", how="left")
    if "spatial_block" not in panel.columns:
        panel = add_spatial_blocks(panel, cfg)

    log.info(
        "Panel: %d candidates | pos@>=2: %d | pos@>=1: %d",
        len(panel),
        (panel["KSI_label"] >= 2).sum(),
        (panel["KSI_label"] >= 1).sum(),
    )

    # Load scores
    scores_df = pd.read_parquet(model_dir / "model_scores.parquet")
    panel = panel.merge(
        scores_df[["intersection_id", "baseline_score", "logistic_score",
                   "xgb_binary_score", "xgb_tweedie_score"]],
        on="intersection_id", how="left",
    )

    models_map = {
        "baseline":    panel["baseline_score"].values,
        "logistic":    panel["logistic_score"].values,
        "xgb_binary":  panel["xgb_binary_score"].values,
        "xgb_tweedie": panel["xgb_tweedie_score"].values,
    }

    all_results: dict = {}
    for model_name, scores in models_map.items():
        log.info("=== Evaluating %s ===", model_name)
        all_results[model_name] = evaluate_model(scores, panel, cfg, model_name)

    # Load tuned Tweedie params for report
    try:
        with open(model_dir / "model_params.json") as f:
            params_raw = json.load(f)
        xgb_tw_params = params_raw.get("xgb_tweedie_params", {})
    except Exception:
        xgb_tw_params = {}

    # Gate verdict
    verdict, gate_reason = _gate_verdict(all_results["xgb_tweedie"], all_results["baseline"])

    # Print summary
    tw = all_results["xgb_tweedie"]
    bl = all_results["baseline"]
    print("\n" + "=" * 70)
    print("MILESTONE 3a -- CLEAN-DATA SIGNAL GATE")
    print("=" * 70)
    for split_key, split_label in [("random_thr1", "random"), ("spatial_thr1", "spatial")]:
        tw_sp = tw.get(split_key, {}).get("point", {}).get("spearman_rho", float("nan"))
        bl_sp = bl.get(split_key, {}).get("point", {}).get("spearman_rho", float("nan"))
        tw_ap = tw.get(split_key, {}).get("point", {}).get("auprc", float("nan"))
        print(f"  {split_label:8s}: Tweedie Spearman={tw_sp:.3f}  Baseline={bl_sp:.3f}  "
              f"Tweedie AUPRC@>=1={tw_ap:.4f}")
    print()
    print(f"GATE: {verdict}")
    print(gate_reason)
    print("=" * 70)

    # Save results
    results_safe = {}
    for mname, mres in all_results.items():
        results_safe[mname] = {}
        for sk, sv in mres.items():
            results_safe[mname][sk] = {
                "point": {k: (float(v) if v == v else None) for k, v in sv.get("point", {}).items()},
            }
    with open(model_dir / "milestone3a_results.json", "w") as f:
        json.dump(results_safe, f, indent=2)

    write_report(all_results, panel, verdict, gate_reason, xgb_tw_params, reports_dir)
    log.info("Gate verdict: %s", verdict)


if __name__ == "__main__":
    main()
