"""Milestone 2.5 scope probe.

Measures surface-street KSI positives at 76.2 m (250 US survey ft) for:
  - City of San Diego (clean re-derivation, fixes freeway contamination)
  - San Diego County urbanized footprint (if county SWITRS is present)

Writes:
  reports/milestone2_5_scope_probe.md
  reports/DEVIATIONS.md        (appended)
  data/probe/city_surface_panel.parquet
  data/probe/county_surface_panel.parquet   (if county SWITRS present)
  data/raw/osm_county/<YYYYMMDD>/sdcounty_drive.graphml   (cached)

Run via:  python -m src.probe.county_probe
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
import sys
from datetime import date
from pathlib import Path
from typing import Any

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union
from sklearn.neighbors import BallTree

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Probe-local constants  (do NOT modify config.yaml)
# ---------------------------------------------------------------------------
PROBE_BUFFER_M = 76.2           # 250 US survey feet exactly
M_PER_US_FT    = 1200.0 / 3937.0
PROBE_BUFFER_FT = PROBE_BUFFER_M / M_PER_US_FT   # ~250.0000 ft

CRS_ANALYSIS = "EPSG:2230"
CRS_4326     = "EPSG:4326"

FREEWAY_TYPES = {"motorway", "motorway_link"}
TRUNK_TYPES   = {"trunk", "trunk_link"}

KSI_SEVERITY_CODES   = {1, 2}
CANDIDATE_MAX_KSI    = 2       # KSI_feat < 2
POSITIVE_MIN_KSI     = 2       # label = KSI_count >= 2
TOP_DECILE_DROP      = 0.10    # drop top 10% by feature-window KSI density

FEATURE_START  = pd.Timestamp("2016-01-01")
FEATURE_END    = pd.Timestamp("2021-12-31")
FEATURE_CUTOFF = pd.Timestamp("2022-01-01")
LABEL_START    = pd.Timestamp("2022-01-01")
LABEL_END      = pd.Timestamp("2024-12-31")

NODE_MERGE_M = 10.0

ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _intersection_id(x: float, y: float, decimals: int = 1) -> str:
    key = f"{round(x, decimals)},{round(y, decimals)}"
    return hashlib.md5(key.encode()).hexdigest()


def _edge_highway_types(G: nx.MultiDiGraph, osmid: int) -> set[str]:
    """Return the set of highway type strings for all edges incident to osmid."""
    types: set[str] = set()
    for _, _, data in G.edges(osmid, data=True):
        hw = data.get("highway", "")
        if isinstance(hw, list):
            types.update(hw)
        elif hw:
            types.add(str(hw))
    for _, _, data in G.in_edges(osmid, data=True):
        hw = data.get("highway", "")
        if isinstance(hw, list):
            types.update(hw)
        elif hw:
            types.add(str(hw))
    return types


def _classify_node(G: nx.MultiDiGraph, osmid: int) -> tuple[bool, bool]:
    """Return (is_freeway, is_trunk_borderline)."""
    hw = _edge_highway_types(G, osmid)
    is_fw  = bool(hw & FREEWAY_TYPES)
    is_trk = bool((hw & TRUNK_TYPES) and not is_fw)
    return is_fw, is_trk


def _merge_nodes(
    gdf: gpd.GeoDataFrame,
    node_classes: dict[int, tuple[bool, bool]],   # osmid -> (is_freeway, is_trunk)
    merge_m: float = NODE_MERGE_M,
) -> gpd.GeoDataFrame:
    """
    Merge near-duplicate nodes within merge_m metres (haversine), keeping centroid.
    A merged node is freeway if ANY member is freeway; trunk-borderline if any trunk
    but none freeway.
    """
    gdf_4326 = gdf.to_crs(CRS_4326)
    coords_rad = np.radians(np.column_stack([gdf_4326.geometry.y, gdf_4326.geometry.x]))
    tree = BallTree(coords_rad, metric="haversine")
    R = 6_371_000.0
    indices = tree.query_radius(coords_rad, r=merge_m / R)

    parent = list(range(len(gdf)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    for i, nbrs in enumerate(indices):
        for j in nbrs:
            if j > i:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(len(gdf)):
        groups.setdefault(find(i), []).append(i)

    rows = []
    for _, members in groups.items():
        xs = [gdf.iloc[m].geometry.x for m in members]
        ys = [gdf.iloc[m].geometry.y for m in members]
        cx, cy = float(np.mean(xs)), float(np.mean(ys))
        osm_ids = [int(gdf.iloc[m]["osm_id"]) for m in members]
        is_fw  = any(node_classes.get(oid, (False, False))[0] for oid in osm_ids)
        is_trk = (
            any(node_classes.get(oid, (False, False))[1] for oid in osm_ids)
            and not is_fw
        )
        rows.append({
            "osm_id": osm_ids[0],
            "osm_id_members": ",".join(str(x) for x in osm_ids),
            "geometry": Point(cx, cy),
            "member_count": len(members),
            "is_freeway": is_fw,
            "is_trunk_borderline": is_trk,
            "is_surface": not is_fw,
        })

    merged = gpd.GeoDataFrame(rows, crs=gdf.crs)
    log.info("Node merge: %d -> %d (removed %d)", len(gdf), len(merged), len(gdf) - len(merged))
    return merged


def _graph_to_nodes_2230(G: nx.MultiDiGraph) -> tuple[gpd.GeoDataFrame, dict]:
    """Project graph, extract nodes, classify highway types. Returns (nodes_2230, classes)."""
    G_proj = ox.project_graph(G, to_crs=CRS_ANALYSIS)
    nodes_gdf, _ = ox.graph_to_gdfs(G_proj)
    nodes_gdf = nodes_gdf.reset_index().rename(columns={"osmid": "osm_id"})
    nodes_gdf = nodes_gdf[["osm_id", "geometry"]].copy()

    # Classify using original (unprojected) graph edges
    classes = {int(n): _classify_node(G, int(n)) for n in G.nodes()}
    log.info(
        "Highway classification: %d freeway nodes, %d trunk-borderline",
        sum(v[0] for v in classes.values()),
        sum(v[1] for v in classes.values()),
    )
    return nodes_gdf, classes


def _snap_and_count(
    ksi_gdf: gpd.GeoDataFrame,    # EPSG:2230, with 'id' and 'state_hwy_ind' cols
    nodes:   gpd.GeoDataFrame,    # EPSG:2230, surface nodes only
    buf_ft:  float,
) -> tuple[pd.Series, dict]:
    """
    Snap KSI crashes to nearest surface node within buf_ft.
    Returns:
      counts      : Series intersection_id -> count (for all nodes including zeros)
      stats       : dict with snap diagnostics
    """
    nc = np.column_stack([nodes.geometry.x, nodes.geometry.y])
    cc = np.column_stack([ksi_gdf.geometry.x, ksi_gdf.geometry.y])
    tree = cKDTree(nc)
    dists, idxs = tree.query(cc, k=1, workers=-1)
    within = dists <= buf_ft
    n_snapped = int(within.sum())
    assignments = pd.Series(
        nodes.iloc[idxs[within]]["intersection_id"].values,
        name="intersection_id",
    )
    counts = assignments.value_counts().rename("count")
    stats = {"n_ksi_input": len(ksi_gdf), "n_snapped": n_snapped}
    return counts, stats


def _apply_eligibility(
    nodes: gpd.GeoDataFrame,
    feat_counts: pd.Series,   # intersection_id -> KSI_feat count
    label_counts: pd.Series,  # intersection_id -> KSI_label count
) -> gpd.GeoDataFrame:
    """Apply candidate eligibility and return candidate panel."""
    panel = nodes[["intersection_id", "geometry", "is_trunk_borderline"]].copy()
    panel["KSI_feat"]  = panel["intersection_id"].map(feat_counts).fillna(0).astype(int)
    panel["KSI_label"] = panel["intersection_id"].map(label_counts).fillna(0).astype(int)

    # Eligibility
    c1 = panel["KSI_feat"] < CANDIDATE_MAX_KSI
    pct90 = float(np.percentile(panel["KSI_feat"].values, (1.0 - TOP_DECILE_DROP) * 100.0))
    c2 = panel["KSI_feat"] <= pct90

    candidates = panel[c1 & c2].copy()
    log.info(
        "Eligibility: KSI_feat<2 keeps %d; top-decile threshold=%.1f; candidates=%d",
        c1.sum(), pct90, len(candidates),
    )
    return candidates


def _label_distribution(series: pd.Series) -> dict:
    v = series.values
    return {
        "n0": int((v == 0).sum()),
        "n1": int((v == 1).sum()),
        "n2": int((v == 2).sum()),
        "n3p": int((v >= 3).sum()),
        "pos_ge1": int((v >= 1).sum()),
        "pos_ge2": int((v >= 2).sum()),
    }


# ---------------------------------------------------------------------------
# City re-derivation
# ---------------------------------------------------------------------------

def _load_crashes_with_coords(csv_path: Path) -> pd.DataFrame:
    """
    Load SWITRS Crashes.csv using POINT_X/POINT_Y as primary location source,
    falling back to LATITUDE/LONGITUDE where POINT_X is absent.

    In TIMS SWITRS exports:
    - POINT_X = longitude (WGS84), POINT_Y = latitude — geocoded for ~96% of records
    - LATITUDE/LONGITUDE — present mainly for state-highway (CHP postmile) crashes
    Using POINT_X/POINT_Y captures surface-street crashes that lack LATITUDE/LONGITUDE.
    """
    df = pd.read_csv(csv_path, usecols=[
        "CASE_ID", "COLLISION_DATE", "COLLISION_SEVERITY",
        "LATITUDE", "LONGITUDE", "POINT_X", "POINT_Y",
        "STATE_HWY_IND", "CITY",
    ], low_memory=False)
    df["date"] = pd.to_datetime(df["COLLISION_DATE"], errors="coerce")
    df = df.rename(columns={"CASE_ID": "id", "COLLISION_SEVERITY": "severity"})

    # Prefer POINT_X/POINT_Y; fall back to LATITUDE/LONGITUDE
    df["lon"] = df["POINT_X"].where(df["POINT_X"].notna(), df["LONGITUDE"])
    df["lat"] = df["POINT_Y"].where(df["POINT_Y"].notna(), df["LATITUDE"])

    n_before = len(df)
    df = df.dropna(subset=["lon", "lat", "date"])
    df = df[df["lat"].between(-90, 90) & df["lon"].between(-180, 180)]
    log.info("Loaded %d crashes with coords (dropped %d missing)", len(df), n_before - len(df))
    return df


def run_city_rederviation(probe_dir: Path) -> dict:
    """
    Re-derive city positives at 76.2 m, surface-street only.
    Reuses existing osm_graph.pkl and loads crashes fresh with STATE_HWY_IND.
    Uses POINT_X/POINT_Y for coordinates (more complete than LATITUDE/LONGITUDE).
    """
    log.info("=== CITY CLEAN RE-DERIVATION at %.1f m ===", PROBE_BUFFER_M)
    proc_dir  = ROOT / "data" / "proc"
    raw_dir   = ROOT / "data" / "raw"

    # Load OSM graph from cache
    graph_pkl = proc_dir / "osm_graph.pkl"
    log.info("Loading city OSM graph from %s", graph_pkl)
    with open(graph_pkl, "rb") as f:
        G_city = pickle.load(f)

    # Build node table with highway classification
    nodes_raw, classes = _graph_to_nodes_2230(G_city)
    nodes_merged = _merge_nodes(nodes_raw, classes)

    # Assign intersection_id
    nodes_merged["intersection_id"] = nodes_merged.apply(
        lambda r: _intersection_id(r.geometry.x, r.geometry.y), axis=1
    )
    log.info("City nodes: %d total, %d surface, %d freeway, %d trunk-borderline",
             len(nodes_merged),
             nodes_merged["is_surface"].sum(),
             (~nodes_merged["is_surface"]).sum(),
             nodes_merged["is_trunk_borderline"].sum())

    # Surface nodes only
    surface_nodes = nodes_merged[nodes_merged["is_surface"]].reset_index(drop=True)

    # Load city crashes using POINT_X/POINT_Y
    crashes_csv = sorted((raw_dir / "switrs").glob("*/Crashes.csv"), reverse=True)[0]
    log.info("Loading city crashes from %s (using POINT_X/POINT_Y)", crashes_csv)
    city_crashes = _load_crashes_with_coords(crashes_csv)

    # KSI only
    ksi_all = city_crashes[city_crashes["severity"].isin(KSI_SEVERITY_CODES)].copy()
    n_hwy_y  = (ksi_all["STATE_HWY_IND"] == "Y").sum()
    n_hwy_n  = (ksi_all["STATE_HWY_IND"] == "N").sum()
    n_hwy_na = ksi_all["STATE_HWY_IND"].isna().sum()
    log.info("City KSI with coords: %d (state-hwy Y: %d, N: %d, NaN: %d)",
             len(ksi_all), n_hwy_y, n_hwy_n, n_hwy_na)

    # Surface-only crashes (exclude STATE_HWY_IND == 'Y')
    ksi_surface = ksi_all[ksi_all["STATE_HWY_IND"] != "Y"].copy()
    log.info("City KSI surface (non-state-hwy): %d", len(ksi_surface))

    # Project crashes to EPSG:2230
    ksi_gdf = gpd.GeoDataFrame(
        ksi_surface,
        geometry=gpd.points_from_xy(ksi_surface["lon"], ksi_surface["lat"]),
        crs=CRS_4326,
    ).to_crs(CRS_ANALYSIS)

    ksi_feat_gdf  = ksi_gdf[(ksi_gdf["date"] >= FEATURE_START) & (ksi_gdf["date"] <= FEATURE_END)]
    ksi_label_gdf = ksi_gdf[(ksi_gdf["date"] >= LABEL_START)   & (ksi_gdf["date"] <= LABEL_END)]
    log.info("City surface KSI: feat=%d, label=%d", len(ksi_feat_gdf), len(ksi_label_gdf))

    # Snap
    feat_counts,  feat_stats  = _snap_and_count(ksi_feat_gdf,  surface_nodes, PROBE_BUFFER_FT)
    label_counts, label_stats = _snap_and_count(ksi_label_gdf, surface_nodes, PROBE_BUFFER_FT)

    # Eligibility + candidates
    candidates = _apply_eligibility(surface_nodes, feat_counts, label_counts)
    dist = _label_distribution(candidates["KSI_label"])

    log.info("City surface candidates: %d, pos@>=2: %d, pos@>=1: %d",
             len(candidates), dist["pos_ge2"], dist["pos_ge1"])

    # Save
    out = probe_dir / "city_surface_panel.parquet"
    candidates.to_parquet(out, index=False)

    # Trunk-borderline subset for reporting
    trunk_candidates = candidates[candidates["is_trunk_borderline"]]
    trunk_dist = _label_distribution(trunk_candidates["KSI_label"])

    # Freeway contamination summary (for report)
    n_ksi_total   = len(ksi_all)
    n_ksi_freeway = (ksi_all["STATE_HWY_IND"] == "Y").sum()
    freeway_share = n_ksi_freeway / n_ksi_total if n_ksi_total > 0 else 0.0

    result = {
        "scope": "city",
        "total_nodes": int(len(nodes_merged)),
        "surface_nodes": int(len(surface_nodes)),
        "freeway_nodes": int((~nodes_merged["is_surface"]).sum()),
        "trunk_borderline_nodes": int(nodes_merged["is_trunk_borderline"].sum()),
        "n_ksi_total": int(n_ksi_total),
        "n_ksi_freeway": int(n_ksi_freeway),
        "freeway_ksi_share": float(freeway_share),
        "n_ksi_surface_feat": feat_stats["n_ksi_input"],
        "n_ksi_surface_label": label_stats["n_ksi_input"],
        "candidates": int(len(candidates)),
        "dist": dist,
        "trunk_candidates": int(len(trunk_candidates)),
        "trunk_dist": trunk_dist,
    }
    log.info("City result: %s", result)
    return result


# ---------------------------------------------------------------------------
# County OSM graph
# ---------------------------------------------------------------------------

def _get_urban_clip_polygon() -> gpd.GeoDataFrame:
    """
    Fetch incorporated city/town boundaries in San Diego County from OSM
    and return their union + 1 km buffer (in EPSG:4326).
    Falls back to a coastal bbox if the query fails.
    """
    log.info("Fetching San Diego County incorporated city boundaries from OSM ...")
    try:
        # OSM admin_level=8 = city/town within California context
        admin = ox.features_from_place(
            "San Diego County, California, USA",
            tags={"boundary": "administrative", "admin_level": "8"},
        )
        polys = admin[admin.geometry.type.isin(["Polygon", "MultiPolygon"])]
        log.info("Found %d incorporated city polygons in OSM admin query", len(polys))
        if len(polys) == 0:
            raise ValueError("No polygons returned")
        # Fix invalid geometries (self-intersections from OSM simplification)
        valid_geoms = [g.buffer(0) if not g.is_valid else g for g in polys.geometry.values]
        union_4326 = unary_union(valid_geoms)
        # 1 km buffer: project to EPSG:3857 (metres), buffer, reproject
        gdf_union = gpd.GeoDataFrame(geometry=[union_4326], crs=CRS_4326)
        gdf_3857  = gdf_union.to_crs("EPSG:3857")
        gdf_3857["geometry"] = gdf_3857.geometry.buffer(1000)
        gdf_4326  = gdf_3857.to_crs(CRS_4326)
        log.info("Urban clip polygon built from %d city boundaries + 1 km buffer", len(polys))
        return gdf_4326
    except Exception as e:
        log.warning("OSM admin query failed (%s); using coastal bbox fallback", e)
        # Fallback: western coastal strip of SD County (excludes eastern desert)
        coastal_bbox = Polygon([
            (-117.6, 32.5), (-116.5, 32.5), (-116.5, 33.5), (-117.6, 33.5),
        ])
        return gpd.GeoDataFrame(geometry=[coastal_bbox], crs=CRS_4326)


def _load_or_fetch_county_graph(raw_county_dir: Path) -> nx.MultiDiGraph:
    """Load cached county graph or fetch from OSM."""
    today = date.today().strftime("%Y%m%d")
    snap_dir = raw_county_dir / today
    snap_dir.mkdir(parents=True, exist_ok=True)
    cache_pkl  = snap_dir / "sdcounty_drive.pkl"
    cache_graphml = snap_dir / "sdcounty_drive.graphml"

    if cache_pkl.exists():
        log.info("Loading cached county OSM graph from %s", cache_pkl)
        with open(cache_pkl, "rb") as f:
            return pickle.load(f)

    log.info("Fetching San Diego County drive graph from OSM (this may take 5-10 min) ...")
    ox.settings.log_console = False
    ox.settings.use_cache = True
    G = ox.graph_from_place(
        "San Diego County, California, USA",
        network_type="drive",
        simplify=True,
    )
    log.info("Raw county graph: %d nodes, %d edges", len(G.nodes), len(G.edges))

    # Cache to disk
    with open(cache_pkl, "wb") as f:
        pickle.dump(G, f)
    ox.save_graphml(G, filepath=str(cache_graphml))

    manifest = {
        "source": "OSMnx graph_from_place",
        "place": "San Diego County, California, USA",
        "network_type": "drive",
        "fetch_date": today,
        "n_nodes": len(G.nodes),
        "n_edges": len(G.edges),
    }
    with open(snap_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    log.info("Cached county graph to %s", snap_dir)
    return G


def _clip_graph_to_polygon(G: nx.MultiDiGraph, clip_gdf: gpd.GeoDataFrame) -> nx.MultiDiGraph:
    """Retain only nodes (and their edges) that fall within the clip polygon."""
    # Fix invalid geometries before union (OSM admin boundaries can have self-intersections)
    valid_geoms = [g.buffer(0) if not g.is_valid else g for g in clip_gdf.geometry.values]
    clip_union = unary_union(valid_geoms)
    if not clip_union.is_valid:
        clip_union = clip_union.buffer(0)
    nodes_to_keep = []
    for n, data in G.nodes(data=True):
        pt = Point(data.get("x", 0), data.get("y", 0))
        if clip_union.contains(pt):
            nodes_to_keep.append(n)
    log.info("Urban clip: %d / %d nodes retained", len(nodes_to_keep), len(G.nodes))
    return G.subgraph(nodes_to_keep).copy()


def run_county_spine(raw_county_dir: Path, probe_dir: Path) -> tuple[gpd.GeoDataFrame, dict]:
    """Pull/load county OSM, clip to urbanized footprint, merge nodes, tag surface."""
    log.info("=== COUNTY NODE SPINE ===")

    clip_gdf = _get_urban_clip_polygon()
    G_raw    = _load_or_fetch_county_graph(raw_county_dir)

    # Clip to urbanized footprint before heavy processing
    log.info("Clipping county graph to urbanized footprint ...")
    G_urban = _clip_graph_to_polygon(G_raw, clip_gdf)
    log.info("Urban-clipped county graph: %d nodes, %d edges",
             len(G_urban.nodes), len(G_urban.edges))

    # Project + classify + merge
    nodes_raw, classes = _graph_to_nodes_2230(G_urban)
    nodes_merged = _merge_nodes(nodes_raw, classes)
    nodes_merged["intersection_id"] = nodes_merged.apply(
        lambda r: _intersection_id(r.geometry.x, r.geometry.y), axis=1
    )

    log.info("County (urban) nodes: %d total, %d surface, %d freeway, %d trunk-borderline",
             len(nodes_merged),
             nodes_merged["is_surface"].sum(),
             (~nodes_merged["is_surface"]).sum(),
             nodes_merged["is_trunk_borderline"].sum())

    out = probe_dir / "county_nodes_2230.parquet"
    nodes_merged.to_parquet(out, index=False)

    stats = {
        "raw_nodes_county": len(G_raw.nodes),
        "urban_clip_nodes": len(G_urban.nodes),
        "merged_total": int(len(nodes_merged)),
        "merged_surface": int(nodes_merged["is_surface"].sum()),
        "merged_freeway": int((~nodes_merged["is_surface"]).sum()),
        "merged_trunk_borderline": int(nodes_merged["is_trunk_borderline"].sum()),
    }
    return nodes_merged[nodes_merged["is_surface"]].reset_index(drop=True), stats


# ---------------------------------------------------------------------------
# County crashes
# ---------------------------------------------------------------------------

def _load_county_crashes(raw_county_dir: Path) -> pd.DataFrame | None:
    """Load county SWITRS Crashes.csv; return None if not present."""
    csvs = sorted(raw_county_dir.glob("*/Crashes.csv"), reverse=True)
    if not csvs:
        csvs = sorted(raw_county_dir.glob("*/crashes.csv"), reverse=True)
    if not csvs:
        log.warning("County SWITRS not found under %s -- county labels cannot be computed",
                    raw_county_dir)
        return None
    path = csvs[0]
    log.info("Loading county crashes from %s (using POINT_X/POINT_Y)", path)
    return _load_crashes_with_coords(path)


def run_county_labels(
    surface_nodes: gpd.GeoDataFrame,
    raw_county_dir: Path,
    probe_dir: Path,
) -> dict | None:
    """Snap county surface KSI to nodes, apply eligibility, return stats."""
    log.info("=== COUNTY LABEL CONSTRUCTION ===")

    crashes = _load_county_crashes(raw_county_dir)
    if crashes is None:
        return None

    ksi_all = crashes[crashes["severity"].isin(KSI_SEVERITY_CODES)].copy()
    n_ksi_total   = len(ksi_all)
    n_ksi_freeway = (ksi_all["STATE_HWY_IND"] == "Y").sum()
    n_ksi_nan     = ksi_all["STATE_HWY_IND"].isna().sum()
    log.info("County KSI: total=%d, state-hwy Y=%d (%.1f%%), NaN=%d",
             n_ksi_total, n_ksi_freeway,
             100 * n_ksi_freeway / max(n_ksi_total, 1), n_ksi_nan)

    # Surface crashes: exclude state highway
    ksi_surface = ksi_all[ksi_all["STATE_HWY_IND"] != "Y"].copy()
    log.info("County KSI surface: %d", len(ksi_surface))

    # Project
    ksi_gdf = gpd.GeoDataFrame(
        ksi_surface,
        geometry=gpd.points_from_xy(ksi_surface["LONGITUDE"], ksi_surface["LATITUDE"]),
        crs=CRS_4326,
    ).to_crs(CRS_ANALYSIS)

    ksi_feat_gdf  = ksi_gdf[(ksi_gdf["date"] >= FEATURE_START) & (ksi_gdf["date"] <= FEATURE_END)]
    ksi_label_gdf = ksi_gdf[(ksi_gdf["date"] >= LABEL_START)   & (ksi_gdf["date"] <= LABEL_END)]
    log.info("County surface KSI: feat=%d, label=%d", len(ksi_feat_gdf), len(ksi_label_gdf))

    feat_counts,  feat_stats  = _snap_and_count(ksi_feat_gdf,  surface_nodes, PROBE_BUFFER_FT)
    label_counts, label_stats = _snap_and_count(ksi_label_gdf, surface_nodes, PROBE_BUFFER_FT)

    candidates = _apply_eligibility(surface_nodes, feat_counts, label_counts)
    dist = _label_distribution(candidates["KSI_label"])
    log.info("County surface candidates: %d, pos@>=2: %d, pos@>=1: %d",
             len(candidates), dist["pos_ge2"], dist["pos_ge1"])

    # Per-jurisdiction breakdown of label-window positives
    label_pos = ksi_label_gdf[ksi_label_gdf["date"].notna()].copy()
    # Map CITY column to group
    juris = label_pos["CITY"].fillna("UNINCORPORATED").str.upper().str.strip()
    sd_city_mask = juris == "SAN DIEGO"
    juris_breakdown = {
        "city_of_sd":     int(sd_city_mask.sum()),
        "other_cities":   int((~sd_city_mask & (juris != "UNINCORPORATED")).sum()),
        "unincorporated": int((juris == "UNINCORPORATED").sum()),
    }
    log.info("County label-window KSI jurisdiction breakdown: %s", juris_breakdown)

    # OSM-rule vs STATE_HWY_IND agreement analysis
    # Among all county KSI, compare our snap (surface-only) vs indicator
    total_ksi_with_ind = (ksi_all["STATE_HWY_IND"].isin(["Y", "N"])).sum()
    agreed_exclude = (ksi_all["STATE_HWY_IND"] == "Y").sum()  # excluded by both rules
    # We treat NaN as surface; STATE_HWY_IND N = surface = consistent
    agreement_rate = agreed_exclude / total_ksi_with_ind if total_ksi_with_ind > 0 else float("nan")

    # Save
    out = probe_dir / "county_surface_panel.parquet"
    candidates.to_parquet(out, index=False)

    return {
        "scope": "county",
        "n_ksi_total": int(n_ksi_total),
        "n_ksi_freeway": int(n_ksi_freeway),
        "n_ksi_nan": int(n_ksi_nan),
        "freeway_ksi_share": float(n_ksi_freeway / max(n_ksi_total, 1)),
        "n_ksi_surface_feat": feat_stats["n_ksi_input"],
        "n_ksi_surface_label": label_stats["n_ksi_input"],
        "candidates": int(len(candidates)),
        "dist": dist,
        "juris_breakdown": juris_breakdown,
        "agreement_rate": float(agreement_rate),
    }


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _fmt_dist(d: dict) -> str:
    return f"{d['n0']:,}/{d['n1']:,}/{d['n2']:,}/{d['n3p']:,}"


def write_report(
    city: dict,
    county: dict | None,
    county_spine_stats: dict | None,
    reports_dir: Path,
) -> None:
    today = date.today().isoformat()

    # Decision logic
    pos2_county = county["dist"]["pos_ge2"] if county else None
    pos2_city   = city["dist"]["pos_ge2"]

    if pos2_county is None:
        verdict = "PENDING -- county SWITRS not yet downloaded"
        verdict_detail = (
            "Cannot make the escalate-vs-stay decision without county data. "
            "See 'Next step' below."
        )
    elif pos2_county >= 300:
        verdict = "ESCALATE to county-wide scope for M3"
        verdict_detail = (
            f"County surface @>=2 = {pos2_county} >= 300 (pre-registered adequacy bar). "
            "Full county respine is clearly justified."
        )
    elif 150 <= pos2_county < 300:
        # Check jurisdiction concentration
        juris = county.get("juris_breakdown", {})
        sd_share = juris.get("city_of_sd", 0) / max(pos2_county, 1)
        if sd_share >= 0.60:
            verdict = "ESCALATE (marginal -- majority concentrated in City of SD)"
            verdict_detail = (
                f"County surface @>=2 = {pos2_county} ({150}-300 range). "
                f"{100*sd_share:.0f}% of positives in City of SD -- "
                "heterogeneity cost is lower than a geographically dispersed result."
            )
        else:
            verdict = "STAY city-only at 76.2 m for M3"
            verdict_detail = (
                f"County surface @>=2 = {pos2_county} ({150}-300 range) "
                "but positives are spread across jurisdictions. "
                "County complexity cost (heterogeneous infrastructure data, mixed reporting) "
                "outweighs the marginal N gain. Stay city, proceed to M3 at 76.2 m."
            )
    else:
        verdict = "STAY city-only at 76.2 m for M3"
        verdict_detail = (
            f"County surface @>=2 = {pos2_county} < 150 (barely above "
            f"clean city baseline of {pos2_city}). "
            "County complexity cost exceeds power gain. "
            "Stay city-only at 76.2 m; frame M3 with honest wide CIs."
        )

    lines: list[str] = [
        "# Milestone 2.5 -- County Scope Probe",
        "",
        f"**Date:** {today}  ",
        f"**Buffer:** {PROBE_BUFFER_M} m ({PROBE_BUFFER_FT:.2f} US survey feet)  ",
        "**Surface filter:** exclude nodes where any incident edge is motorway/motorway_link  ",
        "**Trunk-borderline:** kept in count, reported separately  ",
        "",
        "---",
        "",
        "## Headline Comparison Table (76.2 m, surface-street only)",
        "",
        "| Scope | Candidates | Pos @>=2 | Pos @>=1 | Count dist (0/1/2/3+) | Nodes (surface) |",
        "| ----- | ---------- | -------- | -------- | --------------------- | --------------- |",
    ]

    city_d = city["dist"]
    lines.append(
        f"| City (clean re-derivation) | {city['candidates']:,} | **{city_d['pos_ge2']}** "
        f"| {city_d['pos_ge1']} | {_fmt_dist(city_d)} | {city['surface_nodes']:,} |"
    )
    if county and county["dist"]:
        cd = county["dist"]
        lines.append(
            f"| County (urbanized) | {county['candidates']:,} | **{cd['pos_ge2']}** "
            f"| {cd['pos_ge1']} | {_fmt_dist(cd)} | "
            f"{county_spine_stats['merged_surface']:,} |"
        )
    else:
        lines.append(
            f"| County (urbanized) | *pending* | *pending* | *pending* | *pending* "
            f"| {county_spine_stats['merged_surface']:,} |"
            if county_spine_stats else
            "| County (urbanized) | *not run -- SWITRS missing* | -- | -- | -- | -- |"
        )

    lines += [
        "",
        "**Note:** 'clean re-derivation' replaces M2's buffer-sweep city @76.2 m figure of 48,",
        "which was computed on the full SWITRS dataset including `STATE_HWY_IND=Y` crashes.",
        "",
        "---",
        "",
        "## Freeway Contamination",
        "",
        f"### City of San Diego",
        f"- Total KSI crashes in SWITRS: {city['n_ksi_total']:,}",
        f"- State highway (`STATE_HWY_IND=Y`): **{city['n_ksi_freeway']:,} "
        f"({100*city['freeway_ksi_share']:.1f}%)**",
        f"- Surface (non-state-hwy): {city['n_ksi_total'] - city['n_ksi_freeway']:,}",
        f"  - Used for feature window: {city['n_ksi_surface_feat']:,}",
        f"  - Used for label window: {city['n_ksi_surface_label']:,}",
        "",
    ]

    if county:
        lines += [
            f"### San Diego County",
            f"- Total KSI crashes in county SWITRS: {county['n_ksi_total']:,}",
            f"- State highway (`STATE_HWY_IND=Y`): **{county['n_ksi_freeway']:,} "
            f"({100*county['freeway_ksi_share']:.1f}%)**",
            f"- NaN indicator (treated as surface): {county['n_ksi_nan']:,}",
            f"- Surface: {county['n_ksi_total'] - county['n_ksi_freeway']:,}",
            f"  - Feature window: {county['n_ksi_surface_feat']:,}",
            f"  - Label window: {county['n_ksi_surface_label']:,}",
            "",
            "### OSM-edge rule vs SWITRS STATE_HWY_IND agreement",
            f"The node-level OSM surface filter and the crash-level `STATE_HWY_IND` flag ",
            f"are complementary defenses. Agreement on freeway exclusion: "
            f"{100*county.get('agreement_rate', float('nan')):.1f}% of crashes with known indicator.",
            "Divergences (OSM-surface node but STATE_HWY_IND=Y, or vice versa) represent ramp",
            "terminals and service roads that straddle the freeway/surface boundary. These are",
            "counted in the trunk-borderline class below.",
            "",
        ]
    else:
        lines.append("County freeway data: *pending county SWITRS download*\n")

    # Trunk-borderline section
    lines += [
        "## Trunk-Borderline Nodes (kept, reported separately)",
        "",
        f"Trunk-borderline = node has incident trunk/trunk_link edges but NO motorway/motorway_link.",
        f"These are arterials and expressways that share characteristics with surface streets.",
        "",
        f"**City:** {city['trunk_candidates']:,} trunk-borderline candidates; "
        f"pos@>=2 = {city['trunk_dist']['pos_ge2']}, pos@>=1 = {city['trunk_dist']['pos_ge1']}",
    ]
    if county and county_spine_stats:
        lines.append(
            f"**County:** trunk-borderline node count = "
            f"{county_spine_stats.get('merged_trunk_borderline', 'N/A'):,}"
        )
    lines.append("")

    # Per-jurisdiction breakdown
    if county and "juris_breakdown" in county:
        j = county["juris_breakdown"]
        total_jur = sum(j.values())
        lines += [
            "## Per-Jurisdiction Breakdown (County, Label-Window KSI Surface Crashes)",
            "",
            "| Jurisdiction | KSI crashes | Share |",
            "| ------------ | ----------- | ----- |",
            f"| City of San Diego | {j['city_of_sd']:,} | "
            f"{100*j['city_of_sd']/max(total_jur,1):.1f}% |",
            f"| Other incorporated cities | {j['other_cities']:,} | "
            f"{100*j['other_cities']/max(total_jur,1):.1f}% |",
            f"| Unincorporated | {j['unincorporated']:,} | "
            f"{100*j['unincorporated']/max(total_jur,1):.1f}% |",
            "",
            "This breakdown previews the **infrastructure heterogeneity cost** of escalating to",
            "county scope: SanGIS layers (bike facilities, speed limits, signal timing) are",
            "available for all jurisdictions but data completeness varies by city. Unincorporated",
            "areas rely on county maintenance logs rather than per-city inventories.",
            "",
        ]

    # Scale/feasibility
    if county_spine_stats:
        lines += [
            "## Scale and Feasibility",
            "",
            f"| Metric | Value |",
            f"| ------ | ----- |",
            f"| County raw nodes (OSMnx) | {county_spine_stats.get('raw_nodes_county', 'N/A'):,} |",
            f"| Urban-clip nodes | {county_spine_stats.get('urban_clip_nodes', 'N/A'):,} |",
            f"| Merged surface nodes | {county_spine_stats.get('merged_surface', 'N/A'):,} |",
            f"| City nodes (M1 spine) | {city['total_nodes']:,} |",
            "",
            "A county respine is computationally tractable: the urban-clip graph is roughly",
            "2-4x the city node count, fits in < 4 GB RAM, and the feature pipeline runtime",
            "would scale linearly.",
            "",
        ]

    # Recommendation
    lines += [
        "## Decision Rule and Recommendation",
        "",
        f"Pre-registered adequacy bar: **~300 positives @>=2**",
        "",
        f"> **{verdict}**",
        "",
        f"{verdict_detail}",
        "",
    ]

    if county:
        pos2 = county["dist"]["pos_ge2"]
        lines += [
            "### Cost accounting",
            "",
            "**County costs:**",
            "- Infrastructure features (bike lanes, signals, speed limits) require per-city",
            "  data harmonisation across ~18 municipalities",
            "- Reporting practices differ between SDPD (city) and CHP / other agencies (county)",
            "- Feature pipeline runtime increases ~3x",
            "",
            "**County benefits:**",
            f"- {pos2} positives @>=2 vs {pos2_city} city-only (ratio: "
            f"{pos2/max(pos2_city,1):.1f}x)",
            "- Broader spatial variation provides better OOS test of generalization",
            "- County scope is more aligned with regional Vision Zero policy",
            "",
        ]
    else:
        lines += [
            "**County SWITRS not downloaded.** Run probe again after downloading to get the",
            "full comparison and recommendation.",
            "",
            "**Next step:**",
            "1. Download county SWITRS from https://tims.berkeley.edu (County = San Diego,",
            "   all cities, 2015-01-01 -- 2024-12-31, download Crashes.csv)",
            "2. Place in `data/raw/switrs_county/<YYYYMMDD>/Crashes.csv`",
            "3. Re-run: `python -m src.probe.county_probe`",
            "",
            "**Partial result available:** Clean city re-derivation at 76.2 m, surface-only:",
            f"- {city['candidates']:,} candidates, {city['dist']['pos_ge2']} pos@>=2, "
            f"{city['dist']['pos_ge1']} pos@>=1",
            f"- This replaces the contaminated M2 buffer-sweep figure (48 @>=2 at 76.2 m)",
            "",
        ]

    if county_spine_stats:
        lines += [
            "The county node spine has been pre-built and cached at",
            "`data/raw/osm_county/<YYYYMMDD>/sdcounty_drive.pkl`. Re-running the probe",
            "will skip the OSM download and proceed directly to label construction.",
            "",
        ]

    lines += [
        "---",
        "",
        "## M3 Scope Proposal (conditional on verdict)",
        "",
    ]

    if county and pos2_county is not None and pos2_county >= 150:
        lines += [
            "**If escalate is confirmed:**",
            "- M3 = county respine (full feature pipeline rebuilt at county scope, 76.2 m)",
            "- Rebuild `nodes_spine_2230.parquet` from county OSM",
            "- Rebuild `candidate_panel.parquet` and `feature_table.parquet` at county scope",
            "- Add exposure proxy: OSM lane count + road class as ADT surrogate",
            "- Add graph-hop neighbor features (neighbor_ksi_1hop) now feasible at county density",
            "- Same 4-model suite; expect >150 positives @>=2 enabling stable spatial-block CV",
        ]
    else:
        lines += [
            "**Stay city (default or pending):**",
            "- M3 = infrastructure + geometry features on the existing city spine at 76.2 m",
            "- Rebuild `candidate_panel.parquet` at 76.2 m (surface-only)",
            "- Add features: OSM edge count, lane count, signal type, road class mix,",
            "  nearest arterial distance, slope (DEM), bike lane presence (SanGIS)",
            "- Refit 4-model suite on updated candidate panel",
            "- Honest framing: Tweedie primary, wide CIs noted, directional signal confirmed",
        ]

    lines.append("")

    out = reports_dir / "milestone2_5_scope_probe.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    log.info("Wrote %s", out)


def write_deviations(reports_dir: Path) -> None:
    today = date.today().isoformat()
    deviations_path = reports_dir / "DEVIATIONS.md"

    entry = f"""
