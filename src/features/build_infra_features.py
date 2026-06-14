"""Build infrastructure + geometry features for M3b.

Feature groups:
  3 — Intersection geometry [static]:
        edge_count, lane_count, approach_asymmetry, intersection_type
  4 — Signal / stop control [endogenous → 2021-12-31 OSM vintage]:
        signal_present, stop_control
  5 — Roadway environment:
        functional_class [static], freeway_proximity [static], speed_limit [endogenous]
  6 — Active transport:
        bike_lane_present [endogenous → 2021 vintage], transit_proximity [GTFS ~static]
  7 — Terrain [static]:
        slope_pct

All features are attached to intersection_id (same key as crash features).
Missing values carry a <feature>_missing flag (1 = not observed).

Output:
  data/model/infra_features.parquet
  data/model/feature_dictionary.csv  (appended/updated)

Run via:  python -m src.features.build_infra_features
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from src.ingest import gtfs_loader, dem_loader
from src.ingest.osm_history_loader import fetch_all as fetch_osm_history
from src.utils import load_config, project_root

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _haversine_m(lon1: np.ndarray, lat1: np.ndarray,
                 lon2: np.ndarray, lat2: np.ndarray) -> np.ndarray:
    """Vectorised haversine distance in metres."""
    R = 6_371_000.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi  = np.radians(lat2 - lat1)
    dlam  = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _kdtree_nearest_m(query_lon: np.ndarray, query_lat: np.ndarray,
                      ref_lon: np.ndarray, ref_lat: np.ndarray) -> np.ndarray:
    """Return approximate nearest-neighbour distances in metres using a flat-earth
    KD-tree on degree coordinates.  Accurate to <1% within a city-scale bbox."""
    # Scale lat by cos(mean_lat) so degrees are isotropic
    mean_lat = float(np.mean(np.concatenate([query_lat, ref_lat])))
    clat = np.cos(np.radians(mean_lat))
    ref_xy  = np.column_stack([ref_lon * clat, ref_lat])
    qry_xy  = np.column_stack([query_lon * clat, query_lat])
    tree = cKDTree(ref_xy)
    dists_deg, _ = tree.query(qry_xy, k=1, workers=-1)
    return dists_deg * 111_320.0  # 1 degree latitude ≈ 111,320 m


def _within_snap(query_lon: np.ndarray, query_lat: np.ndarray,
                 ref_lon: np.ndarray, ref_lat: np.ndarray,
                 snap_m: float) -> np.ndarray:
    """Return bool array: True if any ref point is within snap_m of each query."""
    if len(ref_lon) == 0:
        return np.zeros(len(query_lon), dtype=bool)
    dists = _kdtree_nearest_m(query_lon, query_lat, ref_lon, ref_lat)
    return dists <= snap_m


def _parse_lanes(v) -> float | None:
    """Parse an OSM lanes value (string, list, or None) to float."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    # handle "2|1" or "2;1" format
    for sep in ["|", ";", ","]:
        if sep in s:
            parts = [p.strip() for p in s.split(sep)]
            vals = []
            for p in parts:
                try:
                    vals.append(float(p))
                except ValueError:
                    pass
            return float(np.mean(vals)) if vals else None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_maxspeed_kph(v, default_kph: float) -> float:
    """Parse an OSM maxspeed tag to kph."""
    if v is None:
        return default_kph
    s = str(v).lower().strip()
    if s in ("none", "signals", "variable", ""):
        return default_kph
    # e.g. "25 mph", "40", "40 km/h"
    try:
        if "mph" in s:
            num = float(s.replace("mph", "").strip())
            return num * 1.60934
        if "km/h" in s or "kph" in s:
            num = float(s.replace("km/h", "").replace("kph", "").strip())
            return num
        return float(s)
    except ValueError:
        return default_kph


_FREEWAY_HW = frozenset({"motorway", "motorway_link"})
_TRUNK_HW   = frozenset({"trunk", "trunk_link"})
_ARTERIAL_HW = frozenset({"primary", "primary_link", "secondary", "secondary_link",
                           "tertiary", "tertiary_link"})
