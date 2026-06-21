"""Generate live forward-run predictions WITHOUT fitting on resolved future labels.

Replaces calling `python -m src.model.fit_frozen` for the forward window. That
script did `model.fit(X, y)` where `y` was the forward candidate panel's own
KSI_label column -- which, for the forward run, is the 2025-2027 outcome. Since
today's date is after 2025, that outcome has already happened and is sitting in
the SWITRS export the panel was built from, so fitting on it directly handed the
model the answer for the exact rows it was about to be scored against. See
docs/DECISIONS.md D17.

This script instead does what a real forecasting deployment requires: fit the
frozen Protocol-A crash-only model ONCE on the verified-run's own training
window (2016-2021 features -> 2022-2024 labels, fully resolved historical data --
the project's one and only "trained" model), then call .predict() on the
current forward candidate set's 2016-2024 features. The forward candidates'
KSI_label (2025-2027 outcome) is never touched during fitting; it's read only
afterward, for recall@K reporting. This makes the live forward-run score
leakage-free by construction, identical in spirit to scripts/run_recall_evaluation.py
("prospective_2025") -- the difference is this script writes the result to the
paths the dashboard export pipeline actually reads, so the live map matches the
validated number instead of a separately-computed, leakage-tainted one.

Writes:
  data/model/frozen_scores.parquet              (current run, read by
                                                   scripts/build_export_panel_verified.py)
  data/model/forward_run/frozen_scores.parquet  (archive copy)

Run from project root:
    python scripts/predict_forward_run.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import xgboost as xgb

from src.utils import project_root

ROOT = project_root()
MODEL_DIR = ROOT / "data" / "model"
VERIFIED_DIR = MODEL_DIR / "verified_run"
FORWARD_DIR = MODEL_DIR / "forward_run"


def load_frozen_xgb_params() -> tuple[dict, list[str]]:
    """Load the crash-only Protocol-A hyperparameters + feature list, straight
    from frozen_params.json -- the same source every other frozen-model script
    in this project uses, so this can't drift."""
    record = json.loads((MODEL_DIR / "frozen_params.json").read_text())
    raw = record["sets"]["A_crash_only"]
    feature_list = raw["feature_list"]
    frozen = record["frozen"]
    params = {
        "objective":              frozen["objective"],
        "tweedie_variance_power": float(frozen["tweedie_variance_power"]),
        "max_depth":              int(frozen["max_depth"]),
        "learning_rate":          float(frozen["learning_rate"]),
        "n_estimators":           int(frozen["n_estimators"]),
        "reg_alpha":              float(frozen["reg_alpha"]),
        "reg_lambda":             float(frozen["reg_lambda"]),
        "min_child_weight":       int(frozen["min_child_weight"]),
        "subsample":              float(frozen["subsample"]),
        "colsample_bytree":       float(frozen["colsample_bytree"]),
        "random_state":           int(frozen["random_state"]),
    }
    return params, feature_list


def main() -> int:
    params, feature_list = load_frozen_xgb_params()

    # --- Fit ONCE on the verified-run's own resolved historical window ---
    panel_v = pd.read_parquet(VERIFIED_DIR / "candidate_panel.parquet")
    feat_v = pd.read_parquet(VERIFIED_DIR / "feature_table.parquet")
    train_df = panel_v.merge(feat_v, on="intersection_id", how="left")
    missing = [f for f in feature_list if f not in train_df.columns]
    if missing:
        raise RuntimeError(f"verified-run panel missing expected features: {missing}")

    X_train = train_df[feature_list].fillna(0.0).values.astype(float)
    y_train = train_df["KSI_label"].values.astype(float)

    model = xgb.XGBRegressor(**params, verbosity=0)
    model.fit(X_train, y_train)
    print(
        f"Fit once on verified-run window (2016-2021 features -> 2022-2024 labels): "
        f"n_train={len(X_train)}, pos>=2={int((train_df['KSI_label'] >= 2).sum())}"
    )

    # --- Predict only (no fit) on the current forward candidate set ---
    panel_f = pd.read_parquet(MODEL_DIR / "candidate_panel.parquet")
    feat_f = pd.read_parquet(MODEL_DIR / "feature_table.parquet")
    fwd_df = panel_f.merge(feat_f, on="intersection_id", how="left")
    missing_f = [f for f in feature_list if f not in fwd_df.columns]
    if missing_f:
        raise RuntimeError(f"forward candidate panel missing expected features: {missing_f}")

    X_fwd = fwd_df[feature_list].fillna(0.0).values.astype(float)
    fwd_df["A_crash_only__xgb_tweedie"] = model.predict(X_fwd)

    n1 = int((fwd_df["KSI_label"] >= 1).sum())
    n2 = int((fwd_df["KSI_label"] >= 2).sum())
    print(
        f"Predicted (no fit) for {len(fwd_df)} forward candidates. "
        f"2025-2027 outcome ({n1} pos>=1, {n2} pos>=2) was never used for fitting -- "
        f"it's read below only to report recall@K."
    )

    ranked = fwd_df.sort_values("A_crash_only__xgb_tweedie", ascending=False).reset_index(drop=True)
    for k in (50, 100, 200, 500, 1000):
        hits1 = int((ranked.head(k)["KSI_label"] >= 1).sum())
        print(f"  recall@{k:<5} (>=1 KSI): {hits1}/{n1}")

    out = fwd_df[["intersection_id", "A_crash_only__xgb_tweedie"]]
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(MODEL_DIR / "frozen_scores.parquet", index=False)
    FORWARD_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(FORWARD_DIR / "frozen_scores.parquet", index=False)
    print("Wrote data/model/frozen_scores.parquet and data/model/forward_run/frozen_scores.parquet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
