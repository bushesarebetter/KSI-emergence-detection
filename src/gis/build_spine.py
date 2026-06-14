"""Build the intersection node spine.

Pipeline:
  1. Load OSM graph (cached pickle from ingest).
  2. Project to EPSG:2230 (US survey feet).
  3. Classify nodes by incident edge highway type:
       is_freeway         = any incident edge is motorway / motorway_link
       is_trunk_borderline = any trunk/trunk_link but NO freeway edge
       is_surface         = not is_freeway (default candidate class)
  4. Extract intersection nodes (all nodes in OSMnx simplified drive graph).
  5. Merge near-duplicate nodes within node_merge_m (10 m).
     A merged node is freeway if ANY member is freeway.
  6. Assign stable intersection_id (MD5 of rounded EPSG:2230 coords).
  7. Write GeoParquet with surface classification tags.

Run via:  python -m src.gis.build_spine
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from shapely.geometry import Point
from sklearn.neighbors import BallTree

from src.utils import buffer_feet, intersection_id, load_config, project_root

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

_FREEWAY_TYPES = frozenset({"motorway", "motorway_link"})
_TRUNK_TYPES   = frozenset({"trunk", "trunk_link"})


# ---------------------------------------------------------------------------
# Surface classification
# ---------------------------------------------------------------------------

def _edge_highway_set(G: nx.MultiDiGraph, osmid: int) -> set[str]:
    """Return all highway type strings on edges incident to osmid (in + out)."""
    types: set[str] = set()
    for _, _, data in G.edges(osmid, data=True):
        hw = data.get("highway", "")
        if isinstance(hw, list):
            types.update(str(h) for h in hw)
        elif hw:
            types.add(str(hw))
    for _, _, data in G.in_edges(osmid, data=True):
        hw = data.get("highway", "")
        if isinstance(hw, list):
            types.update(str(h) for h in hw)
        elif hw:
            types.add(str(hw))
    return types


def _classify_nodes(G: nx.MultiDiGraph) -> dict[int, tuple[bool, bool]]:
    """Return {osmid: (is_freeway, is_trunk_borderline)} for all nodes."""
    result: dict[int, tuple[bool, bool]] = {}
    for n in G.nodes():
        hw = _edge_highway_set(G, int(n))
        is_fw  = bool(hw & _FREEWAY_TYPES)
        is_trk = bool((hw & _TRUNK_TYPES) and not is_fw)
        result[int(n)] = (is_fw, is_trk)
    n_fw  = sum(v[0] for v in result.values())
    n_trk = sum(v[1] for v in result.values())
    log.info("Node highway classification: %d freeway, %d trunk-borderline, %d surface",
             n_fw, n_trk, len(result) - n_fw - n_trk)
    return result


# ---------------------------------------------------------------------------
# Node merge
# ---------------------------------------------------------------------------

def _merge_near_duplicates(
    gdf: gpd.GeoDataFrame,
    node_classes: dict[int, tuple[bool, bool]],
    merge_m: float,
    crs_analysis: str,
) -> gpd.GeoDataFrame:
    """Collapse nodes within merge_m metres (haversine).

    Surface classification: a merged node is freeway if ANY member is freeway;
    trunk-borderline if any trunk but NO freeway; surface otherwise.
    """
    gdf_4326 = gdf.to_crs("EPSG:4326")
    coords_rad = np.radians(
        np.column_stack([gdf_4326.geometry.y, gdf_4326.geometry.x])
    )
    tree = BallTree(coords_rad, metric="haversine")
    R_earth = 6_371_000.0
    radius_rad = merge_m / R_earth
    indices = tree.query_radius(coords_rad, r=radius_rad)

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
    log.info(
        "Node merge: %d -> %d nodes (removed %d near-duplicates within %.0f m)",
        len(gdf), len(merged), len(gdf) - len(merged), merge_m,
    )
    return merged


# ---------------------------------------------------------------------------
# Main spine builder
# ---------------------------------------------------------------------------

def build_spine(cfg: dict) -> gpd.GeoDataFrame:
    import osmnx as ox

    proc = project_root() / cfg["paths"]["proc"]
    crs_a = cfg["crs"]["analysis"]   # EPSG:2230
    crs_m = cfg["crs"]["mapping"]    # EPSG:4326
    merge_m = cfg["geometry"]["node_merge_m"]

    # Load cached graph
    graph_cache = proc / "osm_graph.pkl"
    log.info("Loading OSM graph from %s", graph_cache)
    with open(graph_cache, "rb") as f:
        G = pickle.load(f)

    # Classify nodes by highway type (using unprojected graph for edge attribute access)
    node_classes = _classify_nodes(G)

    # Project graph to analysis CRS
    G_proj = ox.project_graph(G, to_crs=crs_a)
    nodes_gdf, _ = ox.graph_to_gdfs(G_proj)
    nodes_gdf = nodes_gdf.reset_index().rename(columns={"osmid": "osm_id"})
    nodes_gdf = nodes_gdf[["osm_id", "geometry"]].copy()
    log.info("Extracted %d raw nodes from OSM graph (EPSG:2230)", len(nodes_gdf))

    # Merge near-duplicates, propagating surface classification
    nodes_merged = _merge_near_duplicates(nodes_gdf, node_classes, merge_m, crs_a)

    # Assign intersection_id
    nodes_merged["intersection_id"] = nodes_merged.apply(
        lambda r: intersection_id(r.geometry.x, r.geometry.y), axis=1
    )

    # Check for collisions
    n_unique = nodes_merged["intersection_id"].nunique()
    if n_unique < len(nodes_merged):
        log.warning(
            "intersection_id collision: %d nodes but %d unique IDs",
            len(nodes_merged), n_unique,
        )

    # Add 4326 geometry + lat/lon columns
    nodes_4326 = nodes_merged.to_crs(crs_m)
    nodes_merged["lon"] = nodes_4326.geometry.x
    nodes_merged["lat"] = nodes_4326.geometry.y
    nodes_merged["geometry_4326"] = nodes_4326.geometry

    buf_ft = buffer_feet(cfg)
    nodes_merged["buffer_ft"] = buf_ft

    # Log surface classification summary
    n_surface = nodes_merged["is_surface"].sum()
    n_freeway = (~nodes_merged["is_surface"]).sum()
    n_trunk   = nodes_merged["is_trunk_borderline"].sum()
    log.info(
        "Spine: %d total nodes | %d surface | %d freeway (excluded from candidates) | %d trunk-borderline",
        len(nodes_merged), n_surface, n_freeway, n_trunk,
    )
    log.info(
        "Buffer: %.2f m = %.4f US survey feet (EPSG:2230 linear unit)",
        cfg["geometry"]["buffer_m"], buf_ft,
    )

    out_path = proc / "nodes_spine_2230.parquet"
    nodes_merged.to_parquet(out_path, index=False)
    log.info("Wrote node spine (%d nodes) to %s", len(nodes_merged), out_path)
    return nodes_merged


def main() -> None:
    cfg = load_config()
    build_spine(cfg)


if __name__ == "__main__":
    main()
