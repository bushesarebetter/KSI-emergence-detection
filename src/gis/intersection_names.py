"""Human-readable intersection labels from an OSMnx road graph.

An intersection is labelled by the streets that meet at it: "43rd Street & El
Cajon Boulevard". The original builder only read `name` off the edges incident
to the node, so wherever the cross road has no name in OpenStreetMap -- an
unnamed residential connector, an unclassified road -- it fell back to the one
name it had and produced "Park Boulevard", which reads as a street, not an
intersection. About 8% of the dashboard's entries looked like that.

The fix is deliberately NOT to borrow a name from a neighbouring node. A node
one block along Park Boulevard would yield "Park Boulevard & Upas Street", which
is a different intersection -- a wrong label is worse than a plain one. Instead,
when the cross road is unnamed, describe what it is from its OSM tags:

    Park Boulevard & unnamed street
    Sunset Cliffs Boulevard & service road
    Torrey Pines Road & ramp

That is exactly as much as the data supports, and it still reads as a place
where two things meet.

A second defect fixed here: when OSMnx merges ways, an edge's `name` is a LIST
of spelling variants (["Genesee Avenue", "Genesee Ave"]). The original code
treated every variant as a separate street, so "longest two" could pick both
variants of one road and emit "Genesee Ave & Genesee Avenue". Each edge now
contributes a single name -- its longest variant.

Labelling rules:
  1. two or more named roads meet  -> "A & B" (longest two, then alphabetical)
  2. one named road + unnamed road -> "A & <descriptor of the unnamed road>"
  3. one named road, nothing else  -> "A"
  4. no names at all               -> caller-supplied fallback
Rule 1 is the original rule with a deterministic tie-break, so every label that
already had two distinct street names comes out the same.
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable

# A street name that appears on more nodes than this is not a street, it is a
# generic token ("Unnamed Road" style artefacts) and is ignored.
GENERIC_TOKEN_THRESHOLD = 40_000

# OSM `highway` -> how to describe an unnamed road of that type.
HIGHWAY_DESCRIPTOR = {
    "service": "service road",
    "residential": "unnamed street",
    "living_street": "unnamed street",
    "unclassified": "unnamed road",
    "tertiary": "unnamed road",
    "secondary": "unnamed road",
    "primary": "unnamed road",
    "tertiary_link": "connector road",
    "secondary_link": "connector road",
    "primary_link": "connector road",
    "trunk_link": "ramp",
    "motorway_link": "ramp",
    "track": "track",
    "path": "path",
    "footway": "footpath",
    "cycleway": "bike path",
    "pedestrian": "pedestrian way",
}

# OSM `service=*` refines highway=service, and is more informative when present.
SERVICE_DESCRIPTOR = {
    "alley": "alley",
    "driveway": "driveway",
    "parking_aisle": "parking aisle",
    "drive-through": "drive-through",
    "emergency_access": "emergency access road",
}


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [v for v in value if v is not None]
    return [value]


def clean_names(raw) -> list[str]:
    """OSMnx stores `name` as a str, or a list of variants when ways were merged."""
    return [s.strip() for s in _as_list(raw) if isinstance(s, str) and s.strip()]


def canonical_name(raw) -> str | None:
    """One name per edge. The variants in a merged-way list are spellings of the
    same road, so the longest (usually the unabbreviated one) represents it."""
    names = clean_names(raw)
    if not names:
        return None
    return max(names, key=lambda s: (len(s), s))


def incident_edge_data(G, node) -> list[dict]:
    """Attribute dicts of every edge touching `node`, both directions."""
    if G.is_directed():
        return [d for _, _, d in G.out_edges(node, data=True)] + [
            d for _, _, d in G.in_edges(node, data=True)
        ]
    return [d for _, _, d in G.edges(node, data=True)]


def edge_names(G, node) -> set[str]:
    names: set[str] = set()
    for d in incident_edge_data(G, node):
        name = canonical_name(d.get("name"))
        if name:
            names.add(name)
    return names


def build_name_index(G) -> dict:
    return {n: edge_names(G, n) for n in G.nodes()}


def build_generic_tokens(name_index: dict, threshold: int = GENERIC_TOKEN_THRESHOLD) -> set[str]:
    freq: Counter = Counter()
    for names in name_index.values():
        freq.update(names)
    return {name for name, count in freq.items() if count > threshold}


def describe_unnamed_road(edge: dict) -> str | None:
    """A short noun phrase for an unnamed edge, from its OSM tags."""
    service = _as_list(edge.get("service"))
    if service and service[0] in SERVICE_DESCRIPTOR:
        return SERVICE_DESCRIPTOR[service[0]]
    highway = _as_list(edge.get("highway"))
    if not highway:
        return None
    return HIGHWAY_DESCRIPTOR.get(highway[0], "unnamed road")


def cross_road_descriptor(G, node_ids: Iterable, generic: set[str]) -> str | None:
    """Describe the unnamed road(s) meeting at these nodes, or None if there are
    none. Called only when exactly one named road was found, so every unnamed
    incident edge is a cross road by definition."""
    kinds: Counter = Counter()
    for n in node_ids:
        for d in incident_edge_data(G, n):
            name = canonical_name(d.get("name"))
            if name and name not in generic:
                continue  # a named road; not what we are describing
            desc = describe_unnamed_road(d)
            if desc:
                kinds[desc] += 1
    if not kinds:
        return None
    return kinds.most_common(1)[0][0]


def label_for_nodes(G, node_ids: Iterable, name_index: dict, generic: set[str],
                    fallback: str) -> tuple[str, str]:
    """Label one intersection (possibly several merged OSM nodes).

    Returns (label, method) where method is one of
    "cross", "unnamed_cross", "single", "fallback" -- reported by the builder so
    the share of each is visible after a run.
    """
    node_ids = list(node_ids)
    all_names: set[str] = set()
    for n in node_ids:
        all_names |= name_index.get(n, set())

    # Longest two first (the original rule), with an alphabetical tie-break so
    # the result never depends on set iteration order.
    named = sorted((n for n in all_names if n not in generic), key=lambda s: (-len(s), s))
    if len(named) >= 2:
        return " & ".join(sorted(named[:2])), "cross"

    if len(named) == 1:
        primary = named[0]
        desc = cross_road_descriptor(G, node_ids, generic)
        if desc:
            return f"{primary} & {desc}", "unnamed_cross"
        return primary, "single"

    return fallback, "fallback"
