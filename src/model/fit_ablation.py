"""M3b ablation: incremental feature-group fitting.

Fits the 4-model suite for each cumulative feature group:
  crash_only → +geometry → +control → +roadway → +active_transport → +terrain → all

Also fits an endogenous-excluded variant (crash_only + static infra only).

For each ablation step:
  - Logistic L2 (binary ≥1)
  - XGBoost binary (binary ≥1, Optuna-tuned)
  - XGBoost Tweedie (count, PRIMARY, Optuna-tuned)
  - Persistence baseline (unchanged)

Saves:
  data/model/ablation_scores.parquet  — scores for every (intersection_id, step)
  data/model/ablation_params.json     — tuned XGBoost params per step

Run via:  python -m src.model.fit_ablation
"""
from __future__ import annotations

import json
import logging
import pickle
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from src.eval.splitter import add_spatial_blocks
from src.model.fit import (
    FEATURE_COLS,
    _prepare_xy,
    _tweedie_deviance,
    fit_logistic,
    persistence_baseline_scores,
    tune_xgb_binary,
    tune_xgb_tweedie,
)
from src.utils import load_config, project_root

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
warnings.filterwarnings("ignore", category=UserWarning)


# Ablation steps: each entry is (step_name, extra_feature_cols)
# Cumulative: each step adds its group to all prior groups.
def _ablation_steps(cfg: dict) -> list[tuple[str, list[str]]]:
    groups = cfg["feature_groups"]
    base = groups["crash_only"]

    geom  = [f for f in groups["geometry"]        if f not in ("lane_count_missing", "approach_asymmetry")]
    ctrl  = [f for f in groups["control"]         ]
    road  = [f for f in groups["roadway"]         ]
    at    = [f for f in groups["active_transport"] ]
    terr  = [f for f in groups["terrain"]         ]

    steps = [
        ("crash_only",       base),
        ("crash+geometry",   base + geom),
        ("crash+control",    base + geom + ctrl),
        ("crash+roadway",    base + geom + ctrl + road),
        ("crash+active",     base + geom + ctrl + road + at),
        ("crash+terrain",    base + geom + ctrl + road + at + terr),
        ("all",              base + geom + ctrl + road + at + terr),
        # Endogenous-excluded: crash + static infra only (geometry, functional_class, freeway_proximity, terrain)
        ("static_infra_only", base + geom + ["functional_class", "freeway_proximity"] + terr),
    ]
    return steps


def _available_cols(wanted: list[str], panel: pd.DataFrame) -> list[str]:
    """Return subset of wanted that exists in panel and has non-zero variance on candidates."""
    have = [c for c in wanted if c in panel.columns]
    ok   = []
    for c in have:
        if panel[c].var() > 0:
            ok.append(c)
        else:
            log.debug("Dropping zero-variance col '%s' from ablation step", c)
    return ok


def run_ablation(cfg: dict) -> pd.DataFrame:
    """Fit all ablation steps; return wide scores DataFrame."""
    model_dir = project_root() / cfg["paths"]["model"]
    seed      = cfg["project"]["rng_seed"]

    # Load panels
    candidates   = gpd.read_parquet(model_dir / "candidate_panel.parquet")
    crash_feats  = pd.read_parquet(model_dir / "feature_table.parquet")
    try:
        infra_feats = pd.read_parquet(model_dir / "infra_features.parquet")
    except FileNotFoundError:
        log.warning("infra_features.parquet not found — ablation will only run crash_only step")
        infra_feats = pd.DataFrame({"intersection_id": candidates["intersection_id"]})

    panel = candidates.merge(crash_feats, on="intersection_id", how="left")
    panel = panel.merge(infra_feats,      on="intersection_id", how="left")

    if "spatial_block" not in panel.columns:
        panel = add_spatial_blocks(panel, cfg)

    log.info(
        "Ablation panel: %d rows | pos@>=2: %d | pos@>=1: %d | cols: %d",
        len(panel), (panel["KSI_label"] >= 2).sum(),
        (panel["KSI_label"] >= 1).sum(), panel.shape[1],
    )

    X_all    = panel.drop(columns=["intersection_id", "geometry", "KSI_label",
                                    "KSI_feat", "y", "y_ge1", "y_ge2",
                                    "geometry_4326", "lon", "lat",
                                    "spatial_block", "is_trunk_borderline"],
                           errors="ignore")
    y_count  = panel["KSI_label"].values.astype(float)
    y_bin1   = (y_count >= 1).astype(int)
    groups   = panel["spatial_block"].values

    steps = _ablation_steps(cfg)
    all_params: dict = {}
    scores_dict: dict = {"intersection_id": panel["intersection_id"].values}

    # Persistence baseline (constant across steps)
    baseline_sc = persistence_baseline_scores(panel)
    scores_dict["baseline"] = baseline_sc

    for step_name, feat_list in steps:
        log.info("=== Ablation step: %s (%d requested features) ===", step_name, len(feat_list))
        cols = _available_cols(feat_list, panel)
        log.info("  Available: %d / %d features", len(cols), len(feat_list))
        if not cols:
            log.warning("  No features available for step %s — skipping", step_name)
            continue

        X = panel[cols].fillna(0.0).values.astype(float)

        # Logistic (binary ≥1)
        log_pipe = fit_logistic(X, y_bin1, seed)
        lr_sc    = log_pipe.predict_proba(X)[:, 1]
        scores_dict[f"{step_name}__logistic"] = lr_sc

        # XGBoost binary (tuned)
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        xgb_bin_params = tune_xgb_binary(X, y_bin1, groups, cfg)
        import xgboost as xgb
        xgb_bin = xgb.XGBClassifier(**xgb_bin_params, verbosity=0, use_label_encoder=False)
        xgb_bin.fit(X, y_bin1)
        bin_sc = xgb_bin.predict_proba(X)[:, 1]
        scores_dict[f"{step_name}__xgb_binary"] = bin_sc

        # XGBoost Tweedie (tuned, PRIMARY)
        xgb_tw_params = tune_xgb_tweedie(X, y_count, groups, cfg)
        xgb_tw = xgb.XGBRegressor(**xgb_tw_params, verbosity=0)
        xgb_tw.fit(X, y_count)
        tw_sc = xgb_tw.predict(X)
        scores_dict[f"{step_name}__xgb_tweedie"] = tw_sc

        all_params[step_name] = {
            "n_features": len(cols),
            "feature_list": cols,
            "xgb_binary": {k: str(v) for k, v in xgb_bin_params.items()},
            "xgb_tweedie": {k: str(v) for k, v in xgb_tw_params.items()},
        }
        log.info("  Step '%s' done", step_name)

    # Save scores
    scores_df = pd.DataFrame(scores_dict)
    scores_df.to_parquet(model_dir / "ablation_scores.parquet", index=False)
    log.info("Wrote ablation_scores.parquet (%d rows × %d cols)", len(scores_df), scores_df.shape[1])

    with open(model_dir / "ablation_params.json", "w") as f:
        json.dump(all_params, f, indent=2)

    return scores_df


def main() -> None:
    cfg = load_config()
    run_ablation(cfg)


if __name__ == "__main__":
    main()
