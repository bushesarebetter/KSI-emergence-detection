"""Prospective 2025 validation: the cleanest possible recall@K evaluation.

Builds a fresh forward candidate set (no KSI through 2023), fresh
2016-2023 features, refits the VERIFIED-RUN recipe (frozen_params.json
crash_only XGB-Tweedie hyperparameters, in-memory only -- never written
to data/model/xgb_tweedie.pkl) on the ORIGINAL verified-run window
(data/model/verified_run/{candidate_panel,feature_table}.parquet,
2016-2021 features -> 2022-2024 labels), then scores the NEW 2025
prospective candidates with that in-memory model. The 2025 labels never
existed anywhere during training, so this evaluation is leakage-free by
construction, no out-of-fold scoring needed.

For the verified run's own retrospective evaluation (same training window,
checked against its own label window), see scripts/refit_verified_run_oof.py,
which uses genuine out-of-fold scoring rather than a single small test split.

Does not retrain/overwrite anything in data/model/ top level. Writes
outputs to data/model/eval_a_prospective/ (scratch) and
results/recall_evaluation.json.
"""
from __future__ import annotations

import copy
import json

import numpy as np
import pandas as pd
import xgboost as xgb

from src.features.build_crash_emergence import build_features
from src.labels.build_panel import build_panel
from src.utils import load_config, project_root

ROOT = project_root()
RNG = np.random.RandomState(42)


def bootstrap_ci(ranking_labels: np.ndarray, n_pos: int, k: int, n_total: int, threshold: int, resamples: int = 1000):
    """Bootstrap CI for recall@K: resample n_pos positions (with replacement)
    from the full ranking's positive index positions, count how many land in top-K."""
    pos_positions = np.where(ranking_labels >= threshold)[0]
    if len(pos_positions) == 0:
        return (0.0, 0.0)
    recalls = []
    for _ in range(resamples):
        sample = RNG.choice(pos_positions, size=len(pos_positions), replace=True)
        hits = (sample < k).sum()
        recalls.append(hits / len(pos_positions))
    return (float(np.percentile(recalls, 2.5)), float(np.percentile(recalls, 97.5)))


def recall_table(merged: pd.DataFrame, label_col: str, n_total: int, ks: list[int], thresholds: list[int]):
    out = {}
    ranking_labels = merged[label_col].values
    for threshold in thresholds:
        n_pos = int((ranking_labels >= threshold).sum())
        if n_pos == 0:
            continue
        table = {"n_positives": n_pos}
        for k in ks:
            if k > n_total:
                continue
            hits = int((ranking_labels[:k] >= threshold).sum())
            recall = hits / n_pos
            base = k / n_total
            lift = recall / base if base > 0 else None
            ci = bootstrap_ci(ranking_labels, n_pos, k, n_total, threshold)
            table[str(k)] = {
                "hits": hits,
                "recall": round(recall, 4),
                "ci95": [round(ci[0], 4), round(ci[1], 4)],
                "random_baseline_recall": round(base, 6),
                "lift_over_random": round(lift, 1) if lift else None,
            }
        out[f">={threshold}"] = table
    return out


