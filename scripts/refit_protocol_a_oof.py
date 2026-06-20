"""Genuinely held-out re-test of Protocol A: does infrastructure data help?

src/model/fit_frozen.py fits each feature set (A crash-only, B +geometry,
C +signals, D +all-infra) on the full panel, which is correct for production
scoring. This script redoes the same 4-set comparison with genuine
out-of-fold scoring, the same evaluation standard used in
scripts/refit_verified_run_oof.py, so the infrastructure-vs-crash-only
comparison rests on a genuinely held-out evaluation.

Frozen hyperparameters (tuned once on Set A via nested CV, per the existing
Protocol A design) are reused unchanged across all 4 sets -- only the
fit-and-score step is replaced with OOF.
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
from src.utils import load_config, project_root

ROOT = project_root()
MODEL_DIR = ROOT / "data" / "model"
VERIFIED_DIR = MODEL_DIR / "verified_run"
RESULTS_DIR = ROOT / "results"
N_FOLDS = 5
KS = [50, 100, 200, 500, 1000]


def load_frozen() -> dict:
    f = json.loads((MODEL_DIR / "frozen_params.json").read_text())["frozen"]
    return {
        "objective": f["objective"],
        "tweedie_variance_power": float(f["tweedie_variance_power"]),
        "max_depth": int(f["max_depth"]),
        "learning_rate": float(f["learning_rate"]),
        "n_estimators": int(f["n_estimators"]),
        "reg_alpha": float(f["reg_alpha"]),
        "reg_lambda": float(f["reg_lambda"]),
        "min_child_weight": int(f["min_child_weight"]),
        "subsample": float(f["subsample"]),
        "colsample_bytree": float(f["colsample_bytree"]),
        "random_state": int(f["random_state"]),
        "verbosity": 0,
    }


def build_feature_sets(cfg: dict, panel: pd.DataFrame) -> list[tuple[str, list[str]]]:
    fg = cfg["feature_groups"]
    base = list(fg["crash_only"])
    geom = [f for f in fg["geometry"] if f not in ("lane_count_missing", "approach_asymmetry") and f in panel.columns]
    ctrl = [f for f in fg["control"] if f in panel.columns]
    road = [f for f in fg["roadway"] if f in panel.columns]
    at_ = [f for f in fg["active_transport"] if f in panel.columns]
    terr = [f for f in fg["terrain"] if f in panel.columns]

    def usable(cols):
        return [c for c in cols if panel[c].var() > 0]

    return [
        ("A_crash_only", usable(base)),
        ("B_road_geometry", usable(base + geom + road)),
        ("C_signals", usable(base + ctrl)),
        ("D_all_infra", usable(base + geom + ctrl + road + at_ + terr)),
    ]


def oof_predict(X: np.ndarray, y: np.ndarray, groups: np.ndarray | None, params: dict, mode: str) -> np.ndarray:
    n = len(y)
    oof = np.full(n, np.nan)
    if mode == "random":
        y_strat = (y >= 2).astype(int)
        splits = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=42).split(X, y_strat)
    else:
        splits = GroupKFold(n_splits=N_FOLDS).split(X, y, groups=groups)
    for train_idx, test_idx in splits:
        model = xgb.XGBRegressor(**params)
        model.fit(X[train_idx], y[train_idx])
        oof[test_idx] = model.predict(X[test_idx])
    assert not np.isnan(oof).any()
    return oof


def recall_at_k(scores: np.ndarray, y: np.ndarray, k: int, thr: int) -> tuple[int, int]:
    order = np.argsort(-scores)
    ranked = y[order]
    n_pos = int((ranked >= thr).sum())
    hits = int((ranked[:k] >= thr).sum())
    return hits, n_pos


def main() -> None:
    cfg = load_config()
    panel = __import__("geopandas").read_parquet(VERIFIED_DIR / "candidate_panel.parquet")
    crash_feats = pd.read_parquet(VERIFIED_DIR / "feature_table.parquet")
    infra_feats = pd.read_parquet(MODEL_DIR / "infra_features.parquet")
    panel = panel.merge(crash_feats, on="intersection_id", how="left")
    panel = panel.merge(infra_feats, on="intersection_id", how="left")
    panel = add_spatial_blocks(panel, cfg)

    y = panel["KSI_label"].values.astype(float)
    groups = panel["spatial_block"].values
    n_total = len(panel)
    params = load_frozen()
    feature_sets = build_feature_sets(cfg, panel)

    print(f"Panel: {n_total} | pos>=2: {int((y>=2).sum())} | pos>=1: {int((y>=1).sum())}")
    print("Frozen params (unchanged across all sets, per Protocol A):", params)

    results = {}
    for set_name, cols in feature_sets:
        print(f"\n=== {set_name}: {len(cols)} features ===")
        X = panel[cols].fillna(0.0).values.astype(float)
        oof_random = oof_predict(X, y, None, params, "random")
        oof_spatial = oof_predict(X, y, groups, params, "spatial")

        sp_r = stats.spearmanr(oof_random, y).correlation
        sp_s = stats.spearmanr(oof_spatial, y).correlation
        h500_r, npos = recall_at_k(oof_random, y, 500, 2)
        h500_s, _ = recall_at_k(oof_spatial, y, 500, 2)
        print(f"  Spearman OOF: random={sp_r:.4f} spatial={sp_s:.4f}")
        print(f"  recall@500 (>=2): random={h500_r}/{npos} spatial={h500_s}/{npos}")

        results[set_name] = {
            "n_features": len(cols),
            "features": cols,
            "spearman_oof_random": round(float(sp_r), 4),
            "spearman_oof_spatial": round(float(sp_s), 4),
            "recall_at_500_ge2_random": f"{h500_r}/{npos}",
            "recall_at_500_ge2_spatial": f"{h500_s}/{npos}",
        }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "protocol_a_oof_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out_path}")

    print("\n" + "=" * 70)
    print("PROTOCOL A — HONEST (OOF) SUFFICIENCY-NULL RE-TEST")
    print("=" * 70)
    base_sp = results["A_crash_only"]["spearman_oof_random"]
    for name, r in results.items():
        delta = r["spearman_oof_random"] - base_sp
        print(f"  {name:<18} random_rho={r['spearman_oof_random']:.4f}  "
              f"spatial_rho={r['spearman_oof_spatial']:.4f}  delta_vs_A={delta:+.4f}")


if __name__ == "__main__":
    main()
