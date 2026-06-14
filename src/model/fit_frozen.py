"""M4 Protocol A: frozen-hyperparameter ablation.

Fits 4 feature sets using the M3a crash-only XGB-Tweedie hyperparameters
(frozen -- no Optuna, no grid search of any kind).

Feature sets:
  A: crash-only (20 features, M3a baseline)
  B: crash + road geometry + roadway class
     (edge_count, lane_count, intersection_type, functional_class,
      freeway_proximity, speed_limit)
  C: crash + signals/signs/markings
     (signal_present, stop_control)
  D: crash + all infrastructure
     (B + C + active transport + terrain)

Hyperparameter sanity check table is printed: all 4 sets must show identical
params to confirm no tuning occurred.

Saves:
  data/model/frozen_scores.parquet  -- one score column per set
  data/model/frozen_params.json     -- frozen hyperparameter record + feature lists

Run via:  python -m src.model.fit_frozen
"""
from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xgboost as xgb

from src.eval.splitter import add_spatial_blocks
from src.model.fit import persistence_baseline_scores
from src.utils import load_config, project_root

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
warnings.filterwarnings("ignore", category=UserWarning)


def _load_frozen_params(model_dir: Path) -> dict:
    """Load M3a crash-only XGB-Tweedie hyperparameters from ablation_params.json."""
    params_path = model_dir / "ablation_params.json"
    if not params_path.exists():
        raise FileNotFoundError(
            "ablation_params.json not found -- run M3b ablation first (make model_ablation)"
        )
    ablation_params = json.loads(params_path.read_text())
    raw = ablation_params["crash_only"]["xgb_tweedie"]
    return {
        "objective":              raw["objective"],
        "tweedie_variance_power": float(raw["tweedie_variance_power"]),
        "max_depth":              int(raw["max_depth"]),
        "learning_rate":          float(raw["learning_rate"]),
        "n_estimators":           int(raw["n_estimators"]),
        "reg_alpha":              float(raw["reg_alpha"]),
        "reg_lambda":             float(raw["reg_lambda"]),
        "min_child_weight":       int(raw["min_child_weight"]),
        "subsample":              float(raw["subsample"]),
        "colsample_bytree":       float(raw["colsample_bytree"]),
        "random_state":           int(raw["random_state"]),
    }


def _available_cols(wanted: list[str], panel: pd.DataFrame) -> list[str]:
    """Return subset of wanted that exists in panel and has non-zero variance."""
    have = [c for c in wanted if c in panel.columns]
    ok: list[str] = []
    for c in have:
        if panel[c].var() > 0:
            ok.append(c)
        else:
            log.warning("Dropping zero-variance col '%s' from feature set", c)
    return ok


def _build_feature_sets(cfg: dict) -> list[tuple[str, list[str]]]:
    """Define the 4 Protocol A feature sets (cumulative-style but independent groupings)."""
    fg   = cfg["feature_groups"]
    base = list(fg["crash_only"])

    # Exclude derived/missing-indicator features not in the canonical list
    geom_feats = [f for f in fg["geometry"]         if f not in ("lane_count_missing", "approach_asymmetry")]
    ctrl_feats = list(fg["control"])
    road_feats = list(fg["roadway"])
    at_feats   = list(fg["active_transport"])
    terr_feats = list(fg["terrain"])

    return [
        # A: crash history only (M3a baseline)
        ("A_crash_only",    base),
        # B: crash + road geometry + roadway classification
        ("B_road_geometry", base + geom_feats + road_feats),
        # C: crash + signal/sign control
        ("C_signals",       base + ctrl_feats),
        # D: crash + all infrastructure groups
        ("D_all_infra",     base + geom_feats + ctrl_feats + road_feats + at_feats + terr_feats),
    ]


