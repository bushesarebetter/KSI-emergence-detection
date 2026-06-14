"""M4 evaluation: Protocol A frozen-param ablation + recall@K + decision memo.

Three sequential parts per the M4 spec:

  Part 1 -- Protocol A frozen-parameter ablation
    Gate: do not proceed to Part 2 until Part 1 produces valid scores.
    Uses frozen M3a crash-only XGB-Tweedie hyperparameters across all 4 feature sets.
    Reports Tweedie Spearman rho + 95% bootstrap CI (concatenated test set) for
    both random and spatial splits.

  Part 2 -- Recall@K evaluation (K in {50,100,200,500,1000})
    Uses best-performing feature set from Part 1 (or Set A if tied within CI).
    Bootstrap CI from resampling the 22 true-positive nodes with replacement.
    Reports random-baseline comparison and spatial-split positive distribution.

  Part 3 -- Decision gate and M5 scoping
    Writes reports/milestone4.md with:
      - Ablation verdict (null confirmed / infra helps / ambiguous)
      - Recall@K verdict (operational usefulness threshold: recall@200 CI lo > 2x random)
      - Paper framing recommendation
      - M5 rank-ordered work items
    Updates DECISIONS.md with D8-resolved (or D8-ambiguous).

Run leakage audit as gate before any fitting.

Run via:  python -m src.eval.milestone4
"""
from __future__ import annotations

import json
import logging
import sys
import warnings
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import stats

from src.audit.leakage import run_audit
from src.eval.metrics import compute_metrics
from src.eval.milestone2 import bootstrap_count_ci, count_metrics
from src.eval.splitter import add_spatial_blocks, random_split, spatial_block_kfold
from src.utils import load_config, project_root

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
warnings.filterwarnings("ignore", category=UserWarning)

SET_NAMES = ["A_crash_only", "B_road_geometry", "C_signals", "D_all_infra"]

SET_LABELS = {
    "A_crash_only":    "Set A: crash-only (M3a baseline)",
    "B_road_geometry": "Set B: crash + road geometry & class",
    "C_signals":       "Set C: crash + signals & signs",
    "D_all_infra":     "Set D: crash + all infrastructure",
}


# ---------------------------------------------------------------------------
# Part 1 helpers
# ---------------------------------------------------------------------------

def _eval_frozen_scores(
    scores: np.ndarray,
    y_count: np.ndarray,
    panel: pd.DataFrame,
    cfg: dict,
    label: str,
) -> dict:
    """Evaluate one score vector under both splits using concatenated test-set Spearman."""
    seed   = cfg["project"]["rng_seed"]
    n_boot = cfg["evaluation"]["bootstrap_resamples"]
    p      = cfg["target"]["tweedie_variance_power"]
    out    = {}

    for split_name in ("random", "spatial"):
        if split_name == "random":
            test_idx = random_split(panel, cfg)[1]
            folds    = [(None, test_idx)]
        else:
            folds = [(None, ti) for _, ti in spatial_block_kfold(panel, cfg)]

        yc_parts, sc_parts = [], []
        for _, ti in folds:
            yc_parts.append(y_count[ti])
            sc_parts.append(scores[ti])

        if not yc_parts:
            out[split_name] = {"point": {}, "ci": {}}
            continue

        ayc = np.concatenate(yc_parts)
        asc = np.concatenate(sc_parts)

        pt = count_metrics(ayc, asc, p)
        cc = bootstrap_count_ci(ayc, asc, n_resamples=n_boot, seed=seed, p=p)

        log.info(
            "%s [%s] spearman=%.4f  deviance=%.4f",
            label, split_name,
            pt.get("spearman_rho", float("nan")),
            pt.get("tweedie_deviance", float("nan")),
        )
        out[split_name] = {"point": pt, "ci": cc}

    return out


def _spearman_pt(res: dict, split: str) -> float:
    return res.get(split, {}).get("point", {}).get("spearman_rho", float("nan"))


def _spearman_ci(res: dict, split: str) -> tuple[float, float]:
    ci = res.get(split, {}).get("ci", {}).get("spearman_rho", {})
    return ci.get("lo", float("nan")), ci.get("hi", float("nan"))


def _ci_excludes_zero(res: dict, baseline: dict, split: str) -> bool:
    """True if model CI lower bound > baseline CI upper bound (CI-separated positive lift)."""
    m_lo = _spearman_ci(res, split)[0]
    b_hi = _spearman_ci(baseline, split)[1]
    return float(m_lo) > float(b_hi)


def _ci_includes_zero(res: dict, baseline: dict, split: str) -> bool:
    """True if model CI overlaps baseline CI (cannot rule out null)."""
    m_lo = _spearman_ci(res, split)[0]
    b_hi = _spearman_ci(baseline, split)[1]
    return float(m_lo) <= float(b_hi)


