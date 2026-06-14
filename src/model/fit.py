"""M3a model fitting (clean-coordinate rebuild).

Models:
  1. Adapted persistence baseline: rank by crashes_72mo + crash_trend_slope tiebreaker
  2. Logistic regression (L2) -- binary target: @>=1 (391 positives)
  3. XGBoost binary classifier (binary:logistic) -- binary target: @>=1
  4. XGBoost Tweedie regressor (reg:tweedie) -- PRIMARY on count

M3a binary target change: logistic + XGB-binary now train on @>=1 (391 positives)
instead of M2's @>=2 (22 positives which were mostly freeway contamination).
@>=2 (22 positives) is only an evaluation operating point.

Tuning: Optuna with spatial-block grouped 5-fold CV, k=5.
Strong regularisation preferred; simpler model wins on overlapping CIs.

Run via:  python -m src.model.fit
"""
from __future__ import annotations

import json
import logging
import pickle
import warnings
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import optuna
import pandas as pd
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.eval.splitter import add_spatial_blocks, spatial_block_kfold
from src.utils import load_config, project_root

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)
optuna.logging.set_verbosity(optuna.logging.WARNING)
warnings.filterwarnings("ignore", category=UserWarning)


# ---------------------------------------------------------------------------
# Feature preparation
# ---------------------------------------------------------------------------

FEATURE_COLS = [
    "crashes_36mo", "crashes_72mo",
    "ped_crashes_72mo", "bike_crashes_72mo",
    "broadside_72mo", "left_turn_72mo",
    "dui_72mo", "night_72mo", "ped_row_violation_72mo",
    "years_since_last_crash", "distinct_crash_days_72mo",
    "worst_severity_72mo",
    "crash_trend_slope", "emergence_velocity", "emergence_acceleration",
    "mann_kendall_tau", "changepoint_prob", "ewma_crashes",
    "momentum_ratio", "covid_period_share",
]


