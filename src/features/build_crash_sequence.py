"""Raw per-year crash-history sequences, for the NN-sequence experiment only.

This is additive: it does not touch build_crash_emergence.py, build_panel.py, or
any of their output files. It reuses the same snapping rule (_snap_crashes,
nearest-within-buffer, same buffer_feet/CRS, same STATE_HWY_IND exclusion) so the
sequence channels are computed on the exact same crash-to-node assignment as the
hand-engineered features, just without collapsing years into engineered stats.

Each candidate intersection gets one row per feature year with 8 RAW counts:
  [total_crashes, ksi_crashes, injury_crashes, pdo_crashes,
   ped_crashes, bike_crashes, broadside, night]
No slopes, no EWMA, no changepoint, no engineered ratios. Silent nodes get an
all-zero sequence for every year.

Two windows, two outputs:
  verified: feature years 2016-2021 (cutoff 2022-01-01) -> data/model/verified_run/crash_sequence.parquet
  forward:  feature years 2016-2024 (cutoff 2025-01-01, configs/config.yaml's
            feature_cutoff_date) -> data/model/forward_run/crash_sequence.parquet

The verified window's cutoff is hardcoded here (2022-01-01) because
configs/config.yaml currently holds the forward run's window (see D6/D12); the
verified-run candidate panel/feature table on disk were themselves built under
that now-overwritten earlier config state and are reused as-is, the same way
scripts/refit_verified_run_oof.py and model_bakeoff_oof.py reuse them without
re-deriving the window from the live config.

Run via:  python -m src.features.build_crash_sequence
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from src.utils import buffer_feet, load_config, project_root

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

_NIGHT_CODES = {"B", "C", "D", "E"}
_BROADSIDE_CODES = {"D"}
_KSI_CODES = {1, 2}
_PDO_CODE = 0

CHANNELS = [
    "total_crashes", "ksi_crashes", "injury_crashes", "pdo_crashes",
    "ped_crashes", "bike_crashes", "broadside", "night",
]

VERIFIED_FEATURE_START = pd.Timestamp("2016-01-01")
VERIFIED_CUTOFF = pd.Timestamp("2022-01-01")  # feature years 2016-2021, see D6


# ---------------------------------------------------------------------------
# Crash loading + snapping (mirrors src/features/build_crash_emergence.py)
# ---------------------------------------------------------------------------

def _load_all_crashes(cfg: dict) -> pd.DataFrame:
    """Same loader as build_crash_emergence._load_all_crashes (POINT_X/POINT_Y,
    STATE_HWY_IND exclusion, multi-dir dedup on CASE_ID)."""
    exclude_state_hwy = cfg.get("geometry", {}).get("exclude_state_highway", True)
    usecols = [
        "CASE_ID", "COLLISION_DATE", "COLLISION_SEVERITY",
        "POINT_X", "POINT_Y", "STATE_HWY_IND",
        "TYPE_OF_COLLISION", "LIGHTING",
        "PEDESTRIAN_ACCIDENT", "BICYCLE_ACCIDENT",
    ]

    def _read_one(path: Path) -> pd.DataFrame:
        log.info("Loading crashes from %s", path)
        d = pd.read_csv(path, usecols=usecols, low_memory=False)
        d = d.rename(columns={
            "COLLISION_DATE": "date", "COLLISION_SEVERITY": "severity",
            "POINT_X": "lon", "POINT_Y": "lat",
        })
        d["date"] = pd.to_datetime(d["date"], errors="coerce")
        if exclude_state_hwy:
            n_before = len(d)
            d = d[d["STATE_HWY_IND"] != "Y"].copy()
            log.info("STATE_HWY_IND filter: removed %d freeway crashes", n_before - len(d))
        d = d.dropna(subset=["lat", "lon", "date"])
        d = d[d["lat"].between(-90, 90) & d["lon"].between(-180, 180)]
        return d

    if "switrs_dirs" in cfg:
        frames = [_read_one(project_root() / d / "Crashes.csv") for d in cfg["switrs_dirs"]]
        df = pd.concat(frames, ignore_index=True)
        n_before = len(df)
        df = df.drop_duplicates(subset=["CASE_ID"]).reset_index(drop=True)
        log.info("Merged %d crash records; dropped %d duplicates; %d remain",
                  n_before, n_before - len(df), len(df))
    elif "switrs_dir" in cfg:
        df = _read_one(project_root() / cfg["switrs_dir"] / "Crashes.csv")
    else:
        raw = project_root() / cfg["paths"]["raw"] / "switrs"
        paths = sorted(raw.glob("*/Crashes.csv"), reverse=True)
        if not paths:
            raise FileNotFoundError(f"No Crashes.csv found under {raw}")
        df = _read_one(paths[0])
    return df


def _snap_crashes(crashes: pd.DataFrame, nodes: gpd.GeoDataFrame,
                   buf_ft: float, crs_a: str) -> pd.DataFrame:
    """Identical snapping rule to build_crash_emergence._snap_crashes:
    nearest_within_buffer, one crash -> at most one node."""
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
# Per-year channel counts
# ---------------------------------------------------------------------------

def _year_channels(grp: pd.DataFrame, year: int) -> list[float]:
    yr = grp[grp["date"].dt.year == year]
    sev = pd.to_numeric(yr["severity"], errors="coerce")
    return [
        float(len(yr)),
        float(sev.isin(_KSI_CODES).sum()),
        float(sev.isin({3, 4}).sum()),
        float((sev == _PDO_CODE).sum()),
        float((yr["PEDESTRIAN_ACCIDENT"] == "Y").sum()),
        float((yr["BICYCLE_ACCIDENT"] == "Y").sum()),
        float(yr["TYPE_OF_COLLISION"].isin(_BROADSIDE_CODES).sum()),
        float(yr["LIGHTING"].isin(_NIGHT_CODES).sum()),
    ]


def build_sequence(
    candidate_ids: list[str],
    nodes: gpd.GeoDataFrame,
    assigned: pd.DataFrame,
    feature_start: pd.Timestamp,
    cutoff: pd.Timestamp,
) -> pd.DataFrame:
    """One row per (intersection_id, year) with the 8 raw channels. Silent
    candidates (no assigned crashes at all) still get one all-zero row per year."""
    years = list(range(feature_start.year, cutoff.year))
    grouped = assigned.groupby("intersection_id")
    rows: list[dict] = []
    active_ids = set()
    for iid, grp in grouped:
        if iid not in set(candidate_ids):
            continue
        active_ids.add(iid)
        grp = grp[(grp["date"] >= feature_start) & (grp["date"] < cutoff)]
        for y in years:
            vals = _year_channels(grp, y)
            rows.append({"intersection_id": iid, "year": y, **dict(zip(CHANNELS, vals))})

    for iid in candidate_ids:
        if iid in active_ids:
            continue
        for y in years:
            rows.append({"intersection_id": iid, "year": y, **{c: 0.0 for c in CHANNELS}})

    return pd.DataFrame(rows)


def _sequence_to_array(seq_df: pd.DataFrame, candidate_ids: list[str], years: list[int]) -> tuple[np.ndarray, list[str]]:
    """Pivot the long (intersection_id, year, channel) table into
    (n_nodes, n_years, n_channels), in candidate_ids order."""
    n_nodes, n_years, n_ch = len(candidate_ids), len(years), len(CHANNELS)
    arr = np.zeros((n_nodes, n_years, n_ch), dtype=np.float32)
    id_pos = {iid: i for i, iid in enumerate(candidate_ids)}
    yr_pos = {y: i for i, y in enumerate(years)}
    for row in seq_df.itertuples(index=False):
        i = id_pos[row.intersection_id]
        j = yr_pos[row.year]
        arr[i, j, :] = [getattr(row, c) for c in CHANNELS]
    return arr, candidate_ids


def run_window(cfg: dict, label: str, candidate_panel_path: Path,
               feature_start: pd.Timestamp, cutoff: pd.Timestamp, out_path: Path) -> pd.DataFrame:
    log.info("=== Building crash sequence: %s window (features [%s, %s)) ===",
             label, feature_start.date(), cutoff.date())
    crs_a = cfg["crs"]["analysis"]
    buf_ft = buffer_feet(cfg)

    proc = project_root() / cfg["paths"]["proc"]
    nodes = gpd.read_parquet(proc / "nodes_spine_2230.parquet")
    panel = gpd.read_parquet(candidate_panel_path)
    candidate_ids = panel["intersection_id"].tolist()
    nodes_c = nodes[nodes["intersection_id"].isin(set(candidate_ids))].reset_index(drop=True)

    all_crashes = _load_all_crashes(cfg)
    burn_start = pd.Timestamp(cfg["windows"]["burn_in_start"])
    use_crashes = all_crashes[
        (all_crashes["date"] >= max(burn_start, feature_start)) & (all_crashes["date"] < cutoff)
    ].copy()
    log.info("%s: crashes in feature window: %d", label, len(use_crashes))

    assigned = _snap_crashes(use_crashes, nodes_c, buf_ft, crs_a)
    seq_df = build_sequence(candidate_ids, nodes_c, assigned, feature_start, cutoff)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    seq_df.to_parquet(out_path, index=False)
    log.info("Wrote %s (%d rows, %d candidates x %d years)",
              out_path, len(seq_df), len(candidate_ids), cutoff.year - feature_start.year)
    return seq_df


def main() -> None:
    cfg = load_config()
    model_dir = project_root() / cfg["paths"]["model"]

    run_window(
        cfg, "verified",
        candidate_panel_path=model_dir / "verified_run" / "candidate_panel.parquet",
        feature_start=VERIFIED_FEATURE_START,
        cutoff=VERIFIED_CUTOFF,
        out_path=model_dir / "verified_run" / "crash_sequence.parquet",
    )

    fwd_cutoff = pd.Timestamp(cfg["windows"]["feature_cutoff_date"])
    fwd_feature_start = pd.Timestamp(cfg["windows"]["feature_start"])
    run_window(
        cfg, "forward",
        candidate_panel_path=model_dir / "forward_run" / "candidate_panel.parquet",
        feature_start=fwd_feature_start,
        cutoff=fwd_cutoff,
        out_path=model_dir / "forward_run" / "crash_sequence.parquet",
    )


if __name__ == "__main__":
    main()