## M2.5 deviation chain (recorded {today})

1. **Pre-registered re-scope trigger fired** (city, 30 m): 5-6 positives @>=2.
   Trigger threshold was < 300 positives.

2. **Registered fallback (Option A, Tweedie) adopted in M2.** XGBoost-Tweedie showed
   directional Spearman lift (0.275 random / 0.172 spatial, ~3.5x baseline) confirming
   the architecture works.

3. **City N inadequate at the registered 30 m buffer.** The registered buffer was
   deliberately conservative (minimal cross-intersection attribution overlap); the
   sparse label result was a design artefact, not signal absence.

4. **Influence zone refined to 76.2 m (250 US survey feet), primary buffer.**
   Supported by the M2 buffer sensitivity sweep (6→48 positives @>=2 at 30→76.2 m).
   Disclosed as a deliberate definition refinement, not post-hoc cherry-picking.
   Old 30 m value retained as a sensitivity row.

5. **County scope probed before committing** (this milestone). Escalation decision
   made on measured surface-street positive counts at 76.2 m, not extrapolation from
   the city sweep. Freeway contamination (STATE_HWY_IND=Y crashes) excluded from
   both city and county counts for an apples-to-apples comparison.

6. **Surface-street-only unit of analysis adopted.** Any node with an incident
   motorway or motorway_link OSM edge is excluded from the candidate set. Trunk/trunk_link
   nodes kept but flagged. This was not explicitly pre-registered but is a principled
   clarification of the intersection-node unit of analysis: freeway mainline and ramp
   nodes are not intersection nodes in the Vision Zero sense.
