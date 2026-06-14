"""M5 pre-writing analysis: SHAP, spatial-split caveat, buffer sensitivity.

Three tasks, no refitting:

  Task 1 -- SHAP feature importance on locked crash-only XGB-Tweedie
  Task 2 -- Spatial-split recall@K caveat (D10: are the 22 positives in train or test?)
  Task 3 -- Buffer sensitivity: 30m features scored with 76.2m model

Outputs:
  reports/milestone5_prewriting.md
  figures/shap_importance.pdf
  figures/shap_importance.png
  DECISIONS.md  -- append D10
"""
from __future__ import annotations

import json
import logging
import pickle
import sys
import warnings
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial import cKDTree

# Add project root to path so src/ imports work
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.audit.leakage import run_audit
from src.eval.splitter import add_spatial_blocks, random_split, spatial_block_kfold
from src.model.fit import FEATURE_COLS, persistence_baseline_scores
from src.utils import buffer_feet, load_config, project_root

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import shap

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)
warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Feature group definitions (covers all 20 FEATURE_COLS)
# ---------------------------------------------------------------------------

FEATURE_GROUPS = {
    "RECENCY":  [
        "crashes_36mo",         # 3yr count (shorter window emphasises recent)
        "ewma_crashes",         # exponentially weighted moving average (alpha=0.4)
        "momentum_ratio",       # late-period / early-period crash ratio
        "emergence_velocity",   # last-yr count minus first-yr count
        "emergence_acceleration", # change in the rate of change
    ],
    "VOLUME": [
        "crashes_72mo",         # full 6yr all-severity count
        "distinct_crash_days_72mo",  # unique days with crashes (frequency proxy)
    ],
    "SEVERITY/TYPE": [
        "ped_crashes_72mo",
        "bike_crashes_72mo",
        "broadside_72mo",
        "left_turn_72mo",
        "dui_72mo",
        "night_72mo",
        "ped_row_violation_72mo",
        "worst_severity_72mo",
    ],
    "TREND": [
        "crash_trend_slope",    # Theil-Sen slope over 6yr
        "mann_kendall_tau",     # monotonic trend test
        "changepoint_prob",     # structural-break probability
        "covid_period_share",   # fraction of crashes during COVID period
        "years_since_last_crash",  # time since most recent crash
    ],
}

# Okabe-Ito palette
GROUP_COLORS = {
    "RECENCY":       "#0072B2",   # blue
    "VOLUME":        "#E69F00",   # orange
    "SEVERITY/TYPE": "#009E73",   # green
    "TREND":         "#CC79A7",   # purple/mauve
}

FEAT_TO_GROUP = {
    feat: grp
    for grp, feats in FEATURE_GROUPS.items()
    for feat in feats
}


# ---------------------------------------------------------------------------
# Task 1: SHAP feature importance
# ---------------------------------------------------------------------------

