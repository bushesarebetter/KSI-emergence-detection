"""Genuinely held-out re-test of the extended ablation (Groups E-H), now that
Overpass is reachable and a Census API key is available.

Builds Groups E (ADT proxy), F (ACS demographics), G (pedestrian infrastructure),
and H (E+G) on the verified-run candidate set, using the feature-building
functions from scripts/run_extended_ablation.py, then evaluates each with the
same genuine out-of-fold protocol as scripts/refit_protocol_a_oof.py: frozen
Set-A hyperparameters, 5-fold scoring, model never sees a row before scoring it.
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
from scripts.run_extended_ablation import (
    build_group_e, build_group_f, build_group_g,
    GROUP_E_COLS, GROUP_F_COLS, GROUP_G_COLS, CRASH_ONLY_COLS,
)

ROOT = project_root()
MODEL_DIR = ROOT / "data" / "model"
VERIFIED_DIR = MODEL_DIR / "verified_run"
RESULTS_DIR = ROOT / "results"
N_FOLDS = 5


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


def oof_predict(X, y, groups, params, mode):
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


def recall_at_k(scores, y, k, thr):
    order = np.argsort(-scores)
    ranked = y[order]
    n_pos = int((ranked >= thr).sum())
    hits = int((ranked[:k] >= thr).sum())
    return hits, n_pos


def main():
    cfg = load_config()
    panel = __import__("geopandas").read_parquet(VERIFIED_DIR / "candidate_panel.parquet")
    crash_feats = pd.read_parquet(VERIFIED_DIR / "feature_table.parquet")
    infra_feats = pd.read_parquet(MODEL_DIR / "infra_features.parquet")
    panel = panel.merge(crash_feats, on="intersection_id", how="left")
    panel = panel.merge(infra_feats, on="intersection_id", how="left")
    panel = add_spatial_blocks(panel, cfg)

    print("Building Group E (ADT proxy) ...")
    grp_e = build_group_e(panel, infra_feats)
    print("Building Group F (ACS demographics, requires CENSUS_API_KEY) ...")
    grp_f = build_group_f(panel, cfg)
    print("Building Group G (pedestrian infrastructure, Overpass) ...")
    grp_g = build_group_g(panel)

    panel = panel.merge(grp_e, on="intersection_id", how="left")
    panel = panel.merge(grp_g, on="intersection_id", how="left")
    f_available = grp_f is not None
    if f_available:
        panel = panel.merge(grp_f, on="intersection_id", how="left")
    else:
        print("Group F unavailable (no CENSUS_API_KEY or Census API call failed) -- skipping.")

    y = panel["KSI_label"].values.astype(float)
    groups = panel["spatial_block"].values
    n_total = len(panel)
    params = load_frozen()

    feature_sets = {
        "E_adt_proxy": CRASH_ONLY_COLS + GROUP_E_COLS,
        "G_ped_infra": CRASH_ONLY_COLS + GROUP_G_COLS,
        "H_E_plus_G": CRASH_ONLY_COLS + GROUP_E_COLS + GROUP_G_COLS,
    }
    if f_available:
        feature_sets["F_demographics"] = CRASH_ONLY_COLS + GROUP_F_COLS
        feature_sets["I_all_extended"] = CRASH_ONLY_COLS + GROUP_E_COLS + GROUP_F_COLS + GROUP_G_COLS

    print(f"\nPanel: {n_total} | pos>=2: {int((y>=2).sum())} | pos>=1: {int((y>=1).sum())}")
    print("Frozen params (unchanged across all sets, per Protocol A):", params)

    results = {}
    for set_name, cols in feature_sets.items():
        cols_present = [c for c in cols if c in panel.columns]
        missing = [c for c in cols if c not in panel.columns]
        print(f"\n=== {set_name}: {len(cols_present)}/{len(cols)} features available (missing: {missing}) ===")
        X = panel[cols_present].fillna(0.0).values.astype(float)
        oof_random = oof_predict(X, y, None, params, "random")
        oof_spatial = oof_predict(X, y, groups, params, "spatial")

        sp_r = stats.spearmanr(oof_random, y).correlation
        sp_s = stats.spearmanr(oof_spatial, y).correlation
        h500_r, npos = recall_at_k(oof_random, y, 500, 2)
        h500_s, _ = recall_at_k(oof_spatial, y, 500, 2)
        print(f"  Spearman OOF: random={sp_r:.4f} spatial={sp_s:.4f}")
        print(f"  recall@500 (>=2): random={h500_r}/{npos} spatial={h500_s}/{npos}")

        results[set_name] = {
            "n_features": len(cols_present),
            "missing_features": missing,
            "spearman_oof_random": round(float(sp_r), 4),
            "spearman_oof_spatial": round(float(sp_s), 4),
            "recall_at_500_ge2_random": f"{h500_r}/{npos}",
            "recall_at_500_ge2_spatial": f"{h500_s}/{npos}",
        }

    # Baseline for comparison: re-derive A_crash_only fresh on this same panel,
    # rather than a hardcoded constant left over from a previous candidate set.
    base_X = panel[CRASH_ONLY_COLS].fillna(0.0).values.astype(float)
    base_random = oof_predict(base_X, y, None, params, "random")
    base_spatial = oof_predict(base_X, y, groups, params, "spatial")
    base_sp_r = float(stats.spearmanr(base_random, y).correlation)
    base_sp_s = float(stats.spearmanr(base_spatial, y).correlation)
    results["A_crash_only_reference"] = {
        "spearman_oof_random": round(base_sp_r, 4), "spearman_oof_spatial": round(base_sp_s, 4),
        "note": "re-derived fresh on this panel, not a hardcoded constant from a prior candidate set",
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "extended_ablation_oof_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out_path}")

    print("\n" + "=" * 70)
    print("EXTENDED ABLATION — HONEST (OOF) RE-TEST")
    print("=" * 70)
    base_sp = base_sp_r
    for name, r in results.items():
        if "spearman_oof_random" not in r:
            continue
        delta = r["spearman_oof_random"] - base_sp
        print(f"  {name:<20} random_rho={r['spearman_oof_random']:.4f}  "
              f"spatial_rho={r['spearman_oof_spatial']:.4f}  delta_vs_A={delta:+.4f}")


if __name__ == "__main__":
    main()