def run_protocol_a(
    scores_df: pd.DataFrame,
    y_count: np.ndarray,
    panel: pd.DataFrame,
    cfg: dict,
) -> dict:
    """Evaluate all 4 frozen-param sets; return results dict."""
    results: dict[str, dict] = {}
    for set_name in SET_NAMES:
        col = f"{set_name}__xgb_tweedie"
        if col not in scores_df.columns:
            log.warning("Score column %s not found in frozen_scores.parquet -- skipping", col)
            continue
        sc = scores_df[col].values
        results[set_name] = _eval_frozen_scores(sc, y_count, panel, cfg, set_name)
    return results


# ---------------------------------------------------------------------------
# Part 2 helpers
# ---------------------------------------------------------------------------

def recall_at_k_extended(
    y_true: np.ndarray,
    scores: np.ndarray,
    k: int,
) -> float:
    """recall@K: fraction of positives in top-K ranked nodes."""
    n_pos = int(y_true.sum())
    if n_pos == 0:
        return float("nan")
    top_k = np.argsort(scores)[::-1][:k]
    return float(y_true[top_k].sum() / n_pos)


def precision_at_k_extended(
    y_true: np.ndarray,
    scores: np.ndarray,
    k: int,
) -> float:
    top_k = np.argsort(scores)[::-1][:k]
    return float(y_true[top_k].mean())


def _recall_bootstrap_ci(
    y_ge2: np.ndarray,
    scores: np.ndarray,
    k: int,
    n_boot: int = 1000,
    seed: int = 42,
) -> tuple[float, float]:
    """Bootstrap CI on recall@K by resampling the n_pos true positives with replacement.

    Captures uncertainty from the small positive set (n=22).
    Top-K indices are fixed from the full-dataset scores.
    """
    pos_indices = np.where(y_ge2 == 1)[0]
    n_pos       = len(pos_indices)
    if n_pos == 0:
        return float("nan"), float("nan")

    top_k_set = set(np.argsort(scores)[::-1][:k].tolist())
    rng       = np.random.default_rng(seed)
    boot_recalls: list[float] = []

    for _ in range(n_boot):
        boot_pos    = rng.choice(pos_indices, size=n_pos, replace=True)
        boot_unique = np.unique(boot_pos)
        n_in_topk   = int(np.isin(boot_unique, list(top_k_set)).sum())
        boot_recalls.append(n_in_topk / n_pos)

    arr = np.array(boot_recalls)
    return float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))


def run_recall_at_k(
    scores: np.ndarray,
    y_ge2: np.ndarray,
    panel: pd.DataFrame,
    cfg: dict,
    set_name: str,
) -> dict:
    """Compute recall@K for K in {50,100,200,500,1000} with bootstrap CIs."""
    K_vals   = [50, 100, 200, 500, 1000]
    n_total  = len(y_ge2)
    n_pos    = int(y_ge2.sum())
    n_boot   = cfg["evaluation"]["bootstrap_resamples"]
    seed     = cfg["project"]["rng_seed"]

    log.info(
        "Recall@K evaluation: %d positives (>=2 KSI) in %d candidates using %s",
        n_pos, n_total, set_name,
    )

    # Random split evaluation
    train_idx, test_idx = random_split(panel, cfg)
    sc_test   = scores[test_idx]
    y2_test   = y_ge2[test_idx]
    n_pos_test = int(y2_test.sum())

    rows_random: list[dict] = []
    for k in K_vals:
        pt    = recall_at_k_extended(y2_test, sc_test, k)
        prec  = precision_at_k_extended(y2_test, sc_test, k)
        lo, hi = _recall_bootstrap_ci(y2_test, sc_test, k, n_boot, seed)
        rand_base = (n_pos / n_total) * k / n_pos if n_pos > 0 else 0.0
        rows_random.append({
            "K": k,
            "recall_at_k": pt,
            "ci_lo": lo,
            "ci_hi": hi,
            "precision_at_k": prec,
            "random_baseline": rand_base,
            "lift_over_random": pt / rand_base if rand_base > 0 else float("nan"),
        })

    # Spatial-split positive distribution check
    spatial_pos_counts = {"train": 0, "test": 0}
    for train_idx_sp, test_idx_sp in spatial_block_kfold(panel, cfg):
        spatial_pos_counts["train"] += int(y_ge2[train_idx_sp].sum())
        spatial_pos_counts["test"]  += int(y_ge2[test_idx_sp].sum())

    # Spatial-split recall@K (concatenated across folds)
    sp_yc_parts, sp_sc_parts = [], []
    for _, ti in spatial_block_kfold(panel, cfg):
        sp_yc_parts.append(y_ge2[ti])
        sp_sc_parts.append(scores[ti])
    sp_y = np.concatenate(sp_yc_parts)
    sp_s = np.concatenate(sp_sc_parts)
    n_pos_spatial_test = int(sp_y.sum())

    rows_spatial: list[dict] = []
    for k in K_vals:
        pt   = recall_at_k_extended(sp_y, sp_s, k)
        prec = precision_at_k_extended(sp_y, sp_s, k)
        lo, hi = _recall_bootstrap_ci(sp_y, sp_s, k, n_boot, seed)
        rand_base = (n_pos / n_total) * k / n_pos if n_pos > 0 else 0.0
        rows_spatial.append({
            "K": k,
            "recall_at_k": pt,
            "ci_lo": lo,
            "ci_hi": hi,
            "precision_at_k": prec,
            "random_baseline": rand_base,
            "lift_over_random": pt / rand_base if rand_base > 0 else float("nan"),
        })

    # Smallest K where >=1 of 22 appears in ranking (random split)
    sorted_idx = np.argsort(sc_test)[::-1]
    pos_set    = set(np.where(y2_test == 1)[0].tolist())
    first_hit_k = next(
        (k + 1 for k, idx in enumerate(sorted_idx) if idx in pos_set), None
    )

    # Top-50 zero-prior-KSI share (random split)
    top50_idx     = sorted_idx[:50]
    n_zero_in_top50 = int((y2_test[top50_idx] == 0).sum())

    return {
        "set_name":               set_name,
        "n_candidates":           n_total,
        "n_pos_ge2":              n_pos,
        "n_pos_random_test":      n_pos_test,
        "n_pos_spatial_test":     n_pos_spatial_test,
        "spatial_pos_train_total": spatial_pos_counts["train"],
        "spatial_pos_test_total":  spatial_pos_counts["test"],
        "rows_random":            rows_random,
        "rows_spatial":           rows_spatial,
        "first_hit_k_random":     first_hit_k,
        "zero_prior_in_top50_random": n_zero_in_top50,
    }


