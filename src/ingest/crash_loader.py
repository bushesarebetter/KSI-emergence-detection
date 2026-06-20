"""Crash data loader: SWITRS primary, SDPD open-data fallback.

Coordinate fields (M3a correction):
  Use POINT_X (longitude) / POINT_Y (latitude) as the primary geocode source.
  These are SafeTREC street/intersection-geocoded coordinates in WGS84 decimal
  degrees, present for ~96% of records.  LATITUDE/LONGITUDE (officer GPS or
  CHP postmile) is ~44% populated and ~98.5% freeway crashes; it is loaded only
  as a logged diagnostic, never used for geometry.

Surface-street filter:
  When cfg["geometry"]["exclude_state_highway"] is true (default), crashes with
  STATE_HWY_IND='Y' are excluded before saving the parquet.  These are crashes
  on state-numbered highways and represent freeway/ramp KSI that should not be
  attributed to intersection nodes.

COLLISION_SEVERITY codes (SWITRS codebook):
  1 = Fatal         (KSI)
  2 = Severe injury (KSI)
  3 = Other visible injury
  4 = Complaint of pain only
  5 = PDO
"""
from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

from src.utils import load_config, project_root, sha256_file, write_manifest

log = logging.getLogger(__name__)


def _load_switrs(csv_path: Path, exclude_state_hwy: bool) -> tuple[pd.DataFrame, dict]:
    """Load SWITRS Crashes.csv using POINT_X/POINT_Y as primary coordinate source.

    Returns (DataFrame, quality_stats).
    """
    df = pd.read_csv(
        csv_path,
        usecols=[
            "CASE_ID", "COLLISION_DATE", "COLLISION_SEVERITY",
            "POINT_X", "POINT_Y",          # primary geocode (SafeTREC)
            "LATITUDE", "LONGITUDE",        # diagnostic only
            "STATE_HWY_IND",                # surface-street filter
        ],
        dtype={"COLLISION_SEVERITY": "Int64"},
        low_memory=False,
    )
    df = df.rename(columns={
        "CASE_ID": "id",
        "COLLISION_DATE": "date",
        "COLLISION_SEVERITY": "severity",
    })
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # --- Coordinate provenance ---
    n_total = len(df)
    n_point_xy = df["POINT_X"].notna().sum()
    n_lat_lon  = df["LATITUDE"].notna().sum()
    n_hwy_y    = (df["STATE_HWY_IND"] == "Y").sum()
    log.info(
        "SWITRS coordinate coverage: POINT_X/Y %d/%d (%.1f%%)  "
        "LATITUDE/LON %d/%d (%.1f%%)  STATE_HWY_IND=Y %d",
        n_point_xy, n_total, 100 * n_point_xy / max(n_total, 1),
        n_lat_lon, n_total, 100 * n_lat_lon / max(n_total, 1),
        n_hwy_y,
    )

    # Use POINT_X/POINT_Y; LATITUDE/LONGITUDE is never used for geometry
    df = df.rename(columns={"POINT_X": "lon", "POINT_Y": "lat"})

    # State-highway exclusion (surface-street filter)
    if exclude_state_hwy:
        n_before = len(df)
        df = df[df["STATE_HWY_IND"] != "Y"].copy()
        log.info(
            "STATE_HWY_IND filter: removed %d freeway crashes (%d remain)",
            n_before - len(df), len(df),
        )

    # Drop missing coordinates (MNAR note: missingness concentrated in pre-2012 records
    # and some rural/unincorporated incidents; rate logged above; no imputation)
    n_before_drop = len(df)
    df = df.dropna(subset=["lon", "lat", "date", "severity"])
    df = df[df["lat"].between(-90, 90) & df["lon"].between(-180, 180)]
    n_dropped = n_before_drop - len(df)
    if n_dropped > 0:
        log.info("Dropped %d rows with missing coords/date/severity", n_dropped)

    stats = {
        "n_raw": n_total,
        "n_point_xy_populated": int(n_point_xy),
        "n_lat_lon_populated": int(n_lat_lon),
        "n_state_hwy_excluded": int(n_hwy_y) if exclude_state_hwy else 0,
        "n_coord_missing_dropped": n_dropped,
        "n_loaded": len(df),
        "coord_source": "POINT_X/POINT_Y",
    }
    return df, stats