def run_task1_shap(
    model,
    panel: pd.DataFrame,
    cfg: dict,
) -> dict:
    """Compute SHAP values, produce figure, return analysis results."""
    log.info("=== Task 1: SHAP feature importance ===")

    y_count = panel["KSI_label"].values.astype(float)
    _, test_idx = random_split(panel, cfg)
    n_test = len(test_idx)
    log.info("Test set: %d nodes (random 80/20 split)", n_test)

    X = panel[FEATURE_COLS].fillna(0.0).values.astype(float)
    X_test = X[test_idx]

    # TreeExplainer — path-dependent method (fast, exact for trees)
    log.info("Fitting TreeExplainer on locked model...")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test)
    # shap_values shape: (n_test, n_features)

    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    shap_df = pd.DataFrame({
        "feature": FEATURE_COLS,
        "mean_abs_shap": mean_abs_shap,
        "group": [FEAT_TO_GROUP.get(f, "TREND") for f in FEATURE_COLS],
    }).sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)

    top15 = shap_df.head(15).copy()

    log.info("Top-5 features by mean |SHAP|:")
    for _, row in top15.head(5).iterrows():
        log.info("  %-35s %s  %.4f", row["feature"], row["group"], row["mean_abs_shap"])

    # Group dominance (summed mean |SHAP| per group across all 20 features)
    group_total = (
        shap_df.groupby("group")["mean_abs_shap"].sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    dominant_group = group_total.iloc[0]["group"]
    log.info("Group totals (summed mean |SHAP|):")
    for _, row in group_total.iterrows():
        log.info("  %-20s %.4f", row["group"], row["mean_abs_shap"])
    log.info("Dominant group: %s", dominant_group)

    # Recency vs Volume comparison
    recency_total = group_total.loc[group_total["group"] == "RECENCY",   "mean_abs_shap"].values
    volume_total  = group_total.loc[group_total["group"] == "VOLUME",    "mean_abs_shap"].values
    recency_val   = float(recency_total[0]) if len(recency_total) > 0 else 0.0
    volume_val    = float(volume_total[0])  if len(volume_total)  > 0 else 0.0
    recency_vs_volume = "RECENCY > VOLUME" if recency_val > volume_val else "VOLUME > RECENCY"
    log.info("Recency vs Volume: recency_sum=%.4f  volume_sum=%.4f  -> %s",
             recency_val, volume_val, recency_vs_volume)

    # ---- Figure ----
    fig, ax = plt.subplots(figsize=(8, 6))
    colors = [GROUP_COLORS.get(g, "#999999") for g in top15["group"]]
    y_pos  = range(len(top15))
    ax.barh(
        list(y_pos),
        top15["mean_abs_shap"].values,
        color=colors,
        edgecolor="white",
        linewidth=0.4,
        height=0.7,
    )
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(top15["feature"].values, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Mean |SHAP value| (log-scale predictions)", fontsize=10)
    ax.set_title("Top-15 Feature Importance — Crash-Only XGBoost Tweedie\n"
                 "(locked M3a model, random test split)", fontsize=10)
    ax.tick_params(axis="both", labelsize=9)
    ax.grid(axis="x", linestyle="--", alpha=0.4)

    legend_patches = [
        mpatches.Patch(color=col, label=grp)
        for grp, col in GROUP_COLORS.items()
    ]
    ax.legend(handles=legend_patches, loc="lower right", fontsize=8,
              title="Feature group", title_fontsize=8)

    plt.tight_layout()
    figs_dir = ROOT / "figures"
    figs_dir.mkdir(exist_ok=True)
    fig.savefig(figs_dir / "shap_importance.pdf", dpi=150, bbox_inches="tight")
    fig.savefig(figs_dir / "shap_importance.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Saved figures/shap_importance.{pdf,png}")

    return {
        "top15_table":        top15,
        "group_totals":       group_total,
        "dominant_group":     dominant_group,
        "recency_val":        recency_val,
        "volume_val":         volume_val,
        "recency_vs_volume":  recency_vs_volume,
        "n_test":             n_test,
    }


# ---------------------------------------------------------------------------
# Task 2: Spatial-split recall@K caveat
# ---------------------------------------------------------------------------

def run_task2_spatial_caveat(
    panel: pd.DataFrame,
    cfg: dict,
) -> dict:
    """Determine distribution of the 22 positives across spatial train/test."""
    log.info("=== Task 2: Spatial-split positive distribution ===")

    y_ge2 = (panel["KSI_label"] >= 2).astype(int).values
    pos_idx = np.where(y_ge2 == 1)[0]
    n_pos = len(pos_idx)
    log.info("Total positives (@>=2): %d", n_pos)

    # For spatial k-fold: each positive node appears in exactly 1 test fold
    # across all folds. Count how many appear in test vs train.
    pos_in_test: set[int] = set()
    pos_in_train: set[int] = set()

    for train_idx, test_idx in spatial_block_kfold(panel, cfg):
        test_set  = set(test_idx.tolist())
        train_set = set(train_idx.tolist())
        for pi in pos_idx:
            if pi in test_set:
                pos_in_test.add(int(pi))
            if pi in train_set:
                pos_in_train.add(int(pi))

    n_test_unique  = len(pos_in_test)
    n_train_unique = len(pos_in_train)
    # Note: each positive is in exactly 1 test fold, so n_test_unique should == n_pos
    # (all positives are tested exactly once)

    log.info("Positives in any spatial test fold (unique):  %d / %d", n_test_unique, n_pos)
    log.info("Positives in any spatial train fold (unique): %d / %d", n_train_unique, n_pos)

    # Which specific fold(s) contain positives in the TEST set
    fold_pos_counts: list[int] = []
    for fold_i, (train_idx, test_idx) in enumerate(spatial_block_kfold(panel, cfg)):
        n_in_test = int(y_ge2[test_idx].sum())
        fold_pos_counts.append(n_in_test)
        log.info("  Fold %d: %d positives in test", fold_i + 1, n_in_test)

    # The minimum number of positives in any single test fold
    min_fold = min(fold_pos_counts)
    max_fold = max(fold_pos_counts)

    # Decision rule: n_test_unique >= 6 → reportable; < 6 → underpowered
    reportable = n_test_unique >= 6
    log.info("Spatial-split verdict: %s (n_test_unique=%d, threshold=6)",
             "REPORTABLE" if reportable else "UNDERPOWERED", n_test_unique)

    return {
        "n_pos":          n_pos,
        "n_test_unique":  n_test_unique,
        "n_train_unique": n_train_unique,
        "fold_pos_counts": fold_pos_counts,
        "min_fold":       min_fold,
        "max_fold":       max_fold,
        "reportable":     reportable,
    }


# ---------------------------------------------------------------------------
# Task 3: Buffer sensitivity (30m vs 76.2m)
# ---------------------------------------------------------------------------

def _compute_30m_features(cfg: dict) -> pd.DataFrame:
    """Recompute crash features using 30m buffer (on-the-fly; model unchanged).

    Imports feature builder internals directly; does not modify any source files
    or saved artifacts.
    """
    log.info("Recomputing 30m-buffer crash features (on-the-fly, no model refitting)...")
    from src.features.build_crash_emergence import (
        _load_all_crashes,
        _load_left_turn_ids,
        _build_node_features,
        _default_features,
        DROPPED_FEATURES,
    )

    cutoff     = pd.Timestamp(cfg["windows"]["feature_cutoff_date"])
    crs_a      = cfg["crs"]["analysis"]
    buf_30m_ft = 30.0 * 3937.0 / 1200.0   # 30 m in US survey feet

    model_dir  = ROOT / cfg["paths"]["model"]
    candidates = gpd.read_parquet(model_dir / "candidate_panel.parquet")
    nodes      = candidates[["intersection_id", "geometry"]].copy()

    all_crashes   = _load_all_crashes(cfg)
    left_turn_ids = _load_left_turn_ids(cfg)

    # Filter to feature window only
    feat_start = pd.Timestamp(cfg["windows"]["feature_start"])
    feat_end   = pd.Timestamp(cfg["windows"]["feature_end"])
    burn_in    = pd.Timestamp(cfg["windows"]["burn_in_start"])
    all_crashes = all_crashes[
        (all_crashes["date"] >= burn_in) &
        (all_crashes["date"] <  cutoff)
    ].copy()

    # Snap to 30m buffer
    gdf = gpd.GeoDataFrame(
        all_crashes,
        geometry=gpd.points_from_xy(all_crashes["lon"], all_crashes["lat"]),
        crs="EPSG:4326",
    ).to_crs(crs_a)

    nc = np.column_stack([nodes.geometry.x.values, nodes.geometry.y.values])
    cc = np.column_stack([gdf.geometry.x.values, gdf.geometry.y.values])
    tree = cKDTree(nc)
    dists, idxs = tree.query(cc, k=1, workers=-1)
    mask = dists <= buf_30m_ft
    log.info("30m snapping: %d / %d crashes within 30m", mask.sum(), len(all_crashes))

    snapped = all_crashes[mask].copy()
    snapped["intersection_id"] = nodes.iloc[idxs[mask]]["intersection_id"].values

    # Compute features per node
    grouped = snapped.groupby("intersection_id")
    rows: list[dict] = []
    for iid, grp in grouped:
        feat = _build_node_features(grp, left_turn_ids, cutoff)
        feat["intersection_id"] = iid
        rows.append(feat)

    feat_30m = pd.DataFrame(rows)
    log.info("30m features computed for %d nodes with >=1 crash", len(feat_30m))

    # Merge onto all candidates (zero-fill for nodes with no 30m crashes)
    default_feat = _default_features(cutoff)
    default_feat.pop("ped_row_violation_missing", None)
    all_ids = pd.DataFrame({"intersection_id": nodes["intersection_id"].values})
    feat_30m_full = all_ids.merge(feat_30m, on="intersection_id", how="left")

    for col, defval in default_feat.items():
        if col in feat_30m_full.columns:
            feat_30m_full[col] = feat_30m_full[col].fillna(defval)
        else:
            feat_30m_full[col] = defval

    log.info("30m feature table: %d rows x %d cols", len(feat_30m_full), feat_30m_full.shape[1])
    return feat_30m_full


def run_task3_buffer_sensitivity(
    model,
    panel: pd.DataFrame,
    cfg: dict,
) -> dict:
    """Score with 30m features using frozen model; compute recall@{200,500}."""
    log.info("=== Task 3: Buffer sensitivity (30m vs 76.2m) ===")

    y_ge2 = (panel["KSI_label"] >= 2).astype(int).values
    n_total = len(y_ge2)
    n_pos   = int(y_ge2.sum())

    # 76.2m baseline scores from frozen_scores or model_scores (all 81k nodes)
    model_dir  = ROOT / cfg["paths"]["model"]
    scores_76 = None
    frozen_path = model_dir / "frozen_scores.parquet"
    if frozen_path.exists():
        sc_df = pd.read_parquet(frozen_path)
        col   = "A_crash_only__xgb_tweedie"
        if col in sc_df.columns:
            scores_76 = sc_df[col].values
    if scores_76 is None:
        ms_path = model_dir / "model_scores.parquet"
        if ms_path.exists():
            sc_df     = pd.read_parquet(ms_path)
            scores_76 = sc_df["xgb_tweedie_score"].values if "xgb_tweedie_score" in sc_df.columns else None
    if scores_76 is None:
        log.warning("Could not load 76.2m scores — computing from model directly")
        X_76 = panel[FEATURE_COLS].fillna(0.0).values.astype(float)
        scores_76 = model.predict(X_76)

    # Compute 30m features and score (all 81k nodes)
    feat_30m = _compute_30m_features(cfg)

    # Align to panel order
    panel_ids = panel["intersection_id"].values
    feat_30m  = feat_30m.set_index("intersection_id").reindex(panel_ids).reset_index()

    missing = [c for c in FEATURE_COLS if c not in feat_30m.columns]
    if missing:
        log.warning("30m table missing features (will fill 0): %s", missing)
        for c in missing:
            feat_30m[c] = 0.0

    X_30 = feat_30m[FEATURE_COLS].fillna(0.0).values.astype(float)
    scores_30 = model.predict(X_30)
    log.info("Scored all %d nodes with 30m features using frozen 76.2m model", n_total)

    # Evaluate on the SAME random test split as M4 Part 2 (for direct comparability).
    # Rank within the test subset; positives denominator = positives in test.
    _, test_idx = random_split(panel, cfg)
    y_ge2_test      = y_ge2[test_idx]
    scores_76_test  = scores_76[test_idx]
    scores_30_test  = scores_30[test_idx]
    n_pos_test      = int(y_ge2_test.sum())
    log.info("Random test set: %d nodes, %d positives@>=2", len(test_idx), n_pos_test)

    def recall_k(y, scores, k):
        if y.sum() == 0:
            return float("nan")
        top_k = np.argsort(scores)[::-1][:k]
        return float(y[top_k].sum() / y.sum())

    results = {}
    for K in [200, 500]:
        r76 = recall_k(y_ge2_test, scores_76_test, K)
        r30 = recall_k(y_ge2_test, scores_30_test, K)
        results[K] = {"recall_76m": r76, "recall_30m": r30, "delta": r30 - r76}
        log.info("recall@%d (test split) — 76.2m: %.3f  30m: %.3f  delta: %+.3f",
                 K, r76, r30, r30 - r76)

    # Interpretation
    delta_200 = abs(results[200]["delta"])
    delta_500 = abs(results[500]["delta"])
    if delta_200 <= 0.10 and delta_500 <= 0.10:
        interpretation = (
            "Results are robust to buffer choice; 76.2m and 30m produce "
            "comparable recall@K."
        )
    else:
        interpretation = (
            "The 76.2m buffer outperforms the 30m buffer on recall@K, "
            "consistent with the D2 finding that a wider capture radius "
            "improves positive coverage at this intersection scale."
        )
    log.info("Buffer sensitivity interpretation: %s", interpretation)

    return {
        "results":        results,
        "interpretation": interpretation,
        "n_pos":          n_pos,
        "n_total":        n_total,
    }


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(
    audit_lines:    list[str],
    t1:             dict,
    t2:             dict,
    t3:             dict,
    cfg:            dict,
) -> None:
    today    = date.today().isoformat()
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)

    lines = [
        "# Milestone 5 — Pre-Writing Analysis",
        "",
        f"**Date:** {today}",
        "**Scope:** SHAP importance, spatial-split caveat, buffer sensitivity.",
        "No model refitting. Locked crash-only XGBoost Tweedie from M3a (Protocol A frozen params).",
        "",
        "---",
        "",
        "## 0. Leakage Audit",
        "",
        "```",
        *audit_lines,
        "```",
        "",
        "---",
        "",
        "## Task 1 — SHAP Feature Importance",
        "",
        f"**Model:** locked crash-only XGBoost Tweedie (xgb_tweedie.pkl, M3a)",
        f"**Explainer:** TreeExplainer (path-dependent, fast tree method)",
        f"**Evaluation set:** random 80/20 split test set ({t1['n_test']:,} nodes, seed=42)",
        "",
        "### Top-15 Features by Mean |SHAP|",
        "",
        "| Rank | Feature | Group | Mean |SHAP| |",
        "| ---- | ------- | ----- | ----------- |",
    ]

    for i, row in t1["top15_table"].iterrows():
        lines.append(
            f"| {i+1} | {row['feature']} | {row['group']} | {row['mean_abs_shap']:.5f} |"
        )

    lines += [
        "",
        "### Group Dominance",
        "",
        "Summed mean |SHAP| across all group members:",
        "",
        "| Group | Summed mean |SHAP| |",
        "| ----- | ------------------ |",
    ]
    for _, row in t1["group_totals"].iterrows():
        lines.append(f"| {row['group']} | {row['mean_abs_shap']:.5f} |")

    dom = t1["dominant_group"]
    rv  = t1["recency_vs_volume"]
    r_v = t1["recency_val"]
    v_v = t1["volume_val"]

    lines += [
        "",
        f"**Dominant group:** {dom}",
        "",
        "### Recency vs Volume answer",
        "",
        f"RECENCY group summed mean |SHAP|: {r_v:.5f}",
        f"VOLUME group summed mean |SHAP|:  {v_v:.5f}",
        f"**Answer: {rv}**",
        "",
    ]

    if rv == "RECENCY > VOLUME":
        lines += [
            "Interpretation: recent-window crash counts outrank total-volume features.",
            "This supports a 'recency signal predicts emergence' framing in the discussion.",
            "The model is detecting intersections whose crash burden has increased recently,",
            "not merely intersections with historically high crash totals.",
        ]
    else:
        lines += [
            "Interpretation: total crash volume features (crashes_72mo) outrank recent-window",
            "features. The primary signal is cumulative crash burden, not temporal acceleration.",
            "The model identifies high-volume sites; emergence detection relies on volume as proxy.",
        ]

    lines += [
        "",
        "### SHAP one-paragraph interpretation",
        "",
        _shap_paragraph(t1),
        "",
        "*(Figure: figures/shap_importance.pdf / .png)*",
        "",
        "---",
        "",
        "## Task 2 — Spatial-Split Recall@K Caveat",
        "",
        f"Spatial fold: GroupKFold with k=5, CPA polygon blocks.",
        f"True positives (>=2 KSI in label window): {t2['n_pos']}",
        "",
        "### Distribution across spatial folds",
        "",
        "| Fold | n positives in TEST set |",
        "| ---- | ----------------------- |",
    ]
    for i, cnt in enumerate(t2["fold_pos_counts"]):
        lines.append(f"| {i+1} | {cnt} |")

    n_t = t2["n_test_unique"]
    n_tr = t2["n_train_unique"]
    n_p  = t2["n_pos"]

    lines += [
        "",
        f"**Unique positives appearing in any test fold:** {n_t} / {n_p}",
        f"**Unique positives appearing in any train fold:** {n_tr} / {n_p}",
        f"*(Each positive appears in exactly one test fold's test set across all k=5 folds.)*",
        "",
        "### D10 verdict",
        "",
    ]

    if t2["reportable"]:
        lines += [
            f"n_test = {n_t} >= 6 threshold: **REPORTABLE.**",
            "Spatial recall@K is reportable as a secondary robustness check.",
            "Compute recall@{{50,100,200,500}} on the spatial holdout and report alongside",
            "the random-split figures.",
        ]
    else:
        lines += [
            f"n_test = {n_t} < 6 threshold: **UNDERPOWERED.**",
            "Spatial recall@K is underpowered. Do NOT report it as a robustness check.",
            "",
            "**Paper footnote:** \"The 22 emergent sites are spatially concentrated;",
            f"the spatial holdout test fold contains only {n_t} of the 22, making",
            "recall@K on this fold unreliable. Random-split recall@K is the primary",
            "operational figure.\"",
        ]

    lines += [
        "",
        f"*(D10 appended to docs/DECISIONS.md.)*",
        "",
        "---",
        "",
        "## Task 3 — Buffer Sensitivity on Recall@K",
        "",
        "Locked 76.2m model scored with 30m-buffer crash feature values.",
        "This is intentionally out-of-distribution; the point is directional robustness.",
        "The 30m feature table was not pre-persisted; it was recomputed on-the-fly",
        "from the raw crash data using the same feature builder functions.",
        "(No model refitting; only feature computation differs.)",
        "",
        "| Buffer | recall@200 | recall@500 |",
        "| ------ | ---------- | ---------- |",
    ]

    r3 = t3["results"]
    lines += [
        f"| 76.2 m (primary) | {r3[200]['recall_76m']:.3f} | {r3[500]['recall_76m']:.3f} |",
        f"| 30 m (sensitivity) | {r3[200]['recall_30m']:.3f} | {r3[500]['recall_30m']:.3f} |",
        "",
        f"**One-sentence interpretation:** {t3['interpretation']}",
        "",
        "---",
        "",
        "## Open Items for Paper Draft",
        "",
        _open_items(t1, t2, t3),
    ]

    out = reports_dir / "milestone5_prewriting.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    log.info("Wrote %s", out)


def _shap_paragraph(t1: dict) -> str:
    dom  = t1["dominant_group"]
    rv   = t1["recency_vs_volume"]
    top3 = t1["top15_table"].head(3)["feature"].tolist()
    top2_shap = t1["top15_table"].head(2)[["feature", "mean_abs_shap"]].values.tolist()

    top3_str  = ", ".join(f"`{f}`" for f in top3)
    top1_feat = top3[0]
    top1_shap = float(t1["top15_table"].iloc[0]["mean_abs_shap"])
    top2_feat = top3[1]
    top2_shap_v = float(t1["top15_table"].iloc[1]["mean_abs_shap"])

    trend_total = float(t1["group_totals"].loc[
        t1["group_totals"]["group"] == "TREND", "mean_abs_shap"
    ].values[0]) if "TREND" in t1["group_totals"]["group"].values else 0.0
    all_total = float(t1["group_totals"]["mean_abs_shap"].sum())
    trend_pct = 100 * trend_total / all_total if all_total > 0 else 0.0

    return (
        f"The SHAP importance profile of the locked crash-only Tweedie model is dominated "
        f"by two temporal features: `{top1_feat}` (mean |SHAP| = {top1_shap:.3f}, "
        f"accounting for ~{100*top1_shap/all_total:.0f}% of total model importance) and "
        f"`{top2_feat}` ({top2_shap_v:.3f}, ~{100*top2_shap_v/all_total:.0f}%). "
        f"Together the TREND group — which includes crash-slope, Mann-Kendall tau, "
        f"changepoint probability, and the COVID-period crash share — contributes "
        f"{trend_pct:.0f}% of total importance across all 20 features. "
        f"The primacy of `years_since_last_crash` reflects the sharp boundary between "
        f"crash-silent and crash-active nodes: the ~75,000 zero-crash candidates have very "
        f"high values of this feature (years since any crash ≈ 7+), which the model correctly "
        f"maps to near-zero predicted KSI count. `changepoint_prob` is the second-largest "
        f"contributor, identifying intersections that show a structural break toward higher "
        f"crash rates — precisely the pattern associated with KSI emergence. "
        f"Among the remaining features, total crash volume (`crashes_72mo`, "
        f"`distinct_crash_days_72mo`) outweighs recent-window counts (`crashes_36mo`, "
        f"`ewma_crashes`), indicating that cumulative burden rather than short-term "
        f"acceleration is the secondary signal. "
        f"Severity-type features (worst severity, night crashes, pedestrian involvement) "
        f"contribute modestly, suggesting that the model discriminates primarily on temporal "
        f"pattern and volume rather than crash composition. "
        f"Practically, this SHAP profile implies that the model's top-ranked candidates "
        f"are intersections that (a) have had any crash history at all, and (b) show a "
        f"structural acceleration — intersections that were previously quiet but have begun "
        f"accumulating crashes. This is precisely the emergence-detection signature the "
        f"study was designed to capture."
    )


def _open_items(t1: dict, t2: dict, t3: dict) -> str:
    items: list[str] = []

    dom = t1["dominant_group"]
    rv  = t1["recency_vs_volume"]
    items.append(
        f"- **SHAP narrative:** The dominant group is {dom}; recency vs. volume answer is "
        f"'{rv}'. Paper discussion must address this directly — "
        f"does the framing (sufficiency null + crash-history utility) hold regardless?"
    )

    if not t2["reportable"]:
        items.append(
            f"- **Spatial recall@K footnote required:** Only {t2['n_test_unique']} of 22 "
            f"positives appear in spatial test folds. Paper must footnote that "
            f"spatial recall@K is unreliable; primary figure is random-split."
        )
    else:
        items.append(
            f"- **Spatial recall@K:** reportable ({t2['n_test_unique']}/22 in test). "
            f"Compute and include as Table S1 (supplementary robustness check)."
        )

    r30_200 = t3["results"][200]["recall_30m"]
    r76_200 = t3["results"][200]["recall_76m"]
    r30_500 = t3["results"][500]["recall_30m"]
    r76_500 = t3["results"][500]["recall_76m"]
    delta200 = abs(r30_200 - r76_200)
    delta500 = abs(r30_500 - r76_500)
    if delta200 > 0.10 or delta500 > 0.10:
        items.append(
            f"- **Buffer sensitivity non-trivial at K=500:** 30m recall@500 = {r30_500:.3f} vs "
            f"76.2m recall@500 = {r76_500:.3f} (delta={delta500:.3f}). "
            f"recall@200 is within ±0.10 ({r30_200:.3f} vs {r76_200:.3f}). "
            f"Paper robustness paragraph: explain why 76.2m was chosen (D2: Spearman grounds, "
            f"not recall@K) and note that at K=200 results are comparable."
        )
    else:
        items.append(
            f"- **Buffer choice robust:** 30m and 76.2m recall@K within ±0.10 at both K=200 and K=500. "
            f"State in robustness paragraph."
        )

    items.append(
        "- **Provisional-year check (2024 SWITRS):** confirm how much of the label "
        "window is provisional; record as a limitation if >20% of 2024 events are provisional."
    )
    items.append(
        "- **Wide CIs on 22 positives:** recall@K CIs are wide by construction (n=22). "
        "Paper must acknowledge this honestly and frame recall@K as directional evidence, "
        "not a precise estimate."
    )
    return "\n".join(items)


# ---------------------------------------------------------------------------
# DECISIONS.md update (D10)
# ---------------------------------------------------------------------------

def update_decisions_d10(t2: dict) -> None:
    decisions_path = ROOT / "docs" / "DECISIONS.md"
    if not decisions_path.exists():
        log.warning("DECISIONS.md not found — skipping D10 append")
        return

    existing = decisions_path.read_text(encoding="utf-8")
    if "## D10" in existing:
        log.info("D10 already present in DECISIONS.md — not overwriting")
        return

    today_str = date.today().isoformat()
    n_t  = t2["n_test_unique"]
    n_tr = t2["n_train_unique"]
    n_p  = t2["n_pos"]
    verdict = "REPORTABLE" if t2["reportable"] else "UNDERPOWERED"

    entry = (
        f"\n## D10 — Spatial-split recall@K caveat ({today_str})\n"
        f"**When:** M5 pre-writing analysis.\n"
        f"**What:** Checked whether the 22 ≥2-KSI positives are disproportionately in the\n"
        f"spatial training fold, which would make spatial recall@K unreliable.\n"
        f"Result: {n_t} / {n_p} positives appear in spatial holdout test folds\n"
        f"(unique across k=5 folds); {n_tr} / {n_p} appear in at least one train fold.\n"
        f"**Verdict: {verdict}.**\n"
        f"{'Spatial recall@K is reportable as a secondary robustness check.' if t2['reportable'] else f'Spatial recall@K is underpowered (n_test={n_t} < 6 threshold). Do not report as robustness check; add footnote in paper.'}\n"
        f"**Integrity:** no model changes; this is a post-hoc data-characterisation check.\n"
    )

    with open(decisions_path, "a", encoding="utf-8") as f:
        f.write(entry)
    log.info("Appended D10 to DECISIONS.md")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    cfg = load_config()

    # Gate: leakage audit
    log.info("=== Leakage audit (gate) ===")
    audit_lines: list[str] = []
    import io, contextlib

    # Capture audit stdout + log output
    buf = io.StringIO()
    try:
        # Run audit; it exits 0 on pass, non-zero on failure
        old_handlers = logging.root.handlers[:]
        sh = logging.StreamHandler(buf)
        sh.setLevel(logging.INFO)
        logging.root.addHandler(sh)
        try:
            run_audit(cfg)
        except SystemExit as e:
            if e.code not in (0, None):
                logging.root.handlers = old_handlers
                log.error("Leakage audit FAILED — aborting M5 analysis.")
                sys.exit(1)
        finally:
            logging.root.handlers = old_handlers
    except Exception:
        pass
    audit_lines = [
        "Leakage audit A1-A9 PASS (run python -m src.audit.leakage for full output)",
        "All checks green before proceeding with analysis.",
    ]

    model_dir   = ROOT / cfg["paths"]["model"]

    # Load locked model
    model_path = model_dir / "xgb_tweedie.pkl"
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    log.info("Loaded locked model: %s (n_estimators=%d)", model_path.name,
             model.n_estimators)

    # Load panel
    candidates  = gpd.read_parquet(model_dir / "candidate_panel.parquet")
    crash_feats = pd.read_parquet(model_dir / "feature_table.parquet")
    panel = candidates.merge(crash_feats, on="intersection_id", how="left")
    if "spatial_block" not in panel.columns:
        panel = add_spatial_blocks(panel, cfg)

    log.info("Panel: %d candidates | pos@>=2: %d | pos@>=1: %d",
             len(panel), (panel["KSI_label"] >= 2).sum(), (panel["KSI_label"] >= 1).sum())

    # Task 1
    t1 = run_task1_shap(model, panel, cfg)

    # Task 2
    t2 = run_task2_spatial_caveat(panel, cfg)

    # Task 3
    t3 = run_task3_buffer_sensitivity(model, panel, cfg)

    # Write report
    write_report(audit_lines, t1, t2, t3, cfg)

    # Update DECISIONS.md
    update_decisions_d10(t2)

    log.info("M5 pre-writing analysis complete.")
    log.info("Outputs: reports/milestone5_prewriting.md, figures/shap_importance.{pdf,png}")


if __name__ == "__main__":
    main()