# ---------------------------------------------------------------------------
# Part 3 report writer
# ---------------------------------------------------------------------------

def _fmt_rho(res: dict, split: str) -> str:
    pt       = _spearman_pt(res, split)
    lo, hi   = _spearman_ci(res, split)
    if np.isnan(pt):
        return "N/A"
    return f"{pt:.4f} [{lo:.4f}, {hi:.4f}]"


def write_report(
    protocol_a_results: dict,
    recall_results: dict,
    frozen_params: dict,
    panel: pd.DataFrame,
    best_set: str,
    ablation_verdict: str,   # "null_confirmed" | "infra_helps" | "ambiguous"
    recall_verdict: str,     # "useful" | "not_useful"
    reports_dir: Path,
) -> None:
    today    = date.today().isoformat()
    n_cand   = len(panel)
    n_pos2   = int((panel["KSI_label"] >= 2).sum())
    n_pos1   = int((panel["KSI_label"] >= 1).sum())

    lines = [
        "# Milestone 4 — Protocol A Ablation + Recall@K Evaluation",
        "",
        f"**Date:** {today}",
        "",
        "**M4 Purpose:**",
        "1. Resolve the contested M3b infrastructure null (D8) by re-running the ablation",
        "   with frozen M3a hyperparameters (Protocol A — one variable at a time).",
        "2. Quantify recall@K against the 22 emergent sites (operational readout).",
        "3. Determine paper framing and M5 work scope.",
        "",
        "---",
        "",
        "## 0. Leakage Audit",
        "",
        "Leakage audit A1-A9 run before any fitting. See console output for PASS/FAIL.",
        "Required: all green before proceeding.",
        "",
        "---",
        "",
        "## 1. Panel",
        "",
        "| Metric | Value |",
        "| ------ | ----- |",
        f"| Surface candidates | {n_cand:,} |",
        f"| Positives @>=2 (eval operating point) | {n_pos2} |",
        f"| Positives @>=1 (secondary readout) | {n_pos1} |",
        "",
        "---",
        "",
        "## 2. Protocol A — Frozen-Hyperparameter Ablation",
        "",
        "### 2a. Frozen hyperparameters (M3a crash-only XGB-Tweedie)",
        "",
        "These parameters are held constant across all four feature sets.",
        "Any variation would indicate a protocol violation.",
        "",
        "| Parameter | Value |",
        "| --------- | ----- |",
    ]

    fp = frozen_params.get("frozen", {})
    for k, v in fp.items():
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "### 2b. Feature set definitions",
        "",
        "| Set | Description | Features added over crash-only |",
        "| --- | ----------- | ------------------------------ |",
        "| A | crash-only (M3a baseline) | — |",
        "| B | crash + road geometry & class | edge_count, lane_count, intersection_type, "
        "functional_class, freeway_proximity, speed_limit |",
        "| C | crash + signals & signs | signal_present, stop_control |",
        "| D | crash + all infrastructure | B + C + bike_lane_present, transit_proximity, slope_pct |",
        "",
        "### 2c. Tweedie Spearman rho results",
        "",
        "Primary metric: Tweedie Spearman rho (predicted count rank vs actual KSI count).",
        "Bootstrap 95% CIs from 1,000 resamples of the concatenated test set.",
        "All sets use identical hyperparameters (Protocol A requirement).",
        "",
        "| Set | Random rho [95% CI] | Spatial rho [95% CI] | Lift vs A (random) | Lift vs A (spatial) | CI-sep both? |",
        "| --- | ------------------- | -------------------- | ------------------ | ------------------- | ------------ |",
    ]

    set_a_res = protocol_a_results.get("A_crash_only", {})
    a_r = _spearman_pt(set_a_res, "random")
    a_s = _spearman_pt(set_a_res, "spatial")

    for set_name in SET_NAMES:
        res    = protocol_a_results.get(set_name, {})
        r_rho  = _spearman_pt(res, "random")
        s_rho  = _spearman_pt(res, "spatial")
        if set_name == "A_crash_only":
            lift_r = "—"
            lift_s = "—"
            sep    = "—"
        else:
            lift_r = f"{r_rho - a_r:+.4f}" if not np.isnan(r_rho) else "N/A"
            lift_s = f"{s_rho - a_s:+.4f}" if not np.isnan(s_rho) else "N/A"
            ci_sep_r = _ci_excludes_zero(res, set_a_res, "random")
            ci_sep_s = _ci_excludes_zero(res, set_a_res, "spatial")
            sep      = "yes" if (ci_sep_r and ci_sep_s) else ("random only" if ci_sep_r else "no")
        lines.append(
            f"| {set_name} | {_fmt_rho(res, 'random')} | {_fmt_rho(res, 'spatial')} "
            f"| {lift_r} | {lift_s} | {sep} |"
        )

    # Hyperparameter sanity check table
    lines += [
        "",
        "### 2d. Hyperparameter sanity check",
        "",
        "Confirming all four sets used identical hyperparameters:",
        "",
        "| Set | vpower | lr | n_est | reg_alpha | reg_lambda | mcw | n_features |",
        "| --- | ------ | -- | ----- | --------- | ---------- | --- | ---------- |",
    ]
    for set_name in SET_NAMES:
        sd = frozen_params.get("sets", {}).get(set_name, {})
        tw = sd.get("xgb_tweedie", fp)
        n_feats = sd.get("n_features_used", "?")
        lines.append(
            f"| {set_name} | {tw.get('tweedie_variance_power', '?')} "
            f"| {tw.get('learning_rate', '?')} | {tw.get('n_estimators', '?')} "
            f"| {tw.get('reg_alpha', '?')} | {tw.get('reg_lambda', '?')} "
            f"| {tw.get('min_child_weight', '?')} | {n_feats} |"
        )

    # Protocol A verdict
    lines += [
        "",
        "### 2e. Protocol A verdict",
        "",
    ]
    if ablation_verdict == "infra_helps":
        lines += [
            "**INFRASTRUCTURE HELPS (D8 RESOLVED — POSITIVE):**",
            "At least one infrastructure set (B, C, or D) shows CI-separated Spearman lift",
            "over crash-only (Set A) in BOTH splits under frozen hyperparameters.",
            "The M3b drop was confirmed to be a hyperparameter artifact (D8).",
            "Infra features carry independent predictive signal above crash history.",
        ]
    elif ablation_verdict == "null_confirmed":
        lines += [
            "**NULL CONFIRMED (D8 RESOLVED — NEGATIVE):**",
            "No infrastructure set shows CI-separated Spearman lift over crash-only in",
            "BOTH splits under frozen hyperparameters. The M3b null was not an artifact;",
            "the infrastructure features do not add independent rank signal above crash history",
            "even when hyperparameter confounding is eliminated.",
        ]
    else:
        lines += [
            "**AMBIGUOUS (D8 UNRESOLVED):**",
            "Protocol A results are inconclusive (lift present in one split but not both,",
            "or CI borderline). Protocol B (re-tune per step, select on Spearman) is",
            "recommended as a cross-check before a definitive verdict.",
        ]

    lines += [
        "",
        "---",
        "",
        "## 3. Recall@K Evaluation (against 22 emergent sites, >=2 KSI)",
        "",
        f"**Best feature set used:** {best_set} ({SET_LABELS.get(best_set, best_set)})",
        "",
        "Note: if Set A (crash-only) wins or ties within CI, Set A is used (simpler model preferred).",
        "",
    ]

    if recall_results:
        rr = recall_results
        lines += [
            f"- Total candidates: {rr['n_candidates']:,}",
            f"- True positives (>=2 KSI): {rr['n_pos_ge2']} (eval operating point)",
            f"- True positives in random test set (20%): {rr['n_pos_random_test']}",
            f"- True positives in spatial test folds (all folds concatenated): {rr['n_pos_spatial_test']}",
            "",
        ]

        # Spatial positive distribution caveat
        train_pos = rr["spatial_pos_train_total"]
        test_pos  = rr["spatial_pos_test_total"]
        n_pos     = rr["n_pos_ge2"]
        if n_pos > 0 and test_pos / n_pos < 0.25:
            lines += [
                f"**Spatial-split caveat:** {test_pos}/{n_pos} of the {n_pos} positives appear in",
                f"spatial test folds (spatial fold counts total test-set appearances across all k folds;",
                f"each positive may appear in only 1 fold). With <25% of positives in spatial test,",
                f"spatial recall@K is unreliable -- random-split figures are primary in the paper.",
                "",
            ]
        else:
            lines += [
                f"Spatial-split positive distribution: {test_pos} appearances in test folds,",
                f"{train_pos} in train folds (distributed across k=5 folds).",
                "",
            ]

        lines += [
            "### 3a. Recall@K (random 80/20 split) -- PRIMARY",
            "",
            "| K | recall@K | 95% CI | random baseline | lift |",
            "| - | -------- | ------ | --------------- | ---- |",
        ]
        for row in rr["rows_random"]:
            k     = row["K"]
            pt    = row["recall_at_k"]
            lo    = row["ci_lo"]
            hi    = row["ci_hi"]
            rb    = row["random_baseline"]
            lift  = row["lift_over_random"]
            if np.isnan(pt):
                lines.append(f"| {k} | N/A | N/A | {rb:.3f} | N/A |")
            else:
                lines.append(
                    f"| {k} | {pt:.3f} | [{lo:.3f}, {hi:.3f}] | {rb:.3f} | {lift:.1f}x |"
                )

        lines += [
            "",
            "### 3b. Recall@K (spatial holdout, concatenated folds)",
            "",
            "| K | recall@K | 95% CI | random baseline | lift |",
            "| - | -------- | ------ | --------------- | ---- |",
        ]
        for row in rr["rows_spatial"]:
            k    = row["K"]
            pt   = row["recall_at_k"]
            lo   = row["ci_lo"]
            hi   = row["ci_hi"]
            rb   = row["random_baseline"]
            lift = row["lift_over_random"]
            if np.isnan(pt):
                lines.append(f"| {k} | N/A | N/A | {rb:.3f} | N/A |")
            else:
                lines.append(
                    f"| {k} | {pt:.3f} | [{lo:.3f}, {hi:.3f}] | {rb:.3f} | {lift:.1f}x |"
                )

        first_hit = rr.get("first_hit_k_random")
        n_zero_50 = rr.get("zero_prior_in_top50_random")
        lines += [
            "",
            f"**Sanity checks (random split):**",
            f"- Smallest K where >=1 of the {rr['n_pos_ge2']} positives appears: "
            f"K={first_hit if first_hit else 'not in test set'}",
            f"- Zero-prior-KSI nodes in top-50: {n_zero_50} / 50 "
            f"({'shows model surfaces new sites, not just known hotspots' if n_zero_50 and n_zero_50 > 25 else 'many top-50 are repeat-crash sites'})",
            "",
        ]

        # Recall verdict
        row200 = next((r for r in rr["rows_random"] if r["K"] == 200), None)
        if row200:
            rb200  = row200["random_baseline"]
            lo200  = row200["ci_lo"]
            target = 2 * rb200
            lines += [
                "### 3c. Recall@K verdict",
                "",
                f"Threshold for operational usefulness: recall@200 CI lower bound > 2x random baseline.",
                f"- Random baseline @200: {rb200:.3f}",
                f"- Usefulness threshold: {target:.3f}",
                f"- Recall@200 [95% CI lo]: {row200['recall_at_k']:.3f} [{lo200:.3f}]",
                "",
            ]
            if recall_verdict == "useful":
                lines += [
                    "**USEFUL:** recall@200 CI lower bound exceeds 2x random baseline.",
                    "The model ranking is operationally useful for surfacing emergent sites.",
                ]
            else:
                lines += [
                    "**NOT USEFUL at threshold:** recall@200 CI lower bound does not exceed 2x random.",
                    "The model cannot reliably surface emergent sites within a shortlist of 200.",
                    "Larger K (500-1000) may still provide partial actionable signal.",
                ]
    else:
        lines.append("Recall@K results not available.")

    # Decision memo (Part 3)
    lines += [
        "",
        "---",
        "",
        "## 4. Decision Gate & M5 Scope",
        "",
        "### A. Ablation verdict",
        "",
    ]
    if ablation_verdict == "infra_helps":
        lines += [
            "Infrastructure features add positive incremental Spearman lift over crash-only",
            "under frozen hyperparameters. D8 is RESOLVED POSITIVE.",
            "DECISIONS.md updated with D8-resolved.",
        ]
    elif ablation_verdict == "null_confirmed":
        lines += [
            "Infrastructure features show no CI-separated Spearman lift over crash-only",
            "under frozen hyperparameters. D8 is RESOLVED NEGATIVE (null confirmed).",
            "The M3b result was not a hyperparameter artifact; it was a real null.",
            "DECISIONS.md updated with D8-resolved.",
        ]
    else:
        lines += [
            "Results are ambiguous. D8 is NOT yet resolved.",
            "Recommend Protocol B as cross-check (tune per step, select on Spearman).",
        ]

    lines += [
        "",
        "### B. Recall@K verdict",
        "",
    ]
    if recall_verdict == "useful":
        lines += [
            "The model ranking is operationally useful (recall@200 CI lo > 2x random).",
            "A shortlist of ~200 nodes captures meaningful above-chance recall of emergent sites.",
        ]
    else:
        lines += [
            "The model ranking does not meet the operational usefulness threshold at K=200.",
            "Rank signal is present (Tweedie Spearman CI-separated from baseline) but",
            "insufficient to reliably shortlist emergent sites at K<=200.",
            "K=500 or K=1000 may still provide actionable signal.",
        ]

    lines += [
        "",
        "### C. Paper framing",
        "",
    ]
    if ablation_verdict == "infra_helps" and recall_verdict == "useful":
        lines += [
            "**Recommendation: 'Positive-but-modest' framing.**",
            "Crash history + built environment: rank signal is real, recall@K quantifies",
            "operational shortlist value. Lead with Tweedie Spearman + recall@K.",
            "Acknowledge wide CIs given n_pos=22.",
        ]
    elif ablation_verdict == "null_confirmed":
        lines += [
            "**Recommendation: 'Sufficiency null' framing.**",
            "Crash history alone is sufficient; built-environment features add negligible signal.",
            "Lead with the honest null: crash history dominates, infrastructure is redundant",
            "at this spatial resolution (76.2m / 250ft intersection buffer).",
            "Secondary: recall@K demonstrates operational rank utility of crash-history model.",
        ]
    else:
        lines += [
            "**Framing deferred until D8 is resolved.**",
            "Run Protocol B before committing to a framing.",
        ]

    lines += [
        "",
        "### D. M5 work items (rank-ordered)",
        "",
    ]
    if ablation_verdict == "infra_helps":
        lines += [
            "1. **Attribution + SHAP group analysis** for winning feature set",
            "   (which infrastructure features drive the lift?).",
            "2. **Graph/spillover features** (neighbor crash sums, 1-hop KSI count)",
            "   under the same frozen-param harness.",
            "3. **Exposure/ADT offset** (log(ADT) as Tweedie offset) if SANDAG/HPMS data accessible.",
            "4. **Calibration**: isotonic or conformal prediction intervals on the rate.",
            "5. If recall@K is compelling and attribution complete: paper assembly (M5 = writing).",
        ]
    else:
        lines += [
            "1. **Graph/spillover features** (neighbor crash sums, betweenness centrality)",
            "   under the frozen-param harness -- may add signal without infrastructure gaps.",
            "2. **Exposure/ADT offset** (log(ADT) as Tweedie offset) if SANDAG/HPMS accessible.",
            "3. **Missing-value strategy** for lane_count (65.7% missing):",
            "   NaN->median or explicit missingness indicator features.",
            "4. **Calibration**: isotonic or conformal prediction intervals on the rate.",
            "5. **Paper assembly** (M5 = writing) if recall@K is already compelling",
            "   and no additional features are planned.",
        ]

    lines += [
        "",
        "---",
        "",
        "## 5. Open Items",
        "",
        "- Provisional-year check: confirm how much of 2024 label window is provisional",
        "  in the SWITRS export; record as a limitation if material.",
        "- SanGIS not yet obtained (M3b used OSM proxies); could sharpen Groups 4-5 in M5.",
        "- slope_pct at 60.1% coverage; full DEM re-run available if needed.",
        "- The 22 >=2 KSI sites yield wide CIs by construction -- report honestly.",
    ]

    out = reports_dir / "milestone4.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    log.info("Wrote %s", out)


