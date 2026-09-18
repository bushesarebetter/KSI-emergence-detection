"""Labelling rules for intersections, on small hand-built graphs.

The one property that matters most is backward compatibility: every label that
already had two street names must come out identical, or ~980 deployed labels
would churn for no reason. The rest pins down the new behaviour for unnamed
cross roads and the deliberate refusal to borrow a name from a neighbouring node.
"""
from __future__ import annotations

import networkx as nx
import pytest

from src.gis.intersection_names import (
    build_generic_tokens,
    build_name_index,
    cross_road_descriptor,
    describe_unnamed_road,
    label_for_nodes,
)


def _graph(edges):
    """MultiDiGraph from (u, v, attrs) triples, mirroring OSMnx's structure."""
    G = nx.MultiDiGraph()
    for u, v, attrs in edges:
        G.add_edge(u, v, **attrs)
    return G


def _label(G, nodes, generic=frozenset(), fallback="FALLBACK"):
    return label_for_nodes(G, nodes, build_name_index(G), set(generic), fallback)


# ── unchanged behaviour ─────────────────────────────────────────────────────────

def test_two_named_roads_give_the_classic_label():
    G = _graph([
        (1, 0, {"name": "El Cajon Boulevard", "highway": "primary"}),
        (0, 2, {"name": "El Cajon Boulevard", "highway": "primary"}),
        (3, 0, {"name": "43rd Street", "highway": "residential"}),
        (0, 4, {"name": "43rd Street", "highway": "residential"}),
    ])
    assert _label(G, [0]) == ("43rd Street & El Cajon Boulevard", "cross")


def test_longest_two_names_win_then_alphabetical():
    """Three named roads: keep the two longest (the original rule), A-Z order."""
    G = _graph([
        (1, 0, {"name": "Broadway"}),
        (2, 0, {"name": "Park Boulevard"}),
        (3, 0, {"name": "University Avenue"}),
    ])
    label, method = _label(G, [0])
    assert label == "Park Boulevard & University Avenue"
    assert method == "cross"


def test_merged_way_name_variants_count_as_one_road():
    """OSMnx gives a merged way a LIST of name variants. The original builder
    treated each as a separate street and could emit "Genesee Ave & Genesee
    Avenue" -- a road intersecting itself -- instead of the real cross street."""
    G = _graph([
        (1, 0, {"name": ["Genesee Avenue", "Genesee Ave"], "highway": "primary"}),
        (2, 0, {"name": "Nobel Drive", "highway": "secondary"}),
    ])
    assert _label(G, [0]) == ("Genesee Avenue & Nobel Drive", "cross")


def test_variants_alone_do_not_fake_a_cross_street():
    """One road with two spellings and an unnamed side street is still one
    named road: the descriptor, not the variant, fills the second slot."""
    G = _graph([
        (1, 0, {"name": ["Genesee Avenue", "Genesee Ave"], "highway": "primary"}),
        (0, 2, {"name": "Genesee Avenue", "highway": "primary"}),
        (3, 0, {"highway": "residential"}),
    ])
    assert _label(G, [0]) == ("Genesee Avenue & unnamed street", "unnamed_cross")


def test_tie_break_is_deterministic():
    """Equal-length names must not depend on set iteration order."""
    G = _graph([
        (1, 0, {"name": "Zebra Way"}),   # 9 chars
        (2, 0, {"name": "Apple Way"}),   # 9 chars
        (3, 0, {"name": "Mango Way"}),   # 9 chars
    ])
    for _ in range(20):
        assert _label(G, [0])[0] == "Apple Way & Mango Way"


def test_merged_member_nodes_pool_their_names():
    """A dual carriageway: each carriageway node sees one road; together, two."""
    G = _graph([
        (1, 10, {"name": "Mission Bay Drive"}),
        (2, 11, {"name": "Grand Avenue"}),
    ])
    assert _label(G, [10, 11])[0] == "Grand Avenue & Mission Bay Drive"


def test_generic_tokens_are_ignored():
    G = _graph([(1, 0, {"name": "Unnamed Road"}), (2, 0, {"name": "Broadway"})])
    label, method = _label(G, [0], generic={"Unnamed Road"})
    assert label == "Broadway"
    assert method == "single"


