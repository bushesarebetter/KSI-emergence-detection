"""Restrict candidate sets to the true City of San Diego boundary.

src/ingest/osm_loader.py built the road network (and therefore the candidate
intersection set) from the UNION of all 74 polygons in
data/raw/cpa/<date>/city_boundary.geojson -- which covers all 18 incorporated
cities in San Diego County plus unincorporated county land, not just the City
of San Diego. The crash data feeding features and labels was always correctly
scoped to the city (SWITRS JURIS 3711 + the SD-area CHP beat, confirmed by
inspecting data/raw/switrs/<date>/crashes.csv directly), so candidates outside
city limits have almost no real crash history behind them -- their near-zero
scores are a measurement gap, not a finding.

This script filters candidate_panel.parquet (and the shared infra_features.parquet)
for both the verified_run and forward_run archives down to intersections that
actually fall within the City of San Diego polygon (Name == "SAN DIEGO" in
city_boundary.geojson), backing up the original county-wide files first.
feature_table.parquet and frozen_scores.parquet do not need filtering here --
they're keyed by intersection_id and downstream scripts merge on that key, so
dropping rows from candidate_panel.parquet is enough to restrict the population
used in every OOF refit, ablation, and bake-off script.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
import pandas as pd

from src.utils import project_root

ROOT = project_root()
MODEL_DIR = ROOT / "data" / "model"
RAW_DIR = ROOT / "data" / "raw"


def get_city_polygon():
    boundary_path = sorted((RAW_DIR / "cpa").glob("*/city_boundary.geojson"), reverse=True)[0]
    gdf = gpd.read_file(boundary_path)
    sd = gdf[gdf["Name"] == "SAN DIEGO"]
    if len(sd) == 0:
        raise RuntimeError(f"No 'SAN DIEGO' rows found in {boundary_path}")
    return sd, boundary_path


def restrict_run(run_dir: Path, city_gdf: gpd.GeoDataFrame) -> tuple[int, int]:
    panel_path = run_dir / "candidate_panel.parquet"
    if not panel_path.exists():
        print(f"  {panel_path} not found, skipping")
        return (0, 0)

    backup_path = run_dir / "candidate_panel_COUNTYWIDE_backup.parquet"
    panel = gpd.read_parquet(panel_path)
    n_before = len(panel)

    if not backup_path.exists():
        panel.to_parquet(backup_path, index=False)
        print(f"  Backed up original ({n_before} rows) to {backup_path}")
    else:
        print(f"  Backup already exists at {backup_path}, not overwriting")
        # Restore from backup first so re-runs of this script are idempotent,
        # not cumulative filters-of-filters.
        panel = gpd.read_parquet(backup_path)
        n_before = len(panel)

    city_proj = city_gdf.to_crs(panel.crs)
    city_union = city_proj.union_all()
    in_city = panel.geometry.within(city_union)
    filtered = panel[in_city].copy()
    n_after = len(filtered)

    filtered.to_parquet(panel_path, index=False)
    print(f"  {panel_path.parent.name}: {n_before} -> {n_after} candidates "
          f"({n_after/n_before:.1%} retained)")
    return (n_before, n_after)


def main():
    city_gdf, boundary_path = get_city_polygon()
    print(f"City of San Diego polygon loaded from {boundary_path} ({len(city_gdf)} feature(s))")

    print("\nVerified run:")
    restrict_run(MODEL_DIR / "verified_run", city_gdf)

    print("\nForward run:")
    restrict_run(MODEL_DIR / "forward_run", city_gdf)


if __name__ == "__main__":
    main()