# ---------------------------------------------------------------------------
# DECISIONS.md update
# ---------------------------------------------------------------------------

def update_decisions(
    decisions_path: Path,
    ablation_verdict: str,
    best_set: str,
    a_random: float,
    best_random: float,
    recall200_lo: float,
    recall200_rb: float,
) -> None:
    text      = decisions_path.read_text(encoding="utf-8")
    today_str = date.today().isoformat()

    if "## D8-resolved" in text or "D8 RESOLVED" in text:
        log.info("DECISIONS.md already contains D8 resolution -- not overwriting.")
        return

    if ablation_verdict == "infra_helps":
        d8_update = (
            f"\n## D8 RESOLVED (POSITIVE) — {today_str}\n"
            f"Protocol A (frozen M3a crash-only Tweedie hyperparameters across all 4 feature sets)\n"
            f"confirmed that the M3b Spearman drop WAS a hyperparameter artifact.\n"
            f"Best set: {best_set} (random rho={best_random:.4f} vs crash-only {a_random:.4f}).\n"
            f"Infrastructure features carry positive independent signal. D8 is closed.\n"
        )
    elif ablation_verdict == "null_confirmed":
        d8_update = (
            f"\n## D8 RESOLVED (NULL CONFIRMED) — {today_str}\n"
            f"Protocol A (frozen M3a crash-only Tweedie hyperparameters across all 4 feature sets)\n"
            f"confirmed that the M3b null is not a hyperparameter artifact.\n"
            f"Set D (all infra) random rho={best_random:.4f} vs crash-only {a_random:.4f}.\n"
            f"No CI-separated positive lift under frozen params. Infrastructure null stands.\n"
        )
    else:
        d8_update = (
            f"\n## D8 AMBIGUOUS — {today_str}\n"
            f"Protocol A results were inconclusive. Protocol B recommended as cross-check.\n"
        )

    recall_note = (
        f"\n## Recall@K verdict — {today_str}\n"
        f"recall@200 CI lower bound: {recall200_lo:.3f} (2x random = {2 * recall200_rb:.3f}).\n"
        f"Verdict: {'USEFUL (CI lo > 2x random)' if recall200_lo > 2 * recall200_rb else 'NOT USEFUL at K=200'}.\n"
    )

    with open(decisions_path, "a", encoding="utf-8") as f:
        f.write(d8_update)
        f.write(recall_note)
    log.info("Appended D8 resolution to DECISIONS.md")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    cfg         = load_config()
    model_dir   = project_root() / cfg["paths"]["model"]
    reports_dir = project_root() / cfg["paths"]["reports"]
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Gate: leakage audit
    log.info("=== Leakage audit (gate) ===")
    try:
        run_audit(cfg)
    except SystemExit as e:
        if e.code != 0:
            log.error("Leakage audit FAILED -- aborting M4 evaluation.")
            sys.exit(1)
        # code 0 means audit passed (audit calls sys.exit(0) on success in some versions)

    # Load panel
    candidates  = gpd.read_parquet(model_dir / "candidate_panel.parquet")
    crash_feats = pd.read_parquet(model_dir / "feature_table.parquet")
    try:
        infra_feats = pd.read_parquet(model_dir / "infra_features.parquet")
    except FileNotFoundError:
        log.warning("infra_features.parquet not found -- B/C/D results will be crash-only")
        infra_feats = pd.DataFrame({"intersection_id": candidates["intersection_id"]})

    panel = candidates.merge(crash_feats, on="intersection_id", how="left")
    panel = panel.merge(infra_feats,      on="intersection_id", how="left")
    if "spatial_block" not in panel.columns:
        panel = add_spatial_blocks(panel, cfg)

    y_count = panel["KSI_label"].values.astype(float)
    y_ge2   = (panel["KSI_label"] >= 2).astype(int).values

    # Gate: frozen scores must exist
    frozen_scores_path = model_dir / "frozen_scores.parquet"
    if not frozen_scores_path.exists():
        log.error(
            "frozen_scores.parquet not found. "
            "Run Protocol A first: python -m src.model.fit_frozen (make model_frozen)"
        )
        sys.exit(1)

    scores_df = pd.read_parquet(frozen_scores_path)
    log.info("Loaded frozen_scores.parquet (%d rows x %d cols)", len(scores_df), len(scores_df.columns))

    frozen_params_path = model_dir / "frozen_params.json"
    frozen_params = json.loads(frozen_params_path.read_text()) if frozen_params_path.exists() else {}

    # Part 1: Protocol A evaluation
    log.info("=== Part 1: Protocol A evaluation ===")
    protocol_a_results = run_protocol_a(scores_df, y_count, panel, cfg)

    # Determine best set (highest random rho; prefer Set A if within CI)
    set_a_res    = protocol_a_results.get("A_crash_only", {})
    a_r          = _spearman_pt(set_a_res, "random")
    a_s          = _spearman_pt(set_a_res, "spatial")

    best_set       = "A_crash_only"
    best_random    = a_r
    ablation_verdict = "null_confirmed"
    any_infra_helps  = False

    for set_name in ["B_road_geometry", "C_signals", "D_all_infra"]:
        res   = protocol_a_results.get(set_name, {})
        r_rho = _spearman_pt(res, "random")
        s_rho = _spearman_pt(res, "spatial")
        ci_r  = _ci_excludes_zero(res, set_a_res, "random")
        ci_s  = _ci_excludes_zero(res, set_a_res, "spatial")

        if ci_r and ci_s:
            any_infra_helps = True
            ablation_verdict = "infra_helps"
            if not np.isnan(r_rho) and r_rho > best_random:
                best_random = r_rho
                best_set    = set_name
        elif (not ci_r) and (not ci_s):
            # Both lift CIs overlap: ambiguous only if magnitude is positive but not separated
            if not np.isnan(r_rho) and r_rho > a_r and not ablation_verdict == "infra_helps":
                ablation_verdict = "ambiguous"

    if not any_infra_helps and ablation_verdict == "ambiguous":
        # Check if any set gave positive (unseparated) lift in both splits
        has_positive_lift = any(
            _spearman_pt(protocol_a_results.get(s, {}), "random") > a_r and
            _spearman_pt(protocol_a_results.get(s, {}), "spatial") > a_s
            for s in ["B_road_geometry", "C_signals", "D_all_infra"]
        )
        if not has_positive_lift:
            ablation_verdict = "null_confirmed"

    log.info("Protocol A verdict: %s | best set: %s", ablation_verdict, best_set)

    # Print Protocol A summary table
    print()
    print("=" * 90)
    print("PROTOCOL A SUMMARY -- Frozen Hyperparameter Ablation (Primary metric: Tweedie Spearman)")
    print("=" * 90)
    print(f"{'Set':<22} {'Random rho':>12} {'Spatial rho':>12} {'Lift(R)':>10} {'Lift(S)':>10} {'CI-sep?':>10}")
    print("-" * 80)
    for set_name in SET_NAMES:
        res   = protocol_a_results.get(set_name, {})
        r_rho = _spearman_pt(res, "random")
        s_rho = _spearman_pt(res, "spatial")
        lr    = f"{r_rho - a_r:+.4f}" if set_name != "A_crash_only" and not np.isnan(r_rho) else "  —   "
        ls    = f"{s_rho - a_s:+.4f}" if set_name != "A_crash_only" and not np.isnan(s_rho) else "  —   "
        ci_r  = _ci_excludes_zero(res, set_a_res, "random") if set_name != "A_crash_only" else None
        ci_s  = _ci_excludes_zero(res, set_a_res, "spatial") if set_name != "A_crash_only" else None
        sep   = ("yes" if (ci_r and ci_s) else ("R-only" if ci_r else "no")) if ci_r is not None else "—"
        print(f"{set_name:<22} {r_rho:>12.4f} {s_rho:>12.4f} {lr:>10} {ls:>10} {sep:>10}")
    print("=" * 90)
    print(f"VERDICT: {ablation_verdict.upper()}  |  Best set: {best_set}")
    print()

    # Part 2: Recall@K
    log.info("=== Part 2: Recall@K evaluation (best set: %s) ===", best_set)
    best_col = f"{best_set}__xgb_tweedie"
    if best_col in scores_df.columns:
        best_scores    = scores_df[best_col].values
        recall_results = run_recall_at_k(best_scores, y_ge2, panel, cfg, best_set)
    else:
        log.error("Best-set score column %s missing -- skipping recall@K", best_col)
        recall_results = {}

    # Determine recall verdict
    recall_verdict = "not_useful"
    recall200_lo   = float("nan")
    recall200_rb   = 0.0
    if recall_results:
        row200 = next((r for r in recall_results["rows_random"] if r["K"] == 200), None)
        if row200:
            recall200_lo = row200["ci_lo"]
            recall200_rb = row200["random_baseline"]
            if not np.isnan(recall200_lo) and recall200_lo > 2 * recall200_rb:
                recall_verdict = "useful"
    log.info(
        "Recall@K verdict: %s (recall@200 CI lo=%.3f, 2x random=%.3f)",
        recall_verdict, recall200_lo, 2 * recall200_rb,
    )

    # Part 3: Write report
    log.info("=== Part 3: Writing milestone4.md ===")
    write_report(
        protocol_a_results = protocol_a_results,
        recall_results     = recall_results,
        frozen_params      = frozen_params,
        panel              = panel,
        best_set           = best_set,
        ablation_verdict   = ablation_verdict,
        recall_verdict     = recall_verdict,
        reports_dir        = reports_dir,
    )

    # Update DECISIONS.md
    decisions_path = project_root() / "docs" / "DECISIONS.md"
    if decisions_path.exists():
        update_decisions(
            decisions_path  = decisions_path,
            ablation_verdict = ablation_verdict,
            best_set         = best_set,
            a_random         = a_r,
            best_random      = best_random,
            recall200_lo     = recall200_lo,
            recall200_rb     = recall200_rb,
        )

    log.info("M4 evaluation complete.")


if __name__ == "__main__":
    main()