_HW_FUNC_CLASS = {
    "motorway": 1, "motorway_link": 1,
    "trunk": 2,    "trunk_link": 2,
    "primary": 3,  "primary_link": 3,
    "secondary": 4, "secondary_link": 4,
    "tertiary": 5, "tertiary_link": 5,
    "residential": 6, "living_street": 7,
    "unclassified": 6,
}


def _hw_list(val) -> list[str]:
    if isinstance(val, list):
        return [str(x) for x in val]
    if isinstance(val, str) and val.startswith("["):
        import ast
        try:
            return [str(x) for x in ast.literal_eval(val)]
        except Exception:
            pass
    return [str(val)] if val else []


# ---------------------------------------------------------------------------
# Group 3 — Intersection geometry (static, from current OSM graphml)
# ---------------------------------------------------------------------------

def build_geometry_features(candidates: pd.DataFrame, G: nx.MultiDiGraph,
                            cfg: dict) -> pd.DataFrame:
    """Compute edge_count, lane_count, approach_asymmetry, intersection_type."""
    # Build flat-earth KD-tree on node (lon, lat) from graphml string attributes
    node_ids  = list(G.nodes())
    node_lons = np.array([float(G.nodes[n].get("x", 0.0)) for n in node_ids])
    node_lats = np.array([float(G.nodes[n].get("y", 0.0)) for n in node_ids])

    mean_lat = float(np.mean(node_lats))
    clat = np.cos(np.radians(mean_lat))
    node_xy = np.column_stack([node_lons * clat, node_lats])
    cand_xy = np.column_stack([candidates["lon"].values * clat, candidates["lat"].values])
    tree = cKDTree(node_xy)
    _, idxs = tree.query(cand_xy, k=1, workers=-1)

    records = []
    for i, (cand_row, osm_idx) in enumerate(zip(candidates.itertuples(), idxs)):
        osmid = node_ids[osm_idx]

        # Unique neighbours (approach legs)
        nbrs = set(G.predecessors(osmid)) | set(G.successors(osmid))
        edge_count = len(nbrs)

        # Lane values from all incident edges (in + out)
        lanes_list: list[float] = []
        speeds_list: list[float] = []
        fw_types: set[str] = set()
        func_vals: list[int] = []

        for _, _, edata in list(G.edges(osmid, data=True)) + list(G.in_edges(osmid, data=True)):
            lv = _parse_lanes(edata.get("lanes"))
            if lv is not None:
                lanes_list.append(lv)
            sv = _parse_maxspeed_kph(edata.get("maxspeed"), default_kph=np.nan)
            if not np.isnan(sv):
                speeds_list.append(sv)
            for hw in _hw_list(edata.get("highway", "")):
                fw_types.add(hw)
                fc = _HW_FUNC_CLASS.get(hw)
                if fc is not None:
                    func_vals.append(fc)

        lane_count  = float(np.mean(lanes_list)) if lanes_list else np.nan
        lane_std    = float(np.std(lanes_list))  if len(lanes_list) > 1 else 0.0
        speed_limit = float(np.mean(speeds_list)) if speeds_list else np.nan
        func_class  = int(min(func_vals)) if func_vals else 6  # min = most major road type

        # Freeway proximity: is any incident edge a freeway/motorway?
        near_freeway = bool(fw_types & _FREEWAY_HW)

        # Intersection type (0=dead-end, 2=through, 3=T, 4=4way, 5+=complex)
        if edge_count <= 1:
            itype = 0
        elif edge_count == 2:
            itype = 2
        elif edge_count == 3:
            itype = 3
        elif edge_count == 4:
            itype = 4
        else:
            itype = 5

        records.append({
            "intersection_id":   getattr(cand_row, "intersection_id"),
            "edge_count":        edge_count,
            "lane_count":        lane_count,
            "lane_count_missing": int(np.isnan(lane_count)),
            "approach_asymmetry": lane_std,
            "intersection_type": itype,
            # Store derived static fields here too (used in Group 5)
            "_functional_class": func_class,
            "_near_freeway_osm": int(near_freeway),
            "_speed_limit_osm":  speed_limit,  # current OSM, 2026 vintage
        })

    df = pd.DataFrame(records)
    log.info(
        "Geometry: edge_count mean=%.1f  lane_count coverage=%.1f%%  itype4way=%d",
        df["edge_count"].mean(),
        100 * (1 - df["lane_count_missing"].mean()),
        (df["intersection_type"] == 4).sum(),
    )
    return df


