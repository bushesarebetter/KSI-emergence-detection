"""FT-Transformer vs. frozen-XGBoost, genuine 5-fold OOF, on the verified panel.

Lightweight standalone: reuses the ALREADY-COMPUTED frozen-XGBoost + persistence
OOF scores in data/model/verified_run/oof_scores.parquet, so it needs only torch
(no xgboost / optuna / geopandas). Built to run on Colab GPU.

FT-Transformer = per-feature linear tokenizer + [CLS] + TransformerEncoder ACROSS
the 20 crash-history features, Tweedie-mean head (Gorishniy et al. 2021). A
different bet than the earlier GRU-over-year-sequences (reports/nn_sequence_experiment.md).

Colab:
    !pip -q install scikit-learn   # torch/pandas/numpy/scipy preinstalled
    # upload these 3 files, keeping the paths:
    #   data/model/verified_run/candidate_panel.parquet
    #   data/model/verified_run/feature_table.parquet
    #   data/model/verified_run/oof_scores.parquet
    !ROOT=. python scripts/ft_transformer_bakeoff.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from scipy import stats
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.preprocessing import StandardScaler

ROOT = Path(os.environ.get("ROOT", "."))
VR = ROOT / "data" / "model" / "verified_run"
SEED = 42
N_FOLDS = 5
TWEEDIE_P = 1.1215191398948232
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

FEATURES = [
    "crashes_36mo", "crashes_72mo", "ped_crashes_72mo", "bike_crashes_72mo",
    "broadside_72mo", "left_turn_72mo", "dui_72mo", "night_72mo", "ped_row_violation_72mo",
    "years_since_last_crash", "distinct_crash_days_72mo", "worst_severity_72mo",
    "crash_trend_slope", "emergence_velocity", "emergence_acceleration", "mann_kendall_tau",
    "changepoint_prob", "ewma_crashes", "momentum_ratio", "covid_period_share",
]


def make_folds(X, y, groups, mode):
    if mode == "random":
        ys = (y >= 2).astype(int)
        return list(StratifiedKFold(N_FOLDS, shuffle=True, random_state=SEED).split(X, ys))
    return list(GroupKFold(N_FOLDS).split(X, y, groups=groups))


def tweedie_loss(pred, true, p=TWEEDIE_P):
    pred = pred.clamp(min=1e-6)
    return torch.mean(true.pow(2 - p) / ((1 - p) * (2 - p))
                      - true * pred.pow(1 - p) / (1 - p) + pred.pow(2 - p) / (2 - p))


class FTTransformer(nn.Module):
    def __init__(self, n_feat, d=32, heads=4, layers=2, dropout=0.4):
        super().__init__()
        self.w = nn.Parameter(torch.randn(n_feat, d) * 0.02)
        self.b = nn.Parameter(torch.zeros(n_feat, d))
        self.cls = nn.Parameter(torch.randn(1, 1, d) * 0.02)
        enc = nn.TransformerEncoderLayer(d, heads, d * 2, dropout, activation="gelu", batch_first=True)
        self.encoder = nn.TransformerEncoder(enc, layers)
        self.head = nn.Sequential(nn.LayerNorm(d), nn.Linear(d, 1))

    def forward(self, x):
        tok = x.unsqueeze(-1) * self.w + self.b
        h = torch.cat([self.cls.expand(x.size(0), -1, -1), tok], dim=1)
        h = self.encoder(h)
        return torch.exp(self.head(h[:, 0]).clamp(-10, 10)).squeeze(-1)


def oof_ft(X, y, groups, mode, max_epochs=200, patience=15, bs=512):
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    pred = np.full(len(y), np.nan)
    for tr, te in make_folds(X, y, groups, mode):
        rng = np.random.RandomState(SEED)
        perm = rng.permutation(len(tr))
        n_val = max(500, int(0.15 * len(tr)))
        iv, it = tr[perm[:n_val]], tr[perm[n_val:]]
        sc = StandardScaler().fit(X[it])
        Xtr = torch.tensor(sc.transform(X[it]), dtype=torch.float32, device=DEVICE)
        ytr = torch.tensor(y[it], dtype=torch.float32, device=DEVICE)
        Xva = torch.tensor(sc.transform(X[iv]), dtype=torch.float32, device=DEVICE)
        yva = torch.tensor(y[iv], dtype=torch.float32, device=DEVICE)
        Xte = torch.tensor(sc.transform(X[te]), dtype=torch.float32, device=DEVICE)

        m = FTTransformer(X.shape[1]).to(DEVICE)
        opt = torch.optim.Adam(m.parameters(), lr=1e-3, weight_decay=1e-4)
        best, best_state, bad = float("inf"), None, 0
        n = len(it)
        for _ in range(max_epochs):
            m.train()
            order = torch.randperm(n, device=DEVICE)
            for i in range(0, n, bs):
                idx = order[i:i + bs]
                opt.zero_grad()
                tweedie_loss(m(Xtr[idx]), ytr[idx]).backward()
                opt.step()
            m.eval()
            with torch.no_grad():
                vl = tweedie_loss(m(Xva), yva).item()
            if vl < best - 1e-5:
                best, best_state, bad = vl, {k: v.clone() for k, v in m.state_dict().items()}, 0
            else:
                bad += 1
                if bad >= patience:
                    break
        m.load_state_dict(best_state)
        m.eval()
        with torch.no_grad():
            pred[te] = m(Xte).cpu().numpy()
    return pred


def summ(name, scores, y):
    order = np.argsort(-scores)
    ranked = y[order]
    sp = stats.spearmanr(scores, y).correlation
    p2, p1 = int((y >= 2).sum()), int((y >= 1).sum())
    r5_2, r5_1, r2_2 = int((ranked[:500] >= 2).sum()), int((ranked[:500] >= 1).sum()), int((ranked[:200] >= 2).sum())
    print(f"  {name:<24} rho={sp:+.4f}  r@500(>=2)={r5_2}/{p2}  r@200(>=2)={r2_2}/{p2}  r@500(>=1)={r5_1}/{p1}")
    return dict(spearman=round(float(sp), 4), r500_ge2=f"{r5_2}/{p2}", r200_ge2=f"{r2_2}/{p2}", r500_ge1=f"{r5_1}/{p1}")


def main():
    panel = pd.read_parquet(VR / "candidate_panel.parquet", columns=["intersection_id", "KSI_label"])
    feats = pd.read_parquet(VR / "feature_table.parquet")
    oof = pd.read_parquet(VR / "oof_scores.parquet", columns=[
        "intersection_id", "spatial_block", "persistence_baseline_score", "oof_score_random", "oof_score_spatial"])
    df = panel.merge(feats, on="intersection_id", how="left").merge(oof, on="intersection_id", how="left")

    X = df[FEATURES].fillna(0.0).values.astype(np.float32)
    y = df["KSI_label"].values.astype(np.float32)
    groups = df["spatial_block"].values

    print(f"device={DEVICE} | {len(df)} candidates | pos>=2={int((y >= 2).sum())} pos>=1={int((y >= 1).sum())}\n")
    out = {"persistence_baseline": summ("persistence_baseline", df["persistence_baseline_score"].values, y)}
    for mode, col in [("random", "oof_score_random"), ("spatial", "oof_score_spatial")]:
        print(f"=== {mode} OOF ===")
        out[f"xgb_frozen_{mode}"] = summ("xgb_frozen", df[col].values, y)
        out[f"ft_transformer_{mode}"] = summ("ft_transformer", oof_ft(X, y, groups, mode), y)
        print()

    (ROOT / "results").mkdir(parents=True, exist_ok=True)
    (ROOT / "results" / "ft_transformer_oof_results.json").write_text(json.dumps(out, indent=2))
    print("wrote results/ft_transformer_oof_results.json")


if __name__ == "__main__":
    main()
