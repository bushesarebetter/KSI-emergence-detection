"""Milestone 2 evaluation: count metrics + ranked readouts + buffer sweep.

Count metrics (Tweedie primary):
  - Tweedie deviance, Poisson deviance
  - Spearman rho (predicted rank vs actual count)
  - Decile calibration: mean predicted vs mean actual in deciles of predicted score

Ranked readouts (binarised from predicted ranking):
  - AUPRC, recall@K, precision@K, AUROC for binary >=2 and >=1 thresholds

Buffer diagnostic:
  Re-run label construction at radii [30, 50, 76.2, 100] m and
  report candidate count, positives@>=1, positives@>=2, count distribution.

All with bootstrap 95% CIs under random and spatial-block splits.
Reports lift over adapted persistence baseline.

Run via:  python -m src.eval.milestone2
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial import cKDTree

from src.eval.metrics import bootstrap_ci, compute_metrics, format_metrics_table
from src.eval.splitter import add_spatial_blocks, random_split, spatial_block_kfold
from src.model.fit import _tweedie_deviance, FEATURE_COLS, persistence_baseline_scores
from src.utils import load_config, project_root, buffer_feet

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Count metrics
# ---------------------------------------------------------------------------

def count_metrics(y_true: np.ndarray, y_pred: np.ndarray, p: float = 1.3) -> dict:
    """Tweedie + Poisson deviance and Spearman rho."""
    tw_dev = _tweedie_deviance(y_true, y_pred, p)
    pois_dev = _tweedie_deviance(y_true, y_pred, 1.0)
    spearman, _ = stats.spearmanr(y_pred, y_true)
    return {
        "tweedie_deviance": float(tw_dev),
        "poisson_deviance": float(pois_dev),
        "spearman_rho": float(spearman) if not np.isnan(spearman) else 0.0,
    }


def decile_calibration(y_true: np.ndarray, y_pred: np.ndarray) -> pd.DataFrame:
    """Mean predicted vs mean actual in 10 equal-width prediction deciles."""
    n = len(y_true)
    decile_idx = np.argsort(y_pred)
    decile_size = n // 10
    rows = []
    for i in range(10):
        start = i * decile_size
        end = start + decile_size if i < 9 else n
        idx = decile_idx[start:end]
        rows.append({
            "decile": i + 1,
            "mean_pred": float(y_pred[idx].mean()),
            "mean_actual": float(y_true[idx].mean()),
            "n": len(idx),
        })
    return pd.DataFrame(rows)


def bootstrap_count_ci(
    y_true: np.ndarray, y_pred: np.ndarray,
    n_resamples: int = 1000, seed: int = 42, p: float = 1.3,
) -> dict:
    rng = np.random.default_rng(seed)
    records = []
    n = len(y_true)
    for _ in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        records.append(count_metrics(y_true[idx], y_pred[idx], p))
    df = pd.DataFrame(records)
    ci = {}
    for col in df.columns:
        vals = df[col].dropna().values
        ci[col] = {"mean": float(np.mean(vals)),
                   "lo": float(np.percentile(vals, 2.5)),
                   "hi": float(np.percentile(vals, 97.5))}
    return ci


# ---------------------------------------------------------------------------
# Full evaluation for one model
# ---------------------------------------------------------------------------

def evaluate_model(
    scores: np.ndarray,
    panel: pd.DataFrame,
    cfg: dict,
    model_name: str,
) -> dict:
    """Evaluate under random and spatial-block splits at thresholds >=1 and >=2."""
    y_count = panel["KSI_label"].values.astype(float)
    seed    = cfg["project"]["rng_seed"]
    k_vals  = cfg["evaluation"]["recall_at_k"]
    n_boot  = cfg["evaluation"]["bootstrap_resamples"]
    p       = cfg["target"]["tweedie_variance_power"]
    thrs    = cfg["target"]["binary_readout_thresholds"]
    out     = {}

    # ---- Random split -------------------------------------------------------
    _, test_idx = random_split(panel, cfg)
    y_tc  = y_count[test_idx]
    s_t   = scores[test_idx]
    for thr in thrs:
        y_tb = (y_tc >= thr).astype(int)
        pc   = count_metrics(y_tc, s_t, p)
        pr   = compute_metrics(y_tb, s_t, k_vals)
        cc   = bootstrap_count_ci(y_tc, s_t, n_resamples=n_boot, seed=seed, p=p)
        cr   = bootstrap_ci(y_tb, s_t, k_vals, n_resamples=n_boot, seed=seed)
        out[f"random_thr{thr}"] = {"point": {**pc, **pr}, "ci": {**cc, **cr}}
        log.info("%s [random >=% d] test=%d pos=%d spearman=%.3f auprc=%.4f",
                 model_name, thr, len(test_idx), int(y_tb.sum()),
                 pc["spearman_rho"], pr.get("auprc", float("nan")))

    # ---- Spatial-block k-fold ----------------------------------------------
    for thr in thrs:
        y_bin = (y_count >= thr).astype(int)
        fold_pts: list[dict] = []
        all_y_parts:  list[np.ndarray] = []
        all_s_parts:  list[np.ndarray] = []
        all_yc_parts: list[np.ndarray] = []
        for _, ti in spatial_block_kfold(panel, cfg):
            yb = y_bin[ti]; sc = scores[ti]; yc = y_count[ti]
            if yb.sum() == 0:
                continue
            fold_pts.append({**count_metrics(yc, sc, p), **compute_metrics(yb, sc, k_vals)})
            all_y_parts.append(yb)
            all_s_parts.append(sc)
            all_yc_parts.append(yc)

        if fold_pts:
            agg  = {k: float(np.mean([f[k] for f in fold_pts])) for k in fold_pts[0]}
            ay   = np.concatenate(all_y_parts)
            as_  = np.concatenate(all_s_parts)
            ayc  = np.concatenate(all_yc_parts)
            cc   = bootstrap_count_ci(ayc, as_, n_resamples=n_boot, seed=seed, p=p)
            cr   = bootstrap_ci(ay, as_, k_vals, n_resamples=n_boot, seed=seed)
            out[f"spatial_thr{thr}"] = {"point": agg, "ci": {**cc, **cr}}
            log.info("%s [spatial >=%d] folds=%d spearman=%.3f auprc=%.4f",
                     model_name, thr, len(fold_pts),
                     agg.get("spearman_rho", float("nan")),
                     agg.get("auprc", float("nan")))
        else:
            out[f"spatial_thr{thr}"] = {"point": {}, "ci": {}}

    return out


# ---------------------------------------------------------------------------
# Buffer sweep diagnostic
# ---------------------------------------------------------------------------

def _snap_label_crashes_at_radius(
    ksi_crashes: gpd.GeoDataFrame,
    nodes: gpd.GeoDataFrame,
    buf_ft: float,
    mode: str = "nearest_within_buffer",
) -> pd.Series:
    """Return KSI_label counts per intersection_id at a given buffer."""
    node_coords = np.column_stack([nodes.geometry.x, nodes.geometry.y])
    crash_coords = np.column_stack([ksi_crashes.geometry.x, ksi_crashes.geometry.y])
    tree = cKDTree(node_coords)
    dists, idxs = tree.query(crash_coords, k=1, workers=-1)
    within = dists <= buf_ft
    assignments = pd.DataFrame({
        "intersection_id": nodes.iloc[idxs[within]]["intersection_id"].values,
    })
    return assignments.groupby("intersection_id").size().rename("KSI_label")


def buffer_sweep(cfg: dict) -> pd.DataFrame:
    """Re-run label construction at each sweep radius; return diagnostic table."""
    proc = project_root() / cfg["paths"]["proc"]
    nodes = gpd.read_parquet(proc / "nodes_spine_2230.parquet")
    ksi_label = gpd.read_parquet(proc / "ksi_label_crashes.parquet")
    ksi_label = ksi_label.to_crs(cfg["crs"]["analysis"])

    # Candidate eligibility is based on the PRIMARY buffer; reuse same candidate set
    candidates_base = gpd.read_parquet(project_root() / cfg["paths"]["model"] / "candidate_panel.parquet")
    cand_ids = set(candidates_base["intersection_id"])
    nodes_cand = nodes[nodes["intersection_id"].isin(cand_ids)].reset_index(drop=True)

    # Unit conversion: 1 US survey ft = 1200/3937 m
    m_per_ft = 1200.0 / 3937.0

    rows = []
    for r_m in cfg["buffer_sweep"]["radii_m"]:
        buf_ft_r = r_m / m_per_ft
        label_counts = _snap_label_crashes_at_radius(ksi_label, nodes_cand, buf_ft_r)
        label_series = nodes_cand["intersection_id"].map(label_counts).fillna(0).astype(int)
        pos1 = int((label_series >= 1).sum())
        pos2 = int((label_series >= 2).sum())
        dist_0 = int((label_series == 0).sum())
        dist_1 = int((label_series == 1).sum())
        dist_2 = int((label_series == 2).sum())
        dist_3p = int((label_series >= 3).sum())
        rows.append({
            "radius_m": r_m,
            "buf_ft": round(buf_ft_r, 2),
            "n_candidates": len(nodes_cand),
            "positives_ge1": pos1,
            "positives_ge2": pos2,
            "dist_0": dist_0,
            "dist_1": dist_1,
            "dist_2": dist_2,
            "dist_3p": dist_3p,
        })
        log.info(
            "Buffer %.1fm (%.2fft): pos@>=1=%d, pos@>=2=%d",
            r_m, buf_ft_r, pos1, pos2,
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Lift table
# ---------------------------------------------------------------------------

def _lift_table(model_results: dict, baseline_key: str, models: list[str]) -> str:
    """Build markdown lift-over-baseline table for key metrics."""
    lines = [
        "| Model | Split | Spearman rho | AUPRC (>=2) | recall@100 (>=2) | AUPRC (>=1) |",
        "| ----- | ----- | ------------ | ----------- | ---------------- | ----------- |",
    ]
    base2 = model_results.get(baseline_key, {})
    for m_name in models:
        m_res = model_results.get(m_name, {})
        for split_key, split_label in [
            ("random_thr2", "random"), ("spatial_thr2", "spatial")
        ]:
            p2 = m_res.get(split_key, {}).get("point", {})
            b2 = base2.get(split_key, {}).get("point", {})
            sp = p2.get("spearman_rho", float("nan"))
            auprc2 = p2.get("auprc", float("nan"))
            r100_2 = p2.get("recall@100", float("nan"))
            # >=1 readout
            split_key1 = split_key.replace("thr2", "thr1")
            p1 = m_res.get(split_key1, {}).get("point", {})
            auprc1 = p1.get("auprc", float("nan"))
            lines.append(
                f"| {m_name} | {split_label} | {sp:.3f} | {auprc2:.4f} | {r100_2:.4f} | {auprc1:.4f} |"
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    cfg = load_config()
    model_dir = project_root() / cfg["paths"]["model"]
    reports_dir = project_root() / cfg["paths"]["reports"]
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Load
    candidates = gpd.read_parquet(model_dir / "candidate_panel.parquet")
    feat_table = pd.read_parquet(model_dir / "feature_table.parquet")
    panel = candidates.merge(feat_table, on="intersection_id", how="left")
    if "spatial_block" not in panel.columns:
        panel = add_spatial_blocks(panel, cfg)

    scores_df = pd.read_parquet(model_dir / "model_scores.parquet")
    panel = panel.merge(scores_df[["intersection_id", "baseline_score", "logistic_score",
                                   "xgb_binary_score", "xgb_tweedie_score"]],
                        on="intersection_id", how="left")

    log.info("Panel: %d rows, %d pos@>=2, %d pos@>=1",
             len(panel), (panel["KSI_label"] >= 2).sum(), (panel["KSI_label"] >= 1).sum())

    models_map = {
        "baseline": panel["baseline_score"].values,
        "logistic": panel["logistic_score"].values,
        "xgb_binary": panel["xgb_binary_score"].values,
        "xgb_tweedie": panel["xgb_tweedie_score"].values,
    }

    all_results = {}
    for model_name, scores in models_map.items():
        log.info("=== Evaluating %s ===", model_name)
        all_results[model_name] = evaluate_model(scores, panel, cfg, model_name)

    # Buffer sweep
    log.info("=== Buffer sweep diagnostic ===")
    sweep_df = buffer_sweep(cfg)
    sweep_path = reports_dir / "buffer_sweep.csv"
    sweep_df.to_csv(sweep_path, index=False)
    log.info("Buffer sweep:\n%s", sweep_df.to_string(index=False))

    # Write results JSON
    import json
    results_safe = {}
    for mname, mres in all_results.items():
        results_safe[mname] = {}
        for split_key, split_val in mres.items():
            results_safe[mname][split_key] = {
                "point": {k: (float(v) if not (v != v) else None) for k, v in split_val.get("point", {}).items()},
            }
    with open(model_dir / "milestone2_results.json", "w") as f:
        json.dump(results_safe, f, indent=2)

    # Print lift table
    lift = _lift_table(all_results, "baseline", list(models_map.keys()))
    print("\n" + "=" * 80)
    print("MILESTONE 2 -- Model comparison vs persistence baseline")
    print("=" * 80)
    print()
    print(lift)
    print()
    print("Buffer sweep:")
    print(sweep_df.to_string(index=False))

    log.info("Evaluation complete. Results in %s", reports_dir)


if __name__ == "__main__":
    main()