def _load_sdpd_fallback() -> pd.DataFrame:
    """Pull SDPD open-data as a development stand-in.

    WARNING: This dataset is address-geocoded (not GPS-exact) and
    covers only City of San Diego police incidents, not all of San Diego
    County. It MUST be reconciled with SWITRS before any publication.
    This path is a scaffold only.
    """
    log.warning(
        "SWITRS data not found -- falling back to SDPD open-data portal. "
        "This is a DEVELOPMENT SCAFFOLD only; do not use for final labels."
    )
    url = (
        "https://seshat.datasd.org/pd/vehicle_collisions_details_datasd.csv"
    )
    df = pd.read_csv(url, low_memory=False)
    col_map = {
        "date_time": "date",
        "severity": "severity",
        "latitude": "lat",
        "longitude": "lon",
    }
    available = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=available)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "severity" not in df.columns:
        df["severity"] = pd.NA
    df["id"] = df.index.astype(str)
    df = df.dropna(subset=["lat", "lon", "date"])
    df = df[df["lat"].between(-90, 90) & df["lon"].between(-180, 180)]
    df["severity"] = pd.to_numeric(df["severity"], errors="coerce").astype("Int64")
    return df[["id", "date", "severity", "lat", "lon"]]


def load_crashes(cfg: dict[str, Any]) -> tuple[gpd.GeoDataFrame, str]:
    """Load crash data; return GeoDataFrame (EPSG:4326) + source tag.

    Directory selection priority:
      1. cfg["switrs_dirs"]  — list of explicit directories; deduplicates on CASE_ID
      2. cfg["switrs_dir"]   — single explicit directory
      3. auto-glob: picks most-recent snapdate subdirectory under data/raw/switrs/
      4. SDPD open-data fallback (development scaffold only)
    """
    exclude_state_hwy = cfg.get("geometry", {}).get("exclude_state_highway", True)
    snap_dir = None

    # --- Multiple explicit directories (forward run merge case) ---
    if "switrs_dirs" in cfg:
        dirs = [project_root() / d for d in cfg["switrs_dirs"]]
        log.info("Loading SWITRS from %d explicit directories: %s", len(dirs), dirs)
        frames = []
        for d in dirs:
            csv_path = d / "Crashes.csv"
            if not csv_path.exists():
                raise FileNotFoundError(f"Crashes.csv not found in {d}")
            df_i, _ = _load_switrs(csv_path, exclude_state_hwy)
            frames.append(df_i)
        df = pd.concat(frames, ignore_index=True)
        n_before = len(df)
        df = df.drop_duplicates(subset=["id"]).reset_index(drop=True)
        log.info("Merged %d records; dropped %d duplicates; %d remain",
                 n_before, n_before - len(df), len(df))
        source = "SWITRS_MERGED"
        snap_dir = dirs[-1]
        stats = {"coord_source": "POINT_X/POINT_Y", "merged_dirs": [str(d) for d in dirs]}

    # --- Single explicit directory ---
    elif "switrs_dir" in cfg:
        snap_dir = project_root() / cfg["switrs_dir"]
        csv_path = snap_dir / "Crashes.csv"
        log.info("Loading SWITRS crashes from explicit dir: %s", csv_path)
        df, stats = _load_switrs(csv_path, exclude_state_hwy)
        source = "SWITRS"

    # --- Auto-glob: pick most-recent subdirectory ---
    else:
        raw = project_root() / cfg["paths"]["raw"] / "switrs"
        auto_candidates = sorted(raw.glob("*/Crashes.csv"), reverse=True)
        if auto_candidates:
            csv_path = auto_candidates[0]
            log.info("Loading SWITRS crashes from %s (auto-selected)", csv_path)
            df, stats = _load_switrs(csv_path, exclude_state_hwy)
            source = "SWITRS"
            snap_dir = csv_path.parent
        else:
            # SDPD fallback
            df = _load_sdpd_fallback()
            stats = {"coord_source": "SDPD_FALLBACK"}
            source = "SDPD_FALLBACK"
            today = datetime.date.today().strftime("%Y%m%d")
            snap_dir = project_root() / cfg["paths"]["raw"] / "sdpd" / today
            snap_dir.mkdir(parents=True, exist_ok=True)

    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326",
    )
    log.info("Loaded %d crash records from %s", len(gdf), source)

    # Write/update manifest with coordinate provenance
    if snap_dir is not None:
        manifest_path = snap_dir / "manifest.json"
        if not manifest_path.exists():
            csv_file = snap_dir / "Crashes.csv"
            entries = [
                {
                    "file": "Crashes.csv",
                    "source": "SWITRS / UC Berkeley SafeTREC",
                    "fetch_timestamp": "user-supplied",
                    "row_count": len(gdf),
                    "sha256": sha256_file(csv_file) if csv_file.exists() else "n/a",
                    **stats,
                }
            ]
            write_manifest(snap_dir, entries)

    return gdf, source
