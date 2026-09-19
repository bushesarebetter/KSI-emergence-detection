"""Join City of San Diego traffic counts to exported intersections.

The City publishes 24-hour segment counts (average daily traffic, ADT): a
location string naming the street and the two cross streets that bound the
counted segment ("El Cajon Blvd btwn 43rd St & Van Dyke Ave"), directional and
total counts, the count date, and the coordinates of the count site.

An intersection labelled "A & B" has traffic on A at B wherever a count on
street A names B as one of its limits, and the same for B at A. Where no count
names the cross street, the nearest count on the same street within
GEO_MAX_M of the intersection stands in; that is still the same road a block
away, which is a fair figure for a corner and is reported as such.

Entering volume, the denominator of an intersection crash rate, is what
arrives from every leg. A segment count is two-way, so half of it enters the
intersection at the segment's end; with a segment on each side along street A,
entering from A is (left + right) / 2, which for symmetric segments equals one
segment's count. This module therefore uses the most recent matched count per
street as that street's contribution and sums the streets. `complete` says
whether both streets matched, so the front end can label a one-street figure
as a floor.

Everything here is pure and unit-tested; scripts/join_traffic_counts.py does
the download and the file I/O.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, asdict

GEO_MAX_M = 250  # a count on the same street within this distance stands in for the corner

# The City abbreviates suffixes ("Bl", "Av", "Wy"); OSM spells them out. Both
# collapse to one canonical word so "El Cajon Bl" and "El Cajon Boulevard" agree.
_SUFFIX_CANON = {
    "boulevard": "boulevard", "blvd": "boulevard", "bl": "boulevard", "blv": "boulevard",
    "avenue": "avenue", "ave": "avenue", "av": "avenue",
    "street": "street", "st": "street",
    "drive": "drive", "dr": "drive",
    "road": "road", "rd": "road",
    "way": "way", "wy": "way",
    "lane": "lane", "ln": "lane",
    "court": "court", "ct": "court",
    "place": "place", "pl": "place",
    "parkway": "parkway", "pkwy": "parkway", "pky": "parkway", "pw": "parkway",
    "highway": "highway", "hwy": "highway", "hy": "highway",
    "terrace": "terrace", "ter": "terrace", "terr": "terrace",
    "circle": "circle", "cir": "circle",
    "trail": "trail", "trl": "trail", "tl": "trail",
    "freeway": "freeway", "fwy": "freeway",
    "expressway": "expressway", "expy": "expressway",
    "mount": "mount", "mt": "mount",
}
_DIRECTIONAL = {"north", "south", "east", "west", "n", "s", "e", "w", "ne", "nw", "se", "sw"}


def road_key(name: str) -> str:
    """Canonical key for a street name: lower case, directionals dropped,
    suffix abbreviations expanded, punctuation removed."""
    tokens = re.findall(r"[a-z0-9]+", (name or "").lower())
    tokens = [t for t in tokens if t not in _DIRECTIONAL]
    tokens = [_SUFFIX_CANON.get(t, t) for t in tokens]
    return " ".join(tokens)


def limits_keys(limits: str) -> list[str]:
    """The cross streets named in a segment's limits, as road keys.
    "30th St - Idaho St" -> ["30th street", "idaho street"]."""
    parts = re.split(r"\s+-\s+|\s+to\s+|\s*/\s*|\s*&\s*|\s+and\s+|\s*_\s*", limits or "", flags=re.I)
    return [road_key(p) for p in parts if p and p.strip()]


def parse_location(text: str) -> tuple[str, str] | None:
    """Split the City's location string into (street, limits).
    'El Cajon Blvd btwn 43rd St _ Van Dyke Ave' -> ('El Cajon Blvd', '43rd St & Van Dyke Ave')."""
    t = (text or "").strip()
    m = re.match(r"^(.*?)\s+(?:btwn|between|bet\.?|b/w)\s+(.*)$", t, flags=re.I)
    if m:
        limits = re.sub(r"\s*_\s*", " & ", m.group(2))
        return m.group(1).strip(), limits.strip()
    m = re.match(r"^(.*?)\s+(?:at|@)\s+(.*)$", t, flags=re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None


def year_of(date_text: str) -> int | None:
    m = re.search(r"(19|20)\d{2}", date_text or "")
    return int(m.group(0)) if m else None


def meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Equirectangular distance; exact enough at a few hundred metres."""
    k = math.cos(math.radians(lat1))
    return math.hypot((lon2 - lon1) * 111_320 * k, (lat2 - lat1) * 110_540)


@dataclass(frozen=True)
class Count:
    street: str
    limits: str
    total: int
    date: str  # as published; only the year is used for recency
    lat: float | None = None
    lng: float | None = None


@dataclass(frozen=True)
class Leg:
    street: str
    adt: int
    year: int | None
    limits: str
    method: str  # "limits": the count names this cross street; "nearby": same street within GEO_MAX_M


def index_counts(counts) -> dict[str, list[Count]]:
    idx: dict[str, list[Count]] = defaultdict(list)
    for c in counts:
        if c.total and c.total > 0:
            idx[road_key(c.street)].append(c)
    return idx


def split_label(name: str) -> list[str]:
    """"A & B" -> ["A", "B"]; a single-street label -> ["A"]."""
    return [s.strip() for s in (name or "").split(" & ") if s.strip()]


def legs_for(name: str, index: dict[str, list[Count]], lat: float | None = None,
             lon: float | None = None, max_m: float = GEO_MAX_M) -> list[Leg]:
    """One leg per street of the label. A count whose limits name the other
    street wins; failing that, the nearest count on the same street within
    `max_m`. Among several, the most recent wins, then the larger count."""
    streets = split_label(name)
    if len(streets) != 2:
        return []
    legs: list[Leg] = []
    for street, other in ((streets[0], streets[1]), (streets[1], streets[0])):
        same_street = index.get(road_key(street), [])
        ko = road_key(other)
        cands = [c for c in same_street if ko and ko in limits_keys(c.limits)]
        method = "limits"
        if not cands and lat is not None and lon is not None:
            near = [
                (meters(lat, lon, c.lat, c.lng), c)
                for c in same_street if c.lat is not None and c.lng is not None
            ]
            near = [(d, c) for d, c in near if d <= max_m]
            if near:
                cands = [min(near, key=lambda t: t[0])[1]]
                method = "nearby"
        if not cands:
            continue
        best = max(cands, key=lambda c: (year_of(c.date) or 0, c.total))
        legs.append(Leg(street=street, adt=int(best.total), year=year_of(best.date),
                        limits=best.limits, method=method))
    return legs


def site_record(name: str, index: dict[str, list[Count]], lat: float | None = None,
                lon: float | None = None, max_m: float = GEO_MAX_M) -> dict | None:
    """JSON-ready record for one intersection, or None when nothing matched."""
    legs = legs_for(name, index, lat, lon, max_m)
    if not legs:
        return None
    return {
        "legs": [asdict(l) for l in legs],
        "entering": sum(l.adt for l in legs),
        "complete": len(legs) == 2,
    }