def _prepare_xy(panel: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return X (float), y_count (int), y_binary (int ≥ 1 threshold)."""
    X = panel[FEATURE_COLS].fillna(0.0).values.astype(float)
    y_count = panel["KSI_label"].values.astype(float)
    y_bin2 = (panel["KSI_label"] >= 2).astype(int).values
    y_bin1 = (panel["KSI_label"] >= 1).astype(int).values
    return X, y_count, y_bin2, y_bin1


# ---------------------------------------------------------------------------
# Tweedie deviance loss (for CV scoring)
# ---------------------------------------------------------------------------

def _tweedie_deviance(y_true: np.ndarray, y_pred: np.ndarray, p: float = 1.3) -> float:
    """Mean Tweedie deviance; lower = better."""
    y_pred = np.clip(y_pred, 1e-6, None)
    if p == 1:  # Poisson
        dev = 2 * (y_true * np.log(y_true / y_pred + 1e-10) - (y_true - y_pred))
    elif p == 2:  # Gamma
        dev = 2 * (np.log(y_pred / y_true + 1e-10) + y_true / y_pred - 1)
    else:
        dev = 2 * (
            y_true ** (2 - p) / ((1 - p) * (2 - p))
            - y_true * y_pred ** (1 - p) / (1 - p)
            + y_pred ** (2 - p) / (2 - p)
        )
    return float(np.mean(dev))


# ---------------------------------------------------------------------------
# 1. Adapted persistence baseline
# ---------------------------------------------------------------------------

def persistence_baseline_scores(panel: pd.DataFrame) -> np.ndarray:
    """Rank score = crashes_72mo + crash_trend_slope/100 (tiebreaker)."""
    scores = (
        panel["crashes_72mo"].values.astype(float)
        + panel["crash_trend_slope"].fillna(0).values / 100.0
    )
    # Add tiny jitter for fully tied nodes (all-zero)
    rng = np.random.default_rng(42)
    return scores + rng.uniform(0, 1e-8, size=len(scores))


# ---------------------------------------------------------------------------
# 2. Logistic regression
# ---------------------------------------------------------------------------

def fit_logistic(
    X_train: np.ndarray, y_train: np.ndarray, seed: int
) -> Pipeline:
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(
            C=0.01,             # strong L2 regularisation given few positives
            class_weight="balanced",
            solver="lbfgs",
            max_iter=2000,
            random_state=seed,
        )),
    ])
    pipe.fit(X_train, y_train)
    return pipe


# ---------------------------------------------------------------------------
# 3. XGBoost binary + 4. XGBoost Tweedie — with Optuna tuning
# ---------------------------------------------------------------------------

def _xgb_binary_cv_score(
    params: dict, X: np.ndarray, y: np.ndarray, groups: np.ndarray, k: int
) -> float:
    """Spatial-block CV AUPRC for XGBoost binary."""
    from sklearn.metrics import average_precision_score
    from sklearn.model_selection import GroupKFold
    scores_all, y_all = [], []
    gkf = GroupKFold(n_splits=k)
    for train_idx, val_idx in gkf.split(X, y, groups=groups):
        m = xgb.XGBClassifier(**params, verbosity=0, use_label_encoder=False)
        m.fit(X[train_idx], y[train_idx])
        preds = m.predict_proba(X[val_idx])[:, 1]
        scores_all.append(preds)
        y_all.append(y[val_idx])
    y_cat = np.concatenate(y_all)
    s_cat = np.concatenate(scores_all)
    if y_cat.sum() == 0:
        return 0.0
    return float(average_precision_score(y_cat, s_cat))


def _xgb_tweedie_cv_score(
    params: dict, X: np.ndarray, y: np.ndarray, groups: np.ndarray, k: int, p: float
) -> float:
    """Spatial-block CV mean Tweedie deviance for XGBoost Tweedie (lower = better)."""
    from sklearn.model_selection import GroupKFold
    deviances = []
    gkf = GroupKFold(n_splits=k)
    for train_idx, val_idx in gkf.split(X, y, groups=groups):
        m = xgb.XGBRegressor(**params, verbosity=0)
        m.fit(X[train_idx], y[train_idx])
        preds = m.predict(X[val_idx])
        deviances.append(_tweedie_deviance(y[val_idx], preds, p))
    return float(np.mean(deviances))


def tune_xgb_binary(
    X: np.ndarray, y: np.ndarray, groups: np.ndarray, cfg: dict
) -> dict:
    k = cfg["evaluation"]["spatial_cv_folds"]
    seed = cfg["project"]["rng_seed"]
    n_trials = cfg["tuning"]["n_trials"]
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    scale_pos = max(1.0, n_neg / max(n_pos, 1))

    def objective(trial):
        params = {
            "objective": "binary:logistic",
            "max_depth": trial.suggest_int("max_depth", 3, 5),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 50, 300),
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_alpha": trial.suggest_float("reg_alpha", 0.1, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.1, 10.0, log=True),
            "min_child_weight": trial.suggest_int("min_child_weight", 5, 50),
            "scale_pos_weight": scale_pos,
            "random_state": seed,
            "eval_metric": "aucpr",
        }
        return _xgb_binary_cv_score(params, X, y, groups, k)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    log.info("XGB-binary best AUPRC=%.4f, params=%s", study.best_value, study.best_params)
    best = study.best_params
    best.update({
        "objective": "binary:logistic",
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "scale_pos_weight": scale_pos,
        "random_state": seed,
        "eval_metric": "aucpr",
    })
    return best


def tune_xgb_tweedie(
    X: np.ndarray, y: np.ndarray, groups: np.ndarray, cfg: dict
) -> dict:
    k = cfg["evaluation"]["spatial_cv_folds"]
    seed = cfg["project"]["rng_seed"]
    n_trials = cfg["tuning"]["n_trials"]
    p = cfg["target"]["tweedie_variance_power"]

    def objective(trial):
        params = {
            "objective": "reg:tweedie",
            "tweedie_variance_power": trial.suggest_float("tweedie_variance_power", 1.1, 1.6),
            "max_depth": trial.suggest_int("max_depth", 3, 5),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 50, 300),
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_alpha": trial.suggest_float("reg_alpha", 0.1, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.1, 10.0, log=True),
            "min_child_weight": trial.suggest_int("min_child_weight", 5, 50),
            "random_state": seed,
        }
        return _xgb_tweedie_cv_score(params, X, y, groups, k, p)

    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=seed),
    )
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    log.info(
        "XGB-Tweedie best deviance=%.4f, variance_power=%.3f, params=%s",
        study.best_value,
        study.best_params.get("tweedie_variance_power", p),
        study.best_params,
    )
    best = study.best_params
    best.update({
        "objective": "reg:tweedie",
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": seed,
    })
    return best


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    cfg = load_config()
    model_dir = project_root() / cfg["paths"]["model"]
    seed = cfg["project"]["rng_seed"]

    # Load
    candidates = gpd.read_parquet(model_dir / "candidate_panel.parquet")
    feat_table = pd.read_parquet(model_dir / "feature_table.parquet")
    panel = candidates.merge(feat_table, on="intersection_id", how="left")

    # Ensure spatial blocks exist
    if "spatial_block" not in panel.columns:
        panel = add_spatial_blocks(panel, cfg)

    log.info(
        "Panel: %d candidates, %d positives@>=2, %d positives@>=1",
        len(panel),
        (panel["KSI_label"] >= 2).sum(),
        (panel["KSI_label"] >= 1).sum(),
    )

    X, y_count, y_bin2, y_bin1 = _prepare_xy(panel)
    groups = panel["spatial_block"].values

    results: dict[str, Any] = {}

    # 1. Persistence baseline scores (save, don't "fit")
    log.info("=== 1. Persistence baseline ===")
    baseline_scores = persistence_baseline_scores(panel)
    results["baseline"] = {"scores": baseline_scores.tolist()}

    # 2. Logistic regression (binary >=1 -- M3a secondary readout)
    log.info("=== 2. Logistic regression (target: >=1, %d positives) ===", int(y_bin1.sum()))
    log_pipe = fit_logistic(X, y_bin1, seed)
    lr_scores = log_pipe.predict_proba(X)[:, 1]
    results["logistic"] = {"scores": lr_scores.tolist()}
    with open(model_dir / "logistic_model.pkl", "wb") as f:
        pickle.dump(log_pipe, f)

    # 3. XGBoost binary (>=1 -- M3a secondary readout)
    log.info("=== 3. XGBoost binary — tuning (%d trials, target: >=1) ===", cfg["tuning"]["n_trials"])
    xgb_bin_params = tune_xgb_binary(X, y_bin1, groups, cfg)
    xgb_bin_model = xgb.XGBClassifier(**xgb_bin_params, verbosity=0, use_label_encoder=False)
    xgb_bin_model.fit(X, y_bin1)
    xgb_bin_scores = xgb_bin_model.predict_proba(X)[:, 1]
    results["xgb_binary"] = {"scores": xgb_bin_scores.tolist(), "params": xgb_bin_params}
    with open(model_dir / "xgb_binary.pkl", "wb") as f:
        pickle.dump(xgb_bin_model, f)

    # 4. XGBoost Tweedie (PRIMARY — count head)
    log.info("=== 4. XGBoost Tweedie — tuning (%d trials) ===", cfg["tuning"]["n_trials"])
    xgb_tw_params = tune_xgb_tweedie(X, y_count, groups, cfg)
    xgb_tw_model = xgb.XGBRegressor(**xgb_tw_params, verbosity=0)
    xgb_tw_model.fit(X, y_count)
    xgb_tw_scores = xgb_tw_model.predict(X)
    results["xgb_tweedie"] = {"scores": xgb_tw_scores.tolist(), "params": xgb_tw_params}
    with open(model_dir / "xgb_tweedie.pkl", "wb") as f:
        pickle.dump(xgb_tw_model, f)

    # Save all scores for evaluation
    scores_df = pd.DataFrame({
        "intersection_id": panel["intersection_id"].values,
        "KSI_label": panel["KSI_label"].values,
        "spatial_block": groups,
        "baseline_score": baseline_scores,
        "logistic_score": lr_scores,
        "xgb_binary_score": xgb_bin_scores,
        "xgb_tweedie_score": xgb_tw_scores,
    })
    scores_df.to_parquet(model_dir / "model_scores.parquet", index=False)
    log.info("Wrote model_scores.parquet (%d rows)", len(scores_df))

    # Save params
    with open(model_dir / "model_params.json", "w") as f:
        json.dump(
            {
                "xgb_binary_params": {k: str(v) for k, v in xgb_bin_params.items()},
                "xgb_tweedie_params": {k: str(v) for k, v in xgb_tw_params.items()},
            },
            f, indent=2
        )
    log.info("Model fitting complete.")


if __name__ == "__main__":
    main()
