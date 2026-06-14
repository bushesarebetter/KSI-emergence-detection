"""Supplemental terrain ablation step.

The primary fit_ablation.py loaded infra_features.parquet before the DEM CRS
bug was fixed, so slope_pct was all-NaN → zero-variance → dropped.  This script
re-loads the corrected infra_features.parquet and appends supplemental score
columns to ablation_scores.parquet:

  crash+terrain_supp      — crash_only + geometry + control + roadway + active + slope_pct
  all_supp                — same as above (terrain is the only new thing; 'all' = 'crash+terrain')
  static_infra_only_supp  — crash_only + geometry + functional_class + freeway_proximity + slope_pct

Saves supplemental columns in-place to data/model/ablation_scores.parquet and
writes supplemental params to data/model/ablation_params_terrain_supp.json.

Run via:  python -m src.model.fit_terrain_supp
"""
from __future__ import annotations

import json
import logging
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd

from src.eval.splitter import add_spatial_blocks
from src.model.fit import (
    fit_logistic,
    persistence_baseline_scores,
    tune_xgb_binary,
    tune_xgb_tweedie,
)
from src.utils import load_config, project_root

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
warnings.filterwarnings("ignore", category=UserWarning)


def _available_cols(wanted: list[str], panel: pd.DataFrame) -> list[str]:
    have = [c for c in wanted if c in panel.columns]
    ok = []
    for c in have:
        if panel[c].var() > 0:
            ok.append(c)
        else:
            log.debug("Dropping zero-variance col '%s'", c)
    return ok


def run_terrain_supp(cfg: dict) -> None:
    model_dir = project_root() / cfg["paths"]["model"]
    seed = cfg["project"]["rng_seed"]

    # Load panels (fresh reads — slope_pct now present at 60.1%)
    candidates = gpd.read_parquet(model_dir / "candidate_panel.parquet")
    crash_feats = pd.read_parquet(model_dir / "feature_table.parquet")
    infra_feats = pd.read_parquet(model_dir / "infra_features.parquet")

    panel = candidates.merge(crash_feats, on="intersection_id", how="left")
    panel = panel.merge(infra_feats, on="intersection_id", how="left")
    if "spatial_block" not in panel.columns:
        panel = add_spatial_blocks(panel, cfg)

    slope_coverage = panel["slope_pct"].notna().mean() * 100
    log.info("slope_pct coverage in panel: %.1f%%", slope_coverage)
    if slope_coverage < 1.0:
        log.error("slope_pct still zero-coverage — DEM not fixed. Aborting supplemental run.")
        return

    groups_cfg = cfg["feature_groups"]
    base = groups_cfg["crash_only"]
    geom = groups_cfg["geometry"]
    ctrl = groups_cfg["control"]
    road = groups_cfg["roadway"]
    at = groups_cfg["active_transport"]
    terr = ["slope_pct", "slope_pct_missing"]

    supp_steps = [
        ("crash+terrain_supp",     base + geom + ctrl + road + at + terr),
        ("all_supp",               base + geom + ctrl + road + at + terr),  # same features
        ("static_infra_only_supp", base + geom + ["functional_class", "freeway_proximity"] + terr),
    ]

    y_count = panel["KSI_label"].values.astype(float)
    y_bin1 = (y_count >= 1).astype(int)
    groups_arr = panel["spatial_block"].values

    # Load existing scores to merge into
    scores_path = model_dir / "ablation_scores.parquet"
    scores_df = pd.read_parquet(scores_path) if scores_path.exists() else pd.DataFrame(
        {"intersection_id": panel["intersection_id"].values}
    )

    all_params: dict = {}

    import optuna
    import xgboost as xgb
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    for step_name, feat_list in supp_steps:
        log.info("=== Supplemental step: %s (%d requested) ===", step_name, len(feat_list))
        cols = _available_cols(feat_list, panel)
        log.info("  Available: %d / %d features", len(cols), len(feat_list))
        if not cols:
            log.warning("  No features — skipping")
            continue

        X = panel[cols].fillna(0.0).values.astype(float)

        # Logistic
        log_pipe = fit_logistic(X, y_bin1, seed)
        scores_df[f"{step_name}__logistic"] = log_pipe.predict_proba(X)[:, 1]

        # XGB binary
        xgb_bin_params = tune_xgb_binary(X, y_bin1, groups_arr, cfg)
        xgb_bin = xgb.XGBClassifier(**xgb_bin_params, verbosity=0, use_label_encoder=False)
        xgb_bin.fit(X, y_bin1)
        scores_df[f"{step_name}__xgb_binary"] = xgb_bin.predict_proba(X)[:, 1]

        # XGB Tweedie (PRIMARY)
        xgb_tw_params = tune_xgb_tweedie(X, y_count, groups_arr, cfg)
        xgb_tw = xgb.XGBRegressor(**xgb_tw_params, verbosity=0)
        xgb_tw.fit(X, y_count)
        scores_df[f"{step_name}__xgb_tweedie"] = xgb_tw.predict(X)

        all_params[step_name] = {
            "n_features": len(cols),
            "feature_list": cols,
            "xgb_binary": {k: str(v) for k, v in xgb_bin_params.items()},
            "xgb_tweedie": {k: str(v) for k, v in xgb_tw_params.items()},
        }
        log.info("  Step '%s' done", step_name)

    scores_df.to_parquet(scores_path, index=False)
    log.info("Updated ablation_scores.parquet (%d rows × %d cols)", len(scores_df), scores_df.shape[1])

    params_path = model_dir / "ablation_params_terrain_supp.json"
    params_path.write_text(json.dumps(all_params, indent=2))
    log.info("Wrote %s", params_path)


def main() -> None:
    cfg = load_config()
    run_terrain_supp(cfg)


if __name__ == "__main__":
    main()
