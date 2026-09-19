"""Join San Diego Police collision reports to exported intersections.

The model learns from SWITRS, which lags about a year. The City publishes
police collision reports within weeks (data.sandiego.gov, "Traffic
Collisions"), with the primary street and, when the crash was at an
intersection, the cross street in their own columns. That lets each corner on
the map say how many crashes the police have logged there since the model's
cutoff, which is the reader's first question: is it still happening?

Matching is by the pair of street names, normalised with the same rules as
the traffic-count join (src/traffic/counts.road_key), unordered, so
"EL CAJON BOULEVARD at 43RD STREET" and "43rd Street & El Cajon Boulevard"
agree. Mid-block reports (no cross street) are not intersection crashes and
are skipped. Everything here is pure; scripts/join_recent_collisions.py does
the download and file I/O.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.traffic.counts import road_key, split_label

DEFAULT_SINCE = "2025-01-01"  # the model's training cutoff


@dataclass(frozen=True)
class Collision:
    date: str             # YYYY-MM-DD
    streets: frozenset    # two road keys
    injured: int
    killed: int


def _get(row: dict, key: str) -> str:
    """Column lookup tolerant of the file's upper-case headers."""
    for k in (key, key.upper(), key.lower()):
        if k in row and row[k] is not None:
            return str(row[k]).strip()
    return ""


def _int(text: str) -> int:
    try:
        return int(float(text or 0))
    except ValueError:
        return 0


def street_name(road: str, suffix: str) -> str:
    return f"{road} {suffix}".strip()


def parse_rows(rows, since: str = DEFAULT_SINCE) -> list[Collision]:
    """Intersection collisions on or after `since`, as Collision records."""
    out: list[Collision] = []
    for r in rows:
        cross = _get(r, "address_name_intersecting")
        if not cross:
            continue
        date = _get(r, "date_time")[:10]
        if len(date) < 10 or date < since:
            continue
        a = road_key(street_name(_get(r, "address_road_primary"), _get(r, "address_sfx_primary")))
        b = road_key(street_name(cross, _get(r, "address_sfx_intersecting")))
        if not a or not b or a == b:
            continue
        out.append(Collision(date, frozenset((a, b)), _int(_get(r, "injured")), _int(_get(r, "killed"))))
    return out


def aggregate(collisions) -> dict[frozenset, dict]:
    """Per intersection: count, people injured, people killed, latest date."""
    agg: dict[frozenset, dict] = {}
    for c in collisions:
        d = agg.setdefault(c.streets, {"count": 0, "injured": 0, "killed": 0, "last": ""})
        d["count"] += 1
        d["injured"] += c.injured
        d["killed"] += c.killed
        if c.date > d["last"]:
            d["last"] = c.date
    return agg


def site_key(name: str) -> frozenset | None:
    """The unordered pair of road keys for an "A & B" label, or None for a
    single-street or descriptor label ("Park Boulevard & connector road" has
    no second street the police could have written)."""
    parts = split_label(name)
    if len(parts) != 2:
        return None
    a, b = road_key(parts[0]), road_key(parts[1])
    if not a or not b or a == b:
        return None
    return frozenset((a, b))