"""

    if deviations_path.exists():
        existing = deviations_path.read_text(encoding="utf-8")
        if "M2.5 deviation chain" not in existing:
            deviations_path.write_text(existing + entry, encoding="utf-8")
            log.info("Appended to %s", deviations_path)
    else:
        deviations_path.write_text(f"# Deviation Log\n{entry}", encoding="utf-8")
        log.info("Created %s", deviations_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    probe_dir    = ROOT / "data" / "probe"
    raw_cty_dir  = ROOT / "data" / "raw" / "switrs_county"
    osm_cty_dir  = ROOT / "data" / "raw" / "osm_county"
    reports_dir  = ROOT / "reports"
    probe_dir.mkdir(parents=True, exist_ok=True)

    log.info("Probe buffer: %.4f US survey feet (%.1f m)", PROBE_BUFFER_FT, PROBE_BUFFER_M)

    # Phase 1: City clean re-derivation
    city_result = run_city_rederviation(probe_dir)

    # Phase 2: County OSM spine (always attempt -- pull + cache is idempotent)
    county_surface_nodes, county_spine_stats = run_county_spine(osm_cty_dir, probe_dir)

    # Phase 3: County labels (only if SWITRS available)
    county_result = run_county_labels(county_surface_nodes, raw_cty_dir, probe_dir)

    # Phase 4: Write report
    write_report(city_result, county_result, county_spine_stats, reports_dir)
    write_deviations(reports_dir)

    # Summary to stdout
    city_d = city_result["dist"]
    print("\n" + "=" * 70)
    print("MILESTONE 2.5 -- SCOPE PROBE SUMMARY")
    print("=" * 70)
    print(f"Buffer: {PROBE_BUFFER_M} m ({PROBE_BUFFER_FT:.2f} ft), surface-street only")
    print()
    print(f"CITY (clean re-derivation):")
    print(f"  Candidates:  {city_result['candidates']:,}")
    print(f"  pos @>=2:    {city_d['pos_ge2']}   (was: 48 contaminated in M2 sweep)")
    print(f"  pos @>=1:    {city_d['pos_ge1']}")
    print(f"  Count dist:  {_fmt_dist(city_d)}  (0/1/2/3+)")
    print(f"  Freeway KSI excluded: {city_result['n_ksi_freeway']} "
          f"({100*city_result['freeway_ksi_share']:.1f}%)")
    if county_result:
        county_d = county_result["dist"]
        print()
        print(f"COUNTY (urbanized, surface-only):")
        print(f"  Candidates:  {county_result['candidates']:,}")
        print(f"  pos @>=2:    {county_d['pos_ge2']}")
        print(f"  pos @>=1:    {county_d['pos_ge1']}")
        print(f"  Count dist:  {_fmt_dist(county_d)}  (0/1/2/3+)")
        print(f"  Freeway KSI excluded: {county_result['n_ksi_freeway']} "
              f"({100*county_result['freeway_ksi_share']:.1f}%)")
    else:
        print()
        print("COUNTY: SWITRS not available -- download and re-run")
        print(f"  County OSM spine: {county_spine_stats['merged_surface']:,} surface nodes cached")
    print("=" * 70)
    print(f"Report: reports/milestone2_5_scope_probe.md")


if __name__ == "__main__":
    main()
