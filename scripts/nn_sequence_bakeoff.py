"""Raw-sequence neural net vs. the frozen Protocol-A XGBoost on KSI-emergence ranking.

PRE-REGISTERED WIN CONDITION (read this before looking at any number below):
  The GRU beats XGBoost only if it shows a positive Spearman delta on BOTH the
  random split and the spatial split, and that delta is larger than the
  across-fold standard deviation of the GRU's own Spearman score. A delta
  smaller than the fold std, or one that is positive on only one of the two
  splits, counts as a TIE, not a win.

  378 positives (>=1 KSI) is a small sample for deep learning. The honest
  expectation going in is a tie or a narrow result either way. This is meant
  as an honest probe of whether a sequence model can recover the XGBoost's
  signal from raw counts alone, not a search for a seed that wins.

WHAT THIS SCRIPT DOES
  Feeds a bidirectional GRU with attention pooling the RAW per-year crash
  counts (src/features/build_crash_sequence.py: total/KSI/injury/PDO/ped/bike/
  broadside/night, no hand-engineered features) and trains it with the same
  Tweedie objective (variance_power=1.1215191398948232) as the frozen
  Protocol-A XGBoost. Two variants: GRU alone, and GRU + the same static
  infrastructure vector model_bakeoff_oof.py uses for feature set D. Both run
  through the SAME genuine 5-fold OOF harness (random + spatial,
  src/eval/splitter.add_spatial_blocks, SEED=42) as scripts/model_bakeoff_oof.py,
  for 3 model seeds (42, 1, 2), reported individually (not best-of). Frozen
  XGBoost and the no-fitting persistence baseline are included as reference
  rows via the project's existing functions. A forward run fits each net ONCE
  on the verified window and predicts only (never fits) on forward candidates,
  exactly like scripts/predict_forward_run.py.

  Primary evaluation threshold is >=1 KSI (378 verified positives). >=2 is
  reported as an underpowered secondary readout (21 verified positives).

Writes results/nn_sequence_bakeoff_results.json. Does not touch
results/model_bakeoff_oof_results.json or any other existing results file.

Run via:  python scripts/nn_sequence_bakeoff.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import xgboost as xgb
from scipy import stats

from model_bakeoff_oof import make_folds, SEED, N_FOLDS, TWEEDIE_P  # reuse exactly
from src.eval.splitter import add_spatial_blocks
from src.features.build_crash_sequence import CHANNELS, _sequence_to_array
from src.model.fit import persistence_baseline_scores
from src.utils import load_config, project_root

warnings.filterwarnings("ignore")

ROOT = project_root()
MODEL_DIR = ROOT / "data" / "model"
VERIFIED_DIR = MODEL_DIR / "verified_run"
FORWARD_DIR = MODEL_DIR / "forward_run"
RESULTS_DIR = ROOT / "results"
SEEDS = [42, 1, 2]
N_CHANNELS = len(CHANNELS)
HIDDEN = 64
N_LAYERS = 1
DROPOUT = 0.3
WEIGHT_DECAY = 1e-4
MAX_EPOCHS = 80
PATIENCE = 10


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _all_infra_cols(cfg: dict, panel: pd.DataFrame) -> list[str]:
    """Same all_infra column list model_bakeoff_oof.py builds for feature set D."""
    fg = cfg["feature_groups"]
    geom = [f for f in fg["geometry"] if f not in ("lane_count_missing", "approach_asymmetry") and f in panel.columns]
    ctrl = [f for f in fg["control"] if f in panel.columns]
    road = [f for f in fg["roadway"] if f in panel.columns]
    at_ = [f for f in fg["active_transport"] if f in panel.columns]
    terr = [f for f in fg["terrain"] if f in panel.columns]
    return [c for c in (geom + ctrl + road + at_ + terr) if panel[c].var() > 0]


def load_verified() -> dict:
    import geopandas as gpd
    cfg = load_config()
    panel = gpd.read_parquet(VERIFIED_DIR / "candidate_panel.parquet")
    crash_feats = pd.read_parquet(VERIFIED_DIR / "feature_table.parquet")
    infra_feats = pd.read_parquet(MODEL_DIR / "infra_features.parquet")
    panel = panel.merge(crash_feats, on="intersection_id", how="left")
    panel = panel.merge(infra_feats, on="intersection_id", how="left")
    panel = add_spatial_blocks(panel, cfg)

    crash_only = list(cfg["feature_groups"]["crash_only"])
    infra_cols = _all_infra_cols(cfg, panel)

    seq_df = pd.read_parquet(VERIFIED_DIR / "crash_sequence.parquet")
    years = sorted(seq_df["year"].unique().tolist())
    candidate_ids = panel["intersection_id"].tolist()
    Xseq, _ = _sequence_to_array(seq_df, candidate_ids, years)

    return {
        "panel": panel,
        "candidate_ids": candidate_ids,
        "years": years,
        "Xseq": Xseq,
        "Xinfra": panel[infra_cols].fillna(0.0).values.astype(np.float32),
        "infra_cols": infra_cols,
        "crash_only_cols": crash_only,
        "y": panel["KSI_label"].values.astype(float),
        "groups": panel["spatial_block"].values,
        "cfg": cfg,
    }


def load_forward(cfg: dict, infra_cols: list[str], crash_only_cols: list[str]) -> dict:
    import geopandas as gpd
    panel = gpd.read_parquet(FORWARD_DIR / "candidate_panel.parquet")
    crash_feats = pd.read_parquet(FORWARD_DIR / "feature_table.parquet")
    infra_feats = pd.read_parquet(MODEL_DIR / "infra_features.parquet")
    panel = panel.merge(crash_feats, on="intersection_id", how="left")
    panel = panel.merge(infra_feats, on="intersection_id", how="left")

    seq_df = pd.read_parquet(FORWARD_DIR / "crash_sequence.parquet")
    years = sorted(seq_df["year"].unique().tolist())
    candidate_ids = panel["intersection_id"].tolist()
    Xseq, _ = _sequence_to_array(seq_df, candidate_ids, years)

    return {
        "panel": panel,
        "candidate_ids": candidate_ids,
        "years": years,
        "Xseq": Xseq,
        "Xinfra": panel[infra_cols].fillna(0.0).values.astype(np.float32),
        "crash_only_cols": crash_only_cols,
        "y": panel["KSI_label"].values.astype(float),  # read only for recall@K, never fit on
    }


# ---------------------------------------------------------------------------
# GRU + attention-pooling Tweedie model
# ---------------------------------------------------------------------------

class GRUAttnTweedie(nn.Module):
    def __init__(self, n_channels: int, hidden: int = HIDDEN, n_layers: int = N_LAYERS,
                 infra_dim: int = 0, dropout: float = DROPOUT):
        super().__init__()
        self.gru = nn.GRU(
            n_channels, hidden, num_layers=n_layers, batch_first=True,
            bidirectional=True, dropout=(dropout if n_layers > 1 else 0.0),
        )
        self.attn = nn.Linear(hidden * 2, 1)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Sequential(
            nn.Linear(hidden * 2 + infra_dim, 32), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(32, 1),
        )

    def forward(self, x_seq: torch.Tensor, x_infra: torch.Tensor | None = None):
        out, _ = self.gru(x_seq)                     # (B, T, 2H)
        scores = self.attn(out).squeeze(-1)           # (B, T)
        weights = torch.softmax(scores, dim=1)        # (B, T)
        pooled = torch.bmm(weights.unsqueeze(1), out).squeeze(1)  # (B, 2H)
        pooled = self.drop(pooled)
        if x_infra is not None:
            pooled = torch.cat([pooled, x_infra], dim=-1)
        pred = torch.exp(self.head(pooled).clamp(-10, 10)).squeeze(-1)
        return pred, weights


def tweedie_loss(y_pred: torch.Tensor, y_true: torch.Tensor, p: float = TWEEDIE_P) -> torch.Tensor:
    y_pred = y_pred.clamp(min=1e-6)
    return torch.mean(
        y_true.pow(2 - p) / ((1 - p) * (2 - p))
        - y_true * y_pred.pow(1 - p) / (1 - p)
        + y_pred.pow(2 - p) / (2 - p)
    )


def _fit_scaler(flat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = flat.mean(axis=0)
    std = flat.std(axis=0)
    std[std == 0] = 1.0
    return mean, std


def fit_seq_scaler(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return _fit_scaler(X.reshape(-1, X.shape[-1]))


def apply_seq_scaler(X: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return (X - mean) / std


def train_gru(
    Xseq_train: np.ndarray, y_train: np.ndarray, Xinfra_train: np.ndarray | None,
    seed: int, n_channels: int, infra_dim: int,
) -> tuple[GRUAttnTweedie, dict]:
    """Fit one GRU on a train fold/set. Carves an inner val slice from TRAIN
    only for early stopping; standardizes using train-only statistics."""
    rng = np.random.RandomState(seed)
    n = len(y_train)
    perm = rng.permutation(n)
    n_val = max(200, int(0.15 * n))
    val_idx, inner_train_idx = perm[:n_val], perm[n_val:]

    seq_mean, seq_std = fit_seq_scaler(Xseq_train[inner_train_idx])
    Xtr_seq = apply_seq_scaler(Xseq_train[inner_train_idx], seq_mean, seq_std)
    Xva_seq = apply_seq_scaler(Xseq_train[val_idx], seq_mean, seq_std)

    scalers = {"seq_mean": seq_mean, "seq_std": seq_std}
    Xtr_infra_t = Xva_infra_t = None
    if Xinfra_train is not None:
        infra_mean, infra_std = _fit_scaler(Xinfra_train[inner_train_idx])
        Xtr_infra = (Xinfra_train[inner_train_idx] - infra_mean) / infra_std
        Xva_infra = (Xinfra_train[val_idx] - infra_mean) / infra_std
        Xtr_infra_t = torch.tensor(Xtr_infra, dtype=torch.float32)
        Xva_infra_t = torch.tensor(Xva_infra, dtype=torch.float32)
        scalers["infra_mean"], scalers["infra_std"] = infra_mean, infra_std

    torch.manual_seed(seed)
    model = GRUAttnTweedie(n_channels, infra_dim=infra_dim)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=WEIGHT_DECAY)

    Xtr_seq_t = torch.tensor(Xtr_seq, dtype=torch.float32)
    ytr_t = torch.tensor(y_train[inner_train_idx], dtype=torch.float32)
    Xva_seq_t = torch.tensor(Xva_seq, dtype=torch.float32)
    yva_t = torch.tensor(y_train[val_idx], dtype=torch.float32)

    best_val, best_state, bad_epochs = float("inf"), None, 0
    for _ in range(MAX_EPOCHS):
        model.train()
        opt.zero_grad()
        pred, _ = model(Xtr_seq_t, Xtr_infra_t)
        loss = tweedie_loss(pred, ytr_t)
        loss.backward()
        opt.step()

        model.eval()
        with torch.no_grad():
            vpred, _ = model(Xva_seq_t, Xva_infra_t)
            vloss = tweedie_loss(vpred, yva_t).item()
        if vloss < best_val - 1e-5:
            best_val = vloss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            bad_epochs = 0
        else:
            bad_epochs += 1
            if bad_epochs >= PATIENCE:
                break

    model.load_state_dict(best_state)
    model.eval()
    return model, scalers


def predict_gru(model: GRUAttnTweedie, scalers: dict, Xseq: np.ndarray,
                 Xinfra: np.ndarray | None) -> tuple[np.ndarray, np.ndarray]:
    Xs = apply_seq_scaler(Xseq, scalers["seq_mean"], scalers["seq_std"])
    Xs_t = torch.tensor(Xs, dtype=torch.float32)
    Xi_t = None
    if Xinfra is not None:
        Xi = (Xinfra - scalers["infra_mean"]) / scalers["infra_std"]
        Xi_t = torch.tensor(Xi, dtype=torch.float32)
    with torch.no_grad():
        pred, weights = model(Xs_t, Xi_t)
    return pred.numpy(), weights.numpy()


# ---------------------------------------------------------------------------
# Metrics: fold-level, then mean +/- std across folds
# ---------------------------------------------------------------------------

def fold_metrics(scores: np.ndarray, y: np.ndarray) -> dict:
    n = len(y)
    order = np.argsort(-scores)
    ranked = y[order]
    sp = stats.spearmanr(scores, y).correlation
    n_pos1, n_pos2 = int((y >= 1).sum()), int((y >= 2).sum())
    out = {"spearman": float(sp), "n": n, "n_pos1": n_pos1, "n_pos2": n_pos2}
    for k in (200, 500):
        kk = min(k, n)
        out[f"recall_{k}_ge1"] = int((ranked[:kk] >= 1).sum())
        out[f"recall_{k}_ge2"] = int((ranked[:kk] >= 2).sum())
    return out


def aggregate_folds(fold_results: list[dict]) -> dict:
    keys = [k for k in fold_results[0] if k not in ("n", "n_pos1", "n_pos2")]
    agg = {"n_folds": len(fold_results), "n_pos1_total": sum(f["n_pos1"] for f in fold_results),
           "n_pos2_total": sum(f["n_pos2"] for f in fold_results)}
    for k in keys:
        vals = np.array([f[k] for f in fold_results], dtype=float)
        agg[f"{k}_mean"] = round(float(vals.mean()), 4)
        agg[f"{k}_std"] = round(float(vals.std()), 4)
    return agg


# ---------------------------------------------------------------------------
# Reference rows: frozen XGBoost + persistence baseline (existing functions)
# ---------------------------------------------------------------------------

def frozen_xgb_params() -> dict:
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


def reference_rows(panel: pd.DataFrame, crash_only_cols: list[str], y: np.ndarray,
                    groups: np.ndarray) -> dict:
    X = panel[crash_only_cols].fillna(0.0).values.astype(float)
    params = frozen_xgb_params()
    baseline_scores = persistence_baseline_scores(panel)

    out = {}
    for mode in ("random", "spatial"):
        folds = make_folds(y, groups, mode)
        xgb_folds, base_folds = [], []
        for tr, te in folds:
            m = xgb.XGBRegressor(**params)
            m.fit(X[tr], y[tr])
            xgb_folds.append(fold_metrics(m.predict(X[te]), y[te]))
            base_folds.append(fold_metrics(baseline_scores[te], y[te]))
        out[mode] = {
            "xgb_frozen_crash_only": aggregate_folds(xgb_folds),
            "persistence_baseline": aggregate_folds(base_folds),
        }
    return out


# ---------------------------------------------------------------------------
# OOF bake-off for one GRU variant
# ---------------------------------------------------------------------------

def run_oof_variant(variant: str, data: dict) -> dict:
    Xseq, y, groups = data["Xseq"], data["y"], data["groups"]
    Xinfra = data["Xinfra"] if variant == "gru_infra" else None
    infra_dim = Xinfra.shape[1] if Xinfra is not None else 0
    years = data["years"]

    out = {}
    for mode in ("random", "spatial"):
        folds = make_folds(y, groups, mode)
        out[mode] = {}
        for seed in SEEDS:
            fold_results = []
            attn_sum = np.zeros(len(years))
            attn_n = 0
            for tr, te in folds:
                Xinfra_tr = Xinfra[tr] if Xinfra is not None else None
                Xinfra_te = Xinfra[te] if Xinfra is not None else None
                model, scalers = train_gru(Xseq[tr], y[tr], Xinfra_tr, seed, N_CHANNELS, infra_dim)
                preds, weights = predict_gru(model, scalers, Xseq[te], Xinfra_te)
                fold_results.append(fold_metrics(preds, y[te]))
                attn_sum += weights.sum(axis=0)
                attn_n += weights.shape[0]
            agg = aggregate_folds(fold_results)
            agg["attention_weights_mean_per_year"] = {
                str(yr): round(float(w), 4) for yr, w in zip(years, attn_sum / attn_n)
            }
            out[mode][f"seed_{seed}"] = agg
            print(f"  [{variant}] mode={mode} seed={seed}: "
                  f"spearman={agg['spearman_mean']:.4f}+/-{agg['spearman_std']:.4f}  "
                  f"recall500(>=1)={agg['recall_500_ge1_mean']:.1f}+/-{agg['recall_500_ge1_std']:.1f}")
    return out


# ---------------------------------------------------------------------------
# Forward run: fit ONCE on verified window, predict-only on forward candidates
# ---------------------------------------------------------------------------

def run_forward_variant(variant: str, verified: dict, forward: dict) -> dict:
    Xseq_tr, y_tr = verified["Xseq"], verified["y"]
    Xinfra_tr = verified["Xinfra"] if variant == "gru_infra" else None
    infra_dim = Xinfra_tr.shape[1] if Xinfra_tr is not None else 0

    Xseq_fwd = forward["Xseq"]
    Xinfra_fwd = forward["Xinfra"] if variant == "gru_infra" else None
    y_fwd = forward["y"]  # read only after predicting, for recall@K
    years = forward["years"]

    n1, n2 = int((y_fwd >= 1).sum()), int((y_fwd >= 2).sum())
    out = {"n_forward_candidates": len(y_fwd), "n_pos_ge1": n1, "n_pos_ge2": n2,
           "caveat_ge2": f"only {n2} positives at >=2 KSI in the forward window; not yet meaningful",
           "seeds": {}}
    for seed in SEEDS:
        model, scalers = train_gru(Xseq_tr, y_tr, Xinfra_tr, seed, N_CHANNELS, infra_dim)
        preds, weights = predict_gru(model, scalers, Xseq_fwd, Xinfra_fwd)
        ranked = y_fwd[np.argsort(-preds)]
        recalls = {f"recall_{k}_ge1": int((ranked[:min(k, len(y_fwd))] >= 1).sum())
                   for k in (50, 100, 200, 500, 1000)}
        attn_mean = {str(yr): round(float(w), 4) for yr, w in zip(years, weights.mean(axis=0))}
        out["seeds"][f"seed_{seed}"] = {**recalls, "attention_weights_mean_per_year": attn_mean}
        print(f"  [forward/{variant}] seed={seed}: recall@500(>=1)={recalls['recall_500_ge1']}/{n1}")
    return out


# ---------------------------------------------------------------------------
# Win-condition check
# ---------------------------------------------------------------------------

def check_win_condition(gru_oof: dict, xgb_ref: dict) -> dict:
    verdict = {}
    deltas = {}
    for mode in ("random", "spatial"):
        gru_sp = np.mean([gru_oof[mode][f"seed_{s}"]["spearman_mean"] for s in SEEDS])
        gru_std = np.mean([gru_oof[mode][f"seed_{s}"]["spearman_std"] for s in SEEDS])
        xgb_sp = xgb_ref[mode]["xgb_frozen_crash_only"]["spearman_mean"]
        delta = gru_sp - xgb_sp
        deltas[mode] = {"gru_spearman_mean_3seed": round(float(gru_sp), 4),
                         "xgb_spearman_mean": round(float(xgb_sp), 4),
                         "delta": round(float(delta), 4),
                         "gru_fold_std_mean_3seed": round(float(gru_std), 4),
                         "beats_fold_std": bool(delta > gru_std)}
    win = all(deltas[m]["delta"] > 0 and deltas[m]["beats_fold_std"] for m in ("random", "spatial"))
    verdict["per_split"] = deltas
    verdict["result"] = "WIN" if win else "TIE"
    return verdict


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(__doc__)
    print(f"N_FOLDS={N_FOLDS}, SEED(fold split)={SEED}, model SEEDS={SEEDS}, "
          f"TWEEDIE_P={TWEEDIE_P}\n")

    verified = load_verified()
    forward = load_forward(verified["cfg"], verified["infra_cols"], verified["crash_only_cols"])

    print("=== Reference rows: persistence baseline + frozen Protocol-A XGBoost ===")
    xgb_ref = reference_rows(verified["panel"], verified["crash_only_cols"], verified["y"], verified["groups"])

    results: dict = {"reference": xgb_ref, "oof": {}, "forward": {}}

    for variant in ("gru", "gru_infra"):
        print(f"\n=== OOF bake-off: {variant} ===")
        results["oof"][variant] = run_oof_variant(variant, verified)

    for variant in ("gru", "gru_infra"):
        print(f"\n=== Forward run (fit-once, predict-only): {variant} ===")
        results["forward"][variant] = run_forward_variant(variant, verified, forward)

    print("\n=== Pre-registered win condition check (GRU vs frozen XGBoost, crash-only) ===")
    verdict = check_win_condition(results["oof"]["gru"], xgb_ref)
    for mode, d in verdict["per_split"].items():
        print(f"  {mode}: GRU rho={d['gru_spearman_mean_3seed']} XGB rho={d['xgb_spearman_mean']} "
              f"delta={d['delta']} fold_std={d['gru_fold_std_mean_3seed']} "
              f"beats_std={d['beats_fold_std']}")
    print(f"  VERDICT: {verdict['result']}")
    results["win_condition_verdict"] = verdict

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "nn_sequence_bakeoff_results.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
