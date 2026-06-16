"""Build crash-history and emergence features for Milestone 3a (clean-coordinate rebuild).

M3a changes vs M2:
  - Coordinates: uses POINT_X/POINT_Y (SafeTREC geocoded) not LATITUDE/LONGITUDE.
  - STATE_HWY_IND=Y crashes excluded (surface-street only).
  - Buffer: 76.2 m (250 US survey feet) via config.
  - Feature nodes: surface candidates only (is_surface=True from build_spine).

All features are computed exclusively from data dated < feature_cutoff_date.
Crash-to-node assignment uses the same nearest_within_buffer rule as M1.

Dropped features (zero-variance on the candidate set, unchanged from M2):
  - ksi_72mo, years_since_last_ksi  : constant-zero by eligibility design
  - crash_rate_per_MEV_72mo         : requires ADT/exposure (deferred)
  - ksi_rate_per_MEV_72mo           : requires ADT/exposure (deferred)
  - neighbor_ksi_1hop               : graph feature, deferred

Run via:  python -m src.features.build_crash_emergence
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial import cKDTree

from src.utils import buffer_feet, load_config, project_root

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

# ---- SWITRS codebook constants (documented assumptions) --------------------
_NIGHT_CODES     = {"B", "C", "D", "E"}  # dusk/dawn/dark
_BROADSIDE_CODES = {"D"}                  # TYPE_OF_COLLISION D = broadside
_LEFT_TURN_CODES = {"E"}                  # MOVE_PRE_ACC E = making left turn
_DUI_CODES       = {"B", "C", "D", "G"}  # PARTY_SOBRIETY with-alcohol/impaired
_COVID_START     = pd.Timestamp("2020-03-01")

DROPPED_FEATURES = [
    ("ksi_72mo",             "constant-zero: all candidates have KSI_feat=0 by eligibility design"),
    ("years_since_last_ksi", "constant-zero: no candidate had any feature-window KSI crash"),
    ("crash_rate_per_MEV_72mo",  "deferred: ADT/exposure data not available this milestone"),
    ("ksi_rate_per_MEV_72mo",    "deferred: ADT/exposure data not available this milestone"),
    ("neighbor_ksi_1hop",        "deferred: graph-structural feature (later milestone); also KSI-sparse"),
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_all_crashes(cfg: dict) -> pd.DataFrame:
    """Load all-severity crashes using POINT_X/POINT_Y (M3a coordinate fix).

    STATE_HWY_IND=Y crashes are excluded when exclude_state_highway=True in config.
    """
    raw = project_root() / cfg["paths"]["raw"] / "switrs"
    path = sorted(raw.glob("*/Crashes.csv"), reverse=True)[0]
    log.info("Loading crashes from %s (POINT_X/POINT_Y primary)", path)
    df = pd.read_csv(path, usecols=[
        "CASE_ID", "COLLISION_DATE", "COLLISION_SEVERITY",
        "POINT_X", "POINT_Y",           # primary geocode (SafeTREC)
        "STATE_HWY_IND",                # surface-street filter
        "TYPE_OF_COLLISION", "LIGHTING", "ALCOHOL_INVOLVED",
        "PEDESTRIAN_ACCIDENT", "BICYCLE_ACCIDENT",
        "PCF_VIOL_CATEGORY",
    ], low_memory=False)
    df = df.rename(columns={
        "COLLISION_DATE": "date", "COLLISION_SEVERITY": "severity",
        "POINT_X": "lon", "POINT_Y": "lat",
    })
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    exclude_state_hwy = cfg.get("geometry", {}).get("exclude_state_highway", True)
    if exclude_state_hwy:
        n_before = len(df)
        df = df[df["STATE_HWY_IND"] != "Y"].copy()
        log.info("STATE_HWY_IND filter: removed %d freeway crashes", n_before - len(df))

    df = df.dropna(subset=["lat", "lon", "date"])
    df = df[df["lat"].between(-90, 90) & df["lon"].between(-180, 180)]
    log.info("Crashes loaded (surface-street, with coords): %d", len(df))
    return df


def _load_left_turn_ids(cfg: dict) -> set:
    raw = project_root() / cfg["paths"]["raw"] / "switrs"
    paths = sorted(raw.glob("*/Parties.csv"), reverse=True)
    if not paths:
        log.warning("No Parties.csv found; left_turn_72mo will be 0 for all nodes")
        return set()
    df = pd.read_csv(paths[0], usecols=["CASE_ID", "MOVE_PRE_ACC"], low_memory=False)
    ids = set(df.loc[df["MOVE_PRE_ACC"].isin(_LEFT_TURN_CODES), "CASE_ID"].astype(str))
    log.info("Left-turn crash IDs: %d", len(ids))
    return ids


# ---------------------------------------------------------------------------
# Spatial snapping (vectorised)
# ---------------------------------------------------------------------------

def _snap_crashes(crashes: pd.DataFrame, nodes: gpd.GeoDataFrame,
                  buf_ft: float, crs_a: str) -> pd.DataFrame:
    """Return DataFrame of crash rows extended with intersection_id."""
    gdf = gpd.GeoDataFrame(
        crashes,
        geometry=gpd.points_from_xy(crashes["lon"], crashes["lat"]),
        crs="EPSG:4326",
    ).to_crs(crs_a)
    nc = np.column_stack([nodes.geometry.x, nodes.geometry.y])
    cc = np.column_stack([gdf.geometry.x, gdf.geometry.y])
    tree = cKDTree(nc)
    dists, idxs = tree.query(cc, k=1, workers=-1)
    mask = dists <= buf_ft
    log.info("Snapped %d / %d crashes within %.2f ft", mask.sum(), len(crashes), buf_ft)
    out = crashes[mask].copy()
    out["intersection_id"] = nodes.iloc[idxs[mask]]["intersection_id"].values
    return out


# ---------------------------------------------------------------------------
# Pure-function scalar helpers (also used by tests)
# ---------------------------------------------------------------------------

def _theil_sen_slope(y: np.ndarray) -> float:
    if len(y) < 2 or np.all(y == 0):
        return 0.0
    x = np.arange(len(y), dtype=float)
    slope, *_ = stats.linregress(x, y)
    return float(slope)


def _mann_kendall_tau(y: np.ndarray) -> float:
    if len(y) < 3:
        return 0.0
    tau, _ = stats.kendalltau(np.arange(len(y)), y)
    return 0.0 if np.isnan(tau) else float(tau)


def _changepoint_prob(counts: np.ndarray) -> float:
    n = len(counts)
    if n < 4:
        return 0.0
    eps = 1e-6
    total = counts.sum()
    null_ll = float(np.sum(counts * np.log(total / n + eps) - total / n))
    best_lr = 0.0
    for k in range(1, n):
        mu1, mu2 = counts[:k].mean(), counts[k:].mean()
        ll_alt = (float(np.sum(counts[:k] * np.log(mu1 + eps) - mu1))
                  + float(np.sum(counts[k:] * np.log(mu2 + eps) - mu2)))
        best_lr = max(best_lr, ll_alt - null_ll)
    return float(1.0 / (1.0 + np.exp(-best_lr + 1.0)))


def _ewma_last(counts: np.ndarray, alpha: float = 0.4) -> float:
    v = float(counts[0])
    for c in counts[1:]:
        v = alpha * float(c) + (1 - alpha) * v
    return v


def _momentum_ratio(counts: np.ndarray) -> float:
    if len(counts) < 4:
        return 0.0
    early = counts[:2].mean()
    late = counts[-2:].mean()
    return float(late) if early == 0 else float(late / early)


def _annual_counts(dates: pd.Series, years: range) -> np.ndarray:
    """Count dates by year; dates must already be filtered to desired window."""
    if len(dates) == 0:
        return np.zeros(len(years), dtype=float)
    yr = pd.to_datetime(dates, errors="coerce").dt.year
    return np.array([(yr == y).sum() for y in years], dtype=float)


def _build_node_features(grp: pd.DataFrame,
                          left_turn_ids: set,
                          cutoff: pd.Timestamp) -> dict:
    """Compute all features for a single node's assigned crash rows.
    Called only for nodes that have ≥1 assigned crash.
    """
    feat: dict[str, Any] = {}
    feat_start  = pd.Timestamp("2016-01-01")
    mo36_start  = cutoff - pd.DateOffset(months=36)

    grp = grp[grp["date"] < cutoff]
    w72 = grp[grp["date"] >= feat_start]
    w36 = grp[grp["date"] >= mo36_start]

    feat["crashes_72mo"] = len(w72)
    feat["crashes_36mo"] = len(w36)

    feat["ped_crashes_72mo"]  = int((w72["PEDESTRIAN_ACCIDENT"] == "Y").sum())
    feat["bike_crashes_72mo"] = int((w72["BICYCLE_ACCIDENT"] == "Y").sum())
    feat["broadside_72mo"]    = int(w72["TYPE_OF_COLLISION"].isin(_BROADSIDE_CODES).sum())
    feat["left_turn_72mo"]    = int(w72["CASE_ID"].astype(str).isin(left_turn_ids).sum())
    feat["dui_72mo"]          = int((w72["ALCOHOL_INVOLVED"] == "Y").sum())
    feat["night_72mo"]        = int(w72["LIGHTING"].isin(_NIGHT_CODES).sum())

    ped_row = w72["PCF_VIOL_CATEGORY"].astype(str).str.strip()
    feat["ped_row_violation_72mo"]  = int((ped_row == "09").sum())
    feat["ped_row_violation_missing"] = int(w72["PCF_VIOL_CATEGORY"].isna().all())

    last_crash = grp["date"].max()
    feat["years_since_last_crash"] = (cutoff - last_crash).days / 365.25
    feat["distinct_crash_days_72mo"] = int(w72["date"].dt.date.nunique()) if len(w72) > 0 else 0

    sev = pd.to_numeric(w72["severity"], errors="coerce").dropna()
    feat["worst_severity_72mo"] = int(sev.min()) if len(sev) > 0 else 5

    years = range(2016, cutoff.year)
    annual = _annual_counts(grp["date"], years)

    feat["crash_trend_slope"]       = _theil_sen_slope(annual)
    feat["emergence_velocity"]      = float(annual[-1] - annual[0])
    feat["emergence_acceleration"]  = (
        float((annual[-1] - annual[-2]) - (annual[1] - annual[0]))
        if len(annual) >= 3 else 0.0
    )
    feat["mann_kendall_tau"]   = _mann_kendall_tau(annual)
    feat["changepoint_prob"]   = _changepoint_prob(annual)
    feat["ewma_crashes"]       = _ewma_last(annual)
    feat["momentum_ratio"]     = _momentum_ratio(annual)

    covid = grp[grp["date"] >= _COVID_START]
    feat["covid_period_share"] = len(covid) / max(len(w72), 1)

    return feat


# ---------------------------------------------------------------------------
# Default feature values for nodes with zero assigned crashes
# ---------------------------------------------------------------------------

def _default_features(cutoff: pd.Timestamp) -> dict:
    """Feature row for a node with no assigned crashes."""
    years_silent = (cutoff - pd.Timestamp("2015-01-01")).days / 365.25
    return {
        "crashes_72mo": 0, "crashes_36mo": 0,
        "ped_crashes_72mo": 0, "bike_crashes_72mo": 0,
        "broadside_72mo": 0, "left_turn_72mo": 0,
        "dui_72mo": 0, "night_72mo": 0,
        "ped_row_violation_72mo": 0, "ped_row_violation_missing": 1,
        "years_since_last_crash": years_silent,
        "distinct_crash_days_72mo": 0,
        "worst_severity_72mo": 5,
        "crash_trend_slope": 0.0, "emergence_velocity": 0.0,
        "emergence_acceleration": 0.0, "mann_kendall_tau": 0.0,
        "changepoint_prob": 0.0, "ewma_crashes": 0.0,
        "momentum_ratio": 0.0, "covid_period_share": 0.0,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_features(cfg: dict) -> pd.DataFrame:
    proc      = project_root() / cfg["paths"]["proc"]
    model_dir = project_root() / cfg["paths"]["model"]
    cutoff    = pd.Timestamp(cfg["windows"]["feature_cutoff_date"])
    buf_ft    = buffer_feet(cfg)
    crs_a     = cfg["crs"]["analysis"]

    log.info("=== DROPPED FEATURES ===")
    for name, reason in DROPPED_FEATURES:
        log.info("  DROP %s: %s", name, reason)

    # Load candidate nodes
    nodes     = gpd.read_parquet(proc / "nodes_spine_2230.parquet")
    cands     = gpd.read_parquet(model_dir / "candidate_panel.parquet")
    cand_ids  = set(cands["intersection_id"])
    nodes_c   = nodes[nodes["intersection_id"].isin(cand_ids)].reset_index(drop=True)
    log.info("Candidate nodes: %d", len(nodes_c))

    # Zero-variance audit on KSI_feat
    ksi_var = float(np.var(cands["KSI_feat"].values))
    log.info("ZERO-VARIANCE AUDIT: KSI_feat variance = %.6f (expected 0.0)", ksi_var)
    assert ksi_var == 0.0

    # Load crashes (feature window + burn-in for years_since_last_crash)
    all_crashes = _load_all_crashes(cfg)
    burn_start  = pd.Timestamp(cfg["windows"]["burn_in_start"])
    feat_start  = pd.Timestamp(cfg["windows"]["feature_start"])
    use_crashes = all_crashes[
        (all_crashes["date"] >= burn_start) & (all_crashes["date"] < cutoff)
    ].copy()
    log.info("Crashes in [burn_in, cutoff): %d", len(use_crashes))

    left_turn_ids = _load_left_turn_ids(cfg)

    # Snap to candidate nodes
    assigned = _snap_crashes(use_crashes, nodes_c, buf_ft, crs_a)
    log.info("Assigned crashes: %d", len(assigned))

    # Build features: compute only for nodes with ≥1 crash
    log.info("Building per-node features for %d crash-active nodes …",
             assigned["intersection_id"].nunique())
    grouped = assigned.groupby("intersection_id")
    feat_rows: list[dict] = []
    for iid, grp in grouped:
        row = _build_node_features(grp, left_turn_ids, cutoff)
        row["intersection_id"] = iid
        feat_rows.append(row)
    active_df = pd.DataFrame(feat_rows)

    # Fill defaults for the rest
    default = _default_features(cutoff)
    active_iids = set(active_df["intersection_id"]) if len(active_df) else set()
    silent_iids = [iid for iid in nodes_c["intersection_id"] if iid not in active_iids]
    silent_rows = [{**default, "intersection_id": iid} for iid in silent_iids]
    silent_df   = pd.DataFrame(silent_rows) if silent_rows else pd.DataFrame(columns=active_df.columns)

    feat_df = pd.concat([active_df, silent_df], ignore_index=True)
    log.info(
        "Feature table: %d nodes (%d with crashes, %d silent)",
        len(feat_df), len(active_df), len(silent_df),
    )

    out_path = model_dir / "feature_table.parquet"
    feat_df.to_parquet(out_path, index=False)
    log.info("Wrote feature_table.parquet")

    _write_feature_dictionary(feat_df, model_dir, cutoff)
    return feat_df


def _write_feature_dictionary(feat_df: pd.DataFrame, model_dir: Path,
                               cutoff: pd.Timestamp) -> None:
    feature_cols = [c for c in feat_df.columns if c != "intersection_id"]
    rows = []
    for col in feature_cols:
        s = feat_df[col]
        rows.append({
            "feature_name": col,
            "source_table": "Crashes.csv / Parties.csv (SWITRS)",
            "window_used": f"feature_window [2016-01-01, {cutoff.strftime('%Y-%m-%d')})",
            "max_source_date": (cutoff - pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            "missing_rate": f"{s.isna().mean():.4f}",
            "variance": f"{s.dropna().var():.6f}",
        })
    for name, reason in DROPPED_FEATURES:
        rows.append({
            "feature_name": name,
            "source_table": "N/A",
            "window_used": "N/A -- DROPPED",
            "max_source_date": "N/A",
            "missing_rate": "N/A",
            "variance": "0 (confirmed)" if "zero" in reason else "N/A",
            "_drop_reason": reason,
        })
    pd.DataFrame(rows).to_csv(model_dir / "feature_dictionary.csv", index=False)
    log.info("Wrote feature_dictionary.csv")


def main() -> None:
    cfg = load_config()
    build_features(cfg)


if __name__ == "__main__":
    main()