# ---------------------------------------------------------------------------
# Group 4 — Signal / stop control (endogenous, 2021 vintage)
# ---------------------------------------------------------------------------

def build_control_features(candidates: pd.DataFrame,
                            osm_hist: dict[str, Path | None],
                            cfg: dict) -> pd.DataFrame:
    """signal_present, stop_control from 2021-12-31 OSM snapshot."""
    icfg = cfg["infrastructure"]
    cand_lons = candidates["lon"].values
    cand_lats = candidates["lat"].values
    n = len(candidates)

    # --- signal_present ---
    sig_missing = 1
    signal_present = np.zeros(n, dtype=float)
    sig_path = osm_hist.get("traffic_signals")
    if sig_path and sig_path.exists():
        import geopandas as gpd
        gdf = gpd.read_file(sig_path)
        if len(gdf) > 0 and gdf.geometry.notna().any():
            pts = gdf[gdf.geometry.notna()]
            sig_lons = pts.geometry.x.values
            sig_lats = pts.geometry.y.values
            signal_present = _within_snap(cand_lons, cand_lats, sig_lons, sig_lats,
                                          icfg["signal_snap_m"]).astype(float)
            sig_missing = 0
            log.info("signal_present: %d signal nodes → %d/%d candidates = True",
                     len(gdf), int(signal_present.sum()), n)
    else:
        log.warning("traffic_signals snapshot unavailable — signal_present marked missing")

    # --- stop_control ---
    stp_missing = 1
    stop_control = np.zeros(n, dtype=float)
    stp_path = osm_hist.get("stop_signs")
    if stp_path and stp_path.exists():
        gdf = gpd.read_file(stp_path)
        if len(gdf) > 0 and gdf.geometry.notna().any():
            pts = gdf[gdf.geometry.notna()]
            stp_lons = pts.geometry.x.values
            stp_lats = pts.geometry.y.values
            stop_control = _within_snap(cand_lons, cand_lats, stp_lons, stp_lats,
                                        icfg["stop_snap_m"]).astype(float)
            stp_missing = 0
            log.info("stop_control: %d stop nodes → %d/%d candidates = True",
                     len(gdf), int(stop_control.sum()), n)
    else:
        log.warning("stop_signs snapshot unavailable — stop_control marked missing")

    return pd.DataFrame({
        "intersection_id":        candidates["intersection_id"].values,
        "signal_present":         signal_present,
        "signal_present_missing": sig_missing,
        "stop_control":           stop_control,
        "stop_control_missing":   stp_missing,
    })


# ---------------------------------------------------------------------------
# Group 5 — Roadway environment
# ---------------------------------------------------------------------------