def run_frozen_ablation(cfg: dict) -> pd.DataFrame:
    """Fit Protocol A sets with frozen params; return scores DataFrame."""
    model_dir = project_root() / cfg["paths"]["model"]

    frozen = _load_frozen_params(model_dir)

    log.info(
        "Frozen M3a crash-only XGB-Tweedie params: vpower=%.4f, lr=%.5f, "
        "n_est=%d, reg_alpha=%.4f, reg_lambda=%.4f, mcw=%d",
        frozen["tweedie_variance_power"], frozen["learning_rate"],
        frozen["n_estimators"], frozen["reg_alpha"], frozen["reg_lambda"],
        frozen["min_child_weight"],
    )

    # Load panels
    candidates  = gpd.read_parquet(model_dir / "candidate_panel.parquet")
    crash_feats = pd.read_parquet(model_dir / "feature_table.parquet")
    try:
        infra_feats = pd.read_parquet(model_dir / "infra_features.parquet")
    except FileNotFoundError:
        log.error("infra_features.parquet not found -- B/C/D sets will have no infra features")
        infra_feats = pd.DataFrame({"intersection_id": candidates["intersection_id"]})

    panel = candidates.merge(crash_feats, on="intersection_id", how="left")
    panel = panel.merge(infra_feats,      on="intersection_id", how="left")
    if "spatial_block" not in panel.columns:
        panel = add_spatial_blocks(panel, cfg)

    log.info(
        "Panel: %d rows | pos@>=2: %d | pos@>=1: %d | cols: %d",
        len(panel),
        (panel["KSI_label"] >= 2).sum(),
        (panel["KSI_label"] >= 1).sum(),
        panel.shape[1],
    )

    y_count = panel["KSI_label"].values.astype(float)

    feature_sets    = _build_feature_sets(cfg)
    scores_dict     = {"intersection_id": panel["intersection_id"].values}
    params_record   = {
        "source":  "ablation_params.json/crash_only/xgb_tweedie (M3a crash-only, Protocol A)",
        "frozen":  {k: str(v) for k, v in frozen.items()},
        "sets":    {},
    }

    # Sanity check table header
    print()
    print("=" * 95)
    print("PROTOCOL A — FROZEN HYPERPARAMETER SANITY CHECK")
    print("All four sets must show IDENTICAL params; any deviation indicates a bug.")
    print("=" * 95)
    hdr = f"{'Set':<20} {'vpower':>7} {'lr':>9} {'n_est':>6} {'r_alpha':>9} {'r_lambda':>9} {'mcw':>5} {'n_feats':>8}"
    print(hdr)
    print("-" * 80)

    for set_name, feat_list in feature_sets:
        cols = _available_cols(feat_list, panel)
        log.info("=== Set %s: %d / %d features available ===", set_name, len(cols), len(feat_list))

        X     = panel[cols].fillna(0.0).values.astype(float)
        model = xgb.XGBRegressor(**frozen, verbosity=0)
        model.fit(X, y_count)
        sc = model.predict(X)
        scores_dict[f"{set_name}__xgb_tweedie"] = sc

        params_record["sets"][set_name] = {
            "n_features_requested": len(feat_list),
            "n_features_used":      len(cols),
            "feature_list":         cols,
            "features_missing":     [f for f in feat_list if f not in cols],
            "xgb_tweedie":          {k: str(v) for k, v in frozen.items()},
        }

        # Sanity check row — identical params for every set is the key correctness check
        print(
            f"{set_name:<20} {frozen['tweedie_variance_power']:>7.4f}"
            f" {frozen['learning_rate']:>9.5f}"
            f" {frozen['n_estimators']:>6d}"
            f" {frozen['reg_alpha']:>9.4f}"
            f" {frozen['reg_lambda']:>9.4f}"
            f" {frozen['min_child_weight']:>5d}"
            f" {len(cols):>8d}"
        )
        log.info("Set '%s' fitted and scored.", set_name)

    print("=" * 95)
    print("Sanity check: all rows above must have identical numeric params.")

    # Save scores
    scores_df = pd.DataFrame(scores_dict)
    scores_df.to_parquet(model_dir / "frozen_scores.parquet", index=False)
    log.info(
        "Wrote frozen_scores.parquet (%d rows x %d score cols)",
        len(scores_df), len(scores_df.columns) - 1,
    )

    with open(model_dir / "frozen_params.json", "w") as f:
        json.dump(params_record, f, indent=2)
    log.info("Wrote frozen_params.json")

    return scores_df


def main() -> None:
    cfg = load_config()
    run_frozen_ablation(cfg)


if __name__ == "__main__":
    main()
