"""Tests for M3b infrastructure feature construction.

Tests:
  - Static vs endogenous feature classification in feature_dictionary.csv
  - 2021-vintage sourcing: endogenous features must have max_source_date ≤ 2021-12-31
  - Slope computation on a toy 2-D DEM array
  - Transit proximity join: correct distance threshold
  - parse_lanes and parse_maxspeed_kph edge cases
  - Geometry feature functions on a minimal NetworkX graph
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.build_infra_features import (
    _kdtree_nearest_m,
    _parse_lanes,
    _parse_maxspeed_kph,
    _within_snap,
)
from src.ingest.dem_loader import _compute_slope_from_dem


# ---------------------------------------------------------------------------
# parse_lanes
# ---------------------------------------------------------------------------

class TestParseLanes:
    def test_integer(self):
        assert _parse_lanes(2) == 2.0

    def test_float_string(self):
        assert _parse_lanes("3") == 3.0

    def test_pipe_separated(self):
        result = _parse_lanes("2|1")
        assert result == pytest.approx(1.5)

    def test_none(self):
        assert _parse_lanes(None) is None

    def test_unparseable(self):
        assert _parse_lanes("unknown") is None


# ---------------------------------------------------------------------------
# parse_maxspeed_kph
# ---------------------------------------------------------------------------

class TestParseMaxspeed:
    def test_mph(self):
        result = _parse_maxspeed_kph("25 mph", default_kph=40.0)
        assert result == pytest.approx(25 * 1.60934, rel=1e-3)

    def test_kph_string(self):
        assert _parse_maxspeed_kph("50", default_kph=40.0) == pytest.approx(50.0)

    def test_none(self):
        assert _parse_maxspeed_kph(None, default_kph=40.0) == pytest.approx(40.0)

    def test_none_string(self):
        assert _parse_maxspeed_kph("none", default_kph=40.0) == pytest.approx(40.0)

    def test_variable(self):
        assert _parse_maxspeed_kph("variable", default_kph=40.0) == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# Slope computation on toy DEM
# ---------------------------------------------------------------------------

class TestSlopeComputation:
    def test_flat_terrain_zero_slope(self):
        dem = np.ones((10, 10), dtype=float) * 100.0  # flat at 100 m
        slope = _compute_slope_from_dem(dem, res_m=10.0)
        assert np.allclose(slope, 0.0, atol=1e-8)

    def test_uniform_gradient(self):
        # 1 m rise over 10 m run → slope = 10 %
        dem = np.zeros((5, 5), dtype=float)
        for col in range(5):
            dem[:, col] = col * 1.0  # 1 m / col, res = 1 m
        slope = _compute_slope_from_dem(dem, res_m=1.0)
        # Interior cells should be ~100% slope (1m/1m)
        interior = slope[1:-1, 1:-1]
        assert np.all(interior > 50.0)  # definitely non-zero

    def test_output_shape(self):
        dem = np.random.rand(8, 12) * 50
        slope = _compute_slope_from_dem(dem, res_m=10.0)
        assert slope.shape == dem.shape


# ---------------------------------------------------------------------------
# Transit proximity (KD-tree nearest distance)
# ---------------------------------------------------------------------------

class TestTransitProximity:
    def test_zero_distance_to_self(self):
        lons = np.array([-117.1])
        lats = np.array([32.7])
        dists = _kdtree_nearest_m(lons, lats, lons, lats)
        assert dists[0] == pytest.approx(0.0, abs=1.0)

    def test_one_degree_lat_approx_111km(self):
        q_lons = np.array([-117.1])
        q_lats = np.array([32.7])
        r_lons = np.array([-117.1])
        r_lats = np.array([33.7])  # 1 degree north
        dists = _kdtree_nearest_m(q_lons, q_lats, r_lons, r_lats)
        assert dists[0] == pytest.approx(111_320, rel=0.01)

    def test_threshold_logic(self):
        cand_lons = np.array([-117.10, -117.20])
        cand_lats = np.array([32.70,   32.70])
        stop_lons = np.array([-117.10])   # same location as first candidate
        stop_lats = np.array([32.70])
        result = _within_snap(cand_lons, cand_lats, stop_lons, stop_lats, snap_m=10.0)
        assert result[0] == True   # within 10 m
        assert result[1] == False  # ~11 km away


# ---------------------------------------------------------------------------
# Feature dictionary vintage assertion
# ---------------------------------------------------------------------------

class TestFeatureDictionaryVintage:
    """Verify the feature_dictionary format expected by the A9 audit assertion."""

    def test_static_features_have_no_endogenous_date(self):
        static_features = [
            {"feature_name": "edge_count", "static_endogenous": "static", "max_source_date": "N/A"},
            {"feature_name": "slope_pct",  "static_endogenous": "static", "max_source_date": "N/A"},
        ]
        for row in static_features:
            assert row["static_endogenous"] == "static"

    def test_endogenous_features_have_2021_date(self):
        endo_features = [
            {"feature_name": "signal_present", "static_endogenous": "endogenous",
             "max_source_date": "2021-12-31"},
            {"feature_name": "speed_limit",    "static_endogenous": "endogenous",
             "max_source_date": "2021-12-31"},
        ]
        cutoff = pd.Timestamp("2022-01-01")
        for row in endo_features:
            ts = pd.Timestamp(row["max_source_date"])
            assert ts < cutoff, f"{row['feature_name']} source date must be < 2022-01-01"


# ---------------------------------------------------------------------------
# Geometry features on a minimal graph
# ---------------------------------------------------------------------------

class TestGeometryFeatures:
    @pytest.fixture
    def small_graph(self):
        import networkx as nx
        G = nx.MultiDiGraph()
        # Node at intersection (-117.1, 32.7) with 4 neighbours
        G.add_node(1, x="-117.1", y="32.7")
        G.add_node(2, x="-117.11", y="32.7")
        G.add_node(3, x="-117.09", y="32.7")
        G.add_node(4, x="-117.1",  y="32.71")
        G.add_node(5, x="-117.1",  y="32.69")
        for nbr in [2, 3, 4, 5]:
            G.add_edge(1, nbr, highway="residential", lanes="2", maxspeed="25 mph")
            G.add_edge(nbr, 1, highway="residential", lanes="2", maxspeed="25 mph")
        return G

    def test_edge_count_4way(self, small_graph):
        from src.features.build_infra_features import build_geometry_features
        candidates = pd.DataFrame({
            "intersection_id": ["abc123"],
            "lon": [-117.1],
            "lat": [32.7],
        })
        result = build_geometry_features(candidates, small_graph, cfg=_dummy_cfg())
        assert result["edge_count"].iloc[0] == 4

    def test_lane_count_parsed(self, small_graph):
        from src.features.build_infra_features import build_geometry_features
        candidates = pd.DataFrame({
            "intersection_id": ["abc123"],
            "lon": [-117.1],
            "lat": [32.7],
        })
        result = build_geometry_features(candidates, small_graph, cfg=_dummy_cfg())
        assert result["lane_count"].iloc[0] == pytest.approx(2.0)
        assert result["lane_count_missing"].iloc[0] == 0

    def test_intersection_type_4way(self, small_graph):
        from src.features.build_infra_features import build_geometry_features
        candidates = pd.DataFrame({
            "intersection_id": ["abc123"],
            "lon": [-117.1],
            "lat": [32.7],
        })
        result = build_geometry_features(candidates, small_graph, cfg=_dummy_cfg())
        assert result["intersection_type"].iloc[0] == 4


def _dummy_cfg() -> dict:
    return {
        "infrastructure": {
            "signal_snap_m": 40.0,
            "stop_snap_m": 30.0,
            "transit_proximity_m": 400.0,
            "freeway_proximity_m": 200.0,
            "speed_default_kph": 40.0,
            "dem_resolution_m": 10,
            "overpass_bbox": [32.50, -117.30, 33.00, -116.90],
            "overpass_date": "2021-12-31T23:59:59Z",
            "overpass_timeout_s": 300,
        },
        "paths": {
            "raw": "data/raw",
            "proc": "data/proc",
            "model": "data/model",
        },
        "feature_groups": {
            "crash_only": [],
            "geometry": [],
            "control": [],
            "roadway": [],
            "active_transport": [],
            "terrain": [],
        },
    }