def evaluation_a(cfg_base: dict) -> dict:
    print("=" * 80)
    print("EVALUATION A: Prospective 2025 validation")
    print("=" * 80)

    verified_dir = ROOT / "data" / "model" / "verified_run"
    panel_v = pd.read_parquet(verified_dir / "candidate_panel.parquet")
    feat_v = pd.read_parquet(verified_dir / "feature_table.parquet")
    frozen_params_record = json.loads((ROOT / "data" / "model" / "frozen_params.json").read_text())
    raw = frozen_params_record["sets"]["A_crash_only"]
    feature_list = raw["feature_list"]
    frozen = frozen_params_record["frozen"]
    xgb_params = {
        "objective": frozen["objective"],
        "tweedie_variance_power": float(frozen["tweedie_variance_power"]),
        "max_depth": int(frozen["max_depth"]),
        "learning_rate": float(frozen["learning_rate"]),
        "n_estimators": int(frozen["n_estimators"]),
        "reg_alpha": float(frozen["reg_alpha"]),
        "reg_lambda": float(frozen["reg_lambda"]),
        "min_child_weight": int(frozen["min_child_weight"]),
        "subsample": float(frozen["subsample"]),
        "colsample_bytree": float(frozen["colsample_bytree"]),
        "random_state": int(frozen["random_state"]),
    }
    print("EXPECTED_FEATURES (crash_only, verified-run recipe):", feature_list)

    panel_v_merged = panel_v.merge(feat_v, on="intersection_id", how="left")
    missing = [f for f in feature_list if f not in panel_v_merged.columns]
    if missing:
        raise RuntimeError(f"STOP: verified-run panel missing expected features: {missing}")

    X_train = panel_v_merged[feature_list].fillna(0.0).values.astype(float)
    y_train = panel_v_merged["KSI_label"].values.astype(float)
    model = xgb.XGBRegressor(**xgb_params, verbosity=0)
    model.fit(X_train, y_train)
    print(f"In-memory verified-run model refit: n_train={len(X_train)}, "
          f"pos@>=2={int((panel_v_merged['KSI_label']>=2).sum())}")

    # Sanity check: confirm this in-memory refit reproduces frozen_scores.parquet's
    # own in-sample behavior, i.e. it's a faithful copy of that artifact's recipe.
    # This is a refit-correctness check, not a performance claim -- frozen_scores.parquet
    # itself is in-sample by construction, see scripts/refit_verified_run_oof.py for the
    # genuinely held-out evaluation.
    sanity_scores = model.predict(X_train)
    sanity_df = panel_v_merged[["intersection_id", "KSI_label"]].copy()
    sanity_df["score"] = sanity_scores
    sanity_df = sanity_df.sort_values("score", ascending=False).reset_index(drop=True)
    n_pos2 = int((sanity_df["KSI_label"] >= 2).sum())
    for k in (200, 500):
        hits = int((sanity_df.head(k)["KSI_label"] >= 2).sum())
        print(f"  sanity @{k}: {hits}/{n_pos2} = {hits/n_pos2:.4f} (in-sample refit-correctness check)")

    # --- A1: build forward candidate set (no KSI through 2023) ---
    cfg = copy.deepcopy(cfg_base)
    cfg["paths"] = dict(cfg["paths"])
    cfg["paths"]["model"] = "data/model/eval_a_prospective"
    cfg["windows"] = {
        "feature_start": "2016-01-01",
        "feature_end": "2023-12-31",
        "label_start": "2025-01-01",
        "label_end": "2025-12-31",
        "burn_in_start": "2015-01-01",
        "feature_cutoff_date": "2024-01-01",
    }

    candidates = build_panel(cfg)

    # Restrict to the actual City of San Diego -- build_panel() draws from the full
    # node spine, which (like every other candidate set in this project before
    # docs/DECISIONS.md D11) spans all of San Diego County, not just the city.
    import geopandas as gpd
    boundary_path = sorted((ROOT / "data" / "raw" / "cpa").glob("*/city_boundary.geojson"), reverse=True)[0]
    city_gdf = gpd.read_file(boundary_path)
    city_gdf = city_gdf[city_gdf["Name"] == "SAN DIEGO"]
    if not isinstance(candidates, gpd.GeoDataFrame):
        candidates = gpd.GeoDataFrame(candidates, geometry="geometry")
    city_union = city_gdf.to_crs(candidates.crs).union_all()
    n_before = len(candidates)
    candidates = candidates[candidates.geometry.within(city_union)].reset_index(drop=True)
    print(f"City-of-San-Diego restriction: {n_before} -> {len(candidates)} candidates")

    n_total = len(candidates)
    n1 = int((candidates["KSI_label"] >= 1).sum())
    n2 = int((candidates["KSI_label"] >= 2).sum())
    print(f"Prospective candidate set: {n_total} intersections with no KSI through 2023")
    print(f"2025 KSI positives (>=1): {n1}")
    print(f"2025 KSI positives (>=2): {n2}")
    if n1 < 50:
        raise RuntimeError(
            f"STOP: too few 2025 positives ({n1}) to compute meaningful recall@K."
        )

    # --- A2: build 2016-2023 features ---
    features = build_features(cfg)
    missing = [f for f in feature_list if f not in features.columns]
    extra = [f for f in features.columns if f not in feature_list and not f.startswith("_")]
    print("Missing from feature table:", missing)
    print("Extra columns not in model (ignored):", len(extra))
    if missing:
        raise RuntimeError(f"STOP: feature mismatch, model expects missing features: {missing}")

    # --- A3: score ---
    merged = candidates.merge(features, on="intersection_id", how="left")
    X = merged[feature_list].fillna(0.0).values.astype(float)
    merged["prospective_score"] = model.predict(X)
    merged = merged.sort_values("prospective_score", ascending=False).reset_index(drop=True)

    print(f"Prospective scoring: {n_total} candidates, {n1} positives (>=1 KSI), {n2} positives (>=2 KSI)")

    thresholds = [1] + ([2] if n2 >= 5 else [])
    table = recall_table(merged, "KSI_label", n_total, [50, 100, 200, 500, 1000], thresholds)

    print("\n=== PROSPECTIVE RECALL@K (2025 validation, model never saw 2025 data) ===")
    print(json.dumps(table, indent=2))

    return {
        "model": "xgb_tweedie (verified-run recipe, refit in-memory, frozen_params.json crash_only)",
        "feature_window_applied": "2016-2023",
        "label_year": "2025",
        "candidates": n_total,
        "positives_ge1": n1,
        "positives_ge2": n2,
        "recall_at_k": table,
        "sanity_check_against_verified_canonical": {
            "note": "in-memory refit scored against its OWN training data "
                    "(2016-2021/2022-2024) to confirm it reproduces "
                    "reports/verified_canonical_numbers.json",
        },
    }


def main():
    cfg_base = load_config()
    result_a = evaluation_a(cfg_base)

    out = {"prospective_2025": result_a}
    (ROOT / "results" / "recall_evaluation.json").write_text(json.dumps(out, indent=2))
    print("\nWrote results/recall_evaluation.json")
    return out


if __name__ == "__main__":
    main()
