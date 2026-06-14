"""Spatial-block splitter for cross-validation.

Two modes:
  (a) Spatial-block grouped k-fold (k=5): hold out WHOLE spatial blocks.
      Blocks come from CPA polygons if available, otherwise ~2 km grid tiles
      in EPSG:2230.
  (b) Plain random split (80/20 stratified by label).

Both are deterministic given RNG seed. Block assignment is stored as a
"spatial_block" column in the candidate panel (integer block id).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, StratifiedKFold

from src.utils import load_config, project_root

log = logging.getLogger(__name__)


def assign_cpa_blocks(
    candidates: gpd.GeoDataFrame, cpa_path: Path, crs_a: str
) -> pd.Series:
    """Assign each candidate node to a CPA polygon by spatial join."""
    cpa = gpd.read_file(cpa_path).to_crs(crs_a)
    # Use centroid geometry (2230) for the join
    pts = candidates.copy()
    pts["geometry"] = pts["geometry"]  # already 2230

    joined = gpd.sjoin(pts[["intersection_id", "geometry"]], cpa, how="left", predicate="within")
    # Use index_right as block id (polygon index)
    block_col = joined.get("index_right", joined.get("index_right0"))
    blocks = block_col.fillna(-1).astype(int)
    blocks.index = candidates.index
    return blocks


def assign_grid_blocks(
    candidates: gpd.GeoDataFrame, tile_m: float, crs_a: str
) -> pd.Series:
    """Assign each node to a ~tile_m grid tile in EPSG:2230."""
    # EPSG:2230 units are US survey feet; convert tile_m to feet
    us_ft_per_m = 3937.0 / 1200.0
    tile_ft = tile_m * us_ft_per_m

    xs = candidates.geometry.x.values
    ys = candidates.geometry.y.values
    col_ids = np.floor(xs / tile_ft).astype(int)
    row_ids = np.floor(ys / tile_ft).astype(int)
    # Encode as a single integer block id
    # Normalise so IDs start from 0
    col_ids -= col_ids.min()
    row_ids -= row_ids.min()
    n_cols = col_ids.max() + 1
    blocks = row_ids * n_cols + col_ids
    # Re-label to 0..N-1 contiguous
    unique_blocks = np.unique(blocks)
    remap = {v: i for i, v in enumerate(unique_blocks)}
    blocks = np.array([remap[b] for b in blocks])
    return pd.Series(blocks, index=candidates.index)


def add_spatial_blocks(
    candidates: gpd.GeoDataFrame, cfg: dict
) -> gpd.GeoDataFrame:
    """Add 'spatial_block' column to candidates in-place."""
    crs_a = cfg["crs"]["analysis"]
    mode = cfg["evaluation"]["spatial_block"]
    tile_m = cfg["evaluation"]["grid_tile_m"]

    if mode == "cpa_or_grid":
        cpa_raw = project_root() / cfg["paths"]["raw"] / "cpa"
        cpa_files = sorted(cpa_raw.glob("*/community_planning_districts.geojson"), reverse=True)
        if cpa_files:
            log.info("Using CPA blocks from %s", cpa_files[0])
            blocks = assign_cpa_blocks(candidates, cpa_files[0], crs_a)
        else:
            log.info("CPA file not found — using %.0f m grid tiles", tile_m)
            blocks = assign_grid_blocks(candidates, tile_m, crs_a)
    else:
        blocks = assign_grid_blocks(candidates, tile_m, crs_a)

    candidates = candidates.copy()
    candidates["spatial_block"] = blocks.values
    n_blocks = candidates["spatial_block"].nunique()
    log.info("Assigned %d spatial blocks to %d candidates", n_blocks, len(candidates))
    return candidates


def spatial_block_kfold(
    candidates: pd.DataFrame, cfg: dict
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Yield (train_idx, test_idx) arrays for spatial-block grouped k-fold."""
    k = cfg["evaluation"]["spatial_cv_folds"]
    groups = candidates["spatial_block"].values
    y = candidates["y"].values
    gkf = GroupKFold(n_splits=k)
    for train_idx, test_idx in gkf.split(candidates, y, groups=groups):
        yield train_idx, test_idx


def random_split(
    candidates: pd.DataFrame, cfg: dict
) -> tuple[np.ndarray, np.ndarray]:
    """Return (train_idx, test_idx) for a stratified random 80/20 split."""
    seed = cfg["project"]["rng_seed"]
    y = candidates["y"].values
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    # Take the first fold as the hold-out test set
    train_idx, test_idx = next(skf.split(candidates, y))
    return train_idx, test_idx
