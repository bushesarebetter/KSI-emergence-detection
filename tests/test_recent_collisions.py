"""Unit tests for src/recent/collisions.py. No network."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.recent.collisions import aggregate, parse_rows, site_key  # noqa: E402


def row(date, road, sfx, cross="", csfx="", injured="0", killed="0", pd=""):
    return {
        "REPORT_ID": "1", "DATE_TIME": f"{date} 12:00:00.000",
        "ADDRESS_PD_PRIMARY": pd, "ADDRESS_ROAD_PRIMARY": road, "ADDRESS_SFX_PRIMARY": sfx,
        "ADDRESS_PD_INTERSECTING": "", "ADDRESS_NAME_INTERSECTING": cross, "ADDRESS_SFX_INTERSECTING": csfx,
        "INJURED": injured, "KILLED": killed,
    }


ROWS = [
    row("2025-03-04", "EL CAJON", "BOULEVARD", "43RD", "STREET", injured="1"),
    row("2025-09-10", "43RD", "STREET", "EL CAJON", "BOULEVARD", injured="2", killed="1"),  # same corner, reversed
    row("2024-12-31", "EL CAJON", "BOULEVARD", "43RD", "STREET"),                            # before the cutoff
    row("2025-05-05", "36TH", "STREET"),                                                     # mid-block, no cross street
    row("2026-01-15", "GENESEE", "AVENUE", "NOBEL", "DRIVE", pd="N"),
    row("2025-07-07", "BROADWAY", "", "BROADWAY", ""),                                       # same street both sides
]


def test_parse_rows_keeps_only_intersection_reports_since_the_cutoff():
    cs = parse_rows(ROWS, since="2025-01-01")
    assert len(cs) == 3
    assert all(c.date >= "2025-01-01" for c in cs)
    assert cs[0].streets == frozenset({"el cajon boulevard", "43rd street"})
    assert cs[0].streets == cs[1].streets  # order of the two streets does not matter


def test_parse_rows_is_case_insensitive_about_headers():
    lower = [{k.lower(): v for k, v in ROWS[0].items()}]
    assert len(parse_rows(lower)) == 1


def test_aggregate_sums_and_keeps_the_latest_date():
    agg = aggregate(parse_rows(ROWS))
    corner = agg[frozenset({"el cajon boulevard", "43rd street"})]
    assert corner == {"count": 2, "injured": 3, "killed": 1, "last": "2025-09-10"}
    assert agg[frozenset({"genesee avenue", "nobel drive"})]["count"] == 1


def test_site_key_matches_the_export_label_style():
    assert site_key("43rd Street & El Cajon Boulevard") == frozenset({"el cajon boulevard", "43rd street"})
    assert site_key("North Torrey Pines Road & Genesee Avenue") == frozenset({"torrey pines road", "genesee avenue"})
    assert site_key("Park Boulevard") is None
    # A descriptor is not a street the police could have written; it still yields
    # a key, and simply never matches a report.
    assert site_key("Park Boulevard & connector road") == frozenset({"park boulevard", "connector road"})
