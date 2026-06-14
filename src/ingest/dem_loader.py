"""Download USGS 3DEP DEM raster and compute per-node slope.

Uses py3dep (wraps The National Map API) to download a 1/3 arc-second
(~10 m) DEM tile for the San Diego bounding box, then samples elevation
at each candidate node and computes slope_pct (rise/run × 100) by
finite-difference on the raster.

Terrain is treated as static (time-invariant): current DEM is fine.

Saves:
  data/raw/dem/<YYYYMMDD>/sandiego_dem.tif  — raw raster (GeoTIFF)
  data/raw/dem/<YYYYMMDD>/node_slope.parquet — {intersection_id, elev_m, slope_pct}
  data/raw/dem/<YYYYMMDD>/manifest.json

Run via:  python -m src.ingest.dem_loader
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from src.utils import load_config, project_root

log = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _compute_slope_from_dem(dem_array: np.ndarray, res_m: float) -> np.ndarray:
    """Compute slope_pct from a 2-D elevation array (metres). Returns same shape."""
    # Pad to handle edges
    padded = np.pad(dem_array, 1, mode="edge")
    dz_dx = (padded[1:-1, 2:] - padded[1:-1, :-2]) / (2 * res_m)
    dz_dy = (padded[2:, 1:-1] - padded[:-2, 1:-1]) / (2 * res_m)
    slope_rad = np.arctan(np.sqrt(dz_dx ** 2 + dz_dy ** 2))
    return np.tan(slope_rad) * 100.0  # percent grade


def fetch_and_compute(cfg: dict, candidates: pd.DataFrame) -> Path | None:
    """Download DEM and compute slope at each candidate node.

    Parameters
    ----------
    candidates : DataFrame with columns intersection_id, lon, lat (WGS84).
    """
    today = date.today().strftime("%Y%m%d")
    out_dir = project_root() / cfg["paths"]["raw"] / "dem" / today
    out_dir.mkdir(parents=True, exist_ok=True)

    slope_path    = out_dir / "node_slope.parquet"
    dem_path      = out_dir / "sandiego_dem.tif"
    manifest_path = out_dir / "manifest.json"

    if slope_path.exists():
        log.info("DEM node slope already present: %s", slope_path)
        return slope_path

    try:
        import py3dep
        from shapely.geometry import box
    except ImportError:
        log.warning("py3dep not installed — terrain feature unavailable (run: pip install py3dep)")
        return None

    icfg = cfg["infrastructure"]
    s, w, n, e = icfg["overpass_bbox"]
    res_m = icfg["dem_resolution_m"]

    geom = box(w, s, e, n)
    log.info("Downloading 3DEP DEM (%.0f m resolution) for bbox [%.2f,%.2f,%.2f,%.2f]…",
             res_m, s, w, n, e)

    try:
        # py3dep ≥0.15: get_dem(geometry, resolution, crs)
        dem = py3dep.get_dem(geom, resolution=res_m, crs="EPSG:4326")
    except Exception as exc:
        log.warning("py3dep get_dem failed (%s); trying static_3dep_dem …", exc)
        try:
            dem = py3dep.static_3dep_dem(geom, crs="EPSG:4326", resolution=res_m)
        except Exception as exc2:
            log.warning("py3dep DEM download failed: %s — terrain feature unavailable", exc2)
            return None

    # Save GeoTIFF
    dem.rio.to_raster(str(dem_path))
    log.info("DEM saved to %s (%s)", dem_path, dem.shape)

    # Extract elevation array and compute slope
    transform = dem.rio.transform()
    actual_res_m = abs(transform.a)  # pixel width in DEM CRS units (metres for projected, degrees for WGS84)
    elev_arr = dem.values.squeeze().astype(float)
    nodata = dem.rio.nodata
    if nodata is not None:
        elev_arr[elev_arr == nodata] = np.nan
    slope_arr = _compute_slope_from_dem(np.nan_to_num(elev_arr, nan=0.0), actual_res_m)

    # Sample at each candidate node (lon, lat → raster pixel)
    lons = candidates["lon"].values
    lats = candidates["lat"].values
    # Project WGS84 node coordinates to the DEM CRS before pixel lookup.
    # py3dep may return data in a projected CRS (e.g. EPSG:5070 Albers), not WGS84.
    import rasterio
    from pyproj import Transformer
    dem_crs_str = str(dem.rio.crs)
    if dem_crs_str.upper() not in ("EPSG:4326", "WGS84"):
        log.info("Projecting candidate coords from WGS84 → %s for DEM sampling", dem_crs_str)
        xformer = Transformer.from_crs("EPSG:4326", dem_crs_str, always_xy=True)
        proj_x, proj_y = xformer.transform(lons, lats)
    else:
        proj_x, proj_y = lons, lats

    rows, cols = rasterio.transform.rowcol(transform, proj_x, proj_y)

    rows = np.array(rows)
    cols = np.array(cols)
    h, w_px = elev_arr.shape
    valid = (rows >= 0) & (rows < h) & (cols >= 0) & (cols < w_px)

    elevs  = np.full(len(candidates), np.nan)
    slopes = np.full(len(candidates), np.nan)
    elevs[valid]  = elev_arr[rows[valid], cols[valid]]
    slopes[valid] = slope_arr[rows[valid], cols[valid]]

    result = pd.DataFrame({
        "intersection_id": candidates["intersection_id"].values,
        "elev_m": elevs,
        "slope_pct": slopes,
    })
    result.to_parquet(slope_path, index=False)

    sha_dem = _sha256(dem_path)
    manifest = {
        "source": "USGS 3DEP via py3dep",
        "resolution_m": res_m,
        "bbox": [s, w, n, e],
        "fetch_date": today,
        "n_nodes": len(candidates),
        "n_valid": int(valid.sum()),
        "dem_sha256": sha_dem,
        "temporal_class": "static",
        "status": "OK",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    log.info("Slope computed for %d / %d nodes", valid.sum(), len(candidates))
    return slope_path


def load_slope(cfg: dict) -> pd.DataFrame | None:
    """Load most recent DEM node_slope snapshot; return DataFrame or None."""
    dem_raw = project_root() / cfg["paths"]["raw"] / "dem"
    dated = sorted(dem_raw.glob("*/node_slope.parquet"), reverse=True)
    if not dated:
        return None
    df = pd.read_parquet(dated[0])
    log.info("Loaded slope data for %d nodes from %s", len(df), dated[0])
    return df


def main() -> None:
    import geopandas as gpd
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    model_dir = project_root() / cfg["paths"]["model"]
    candidates = gpd.read_parquet(model_dir / "candidate_panel.parquet")
    path = fetch_and_compute(cfg, candidates)
    if path:
        df = pd.read_parquet(path)
        log.info("Slope stats: mean=%.2f%% std=%.2f%% missing=%d",
                 df["slope_pct"].mean(), df["slope_pct"].std(), df["slope_pct"].isna().sum())


if __name__ == "__main__":
    main()
