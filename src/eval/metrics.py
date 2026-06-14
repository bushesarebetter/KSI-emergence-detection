"""Evaluation metrics with bootstrap confidence intervals.

Primary metric: AUPRC (area under precision-recall curve).
Also: AUROC, recall@K, precision@K for K in recall_at_k config list.
Bootstrap CIs via percentile method (1000 resamples, configurable).
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

log = logging.getLogger(__name__)


def recall_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> float:
    """Fraction of positives captured in top-k scored candidates."""
    top_k = np.argsort(scores)[::-1][:k]
    return float(y_true[top_k].sum() / max(y_true.sum(), 1))


def precision_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> float:
    """Fraction of top-k scored candidates that are positive."""
    top_k = np.argsort(scores)[::-1][:k]
    return float(y_true[top_k].mean())


def compute_metrics(
    y_true: np.ndarray,
    scores: np.ndarray,
    k_values: list[int],
) -> dict[str, float]:
    """Point-estimate metrics dict."""
    n_pos = int(y_true.sum())
    if n_pos == 0:
        log.warning("No positive labels in this split — metrics undefined.")
        return {m: float("nan") for m in _metric_names(k_values)}

    result = {
        "auprc": float(average_precision_score(y_true, scores)),
        "auroc": float(roc_auc_score(y_true, scores)),
    }
    for k in k_values:
        result[f"recall@{k}"] = recall_at_k(y_true, scores, k)
        result[f"precision@{k}"] = precision_at_k(y_true, scores, k)
    return result


def _metric_names(k_values: list[int]) -> list[str]:
    names = ["auprc", "auroc"]
    for k in k_values:
        names += [f"recall@{k}", f"precision@{k}"]
    return names


def bootstrap_ci(
    y_true: np.ndarray,
    scores: np.ndarray,
    k_values: list[int],
    n_resamples: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict[str, dict[str, float]]:
    """Bootstrap 95% CIs for all metrics.

    Returns dict metric_name -> {"mean": ..., "lo": ..., "hi": ...}.
    """
    rng = np.random.default_rng(seed)
    n = len(y_true)
    boot_records: list[dict[str, float]] = []

    for _ in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        yt = y_true[idx]
        sc = scores[idx]
        if yt.sum() == 0 or yt.sum() == n:
            continue  # skip degenerate resamples
        boot_records.append(compute_metrics(yt, sc, k_values))

    if not boot_records:
        return {m: {"mean": float("nan"), "lo": float("nan"), "hi": float("nan")}
                for m in _metric_names(k_values)}

    boot_df = pd.DataFrame(boot_records)
    lo, hi = alpha / 2, 1 - alpha / 2
    ci: dict[str, dict[str, float]] = {}
    for col in boot_df.columns:
        vals = boot_df[col].dropna().values
        ci[col] = {
            "mean": float(np.mean(vals)),
            "lo": float(np.percentile(vals, lo * 100)),
            "hi": float(np.percentile(vals, hi * 100)),
        }
    return ci


def format_metrics_table(
    point: dict[str, float],
    ci: dict[str, dict[str, float]],
    split_name: str,
) -> str:
    """Return a markdown table string."""
    lines = [
        f"### {split_name}",
        "",
        "| Metric | Point est. | 95% CI lower | 95% CI upper |",
        "| ------ | ---------- | ------------ | ------------ |",
    ]
    for metric, val in point.items():
        cival = ci.get(metric, {})
        lo = cival.get("lo", float("nan"))
        hi = cival.get("hi", float("nan"))
        lines.append(f"| {metric} | {val:.4f} | {lo:.4f} | {hi:.4f} |")
    lines.append("")
    return "\n".join(lines)
