"""Model architecture bake-off, all evaluated via genuine out-of-fold scoring.

Compares, on both the crash-only (A) and all-infrastructure (D) feature sets:
  - Persistence baseline (no fitting)
  - XGBoost Tweedie, frozen Set-A hyperparameters (the project's original choice)
  - XGBoost Tweedie, freshly tuned per feature set (Optuna, spatial-block CV)
  - Random Forest regressor (bagged trees -- naturally regularized, good fit
    for small-n / high-imbalance tabular data)
  - A small MLP neural network (PyTorch, Tweedie-deviance loss to match the
    XGBoost objective, ~100 epochs with early stopping per fold)

All models are evaluated with the SAME 5-fold genuine OOF scheme (random +
spatial) used in scripts/refit_verified_run_oof.py, so the comparison is
apples-to-apples and leak-free across the board.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import xgboost as xgb
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.preprocessing import StandardScaler

import optuna

from src.eval.splitter import add_spatial_blocks
from src.model.fit import persistence_baseline_scores
from src.utils import load_config, project_root

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

ROOT = project_root()
MODEL_DIR = ROOT / "data" / "model"
VERIFIED_DIR = MODEL_DIR / "verified_run"
RESULTS_DIR = ROOT / "results"
N_FOLDS = 5
SEED = 42
TWEEDIE_P = 1.1215191398948232  # match the project's chosen variance power


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_panel_and_sets():
    import geopandas as gpd
    cfg = load_config()
    panel = gpd.read_parquet(VERIFIED_DIR / "candidate_panel.parquet")
    crash_feats = pd.read_parquet(VERIFIED_DIR / "feature_table.parquet")
    infra_feats = pd.read_parquet(MODEL_DIR / "infra_features.parquet")
    panel = panel.merge(crash_feats, on="intersection_id", how="left")
    panel = panel.merge(infra_feats, on="intersection_id", how="left")
    panel = add_spatial_blocks(panel, cfg)

    fg = cfg["feature_groups"]
    crash_only = list(fg["crash_only"])
    geom = [f for f in fg["geometry"] if f not in ("lane_count_missing", "approach_asymmetry") and f in panel.columns]
    ctrl = [f for f in fg["control"] if f in panel.columns]
    road = [f for f in fg["roadway"] if f in panel.columns]
    at_ = [f for f in fg["active_transport"] if f in panel.columns]
    terr = [f for f in fg["terrain"] if f in panel.columns]
    all_infra = [c for c in (geom + ctrl + road + at_ + terr) if panel[c].var() > 0]

    feature_sets = {
        "A_crash_only": crash_only,
        "D_all_infra": crash_only + all_infra,
    }
    return panel, feature_sets


def make_folds(y: np.ndarray, groups: np.ndarray, mode: str):
    if mode == "random":
        y_strat = (y >= 2).astype(int)
        return list(StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED).split(np.zeros_like(y), y_strat))
    return list(GroupKFold(n_splits=N_FOLDS).split(np.zeros_like(y), y, groups=groups))


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def tune_xgb_for_set(X: np.ndarray, y: np.ndarray, groups: np.ndarray, n_trials: int = 25) -> dict:
    """Fresh Optuna tuning via spatial-block CV (same protocol the project already uses)."""
    def tweedie_dev(y_true, y_pred, p=TWEEDIE_P):
        y_pred = np.clip(y_pred, 1e-6, None)
        return float(np.mean(
            y_true ** (2 - p) / ((1 - p) * (2 - p))
            - y_true * y_pred ** (1 - p) / (1 - p)
            + y_pred ** (2 - p) / (2 - p)
        ))

    def cv_score(params):
        devs = []
        for tr, va in GroupKFold(n_splits=5).split(X, y, groups=groups):
            m = xgb.XGBRegressor(**params, verbosity=0)
            m.fit(X[tr], y[tr])
            devs.append(tweedie_dev(y[va], m.predict(X[va])))
        return float(np.mean(devs))

    def objective(trial):
        params = {
            "objective": "reg:tweedie",
            "tweedie_variance_power": trial.suggest_float("tweedie_variance_power", 1.05, 1.6),
            "max_depth": trial.suggest_int("max_depth", 2, 5),
            "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.2, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 50, 300),
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_alpha": trial.suggest_float("reg_alpha", 0.1, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.1, 10.0, log=True),
            "min_child_weight": trial.suggest_int("min_child_weight", 5, 60),
            "random_state": SEED,
        }
        return cv_score(params)

    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    best = dict(study.best_params)
    best.update({"objective": "reg:tweedie", "subsample": 0.8, "colsample_bytree": 0.8, "random_state": SEED, "verbosity": 0})
    return best


def oof_xgb(X, y, groups, params, mode):
    oof = np.full(len(y), np.nan)
    for tr, te in make_folds(y, groups, mode):
        m = xgb.XGBRegressor(**params)
        m.fit(X[tr], y[tr])
        oof[te] = m.predict(X[te])
    return oof


def oof_rf(X, y, groups, mode):
    oof = np.full(len(y), np.nan)
    for tr, te in make_folds(y, groups, mode):
        m = RandomForestRegressor(
            n_estimators=400, max_depth=6, min_samples_leaf=15,
            max_features="sqrt", random_state=SEED, n_jobs=-1,
        )
        m.fit(X[tr], y[tr])
        oof[te] = m.predict(X[te])
    return oof


class TweedieMLP(nn.Module):
    def __init__(self, n_in: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_in, 64), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(32, 1),
        )

    def forward(self, x):
        return torch.exp(self.net(x).clamp(-10, 10)).squeeze(-1)


def tweedie_loss(y_pred, y_true, p=TWEEDIE_P):
    y_pred = y_pred.clamp(min=1e-6)
    return torch.mean(
        y_true.pow(2 - p) / ((1 - p) * (2 - p))
        - y_true * y_pred.pow(1 - p) / (1 - p)
        + y_pred.pow(2 - p) / (2 - p)
    )


def oof_mlp(X, y, groups, mode, max_epochs=100, patience=10):
    oof = np.full(len(y), np.nan)
    torch.manual_seed(SEED)
    for tr, te in make_folds(y, groups, mode):
        # carve an inner validation slice out of the train fold ONLY, for early stopping
        rng = np.random.RandomState(SEED)
        perm = rng.permutation(len(tr))
        n_val = max(500, int(0.15 * len(tr)))
        inner_val, inner_train = tr[perm[:n_val]], tr[perm[n_val:]]

        scaler = StandardScaler().fit(X[inner_train])
        Xtr = torch.tensor(scaler.transform(X[inner_train]), dtype=torch.float32)
        ytr = torch.tensor(y[inner_train], dtype=torch.float32)
        Xva = torch.tensor(scaler.transform(X[inner_val]), dtype=torch.float32)
        yva = torch.tensor(y[inner_val], dtype=torch.float32)
        Xte = torch.tensor(scaler.transform(X[te]), dtype=torch.float32)

        model = TweedieMLP(X.shape[1])
        opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)

        best_val = float("inf")
        best_state = None
        bad_epochs = 0
        for epoch in range(max_epochs):
            model.train()
            opt.zero_grad()
            pred = model(Xtr)
            loss = tweedie_loss(pred, ytr)
            loss.backward()
            opt.step()

            model.eval()
            with torch.no_grad():
                val_loss = tweedie_loss(model(Xva), yva).item()
            if val_loss < best_val - 1e-5:
                best_val = val_loss
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
                bad_epochs = 0
            else:
                bad_epochs += 1
                if bad_epochs >= patience:
                    break

        model.load_state_dict(best_state)
        model.eval()
        with torch.no_grad():
            oof[te] = model(Xte).numpy()
    return oof


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def summarize(name: str, scores: np.ndarray, y: np.ndarray) -> dict:
    order = np.argsort(-scores)
    ranked = y[order]
    sp = stats.spearmanr(scores, y).correlation
    n_pos2 = int((y >= 2).sum())
    n_pos1 = int((y >= 1).sum())
    h500_2 = int((ranked[:500] >= 2).sum())
    h500_1 = int((ranked[:500] >= 1).sum())
    h200_2 = int((ranked[:200] >= 2).sum())
    print(f"  {name:<28} rho={sp:.4f}  recall@500(>=2)={h500_2}/{n_pos2}  "
          f"recall@200(>=2)={h200_2}/{n_pos2}  recall@500(>=1)={h500_1}/{n_pos1}")
    return {
        "spearman": round(float(sp), 4),
        "recall_at_500_ge2": f"{h500_2}/{n_pos2}",
        "recall_at_200_ge2": f"{h200_2}/{n_pos2}",
        "recall_at_500_ge1": f"{h500_1}/{n_pos1}",
    }


def main():
    panel, feature_sets = load_panel_and_sets()
    y = panel["KSI_label"].values.astype(float)
    groups = panel["spatial_block"].values
    baseline_scores = persistence_baseline_scores(panel)

    frozen_params = json.loads((MODEL_DIR / "frozen_params.json").read_text())["frozen"]
    frozen_params = {
        "objective": frozen_params["objective"],
        "tweedie_variance_power": float(frozen_params["tweedie_variance_power"]),
        "max_depth": int(frozen_params["max_depth"]),
        "learning_rate": float(frozen_params["learning_rate"]),
        "n_estimators": int(frozen_params["n_estimators"]),
        "reg_alpha": float(frozen_params["reg_alpha"]),
        "reg_lambda": float(frozen_params["reg_lambda"]),
        "min_child_weight": int(frozen_params["min_child_weight"]),
        "subsample": float(frozen_params["subsample"]),
        "colsample_bytree": float(frozen_params["colsample_bytree"]),
        "random_state": 42,
        "verbosity": 0,
    }

    all_results = {}
    print(f"Persistence baseline: ", end="")
    all_results["persistence_baseline"] = summarize("persistence_baseline", baseline_scores, y)

    for set_name, cols in feature_sets.items():
        print(f"\n=== Feature set: {set_name} ({len(cols)} features) ===")
        X = panel[cols].fillna(0.0).values.astype(float)

        print("Tuning fresh XGBoost hyperparameters (Optuna, 25 trials, spatial CV)...")
        tuned_params = tune_xgb_for_set(X, y, groups, n_trials=25)
        print(f"  tuned params: {tuned_params}")

        for mode in ["random", "spatial"]:
            print(f"\n -- OOF mode: {mode} --")
            oof_frozen = oof_xgb(X, y, groups, frozen_params, mode)
            oof_tuned = oof_xgb(X, y, groups, tuned_params, mode)
            oof_rf_ = oof_rf(X, y, groups, mode)
            oof_mlp_ = oof_mlp(X, y, groups, mode)

            key = f"{set_name}__{mode}"
            all_results[key] = {
                "xgb_frozen_setA_params": summarize("xgb_frozen_setA_params", oof_frozen, y),
                "xgb_freshly_tuned": summarize("xgb_freshly_tuned", oof_tuned, y),
                "random_forest": summarize("random_forest", oof_rf_, y),
                "mlp_neural_net": summarize("mlp_neural_net", oof_mlp_, y),
            }
            all_results[key]["tuned_xgb_params"] = tuned_params

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "model_bakeoff_oof_results.json"
    out_path.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
