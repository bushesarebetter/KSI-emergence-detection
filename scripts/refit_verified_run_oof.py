"""Genuinely held-out (out-of-fold) refit of the verified-run model.

This is the standard this project holds every headline number to: a model
should never be scored on a row it was trained on. `src/model/fit.py` and
`src/model/fit_frozen.py` fit the XGBoost Tweedie model on the full
81,007-candidate panel for production scoring (correct, since there's no
future label to leak when ranking unlabeled candidates), but performance
claims need a genuinely held-out evaluation, which this script provides.

This script computes that with genuine k-fold out-of-fold (OOF) scoring:
  - For each of 5 folds (stratified-random and spatial-block separately),
    fit ONLY on the other 4 folds, predict ONLY the held-out fold.
  - Every candidate ends up with exactly one prediction from a model that
    never saw its label during training.
  - Hyperparameters are NOT re-tuned here -- they were already chosen via
    proper nested CV in src/model/fit.py's Optuna search (frozen in
    data/model/frozen_params.json, sets.A_crash_only). Reusing them is
    legitimate; this script only replaces the final fit-and-score step.

Outputs:
  data/model/verified_run/oof_scores.parquet
  results/oof_verified_run_results.json
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
VERIFIED_DIR = MODEL_DIR / "verified_run"
PROC_DIR = ROOT / "data" / "proc"
RESULTS_DIR = ROOT / "results"

FHWA_FATAL_COST = 15_988_000.0
FHWA_SERIOUS_COST = 1_705_100.0
KSI_SEVERITY_CODES = {1, 2}
FATAL_CODE = 1

RNG = np.random.RandomState(42)
N_FOLDS = 5
KS = [50, 100, 200, 500, 1000]
THRESHOLDS = [1, 2]


def load_frozen_crash_only_params() -> tuple[dict, list[str]]:
    raw = json.loads((MODEL_DIR / "frozen_params.json").read_text())
    s = raw["sets"]["A_crash_only"]
    f = raw["frozen"]
    params = {
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
    return params, s["feature_list"]


def oof_predict(X: np.ndarray, y: np.ndarray, groups: np.ndarray | None, params: dict, mode: str) -> np.ndarray:
    """Genuine out-of-fold predictions: fit on train folds only, predict the held-out fold."""
    n = len(y)
    oof = np.full(n, np.nan)
    if mode == "random":
        # Stratify on the rarer >=2 threshold so every fold has positives.
        y_strat = (y >= 2).astype(int)
        splitter = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=42)
        splits = splitter.split(X, y_strat)
    elif mode == "spatial":
        splitter = GroupKFold(n_splits=N_FOLDS)
        splits = splitter.split(X, y, groups=groups)
    else:
        raise ValueError(mode)

    for fold_i, (train_idx, test_idx) in enumerate(splits):
        model = xgb.XGBRegressor(**params)
        model.fit(X[train_idx], y[train_idx])
        oof[test_idx] = model.predict(X[test_idx])
        n_pos2_test = int((y[test_idx] >= 2).sum())
        print(f"  [{mode}] fold {fold_i}: train={len(train_idx)} test={len(test_idx)} "
              f"pos@>=2 in held-out fold={n_pos2_test}")

    assert not np.isnan(oof).any(), "every row must get exactly one OOF prediction"
    return oof


def severity_mix(label_start: str = "2022-01-01", label_end: str = "2024-12-31") -> float:
    """Fatal share of KSI crashes in a specific label window, computed directly from raw
    SWITRS rather than data/proc/ksi_label_crashes.parquet.

    That proc file is NOT archived per-run: it gets overwritten in place every time
    src/labels/build_panel.py runs for any window (verified, forward, ...), so it silently
    reflects whichever run was built most recently rather than the window this function's
    caller actually wants. Filtering raw SWITRS by the label window directly avoids that.
    """
    raw_dir = ROOT / "data" / "raw" / "switrs"
    if not raw_dir.exists():
        print("  WARNING: data/raw/switrs not found; using fallback 0.243 fatal share")
        return 0.243
    frames = []
    for snapshot_dir in sorted(raw_dir.iterdir()):
        f = snapshot_dir / "crashes.csv"
        if f.exists():
            frames.append(pd.read_csv(f, low_memory=False))
    if not frames:
        print("  WARNING: no crashes.csv found under data/raw/switrs; using fallback 0.243")
        return 0.243
    crashes = pd.concat(frames).drop_duplicates(subset="CASE_ID")
    crashes["COLLISION_DATE"] = pd.to_datetime(crashes["COLLISION_DATE"], errors="coerce")
    in_window = (crashes["COLLISION_DATE"] >= label_start) & (crashes["COLLISION_DATE"] <= label_end)
    surface = crashes["STATE_HWY_IND"].astype(str).str.upper() != "Y"
    ksi = crashes.loc[in_window & surface & crashes["COLLISION_SEVERITY"].isin(KSI_SEVERITY_CODES), "COLLISION_SEVERITY"]
    if len(ksi) == 0:
        return 0.243
    return float((ksi == FATAL_CODE).sum() / len(ksi))


def harm_estimate(total_events: int, fatal_share: float) -> dict:
    blended = fatal_share * FHWA_FATAL_COST + (1.0 - fatal_share) * FHWA_SERIOUS_COST
    total = total_events * blended
    return {
        "total_ksi_events": total_events,
        "fatal_share_measured": round(fatal_share, 4),
        "blended_cost_per_event_usd": round(blended),
        "total_harm_usd": round(total),
        "total_harm_readable": "$%.0fM" % (total / 1e6),
    }


def bootstrap_recall_ci(label: np.ndarray, k: int, threshold: int, resamples: int = 2000) -> tuple[float, float]:
    """Bootstrap 95% CI for recall@K by resampling the positive index positions."""
    pos_positions = np.where(label >= threshold)[0]
    if len(pos_positions) == 0:
        return (0.0, 0.0)
    recalls = []
    for _ in range(resamples):
        sample = RNG.choice(pos_positions, size=len(pos_positions), replace=True)
        hits = (sample < k).sum()
        recalls.append(hits / len(pos_positions))
    return (float(np.percentile(recalls, 2.5)), float(np.percentile(recalls, 97.5)))


def recall_table(ranked_label: np.ndarray, n_total: int, threshold: int) -> dict:
    n_pos = int((ranked_label >= threshold).sum())
    out = {"n_positives": n_pos}
    for k in KS:
        hits = int((ranked_label[:k] >= threshold).sum())
        recall = hits / n_pos if n_pos else None
        base = k / n_total
        lift = (recall / base) if (recall is not None and base > 0) else None
        lo, hi = bootstrap_recall_ci(ranked_label, k, threshold)
        out[str(k)] = {
            "hits": hits,
            "recall": round(recall, 4) if recall is not None else None,
            "ci95": [round(lo, 4), round(hi, 4)],
            "random_baseline_recall": round(base, 6),
            "lift_over_random": round(lift, 1) if lift else None,
        }
    return out


def main() -> None:
    cfg = load_config()

    panel = gpd_or_pd_read(VERIFIED_DIR / "candidate_panel.parquet")
    feat = pd.read_parquet(VERIFIED_DIR / "feature_table.parquet")
    panel = panel.merge(feat, on="intersection_id", how="left")
    panel = add_spatial_blocks(panel, cfg)

    params, feature_list = load_frozen_crash_only_params()
    print(f"Frozen Protocol-A crash-only params (already nested-CV-tuned, NOT re-tuned here):")
    print(f"  {params}")
    print(f"Feature list ({len(feature_list)}): {feature_list}")

    X = panel[feature_list].fillna(0.0).values.astype(float)
    y_count = panel["KSI_label"].values.astype(float)
    groups = panel["spatial_block"].values
    n_total = len(panel)
    print(f"\nPanel: {n_total} candidates | pos@>=2: {int((y_count>=2).sum())} | pos@>=1: {int((y_count>=1).sum())}")

    print("\n=== Genuine out-of-fold refit: RANDOM (stratified 5-fold) ===")
    oof_random = oof_predict(X, y_count, None, params, "random")

    print("\n=== Genuine out-of-fold refit: SPATIAL (grouped 5-fold by spatial block) ===")
    oof_spatial = oof_predict(X, y_count, groups, params, "spatial")

    baseline_scores = persistence_baseline_scores(panel)

    sp_random = stats.spearmanr(oof_random, y_count).correlation
    sp_spatial = stats.spearmanr(oof_spatial, y_count).correlation
    sp_baseline = stats.spearmanr(baseline_scores, y_count).correlation
    print(f"\nOOF Spearman rho: random={sp_random:.4f}  spatial={sp_spatial:.4f}  (persistence baseline={sp_baseline:.4f})")

    # Save OOF scores
    out_df = pd.DataFrame({
        "intersection_id": panel["intersection_id"].values,
        "KSI_label": panel["KSI_label"].values,
        "spatial_block": groups,
        "persistence_baseline_score": baseline_scores,
        "oof_score_random": oof_random,
        "oof_score_spatial": oof_spatial,
    })
    out_df.to_parquet(VERIFIED_DIR / "oof_scores.parquet", index=False)
    print(f"\nWrote {VERIFIED_DIR / 'oof_scores.parquet'}")

    # Recall@K tables (genuinely held-out) for both split schemes x both thresholds
    fatal_share = severity_mix()
    print(f"Measured fatal share (from data/proc/ksi_label_crashes.parquet): {fatal_share:.4f}")

    results: dict = {
        "methodology": (
            "Genuine k=5 out-of-fold (OOF) predictions: model fit on 4/5 folds, "
            "scored only on the held-out 1/5, repeated across all folds so every "
            "candidate gets exactly one prediction from a model that never saw "
            "its label. Hyperparameters reused from data/model/frozen_params.json "
            "(already nested-CV-tuned via Optuna in src/model/fit.py); NOT re-tuned here."
        ),
        "n_candidates": n_total,
        "spearman_rho": {
            "random_split_oof": round(float(sp_random), 4),
            "spatial_split_oof": round(float(sp_spatial), 4),
            "persistence_baseline_oof_comparable": round(float(sp_baseline), 4),
        },
        "fatal_share_measured": round(fatal_share, 4),
    }

    for split_name, scores in [("random", oof_random), ("spatial", oof_spatial), ("persistence_baseline", baseline_scores)]:
        order = np.argsort(-scores)
        ranked_label = y_count[order]
        split_results = {}
        for thr in THRESHOLDS:
            tbl = recall_table(ranked_label, n_total, thr)
            n_events_caught_500 = int(np.sum(ranked_label[:500][ranked_label[:500] >= thr]))
            harm = harm_estimate(n_events_caught_500, fatal_share)
            tbl["harm_at_top500_caught_sites"] = harm
            split_results[f">={thr}"] = tbl
        results[split_name] = split_results

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "oof_verified_run_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out_path}")

    print("\n" + "=" * 78)
    print("SUMMARY: genuinely held-out recall@500, >=2 KSI threshold")
    print("=" * 78)
    for split_name in ("random", "spatial"):
        t = results[split_name][">=2"]["500"]
        print(f"  {split_name:8s}: {t['hits']}/{results[split_name]['>=2']['n_positives']} "
              f"= {t['recall']:.3f}  (95% CI {t['ci95']})  lift={t['lift_over_random']}x")


def gpd_or_pd_read(path: Path):
    import geopandas as gpd
    return gpd.read_parquet(path)


if __name__ == "__main__":
    main()
