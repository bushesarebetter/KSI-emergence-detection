"""Frequency baseline evaluation.

Baseline score = feature-window KSI count (KSI_feat) as a ranking score.
Ties broken by a Theil-Sen trend proxy: sign of (KSI_feat - expected_mean)
— trivially equivalent to KSI_feat here since counts are integers. If ties
are rare (integer counts with few unique values), no tie-breaking is needed
for AUPRC/AUROC; recall@K might be tie-sensitive so we add a tiny jitter
from the RNG seeded with the project seed.

Evaluated under:
  (a) spatial-block 5-fold CV (score = KSI_feat, aggregate metrics averaged)
  (b) random 80/20 stratified split

Outputs metric table to stdout AND reports/milestone1_baseline.md.

Run via:  python -m src.eval.baseline
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from src.eval.metrics import bootstrap_ci, compute_metrics, format_metrics_table
from src.eval.splitter import add_spatial_blocks, random_split, spatial_block_kfold
from src.utils import load_config, project_root

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def _baseline_score(
    candidates: pd.DataFrame, seed: int
) -> np.ndarray:
    """KSI_feat with small uniform jitter to break integer ties."""
    rng = np.random.default_rng(seed)
    scores = candidates["KSI_feat"].values.astype(float)
    jitter = rng.uniform(0, 1e-6, size=len(scores))
    return scores + jitter


def evaluate_random(
    candidates: pd.DataFrame, cfg: dict
) -> tuple[dict, dict]:
    seed = cfg["project"]["rng_seed"]
    k_values = cfg["evaluation"]["recall_at_k"]
    n_boot = cfg["evaluation"]["bootstrap_resamples"]
    scores = _baseline_score(candidates, seed)
    train_idx, test_idx = random_split(candidates, cfg)
    y_test = candidates["y"].values[test_idx]
    s_test = scores[test_idx]
    point = compute_metrics(y_test, s_test, k_values)
    ci = bootstrap_ci(y_test, s_test, k_values, n_resamples=n_boot, seed=seed)
    log.info("Random split — test nodes: %d, positives: %d", len(test_idx), int(y_test.sum()))
    return point, ci


def evaluate_spatial(
    candidates: pd.DataFrame, cfg: dict
) -> tuple[dict, dict]:
    """Spatial-block k-fold: average metrics across folds."""
    seed = cfg["project"]["rng_seed"]
    k_values = cfg["evaluation"]["recall_at_k"]
    n_boot = cfg["evaluation"]["bootstrap_resamples"]
    scores = _baseline_score(candidates, seed)
    y = candidates["y"].values

    fold_metrics: list[dict] = []
    for fold_i, (train_idx, test_idx) in enumerate(spatial_block_kfold(candidates, cfg)):
        y_test = y[test_idx]
        s_test = scores[test_idx]
        if y_test.sum() == 0:
            log.warning("Fold %d has 0 positives — skipping", fold_i)
            continue
        m = compute_metrics(y_test, s_test, k_values)
        log.info(
            "Spatial fold %d — test nodes: %d, positives: %d, AUPRC=%.4f",
            fold_i, len(test_idx), int(y_test.sum()), m["auprc"],
        )
        fold_metrics.append(m)

    if not fold_metrics:
        return {}, {}

    agg = {}
    for key in fold_metrics[0]:
        agg[key] = float(np.mean([m[key] for m in fold_metrics]))

    # Bootstrap CI over pooled test predictions (concatenate all folds)
    all_y, all_s = [], []
    for _, test_idx in spatial_block_kfold(candidates, cfg):
        all_y.append(y[test_idx])
        all_s.append(scores[test_idx])
    all_y_arr = np.concatenate(all_y)
    all_s_arr = np.concatenate(all_s)
    ci = bootstrap_ci(all_y_arr, all_s_arr, k_values, n_resamples=n_boot, seed=seed)

    return agg, ci


def main() -> None:
    cfg = load_config()
    model_dir = project_root() / cfg["paths"]["model"]
    reports_dir = project_root() / cfg["paths"]["reports"]
    reports_dir.mkdir(parents=True, exist_ok=True)

    candidates = gpd.read_parquet(model_dir / "candidate_panel.parquet")
    log.info("Loaded candidate panel: %d rows, %d positives", len(candidates), candidates["y"].sum())

    # Add spatial blocks if not already present
    if "spatial_block" not in candidates.columns:
        candidates = add_spatial_blocks(candidates, cfg)
        candidates.to_parquet(model_dir / "candidate_panel.parquet", index=False)

    log.info("=== Random split evaluation ===")
    rand_point, rand_ci = evaluate_random(candidates, cfg)

    log.info("=== Spatial-block evaluation ===")
    spat_point, spat_ci = evaluate_spatial(candidates, cfg)

    # Print tables
    rand_table = format_metrics_table(rand_point, rand_ci, "Random split (80/20 stratified)")
    spat_table = format_metrics_table(spat_point, spat_ci, "Spatial-block 5-fold CV")

    print("\n" + "=" * 70)
    print("FREQUENCY BASELINE -- KSI_feat ranking")
    print("=" * 70)
    print()
    print(rand_table)
    print(spat_table)

    # Gap analysis
    auprc_gap = rand_point.get("auprc", float("nan")) - spat_point.get("auprc", float("nan"))
    r100_gap = rand_point.get("recall@100", float("nan")) - spat_point.get("recall@100", float("nan"))
    print(f"Spatial-autocorrelation inflation (random - spatial):")
    print(f"  AUPRC gap:      {auprc_gap:+.4f}")
    print(f"  recall@100 gap: {r100_gap:+.4f}")
    print()

    # Write to reports
    out_path = reports_dir / "milestone1_baseline.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Milestone 1 -- Frequency Baseline Metrics\n\n")
        f.write(rand_table + "\n")
        f.write(spat_table + "\n")
        f.write("## Spatial-autocorrelation gap\n\n")
        f.write(f"| Metric | Random | Spatial-block | Gap (R-S) |\n")
        f.write(f"| ------ | ------ | ------------- | --------- |\n")
        f.write(
            f"| AUPRC | {rand_point.get('auprc', float('nan')):.4f} | "
            f"{spat_point.get('auprc', float('nan')):.4f} | {auprc_gap:+.4f} |\n"
        )
        f.write(
            f"| recall@100 | {rand_point.get('recall@100', float('nan')):.4f} | "
            f"{spat_point.get('recall@100', float('nan')):.4f} | {r100_gap:+.4f} |\n"
        )
    log.info("Wrote baseline metrics to %s", out_path)


if __name__ == "__main__":
    main()
