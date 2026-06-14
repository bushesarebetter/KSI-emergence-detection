"""Ingest orchestration: fetch OSM graph + load crash data.

Run via:  python -m src.ingest.run
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path

from src.ingest.crash_loader import load_crashes
from src.ingest.osm_loader import fetch_or_load
from src.utils import load_config, project_root

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    cfg = load_config()
    proc = project_root() / cfg["paths"]["proc"]
    proc.mkdir(parents=True, exist_ok=True)

    # 1. OSM graph
    log.info("=== Step 1: OSM graph ===")
    G = fetch_or_load(cfg)
    log.info("OSM graph: %d nodes, %d edges", len(G.nodes), len(G.edges))

    # Persist graph for downstream spine builder
    graph_cache = proc / "osm_graph.pkl"
    with open(graph_cache, "wb") as f:
        pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)
    log.info("Cached graph to %s", graph_cache)

    # 2. Crash data
    log.info("=== Step 2: Crash data ===")
    crashes_gdf, source = load_crashes(cfg)
    log.info("Crash records loaded: %d  (source=%s)", len(crashes_gdf), source)

    crashes_path = proc / "crashes_4326.parquet"
    crashes_gdf.to_parquet(crashes_path, index=False)
    log.info("Wrote crashes to %s", crashes_path)


if __name__ == "__main__":
    main()
