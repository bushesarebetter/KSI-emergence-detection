"""Does infrastructure data help the forward run? Predict-only, no fitting on forward labels.

Replaces scripts/refit_protocol_a_forward_oof.py, which had the same bug as
src/model/fit_frozen.py before D17 (see docs/DECISIONS.md): it called
`model.fit(X[train_idx], y[train_idx])` where `y` was the forward candidate
panel's own KSI_label -- the 2025-2027 outcome, which has already happened and
is sitting in the SWITRS export the panel was built from. Five-fold OOF kept any
single row from being scored by a model that had directly trained on that exact
row, but it was still answering a different question than "does infra data help
the live, never-retrained forecasting model" -- it was retraining a brand new
model on the freshest (partially resolved) window each time, which contradicts
the project's now-singular deployment philosophy (D17): one model, fit once on
fully resolved historical data, never retrained as new labels arrive.

This script instead fits each of the 4 Protocol-A feature sets (A crash-only,
B +geometry, C +signals, D +all-infra) ONCE on the verified-run's own resolved
window (2016-2021 features -> 2022-2024 labels), then scores the forward
candidates' 2016-2024 features via .predict() only -- exactly the same
methodology scripts/predict_forward_run.py uses for the deployed crash-only
model, just repeated for all 4 sets so the infra-vs-crash-only comparison is
leakage-free too. The forward panel's KSI_label is read only afterward, for
recall@K reporting.

Writes:
  results/protocol_a_forward_results.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy import stats

from src.utils import load_config, project_root

ROOT = project_root()
MODEL_DIR = ROOT / "data" / "model"
VERIFIED_DIR = MODEL_DIR / "verified_run"
FORWARD_DIR = MODEL_DIR / "forward_run"
RESULTS_DIR = ROOT / "results"
KS = [50, 100, 200, 500, 1000]


def load_frozen() -> dict:
    f = json.loads((MODEL_DIR / "frozen_params.json").read_text())["frozen"]
    return {
        "objective":              f["objective"],
        "tweedie_variance_power": float(f["tweedie_variance_power"]),
        "max_depth":              int(f["max_depth"]),
        "learning_rate":          float(f["learning_rate"]),
        "n_estimators":           int(f["n_estimators"]),
        "reg_alpha":              float(f["reg_alpha"]),
        "reg_lambda":             float(f["reg_lambda"]),
        "min_child_weight":       int(f["min_child_weight"]),
        "subsample":              float(f["subsample"]),
        "colsample_bytree":       float(f["colsample_bytree"]),
        "random_state":           int(f["random_state"]),
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


def recall_at_k(scores: np.ndarray, y: np.ndarray, k: int, thr: int) -> tuple[int, int]:
    order = np.argsort(-scores)
    ranked = y[order]
    n_pos = int((ranked >= thr).sum())
    hits = int((ranked[:k] >= thr).sum())
    return hits, n_pos


def main() -> None:
    cfg = load_config()
    params = load_frozen()

    panel_v = gpd.read_parquet(VERIFIED_DIR / "candidate_panel.parquet")
    crash_v = pd.read_parquet(VERIFIED_DIR / "feature_table.parquet")
    infra = pd.read_parquet(MODEL_DIR / "infra_features.parquet")
    train_df = panel_v.merge(crash_v, on="intersection_id", how="left")
    train_df = train_df.merge(infra, on="intersection_id", how="left")
    y_train = train_df["KSI_label"].values.astype(float)

    panel_f = gpd.read_parquet(FORWARD_DIR / "candidate_panel.parquet")
    crash_f = pd.read_parquet(FORWARD_DIR / "feature_table.parquet")
    fwd_df = panel_f.merge(crash_f, on="intersection_id", how="left")
    fwd_df = fwd_df.merge(infra, on="intersection_id", how="left")
    y_fwd = fwd_df["KSI_label"].values.astype(float)

    feature_sets = build_feature_sets(cfg, train_df)

    print(f"Train (verified-run window): {len(train_df)} | pos>=2: {int((y_train >= 2).sum())}")
    print(f"Predict (forward candidates): {len(fwd_df)} | pos>=1: {int((y_fwd >= 1).sum())} "
          f"(2025 partial -- pos>=2: {int((y_fwd >= 2).sum())}, too few to read recall from)")
    print("Frozen params (unchanged across all sets, per Protocol A):", params)

    results = {}
    for set_name, cols in feature_sets:
        missing = [c for c in cols if c not in fwd_df.columns]
        if missing:
            print(f"  SKIP {set_name}: forward panel missing {missing}")
            continue
        print(f"\n=== {set_name}: {len(cols)} features ===")
        X_train = train_df[cols].fillna(0.0).values.astype(float)
        X_fwd = fwd_df[cols].fillna(0.0).values.astype(float)

        model = xgb.XGBRegressor(**params)
        model.fit(X_train, y_train)
        scores = model.predict(X_fwd)

        sp = stats.spearmanr(scores, y_fwd).correlation
        h500_1, npos1 = recall_at_k(scores, y_fwd, 500, 1)
        h500_2, npos2 = recall_at_k(scores, y_fwd, 500, 2)
        print(f"  Spearman (predict-only vs true 2025-2027 outcome): {sp:.4f}")
        print(f"  recall@500 (>=1): {h500_1}/{npos1}")
        print(f"  recall@500 (>=2, noisy, n={npos2}): {h500_2}/{npos2}")

        results[set_name] = {
            "n_features": len(cols),
            "features": cols,
            "spearman_predict_only": round(float(sp), 4),
            "recall_at_500_ge1": f"{h500_1}/{npos1}",
            "recall_at_500_ge2": f"{h500_2}/{npos2}",
        }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "protocol_a_forward_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out_path}")

    print("\n" + "=" * 70)
    print("PROTOCOL A — FORWARD RUN, PREDICT-ONLY INFRASTRUCTURE RE-TEST")
    print("=" * 70)
    base_sp = results["A_crash_only"]["spearman_predict_only"]
    for name, r in results.items():
        delta = r["spearman_predict_only"] - base_sp
        print(f"  {name:<18} rho={r['spearman_predict_only']:.4f}  delta_vs_A={delta:+.4f}")


if __name__ == "__main__":
    main()
