"""OSM drivable-graph ingest for the City of San Diego.

Fetches via OSMnx (network access required) and snapshots the GraphML.
If a cached GraphML already exists at the expected path it is reused.
"""
from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any

import networkx as nx

from src.utils import load_config, project_root, sha256_file, write_manifest

log = logging.getLogger(__name__)


def latest_snapshot(raw_osm: Path) -> Path | None:
    """Return the most-recently-dated OSM snapshot dir, or None."""
    dirs = sorted([d for d in raw_osm.iterdir() if d.is_dir()], reverse=True)
    for d in dirs:
        candidate = d / "sandiego_drive.graphml"
        if candidate.exists():
            return candidate
    return None


def fetch_or_load(cfg: dict[str, Any]) -> nx.MultiDiGraph:
    """Return the OSM drivable graph, fetching if not cached."""
    import osmnx as ox

    raw_osm = project_root() / cfg["paths"]["raw"] / "osm"
    today = datetime.date.today().strftime("%Y%m%d")
    snap_dir = raw_osm / today
    graphml_path = snap_dir / "sandiego_drive.graphml"

    cached = latest_snapshot(raw_osm)
    if cached is not None:
        log.info("Reusing cached OSM graph: %s", cached)
        G = ox.load_graphml(cached)
        return G

    log.info("Fetching OSM drivable graph for City of San Diego …")
    # Use city_boundary.geojson if present; otherwise query by name
    cpa_raw = project_root() / cfg["paths"]["raw"] / "cpa"
    boundary_candidates = sorted(cpa_raw.glob("*/city_boundary.geojson"), reverse=True)
    if boundary_candidates:
        import geopandas as gpd
        boundary_gdf = gpd.read_file(boundary_candidates[0])
        polygon = boundary_gdf.union_all() if hasattr(boundary_gdf, "union_all") else boundary_gdf.unary_union
        G = ox.graph_from_polygon(polygon, network_type="drive", simplify=True)
    else:
        G = ox.graph_from_place(
            "San Diego, California, USA",
            network_type="drive",
            simplify=True,
        )

    snap_dir.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(G, filepath=graphml_path)
    log.info("Saved OSM graph to %s", graphml_path)

    entries = [
        {
            "file": graphml_path.name,
            "source": "OpenStreetMap via OSMnx",
            "fetch_timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "node_count": len(G.nodes),
            "edge_count": len(G.edges),
            "sha256": sha256_file(graphml_path),
        }
    ]
    write_manifest(snap_dir, entries)
    return G
