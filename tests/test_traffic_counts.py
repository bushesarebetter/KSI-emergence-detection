"""Unit tests for src/traffic/counts.py: name normalisation, location parsing
and the intersection join. No network."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.traffic.counts import (  # noqa: E402
    Count, index_counts, legs_for, limits_keys, parse_location, road_key,
    site_record, split_label, year_of,
)


@pytest.mark.parametrize("a, b", [
    ("El Cajon Boulevard", "El Cajon Bl"),
    ("El Cajon Boulevard", "El Cajon Blvd"),
    ("43rd Street", "43rd St"),
    ("West Point Loma Boulevard", "Point Loma Blvd"),
    ("Genesee Avenue", "Genesee Av"),
    ("Camino del Rio North", "Camino Del Rio N"),
    ("Sports Arena Boulevard", "SPORTS ARENA BL"),
])
def test_road_key_matches_city_spelling(a, b):
    assert road_key(a) == road_key(b)


def test_road_key_keeps_distinct_streets_distinct():
    assert road_key("30th Street") != road_key("30th Avenue")
    assert road_key("El Cajon Boulevard") != road_key("Cajon Street")


def test_limits_keys_splits_on_every_separator_the_city_uses():
    assert limits_keys("30th St - Idaho St") == ["30th street", "idaho street"]
    assert limits_keys("Euclid Av to 54th St") == ["euclid avenue", "54th street"]
    assert limits_keys("43rd St & Van Dyke Ave") == ["43rd street", "van dyke avenue"]
    assert limits_keys("43rd St _ Van Dyke Ave") == ["43rd street", "van dyke avenue"]
    assert limits_keys("") == []


def test_parse_location():
    assert parse_location("El Cajon Blvd btwn 43rd St _ Van Dyke Ave") == ("El Cajon Blvd", "43rd St & Van Dyke Ave")
    assert parse_location("Judson St btwn Fulton St & Hyatt St") == ("Judson St", "Fulton St & Hyatt St")
    assert parse_location("Harbor Dr at Grape St") == ("Harbor Dr", "Grape St")
    assert parse_location("no separator here") is None


def test_year_of():
    assert year_of("2023-11-01") == 2023
    assert year_of("03/05/2017 00:00") == 2017
    assert year_of("") is None


def test_split_label():
    assert split_label("43rd Street & El Cajon Boulevard") == ["43rd Street", "El Cajon Boulevard"]
    assert split_label("Park Boulevard") == ["Park Boulevard"]


# 43rd & El Cajon sits at roughly (32.75507, -117.10189).
LAT, LON = 32.75507, -117.10189
COUNTS = [
    Count("El Cajon Blvd", "42nd St & 43rd St", 28100, "2015-06-02", 32.7550, -117.1032),
    Count("El Cajon Blvd", "43rd St & Van Dyke Ave", 16841, "2023-11-01", 32.75509, -117.10239),  # more recent
    Count("43rd St", "El Cajon Blvd & Orange Ave", 9300, "2017-10-30", 32.7562, -117.1019),
    Count("Park Blvd", "University Ave & Robinson Ave", 12000, "2018-01-01", 32.7480, -117.1540),
    Count("Fairmount Ave", "Home Ave & Cliff St", 21000, "2024-03-03", 32.7551, -117.1015),      # 60 m away, wrong street
    Count("Broken St", "Nowhere & Elsewhere", 0, "2018-01-01", LAT, LON),                            # zero counts are ignored
]


def test_legs_for_prefers_a_count_that_names_the_cross_street_and_the_most_recent():
    idx = index_counts(COUNTS)
    legs = {l.street: l for l in legs_for("43rd Street & El Cajon Boulevard", idx, LAT, LON)}
    assert legs["El Cajon Boulevard"].adt == 16841
    assert legs["El Cajon Boulevard"].year == 2023
    assert legs["El Cajon Boulevard"].method == "limits"
    assert legs["43rd Street"].adt == 9300


def test_nearby_fallback_uses_same_street_only_and_respects_the_radius():
    idx = index_counts(COUNTS)
    # No count on El Cajon names "Euclid", but one sits ~50 m from this point.
    legs = legs_for("El Cajon Boulevard & Euclid Avenue", idx, 32.75509, -117.10239)
    assert [l.method for l in legs] == ["nearby"]
    assert legs[0].street == "El Cajon Boulevard" and legs[0].adt == 16841
    # Far away, nothing qualifies.
    assert legs_for("El Cajon Boulevard & Euclid Avenue", idx, 32.80, -117.20) == []
    # Without a point there is no fallback at all.
    assert legs_for("El Cajon Boulevard & Euclid Avenue", idx) == []


def test_site_record_sums_entering_and_flags_completeness():
    idx = index_counts(COUNTS)
    rec = site_record("43rd Street & El Cajon Boulevard", idx, LAT, LON)
    assert rec["entering"] == 16841 + 9300
    assert rec["complete"] is True
    partial = site_record("Park Boulevard & University Avenue", idx)
    assert partial["entering"] == 12000 and partial["complete"] is False
    assert site_record("Park Boulevard & connector road", idx) is None
    assert site_record("Park Boulevard", idx) is None


def test_zero_counts_never_match():
    assert "broken street" not in index_counts(COUNTS)
