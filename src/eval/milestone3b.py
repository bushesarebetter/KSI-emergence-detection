"""Milestone 3b: Infrastructure feature ablation evaluation.

Evaluates incremental Tweedie Spearman lift over crash-only baseline for each
feature group, in both random and spatial splits with bootstrap 95% CIs.

Ablation order (cumulative):
  crash_only → +geometry → +control → +roadway → +active_transport → +terrain → all
  Plus: static_infra_only (endogenous-excluded sensitivity check)

Gate per group: incremental lift CI-separated from crash-only in BOTH splits.

Run via:  python -m src.eval.milestone3b
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
from src.eval.milestone2 import bootstrap_count_ci, count_metrics
from src.eval.splitter import add_spatial_blocks, random_split, spatial_block_kfold
from src.utils import load_config, project_root

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def _eval_scores(
    scores: np.ndarray,
    y_count: np.ndarray,
    panel: pd.DataFrame,
    cfg: dict,
    label: str,
) -> dict:
    """Evaluate one score vector under both splits at >=1 threshold (primary)."""
    seed   = cfg["project"]["rng_seed"]
    k_vals = cfg["evaluation"]["recall_at_k"]
    n_boot = cfg["evaluation"]["bootstrap_resamples"]
    p      = cfg["target"]["tweedie_variance_power"]
    out    = {}

    for split_name in ("random", "spatial"):
        y_bin = (y_count >= 1).astype(int)

        if split_name == "random":
            test_idx = random_split(panel, cfg)[1]
            folds = [(None, test_idx)]
        else:
            folds = [(None, ti) for _, ti in spatial_block_kfold(panel, cfg)]

        all_yb, all_sc, all_yc = [], [], []
        for _, ti in folds:
            yb = y_bin[ti]; sc = scores[ti]; yc = y_count[ti]
            if yb.sum() == 0:
                continue
            all_yb.append(yb); all_sc.append(sc); all_yc.append(yc)

        if not all_yb:
            out[split_name] = {"point": {}, "ci": {}}
            continue

        ay  = np.concatenate(all_yb)
        as_ = np.concatenate(all_sc)
        ayc = np.concatenate(all_yc)

        pt = {**count_metrics(ayc, as_, p), **compute_metrics(ay, as_, k_vals)}
        cc = bootstrap_count_ci(ayc, as_, n_resamples=n_boot, seed=seed, p=p)
        cr = bootstrap_ci(ay, as_, k_vals, n_resamples=n_boot, seed=seed)

        log.info(
            "%s [%s] spearman=%.3f auprc=%.4f",
            label, split_name,
            pt.get("spearman_rho", float("nan")),
            pt.get("auprc", float("nan")),
        )
        out[split_name] = {"point": pt, "ci": {**cc, **cr}}

    return out


def _ci_separated(model_res: dict, base_res: dict, split: str) -> bool:
    """True if model 95% CI lower > baseline 95% CI upper in this split."""
    m_lo = model_res.get(split, {}).get("ci", {}).get("spearman_rho", {}).get("lo", float("nan"))
    b_hi = base_res.get(split, {}).get("ci", {}).get("spearman_rho", {}).get("hi", float("nan"))
    return float(m_lo) > float(b_hi)


def _spearman_pt(res: dict, split: str) -> float:
    return res.get(split, {}).get("point", {}).get("spearman_rho", float("nan"))


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_report(
    ablation_results: dict,     # {step_name: {model_type: {split: {point,ci}}}}
    baseline_results: dict,     # {"baseline": {split: {point,ci}}}
    panel: pd.DataFrame,
    available_steps: list[str],
    infra_coverage: dict,       # {feature_name: coverage_pct}
    xgb_params: dict,
    reports_dir: Path,
) -> None:
    from datetime import date
    today = date.today().isoformat()
    n_cand = len(panel)
    n_pos2 = int((panel["KSI_label"] >= 2).sum())
    n_pos1 = int((panel["KSI_label"] >= 1).sum())

    lines = [
        "# Milestone 3b — Infrastructure + Geometry Feature Ablation",
        "",
        f"**Date:** {today}",
        "**Question:** Do built-environment features carry independent predictive signal",
        "above crash history on the corrected surface-street panel?",
        "",
        "**Bar to beat:** crash-only Tweedie Spearman (M3a), CI-separated in BOTH splits.",
        "**Temporal wall:** endogenous features (signals, stop control, speed limit,",
        "bike lanes) must use ≤2021 OSM vintage (Overpass attic) or be excluded.",
        "",
        "---",
        "",
        "## 1. Panel",
        "",
        f"| Metric | Value |",
        f"| ------ | ----- |",
        f"| Surface candidates | {n_cand:,} |",
        f"| Positives @≥2 (eval operating point) | {n_pos2} |",
        f"| Positives @≥1 (secondary readout) | {n_pos1} |",
        "",
        "---",
        "",
        "## 2. Infrastructure Feature Coverage",
        "",
        "| Feature | Group | Source | Vintage | Class | Coverage |",
        "| ------- | ----- | ------ | ------- | ----- | -------- |",
    ]

    coverage_meta = [
        ("edge_count",         3, "OSM current", "2026",        "static"),
        ("lane_count",         3, "OSM current", "2026",        "static"),
        ("signal_present",     4, "OSM history", "2021-12-31",  "endogenous"),
        ("stop_control",       4, "OSM history", "2021-12-31",  "endogenous"),
        ("functional_class",   5, "OSM current", "2026",        "static"),
        ("freeway_proximity",  5, "OSM current", "2026",        "static"),
        ("speed_limit",        5, "OSM history", "2021-12-31",  "endogenous"),
        ("bike_lane_present",  6, "OSM history", "2021-12-31",  "endogenous"),
        ("transit_proximity",  6, "MTS GTFS",    "~current",    "static"),
        ("slope_pct",          7, "USGS 3DEP",   "static",      "static"),
    ]
    for feat, grp, src, vintage, cls in coverage_meta:
        cov = infra_coverage.get(feat, "N/A")
        if isinstance(cov, float):
            cov = f"{cov:.1f}%"
        lines.append(f"| {feat} | {grp} | {src} | {vintage} | {cls} | {cov} |")

    lines += [
        "",
        "*Endogenous features must use ≤2021 vintage to avoid leakage (FEATURE_CATALOG.md §TWO temporal walls).*",
        "",
        "---",
        "",
        "## 3. Incremental Ablation — Tweedie Spearman ρ",
        "",
        "Primary metric: Tweedie Spearman ρ (predicted count rank vs actual KSI count).",
        "Each row adds its group to all prior groups (cumulative).",
        "Bootstrap 95% CIs from 1,000 resamples of the concatenated test set.",
        "",
        "| Step | Random ρ [95% CI] | Spatial ρ [95% CI] | Lift (random) | Lift (spatial) | CI-sep both? |",
        "| ---- | ------------------ | ------------------- | ------------- | -------------- | ------------ |",
    ]

    crash_only_res = ablation_results.get("crash_only", {}).get("xgb_tweedie", {})
    crash_r = _spearman_pt(crash_only_res, "random")
    crash_s = _spearman_pt(crash_only_res, "spatial")

    def _fmt_rho(res: dict, split: str) -> str:
        pt = _spearman_pt(res, split)
        ci = res.get(split, {}).get("ci", {}).get("spearman_rho", {})
        lo = ci.get("lo", float("nan"))
        hi = ci.get("hi", float("nan"))
        if np.isnan(pt):
            return "N/A"
        return f"{pt:.3f} [{lo:.3f}, {hi:.3f}]"

    step_labels = {
        "crash_only":             "crash-only (M3a baseline)",
        "crash+geometry":         "+geometry (Group 3)",
        "crash+control":          "+control (Group 4, endogenous)",
        "crash+roadway":          "+roadway (Group 5)",
        "crash+active":           "+active transport (Group 6)",
        "crash+terrain":          "+terrain (Group 7)",
        "crash+terrain_supp":     "+terrain (Group 7, supplemental)",
        "all":                    "all features",
        "all_supp":               "all features (supplemental terrain)",
        "static_infra_only":      "static infra only (endogenous-excluded)",
        "static_infra_only_supp": "static infra only, supp (endogenous-excluded)",
    }

    for step_name in available_steps:
        tw_res = ablation_results.get(step_name, {}).get("xgb_tweedie", {})
        r_rho = _spearman_pt(tw_res, "random")
        s_rho = _spearman_pt(tw_res, "spatial")
        lift_r = f"+{r_rho - crash_r:.3f}" if not np.isnan(r_rho) and step_name != "crash_only" else "—"
        lift_s = f"+{s_rho - crash_s:.3f}" if not np.isnan(s_rho) and step_name != "crash_only" else "—"
        sep_r = _ci_separated(tw_res, crash_only_res, "random")
        sep_s = _ci_separated(tw_res, crash_only_res, "spatial")
        sep   = "✓" if (sep_r and sep_s) else ("random only" if sep_r else "no")
        label = step_labels.get(step_name, step_name)
        lines.append(
            f"| {label} | {_fmt_rho(tw_res, 'random')} | {_fmt_rho(tw_res, 'spatial')} "
            f"| {lift_r} | {lift_s} | {sep} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 4. Per-Group Verdict",
        "",
        "| Group | Features | Random lift | Spatial lift | CI-sep | Verdict |",
        "| ----- | -------- | ----------- | ------------ | ------ | ------- |",
    ]

    # Use supplemental terrain step if primary terrain step had zero-variance slope
    terrain_next = (
        "crash+terrain_supp"
        if "crash+terrain_supp" in ablation_results and "crash+terrain" not in ablation_results
        else "crash+terrain"
    )
    group_steps = [
        ("geometry",        "crash_only",    "crash+geometry",  "Group 3: Intersection geometry"),
        ("control",         "crash+geometry","crash+control",   "Group 4: Signal/stop control"),
        ("roadway",         "crash+control", "crash+roadway",   "Group 5: Roadway environment"),
        ("active_transport","crash+roadway", "crash+active",    "Group 6: Active transport"),
        ("terrain",         "crash+active",  terrain_next,      "Group 7: Terrain"),
    ]

    for grp_key, base_step, next_step, grp_label in group_steps:
        base_res = ablation_results.get(base_step, {}).get("xgb_tweedie", {})
        next_res = ablation_results.get(next_step, {}).get("xgb_tweedie", {})
        base_r = _spearman_pt(base_res, "random")
        base_s = _spearman_pt(base_res, "spatial")
        next_r = _spearman_pt(next_res, "random")
        next_s = _spearman_pt(next_res, "spatial")
        if np.isnan(next_r) or np.isnan(next_s):
            lines.append(f"| {grp_label} | — | N/A | N/A | N/A | data unavailable |")
            continue
        lift_r = next_r - base_r
        lift_s = next_s - base_s
        sep_r = _ci_separated(next_res, base_res, "random")
        sep_s = _ci_separated(next_res, base_res, "spatial")
        sep = "✓" if (sep_r and sep_s) else "✗"
        verdict = ("ADDS SIGNAL" if sep_r and sep_s
                   else "WEAK" if sep_r or sep_s
                   else "NO INCREMENTAL SIGNAL")
        lines.append(
            f"| {grp_label} | see §2 | {lift_r:+.3f} | {lift_s:+.3f} | {sep} | **{verdict}** |"
        )

    # Endogenous-sensitivity check
    lines += [
        "",
        "---",
        "",
        "## 5. Endogenous-Excluded Sensitivity Check",
        "",
        "Refits with crash + static infrastructure only (no signals, stop control,",
        "speed limit, or bike lanes). If conclusions hold, the endogenous leakage risk",
        "does not materially affect the result.",
        "",
    ]
    # Prefer supplemental steps if available (correct slope included)
    si_key  = "static_infra_only_supp" if "static_infra_only_supp" in ablation_results else "static_infra_only"
    all_key = "all_supp"               if "all_supp"               in ablation_results else "all"
    si_res  = ablation_results.get(si_key,  {}).get("xgb_tweedie", {})
    all_res = ablation_results.get(all_key, {}).get("xgb_tweedie", {})
    si_r = _spearman_pt(si_res, "random")
    si_s = _spearman_pt(si_res, "spatial")
    al_r = _spearman_pt(all_res, "random")
    al_s = _spearman_pt(all_res, "spatial")

    if not np.isnan(si_r):
        lines += [
            f"- **Static-only Spearman:** random={si_r:.3f}, spatial={si_s:.3f}",
            f"- **All-features Spearman:** random={al_r:.3f}, spatial={al_s:.3f}",
            f"- **Endogenous marginal contribution:** random={al_r - si_r:+.3f}, spatial={al_s - si_s:+.3f}",
            "",
        ]
        if abs(al_r - si_r) < 0.005 and abs(al_s - si_s) < 0.005:
            lines.append("**Verdict:** Endogenous features add negligible lift. Conclusions hold even with static-only features.")
        else:
            lines.append("**Verdict:** Endogenous features contribute non-trivially. Interpret with caution: 2021 vintage is required.")
    else:
        lines.append("Static-infra-only step not available (insufficient data).")

    # Headline answer
    all_key2 = "all_supp" if "all_supp" in ablation_results else "all"
    all_tw = ablation_results.get(all_key2, {}).get("xgb_tweedie", {})
    base_tw = ablation_results.get("crash_only", {}).get("xgb_tweedie", {})
    total_lift_r = _spearman_pt(all_tw, "random") - _spearman_pt(base_tw, "random")
    total_lift_s = _spearman_pt(all_tw, "spatial") - _spearman_pt(base_tw, "spatial")

    lines += [
        "",
        "---",
        "",
        "## 6. Headline Answer: Does Built Environment Add Independent Signal?",
        "",
        f"Total Tweedie Spearman lift (all features over crash-only): "
        f"random={total_lift_r:+.3f}, spatial={total_lift_s:+.3f}.",
        "",
    ]

    any_sep = any(
        _ci_separated(
            ablation_results.get(next_s, {}).get("xgb_tweedie", {}),
            ablation_results.get(base_s, {}).get("xgb_tweedie", {}),
            "random",
        ) and _ci_separated(
            ablation_results.get(next_s, {}).get("xgb_tweedie", {}),
            ablation_results.get(base_s, {}).get("xgb_tweedie", {}),
            "spatial",
        )
        for _, base_s, next_s, _ in group_steps
        if next_s in ablation_results
    )

    if any_sep:
        lines += [
            "At least one infrastructure group shows CI-separated incremental lift in both splits.",
            "**Built-environment features carry independent predictive signal above crash history.",
            "Proceed to M4 with infrastructure features retained.**",
        ]
    elif total_lift_r > 0.01 or total_lift_s > 0.01:
        lines += [
            "Infrastructure features provide modest positive lift but without CI separation.",
            "**Weak / inconclusive signal: interpret cautiously.",
            "Infrastructure may help but the evidence is not definitive at this sample size.**",
        ]
    else:
        lines += [
            "Infrastructure features show negligible or no incremental lift over crash history.",
            "**Honest null: built-environment features do not add independent signal",
            "at this spatial resolution and sample size.**",
            "This is a valid, publishable finding (target: TMLR).",
        ]

    lines += [
        "",
        "---",
        "",
        "## 7. Interpretation Notes",
        "",
        "- With ~389 non-zero count nodes and ~22 true ≥2 sites, CIs are wide by construction.",
        "- Overlapping CIs are not a win; honest null is reportable.",
        "- Infrastructure-feature coverage gaps (see §2) may mask signal.",
        "- The crash-only M3a Tweedie is the primary bar; M3b baseline Spearman is",
        "  re-estimated here (may differ slightly due to different random-split seed).",
        "- SanGIS data was not obtained this milestone; OSM-derived versions used instead.",
    ]

    out = reports_dir / "milestone3b_infrastructure.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    log.info("Wrote %s", out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    cfg         = load_config()
    model_dir   = project_root() / cfg["paths"]["model"]
    reports_dir = project_root() / cfg["paths"]["reports"]
    reports_dir.mkdir(parents=True, exist_ok=True)

    candidates  = gpd.read_parquet(model_dir / "candidate_panel.parquet")
    crash_feats = pd.read_parquet(model_dir / "feature_table.parquet")

    try:
        infra_feats = pd.read_parquet(model_dir / "infra_features.parquet")
    except FileNotFoundError:
        infra_feats = pd.DataFrame({"intersection_id": candidates["intersection_id"]})
        log.warning("infra_features.parquet not found — only crash_only step will be evaluated")

    panel = candidates.merge(crash_feats, on="intersection_id", how="left")
    panel = panel.merge(infra_feats, on="intersection_id", how="left")
    if "spatial_block" not in panel.columns:
        panel = add_spatial_blocks(panel, cfg)

    y_count = panel["KSI_label"].values.astype(float)

    # Load ablation scores
    try:
        abl_scores = pd.read_parquet(model_dir / "ablation_scores.parquet")
    except FileNotFoundError:
        log.error("ablation_scores.parquet not found — run fit_ablation first (make model_ablation)")
        return

    # Evaluate each score column
    ablation_results: dict = {}
    available_steps: list[str] = []

    # Baseline
    if "baseline" in abl_scores.columns:
        bl_scores = abl_scores["baseline"].values
        baseline_eval = _eval_scores(bl_scores, y_count, panel, cfg, "baseline")
        ablation_results["__baseline"] = {"xgb_tweedie": baseline_eval}

    score_cols = [c for c in abl_scores.columns if c not in ("intersection_id", "baseline")]
    steps_seen: set[str] = set()
    for col in score_cols:
        parts     = col.rsplit("__", 1)
        step_name = parts[0]
        model_key = parts[1] if len(parts) == 2 else col

        if step_name not in ablation_results:
            ablation_results[step_name] = {}
            available_steps.append(step_name)
            steps_seen.add(step_name)

        sc = abl_scores[col].values
        result = _eval_scores(sc, y_count, panel, cfg, f"{step_name}/{model_key}")
        ablation_results[step_name][model_key] = result

    log.info("Evaluated %d ablation steps", len(available_steps))

    # Print summary table
    print("\n" + "=" * 80)
    print("MILESTONE 3b — INFRASTRUCTURE ABLATION SUMMARY (Tweedie Spearman)")
    print("=" * 80)
    print(f"{'Step':<30} {'Random rho':>10} {'Spatial rho':>10} {'Lift(R)':>10} {'Lift(S)':>10}")
    print("-" * 70)

    crash_r = _spearman_pt(ablation_results.get("crash_only", {}).get("xgb_tweedie", {}), "random")
    crash_s = _spearman_pt(ablation_results.get("crash_only", {}).get("xgb_tweedie", {}), "spatial")

    for step_name in available_steps:
        tw = ablation_results.get(step_name, {}).get("xgb_tweedie", {})
        r  = _spearman_pt(tw, "random")
        s  = _spearman_pt(tw, "spatial")
        lr = f"{r - crash_r:+.3f}" if not np.isnan(r) and step_name != "crash_only" else "  —  "
        ls = f"{s - crash_s:+.3f}" if not np.isnan(s) and step_name != "crash_only" else "  —  "
        print(f"{step_name:<30} {r:>10.3f} {s:>10.3f} {lr:>10} {ls:>10}")

    print("=" * 80)

    # Infrastructure coverage from feature dict
    infra_coverage: dict = {}
    fdict_path = model_dir / "feature_dictionary.csv"
    if fdict_path.exists():
        fd = pd.read_csv(fdict_path)
        col = "milestone" if "milestone" in fd.columns else ("group" if "group" in fd.columns else None)
        m3b = fd[fd[col] == "M3b"] if col else pd.DataFrame()
        for _, row in m3b.iterrows():
            feat = row.get("feature_name", "")
            miss = row.get("missing_rate", float("nan"))
            if feat and not (isinstance(miss, float) and np.isnan(miss)):
                infra_coverage[feat] = f"{100*(1-float(miss)):.1f}%"

    # Load params
    params_path = model_dir / "ablation_params.json"
    xgb_params  = json.loads(params_path.read_text()) if params_path.exists() else {}

    write_report(
        ablation_results, ablation_results.get("__baseline", {}),
        panel, available_steps, infra_coverage, xgb_params, reports_dir,
    )


if __name__ == "__main__":
    main()