def test_no_names_at_all_uses_fallback():
    G = _graph([(1, 0, {"highway": "residential"}), (2, 0, {"highway": "residential"})])
    label, method = _label(G, [0])
    assert label == "FALLBACK" and method == "fallback"


# ── new behaviour: unnamed cross roads ──────────────────────────────────────────

def test_unnamed_alley_is_described_not_dropped():
    G = _graph([
        (1, 0, {"name": "Park Boulevard", "highway": "primary"}),
        (0, 2, {"name": "Park Boulevard", "highway": "primary"}),
        (3, 0, {"highway": "service", "service": "alley"}),
    ])
    assert _label(G, [0]) == ("Park Boulevard & alley", "unnamed_cross")


def test_unnamed_residential_street_is_described():
    G = _graph([
        (1, 0, {"name": "49th Street", "highway": "residential"}),
        (0, 2, {"highway": "residential"}),
    ])
    assert _label(G, [0])[0] == "49th Street & unnamed street"


def test_service_road_without_service_tag():
    G = _graph([
        (1, 0, {"name": "Sunset Cliffs Boulevard", "highway": "secondary"}),
        (2, 0, {"highway": "service"}),
    ])
    assert _label(G, [0])[0] == "Sunset Cliffs Boulevard & service road"


def test_most_common_unnamed_kind_wins():
    G = _graph([
        (1, 0, {"name": "Broadway", "highway": "primary"}),
        (2, 0, {"highway": "service", "service": "driveway"}),
        (3, 0, {"highway": "service", "service": "parking_aisle"}),
        (4, 0, {"highway": "service", "service": "parking_aisle"}),
    ])
    assert _label(G, [0])[0] == "Broadway & parking aisle"


def test_one_named_road_and_nothing_else_stays_single():
    """A bend or end node: no cross road at all -> keep the plain name, and say
    so via the method, rather than pretending."""
    G = _graph([
        (1, 0, {"name": "Torrey Pines Road"}),
        (0, 2, {"name": "Torrey Pines Road"}),
    ])
    assert _label(G, [0]) == ("Torrey Pines Road", "single")


def test_never_borrows_a_name_from_a_neighbouring_node():
    """Node 0 is Park Blvd & alley. One block along the alley (node 3) is Upas
    Street. Labelling node 0 "Park Boulevard & Upas Street" would name a
    different intersection; the descriptor must win."""
    G = _graph([
        (1, 0, {"name": "Park Boulevard", "highway": "primary"}),
        (0, 2, {"name": "Park Boulevard", "highway": "primary"}),
        (0, 3, {"highway": "service", "service": "alley"}),
        (3, 4, {"name": "Upas Street", "highway": "residential"}),
    ])
    label, _ = _label(G, [0])
    assert label == "Park Boulevard & alley"
    assert "Upas" not in label


def test_descriptor_helpers():
    assert describe_unnamed_road({"highway": "service", "service": "alley"}) == "alley"
    assert describe_unnamed_road({"highway": "service"}) == "service road"
    assert describe_unnamed_road({"highway": "residential"}) == "unnamed street"
    assert describe_unnamed_road({"highway": ["tertiary", "residential"]}) == "unnamed road"
    assert describe_unnamed_road({"highway": "motorway_link"}) == "ramp"
    assert describe_unnamed_road({}) is None


def test_cross_descriptor_ignores_named_edges():
    G = _graph([
        (1, 0, {"name": "Broadway", "highway": "primary"}),
        (2, 0, {"name": "Broadway", "highway": "primary"}),
    ])
    assert cross_road_descriptor(G, [0], set()) is None


def test_generic_token_threshold():
    idx = {i: {"Common"} for i in range(5)} | {99: {"Rare"}}
    assert build_generic_tokens(idx, threshold=3) == {"Common"}
    assert build_generic_tokens(idx, threshold=10) == set()


@pytest.mark.parametrize("directed", [True, False])
def test_works_on_directed_and_undirected_graphs(directed):
    G = nx.MultiDiGraph() if directed else nx.MultiGraph()
    G.add_edge(1, 0, name="A Street")
    G.add_edge(0, 2, name="B Avenue")
    assert _label(G, [0])[0] == "A Street & B Avenue"