def build_roadway_features(candidates: pd.DataFrame,
                            geom_df: pd.DataFrame,
                            osm_hist: dict[str, Path | None],
                            cfg: dict) -> pd.DataFrame:
    """functional_class [static], freeway_proximity [static], speed_limit [endogenous]."""
    icfg = cfg["infrastructure"]
    n = len(candidates)
    cand_lons = candidates["lon"].values
    cand_lats = candidates["lat"].values
    geom_idx = geom_df.set_index("intersection_id")

    # functional_class and near_freeway: from the geometry pass (static)
    func_class  = geom_idx["_functional_class"].reindex(candidates["intersection_id"]).values
    # freeway_proximity: use the current OSM graph data.
    # near_freeway_osm is a boolean; convert to a continuous distance proxy.
    # A more precise distance would require iterating edge geometries. Use flag as
    # a proxy (0 = >200m, 1 = ≤200m, i.e. incident freeway edge).
    freeway_prox = geom_idx["_near_freeway_osm"].reindex(candidates["intersection_id"]).values.astype(float)

    # speed_limit: prefer 2021 Overpass vintage; fallback to current OSM
    speed_missing = 1
    speed_limit = geom_idx["_speed_limit_osm"].reindex(candidates["intersection_id"]).values.copy()

    sl_path = osm_hist.get("speed_limits")
    # Per-row missing flag (1 = no usable value; 0 = value present)
    # speed_vintage_flag: separate scalar stored in manifest (0=2021, 2=2026 fallback, 3=unavailable)
    speed_vintage = 3  # default: fully unavailable

    if sl_path and sl_path.exists():
        import geopandas as gpd
        gdf = gpd.read_file(sl_path)
        if len(gdf) > 0:
            # For each way: extract midpoint and maxspeed; snap to candidates
            default_kph = icfg["speed_default_kph"]
            way_lons, way_lats, way_speeds = [], [], []
            for geom, props in zip(gdf.geometry, gdf.itertuples()):
                if geom is None or geom.is_empty:
                    continue
                mp = geom.interpolate(0.5, normalized=True)
                sp = _parse_maxspeed_kph(getattr(props, "maxspeed", None), default_kph)
                way_lons.append(mp.x)
                way_lats.append(mp.y)
                way_speeds.append(sp)

            if way_lons:
                way_lons_a  = np.array(way_lons)
                way_lats_a  = np.array(way_lats)
                way_speeds_a = np.array(way_speeds)
                mean_lat = float(np.mean(np.concatenate([cand_lats, way_lats_a])))
                clat = np.cos(np.radians(mean_lat))
                ref_xy = np.column_stack([way_lons_a * clat, way_lats_a])
                qry_xy = np.column_stack([cand_lons * clat, cand_lats])
                tree = cKDTree(ref_xy)
                dists_deg, nn_idx = tree.query(qry_xy, k=1, workers=-1)
                # Only assign if nearest way within 50m
                dists_m = dists_deg * 111_320.0
                mask = dists_m <= 50.0
                speed_limit_2021 = np.full(n, np.nan)
                speed_limit_2021[mask] = way_speeds_a[nn_idx[mask]]
                # Fill NaN from current OSM where 2021 unavailable
                missing_2021 = np.isnan(speed_limit_2021)
                speed_limit_2021[missing_2021] = speed_limit[missing_2021]
                speed_limit = speed_limit_2021
                speed_vintage = 0  # 2021 vintage (proper)
                log.info("speed_limit: 2021 vintage coverage=%.1f%% (filled %.1f%% from 2026 OSM)",
                         100 * mask.mean(), 100 * missing_2021.mean())
    else:
        log.warning("speed_limits 2021 snapshot unavailable — using current OSM speed_limit (FLAGGED as 2026)")
        speed_vintage = 2  # 2026 fallback — endogenous risk

    # Per-row missing flag: 1 where speed_limit is NaN
    speed_limit_missing_row = np.isnan(speed_limit).astype(int)
    log.info("speed_limit: vintage=%d  coverage=%.1f%%",
             speed_vintage, 100 * (1 - speed_limit_missing_row.mean()))

    return pd.DataFrame({
        "intersection_id":    candidates["intersection_id"].values,
        "functional_class":   func_class.astype(float),
        "freeway_proximity":  freeway_prox,
        "speed_limit":        speed_limit,
        "speed_limit_missing": speed_limit_missing_row,
        "speed_limit_vintage": speed_vintage,  # 0=2021, 2=2026-fallback, 3=unavailable
    })


# ---------------------------------------------------------------------------
# Group 6 — Active transport
# ---------------------------------------------------------------------------

