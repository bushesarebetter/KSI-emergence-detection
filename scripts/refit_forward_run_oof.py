"""Genuinely held-out (out-of-fold) refit of the FORWARD run model.

Same evaluation standard as the verified run (see scripts/refit_verified_run_oof.py).
The forward-run frozen_scores.parquet (data/model/forward_run/) is the model
currently live on the dashboard, fit on the full candidate panel, which is
correct for production scoring. This script provides the genuinely held-out
performance evaluation that production scoring alone doesn't give you.

This script applies the same approach: genuine 5-fold OOF scoring, crash-only
features, using the SAME frozen Protocol-A hyperparameters from
data/model/frozen_params.json that every other OOF script in this project uses
(refit_verified_run_oof.py, refit_protocol_a_oof.py, refit_protocol_a_forward_oof.py,
fit_frozen.py) -- loaded directly from that file rather than hardcoded, so this
can't silently drift from the rest of the project if frozen_params.json is ever
regenerated. (D16: this script previously hardcoded a third, different
hyperparameter set that matched neither frozen_params.json nor the bake-off's
freshly-tuned model it claimed to mirror; see docs/DECISIONS.md D16.)

NOTE: the forward run's label window (2025-2027) is only partially complete
(2024 done; 2025-2026 pending), so the numbers here are provisional and will
keep changing as more 2025/2026 SWITRS data lands. That's a data-completeness
limitation, not something OOF scoring can fix.

Outputs:
  data/model/forward_run/oof_scores.parquet
  results/oof_forward_run_results.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy import stats
from sklearn.model_selection import GroupKFold, StratifiedKFold

from src.eval.splitter import add_spatial_blocks
from src.model.fit import persistence_baseline_scores
from src.utils import load_config, project_root

ROOT = project_root()
MODEL_DIR = ROOT / "data" / "model"
FORWARD_DIR = MODEL_DIR / "forward_run"
RESULTS_DIR = ROOT / "results"

N_FOLDS = 5
KS = [50, 100, 200, 500, 1000]
THRESHOLDS = [1, 2]
RNG = np.random.RandomState(42)

def _load_frozen_params() -> dict:
    """Load the same frozen Protocol-A crash-only hyperparameters every other
    OOF script in this project uses, directly from the source file (no hardcoded
    copy that can drift)."""
    raw = json.loads((MODEL_DIR / "frozen_params.json").read_text())["frozen"]
    return {
        "objective": raw["objective"],
        "tweedie_variance_power": float(raw["tweedie_variance_power"]),
        "max_depth": int(raw["max_depth"]),
        "learning_rate": float(raw["learning_rate"]),
        "n_estimators": int(raw["n_estimators"]),
        "reg_alpha": float(raw["reg_alpha"]),
        "reg_lambda": float(raw["reg_lambda"]),
        "min_child_weight": int(raw["min_child_weight"]),
        "subsample": float(raw["subsample"]),
        "colsample_bytree": float(raw["colsample_bytree"]),
        "random_state": 42,
        "verbosity": 0,
    }


TUNED_PARAMS = _load_frozen_params()


def oof_predict(X, y, groups, mode):
    n = len(y)
    oof = np.full(n, np.nan)
    if mode == "random":
        y_strat = (y >= 1).astype(int)  # only 2 positives at >=2 -- stratify on >=1 instead
        splits = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=42).split(X, y_strat)
    else:
        splits = GroupKFold(n_splits=N_FOLDS).split(X, y, groups=groups)
    for train_idx, test_idx in splits:
        model = xgb.XGBRegressor(**TUNED_PARAMS)
        model.fit(X[train_idx], y[train_idx])
        oof[test_idx] = model.predict(X[test_idx])
    assert not np.isnan(oof).any()
    return oof


def bootstrap_ci(label, k, thr, resamples=2000):
    pos = np.where(label >= thr)[0]
    if len(pos) == 0:
        return (0.0, 0.0)
    rs = []
    for _ in range(resamples):
        s = RNG.choice(pos, size=len(pos), replace=True)
        rs.append((s < k).sum() / len(pos))
    return (float(np.percentile(rs, 2.5)), float(np.percentile(rs, 97.5)))


def recall_table(ranked_label, n_total, thr):
    n_pos = int((ranked_label >= thr).sum())
    out = {"n_positives": n_pos}
    for k in KS:
        if k > n_total:
            continue
        hits = int((ranked_label[:k] >= thr).sum())
        recall = hits / n_pos if n_pos else None
        lo, hi = bootstrap_ci(ranked_label, k, thr)
        out[str(k)] = {
            "hits": hits,
            "recall": round(recall, 4) if recall is not None else None,
            "ci95": [round(lo, 4), round(hi, 4)],
        }
    return out


def main():
    import geopandas as gpd

    cfg = load_config()
    panel = gpd.read_parquet(FORWARD_DIR / "candidate_panel.parquet")
    feat = pd.read_parquet(FORWARD_DIR / "feature_table.parquet")
    panel = panel.merge(feat, on="intersection_id", how="left")
    panel = add_spatial_blocks(panel, cfg)

    cols = list(cfg["feature_groups"]["crash_only"])
    X = panel[cols].fillna(0.0).values.astype(float)
    y = panel["KSI_label"].values.astype(float)
    groups = panel["spatial_block"].values
    n_total = len(panel)

    n2 = int((y >= 2).sum())
    n1 = int((y >= 1).sum())
    print(f"Forward-run panel: {n_total} candidates | pos>=2: {n2} (2024 data only -- label window 2025-2027 incomplete) | pos>=1: {n1}")
    print("WARNING: only", n2, "positives at the >=2 threshold -- any recall@K figure there is",
          "extremely noisy and will be superseded once 2025-2026 labels are available.")

    oof_random = oof_predict(X, y, None, "random")
    oof_spatial = oof_predict(X, y, groups, "spatial")
    baseline = persistence_baseline_scores(panel)

    sp_r = stats.spearmanr(oof_random, y).correlation
    sp_s = stats.spearmanr(oof_spatial, y).correlation
    sp_b = stats.spearmanr(baseline, y).correlation
    print(f"Spearman OOF: random={sp_r:.4f} spatial={sp_s:.4f} baseline={sp_b:.4f}")

    out_df = pd.DataFrame({
        "intersection_id": panel["intersection_id"].values,
        "KSI_label": panel["KSI_label"].values,
        "persistence_baseline_score": baseline,
        "oof_score_random": oof_random,
        "oof_score_spatial": oof_spatial,
    })
    out_df.to_parquet(FORWARD_DIR / "oof_scores.parquet", index=False)
    print(f"Wrote {FORWARD_DIR / 'oof_scores.parquet'}")

    results = {
        "label_window_completeness": "2024 only (2025-2026 pending) -- numbers below are PROVISIONAL",
        "n_candidates": n_total,
        "spearman_rho": {
            "random_split_oof": round(float(sp_r), 4),
            "spatial_split_oof": round(float(sp_s), 4),
            "persistence_baseline": round(float(sp_b), 4),
            "old_in_sample_random": 0.0907,
            "old_in_sample_spatial": 0.1007,
        },
    }
    for split_name, scores in [("random", oof_random), ("spatial", oof_spatial), ("persistence_baseline", baseline)]:
        order = np.argsort(-scores)
        ranked = y[order]
        results[split_name] = {f">={thr}": recall_table(ranked, n_total, thr) for thr in THRESHOLDS}

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "oof_forward_run_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"Wrote {out_path}")

    print("\nSUMMARY -- forward run, genuine OOF, recall@500 (>=1 KSI, the only threshold with enough positives to be meaningful):")
    for name in ("random", "spatial", "persistence_baseline"):
        t = results[name][">=1"]["500"]
        print(f"  {name:22s}: {t['hits']}/{results[name]['>=1']['n_positives']} = {t['recall']:.3f}  CI={t['ci95']}")


if __name__ == "__main__":
    main()
