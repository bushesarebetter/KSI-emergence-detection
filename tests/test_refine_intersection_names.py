"""Unit tests for the offline parts of scripts/refine_intersection_names.py:
graph construction from an Overpass response, point matching, the
same-road guard and spelling-variant collapse. No network."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location(
        "refine_intersection_names", ROOT / "scripts" / "refine_intersection_names.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# A T-junction at (32.75, -117.10): Park Boulevard runs north-south through
# node 1 (south), 2 (the junction) and 3 (north); an unnamed tertiary_link
# comes in from the east via node 4. Node 5 is a stray node 40 m away.
LAT, LON = 32.75, -117.10
DLAT = 0.00045  # ~50 m
DLON = 0.00053  # ~50 m at this latitude

ELEMENTS = [
    {"type": "way", "id": 10, "nodes": [1, 2, 3], "tags": {"highway": "primary", "name": "Park Boulevard"}},
    {"type": "way", "id": 11, "nodes": [2, 4], "tags": {"highway": "tertiary_link"}},
    {"type": "node", "id": 1, "lat": LAT - DLAT, "lon": LON},
    {"type": "node", "id": 2, "lat": LAT, "lon": LON},
    {"type": "node", "id": 3, "lat": LAT + DLAT, "lon": LON},
    {"type": "node", "id": 4, "lat": LAT, "lon": LON + DLON},
    {"type": "node", "id": 5, "lat": LAT + DLAT * 0.8, "lon": LON + DLON * 0.8},
]


def _graph_and_index(mod, elements=ELEMENTS):
    from src.gis.intersection_names import build_name_index
    G = mod.graph_from_elements(elements)
    idx = {n: mod.collapse_variants(names) for n, names in build_name_index(G).items()}
    return G, idx


def test_graph_carries_tags_both_directions(mod):
    G, _ = _graph_and_index(mod)
    assert G.number_of_nodes() == 5
    assert G.has_edge(1, 2) and G.has_edge(2, 1)
    assert G.edges[1, 2, 0]["name"] == "Park Boulevard"
    assert G.edges[2, 4, 0]["highway"] == "tertiary_link"
    assert "name" not in G.edges[2, 4, 0]


def test_unnamed_cross_road_is_described(mod):
    G, idx = _graph_and_index(mod)
    rec = mod.relabel_point(LAT, LON, G, idx)
    assert rec["status"] == "ok"
    assert rec["label"] == "Park Boulevard & connector road"
    assert rec["method"] == "unnamed_cross"


def test_point_far_from_any_node_is_no_match(mod):
    G, idx = _graph_and_index(mod)
    rec = mod.relabel_point(LAT + DLAT * 0.5, LON - DLON * 0.5, G, idx)
    assert rec["status"] == "no_match"
    assert rec["nearest_m"] > mod.MATCH_MAX_M


def test_empty_response_is_no_roads(mod):
    G, idx = _graph_and_index(mod, elements=[])
    assert mod.relabel_point(LAT, LON, G, idx) == {"status": "no_roads"}


def test_spelling_variants_collapse_to_one_road(mod):
    # Two adjacent ways, one spelled "Genesee Ave", meet an "Avenue"-spelled one.
    elements = [
        {"type": "way", "id": 20, "nodes": [1, 2], "tags": {"highway": "primary", "name": "Genesee Ave"}},
        {"type": "way", "id": 21, "nodes": [2, 3], "tags": {"highway": "primary", "name": "Genesee Avenue"}},
        {"type": "way", "id": 22, "nodes": [2, 4], "tags": {"highway": "residential", "name": "Nobel Drive"}},
        {"type": "node", "id": 1, "lat": LAT - DLAT, "lon": LON},
        {"type": "node", "id": 2, "lat": LAT, "lon": LON},
        {"type": "node", "id": 3, "lat": LAT + DLAT, "lon": LON},
        {"type": "node", "id": 4, "lat": LAT, "lon": LON + DLON},
    ]
    G, idx = _graph_and_index(mod, elements)
    rec = mod.relabel_point(LAT, LON, G, idx)
    assert rec["label"] == "Genesee Avenue & Nobel Drive"


@pytest.mark.parametrize("original, live, expected", [
    ("Broadway", "East Broadway", True),
    ("Torrey Pines Road", "N Torrey Pines Rd", True),
    ("Park Boulevard", "Park Blvd", True),
    ("Park Boulevard", "Upas Street", False),
    ("", "Park Boulevard", False),
])
def test_same_road(mod, original, live, expected):
    assert mod.same_road(original, live) is expected


def test_query_mirrors_drive_filter_and_lists_every_point(mod):
    q = mod.overpass_query([(LAT, LON), (LAT + 1, LON + 1)])
    assert q.count("way(around:") == 2
    assert 'highway!~"^(' in q and "footway" in q and "service" in q
    assert q.endswith("out body;>;out skel qt;")