def build_active_transport_features(candidates: pd.DataFrame,
                                     osm_hist: dict[str, Path | None],
                                     cfg: dict) -> pd.DataFrame:
    """bike_lane_present [endogenous], transit_proximity [GTFS ~static]."""
    icfg = cfg["infrastructure"]
    n = len(candidates)
    cand_lons = candidates["lon"].values
    cand_lats = candidates["lat"].values

    # --- bike_lane_present ---
    bike_missing = 1
    bike_lane = np.zeros(n, dtype=float)
    bl_path = osm_hist.get("bike_lanes")
    if bl_path and bl_path.exists():
        import geopandas as gpd
        gdf = gpd.read_file(bl_path)
        if len(gdf) > 0:
            # For each way, check if any point on it is near a candidate
            # Efficient: sample way midpoints; snap within 30m
            way_lons, way_lats = [], []
            for geom in gdf.geometry:
                if geom is None or geom.is_empty:
                    continue
                mp = geom.interpolate(0.5, normalized=True)
                way_lons.append(mp.x)
                way_lats.append(mp.y)

            if way_lons:
                # Within 30 m of a bike-lane way midpoint → bike_lane_present=1
                bl_lons = np.array(way_lons)
                bl_lats = np.array(way_lats)
                bike_lane = _within_snap(cand_lons, cand_lats, bl_lons, bl_lats,
                                         snap_m=30.0).astype(float)
                bike_missing = 0
                log.info("bike_lane: 2021 vintage %d ways → %d/%d candidates = True",
                         len(way_lons), int(bike_lane.sum()), n)
    else:
        log.warning("bike_lanes 2021 snapshot unavailable — bike_lane_present marked missing")

    # --- transit_proximity ---
    transit_missing = 1
    transit_prox_m = np.full(n, np.nan)
    transit_proximity = np.zeros(n, dtype=float)
    stops = gtfs_loader.load_stops(cfg)
    if stops is not None and len(stops) > 0:
        stop_lons = stops["stop_lon"].values
        stop_lats = stops["stop_lat"].values
        dists = _kdtree_nearest_m(cand_lons, cand_lats, stop_lons, stop_lats)
        transit_prox_m = dists
        transit_proximity = (dists <= icfg["transit_proximity_m"]).astype(float)
        transit_missing = 0
        log.info("transit_proximity: %d stops, %.1f%% candidates within %.0fm",
                 len(stops), 100 * transit_proximity.mean(), icfg["transit_proximity_m"])
    else:
        log.warning("GTFS stops unavailable — transit_proximity marked missing")

    return pd.DataFrame({
        "intersection_id":        candidates["intersection_id"].values,
        "bike_lane_present":      bike_lane,
        "bike_lane_present_missing": bike_missing,
        "transit_proximity":      transit_proximity,
        "transit_prox_m":         transit_prox_m,
        "transit_proximity_missing": transit_missing,
    })


# ---------------------------------------------------------------------------
# Group 7 — Terrain (static)
# ---------------------------------------------------------------------------

def build_terrain_features(candidates: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """slope_pct from USGS 3DEP DEM."""
    slope_df = dem_loader.load_slope(cfg)

    if slope_df is not None and len(slope_df) > 0:
        merged = candidates[["intersection_id"]].merge(
            slope_df[["intersection_id", "slope_pct", "elev_m"]], on="intersection_id", how="left"
        )
        merged["slope_pct_missing"] = merged["slope_pct"].isna().astype(int)
        log.info("slope_pct: coverage=%.1f%%  mean=%.2f%%",
                 100 * (1 - merged["slope_pct_missing"].mean()),
                 merged["slope_pct"].mean(skipna=True))
        return merged[["intersection_id", "slope_pct", "slope_pct_missing"]]
    else:
        log.warning("DEM slope unavailable — slope_pct marked missing")
        return pd.DataFrame({
            "intersection_id": candidates["intersection_id"].values,
            "slope_pct": np.nan,
            "slope_pct_missing": 1,
        })


# ---------------------------------------------------------------------------
# Feature dictionary
# ---------------------------------------------------------------------------

_FEATURE_META = [
    # (name, group, source, vintage, static_endogenous)
    ("edge_count",          3, "OSM current", "2026", "static"),
    ("lane_count",          3, "OSM current", "2026", "static"),
    ("approach_asymmetry",  3, "OSM current", "2026", "static"),
    ("intersection_type",   3, "OSM current", "2026", "static"),
    ("signal_present",      4, "OSM history", "2021-12-31", "endogenous"),
    ("stop_control",        4, "OSM history", "2021-12-31", "endogenous"),
    ("functional_class",    5, "OSM current", "2026", "static"),
    ("freeway_proximity",   5, "OSM current", "2026", "static"),
    ("speed_limit",         5, "OSM history", "2021-12-31", "endogenous"),
    ("bike_lane_present",   6, "OSM history", "2021-12-31", "endogenous"),
    ("transit_proximity",   6, "MTS GTFS",    "current (~static)", "static"),
    ("slope_pct",           7, "USGS 3DEP",   "static", "static"),
]


def _update_feature_dictionary(infra_df: pd.DataFrame, model_dir: Path) -> None:
    fdict_path = model_dir / "feature_dictionary.csv"
    existing   = pd.read_csv(fdict_path) if fdict_path.exists() else pd.DataFrame()

    new_rows = []
    for name, group, source, vintage, s_or_e in _FEATURE_META:
        if name not in infra_df.columns:
            continue
        vals = infra_df[name].dropna()
        row = {
            "feature_name":    name,
            "group":           group,
            "milestone":       "M3b",
            "source":          source,
            "vintage":         vintage,
            "static_endogenous": s_or_e,
            "missing_rate":    float(infra_df[f"{name}_missing"].mean())
                               if f"{name}_missing" in infra_df.columns else 0.0,
            "variance":        float(vals.var()) if len(vals) > 1 else 0.0,
            "window_used":     "infrastructure_snapshot",
            "max_source_date": "N/A" if s_or_e == "static" else "2021-12-31",
        }
        new_rows.append(row)

    new_df = pd.DataFrame(new_rows)
    combined = pd.concat([existing, new_df], ignore_index=True).drop_duplicates(
        subset=["feature_name"], keep="last"
    )
    combined.to_csv(fdict_path, index=False)
    log.info("feature_dictionary.csv updated (%d rows)", len(combined))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    cfg       = load_config()
    model_dir = project_root() / cfg["paths"]["model"]

    # Load candidates (need lon/lat in WGS84)
    candidates = gpd.read_parquet(model_dir / "candidate_panel.parquet")
    # Ensure lon/lat columns exist
    if "lon" not in candidates.columns or "lat" not in candidates.columns:
        raise ValueError("Candidate panel missing lon/lat columns; re-run build_panel.py")

    # Load OSM graphml
    graphml_path = project_root() / cfg["paths"]["raw"] / "osm" / "20260608" / "sandiego_drive.graphml"
    log.info("Loading OSM graphml from %s …", graphml_path)
    G = nx.read_graphml(str(graphml_path))
    log.info("Graph: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())

    # Fetch/load endogenous OSM history snapshots
    log.info("=== Fetching OSM history (2021-12-31 vintage) ===")
    osm_hist = fetch_osm_history(cfg)

    # Fetch GTFS if not already present
    log.info("=== Fetching GTFS transit stops ===")
    gtfs_loader.fetch_stops(cfg)

    # Fetch DEM slope
    log.info("=== Fetching DEM slope ===")
    dem_loader.fetch_and_compute(cfg, candidates)

    # Build feature groups
    log.info("=== Building Group 3: Geometry ===")
    geom_df = build_geometry_features(candidates, G, cfg)

    log.info("=== Building Group 4: Control (2021 vintage) ===")
    ctrl_df = build_control_features(candidates, osm_hist, cfg)

    log.info("=== Building Group 5: Roadway environment ===")
    road_df = build_roadway_features(candidates, geom_df, osm_hist, cfg)

    log.info("=== Building Group 6: Active transport ===")
    at_df = build_active_transport_features(candidates, osm_hist, cfg)

    log.info("=== Building Group 7: Terrain ===")
    terr_df = build_terrain_features(candidates, cfg)

    # Merge all groups on intersection_id
    dfs = [geom_df, ctrl_df, road_df, at_df, terr_df]
    # Drop internal _prefixed columns from geometry before merging
    geom_pub = geom_df.drop(columns=[c for c in geom_df.columns if c.startswith("_")],
                             errors="ignore")
    dfs[0] = geom_pub

    infra_df = candidates[["intersection_id"]].copy()
    for df in dfs:
        infra_df = infra_df.merge(df, on="intersection_id", how="left")

    out_path = model_dir / "infra_features.parquet"
    infra_df.to_parquet(out_path, index=False)
    log.info("Wrote infra_features.parquet (%d rows × %d cols)", len(infra_df), infra_df.shape[1])

    # Log coverage summary
    infra_cols = [c for c in infra_df.columns if c != "intersection_id"]
    missing_cols = [c for c in infra_cols if c.endswith("_missing")]
    for mc in missing_cols:
        feat = mc.replace("_missing", "")
        miss_rate = infra_df[mc].mean()
        log.info("  %-30s coverage=%.1f%%", feat, 100 * (1 - miss_rate))

    _update_feature_dictionary(infra_df, model_dir)


if __name__ == "__main__":
    main()
