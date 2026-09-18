"""Contract tests for crash-source adapters.

These guard the invariants that make multi-source modelling safe. The one that
matters most is the severity-scheme guard: FARS is fatal-only, SWITRS is KSI, and
a model trained on the former silently reported as the latter would produce
numbers that look like the San Diego results while meaning something different.

Tests that need real data skip cleanly when it is absent, so a fresh clone still
runs green.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.ingest.adapters import (
    OPTIONAL_ATTRS,
    OPTIONAL_FLAGS,
    REQUIRED_COLUMNS,
    CrashSource,
    get_adapter,
)
from src.ingest.adapters.base import (
    SEVERITY_FATAL,
    SEVERITY_SCHEME_FATAL_ONLY,
    SEVERITY_SCHEME_KSI,
    CrashAdapter,
)
from src.ingest.region import Region, utm_epsg_for

ROOT = Path(__file__).resolve().parent.parent
FARS_DIR = ROOT / "data" / "raw" / "fars"
has_fars = pytest.mark.skipif(
    not list(FARS_DIR.glob("FARS*NationalCSV.zip")),
    reason="no FARS bundles in data/raw/fars (public download; see docs/UNIVERSAL.md)",
)


# ── the severity-scheme guard ───────────────────────────────────────────────────

def _src(scheme: str) -> CrashSource:
    df = pd.DataFrame({
        "crash_id": ["a"], "date": pd.to_datetime(["2022-01-01"]),
        "lat": [32.7], "lon": [-117.1], "severity": [SEVERITY_FATAL],
    })
    return CrashSource(df, scheme, "test", frozenset(), {})


def test_fatal_only_source_does_not_claim_ksi_support():
    s = _src(SEVERITY_SCHEME_FATAL_ONLY)
    assert s.supports_ksi is False
    assert s.label_name() == "fatal"


def test_ksi_source_reports_ksi():
    s = _src(SEVERITY_SCHEME_KSI)
    assert s.supports_ksi is True
    assert s.label_name() == "KSI"


def test_unknown_severity_scheme_is_rejected():
    """A typo must fail loudly rather than default to KSI."""
    with pytest.raises(ValueError, match="severity_scheme"):
        _src("serious_injury_maybe")


# ── the canonical contract ──────────────────────────────────────────────────────

def test_validate_rejects_missing_required_columns():
    df = pd.DataFrame({"crash_id": ["a"], "date": pd.to_datetime(["2022-01-01"])})
    with pytest.raises(ValueError, match="required columns"):
        CrashAdapter.validate(df, "test")


def test_validate_rejects_empty_frame():
    df = pd.DataFrame({c: [] for c in REQUIRED_COLUMNS})
    with pytest.raises(ValueError, match="zero crashes"):
        CrashAdapter.validate(df, "test")


def test_validate_flags_centroid_snapping():
    """Many crashes on one coordinate is the signature that breaks a 76.2 m buffer."""
    n = 100
    df = pd.DataFrame({
        "crash_id": [str(i) for i in range(n)],
        "date": pd.to_datetime(["2022-01-01"] * n),
        "lat": [32.7] * n, "lon": [-117.1] * n,   # all identical
        "severity": [SEVERITY_FATAL] * n,
    })
    stats = CrashAdapter.validate(df, "test")
    assert stats["pct_duplicate_coords"] == 1.0


def test_finalize_fills_absent_optional_columns_with_na():
    """Absent must mean NA, never False.

    If a source cannot say whether a crash involved a pedestrian, filling False
    would make the feature builder count it as 'no pedestrian' and silently bias
    every ped_ feature toward zero.
    """
    df = pd.DataFrame({
        "crash_id": ["a"], "date": pd.to_datetime(["2022-01-01"]),
        "lat": [32.7], "lon": [-117.1], "severity": [SEVERITY_FATAL],
    })
    out = CrashAdapter.finalize(df, available_flags=set())
    for col in OPTIONAL_FLAGS + OPTIONAL_ATTRS:
        assert col in out.columns, f"{col} should be present"
        assert out[col].isna().all(), f"{col} should be NA, not a default value"


def test_finalize_drops_rows_violating_the_contract():
    df = pd.DataFrame({
        "crash_id": ["ok", "badlat", "baddate", "badsev"],
        "date": pd.to_datetime(["2022-01-01", "2022-01-01", None, "2022-01-01"]),
        "lat": [32.7, 999.0, 32.7, 32.7],
        "lon": [-117.1, -117.1, -117.1, -117.1],
        "severity": [1, 1, 1, 99],
    })
    out = CrashAdapter.finalize(df, available_flags=set())
    assert list(out["crash_id"]) == ["ok"]


def test_get_adapter_rejects_unknown_name():
    with pytest.raises(KeyError, match="No adapter named"):
        get_adapter("definitely_not_a_real_source")


# ── region / CRS ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("lon,lat,expected", [
    (-117.16, 32.72, "EPSG:32611"),   # San Diego      UTM 11N
    (-87.63, 41.88, "EPSG:32616"),    # Chicago        UTM 16N
    (-74.01, 40.71, "EPSG:32618"),    # New York       UTM 18N
    (-95.37, 29.76, "EPSG:32615"),    # Houston        UTM 15N
    (-0.13, 51.51, "EPSG:32630"),     # London         UTM 30N
    (151.21, -33.87, "EPSG:32756"),   # Sydney         UTM 56S, southern
])
def test_utm_zone_derivation(lon, lat, expected):
    assert utm_epsg_for(lon, lat) == expected


def test_utm_rejects_out_of_range_coordinates():
    with pytest.raises(ValueError):
        utm_epsg_for(200.0, 0.0)


def test_san_diego_region_keeps_its_historical_projection():
    """San Diego must stay on EPSG:2230 so published results stay reproducible."""
    r = Region.load("san_diego")
    assert r.crs == "EPSG:2230"
    assert r.adapter == "switrs"


def test_every_region_config_loads():
    available = Region.available()
    assert available, "expected at least one region config"
    for slug in available:
        r = Region.load(slug)
        assert r.name == slug, f"{slug}.yaml declares name={r.name!r}"
        assert r.crs.startswith("EPSG:")
        assert r.adapter in {"fars", "switrs"}


# ── real FARS data ──────────────────────────────────────────────────────────────

@has_fars
def test_fars_adapter_produces_the_canonical_frame():
    src = get_adapter("fars").load(FARS_DIR, years=[2022])
    df = src.crashes

    assert set(REQUIRED_COLUMNS).issubset(df.columns)
    assert len(df) > 20_000, "2022 should have tens of thousands of fatal crashes"
    assert (df["severity"] == SEVERITY_FATAL).all(), "every FARS record is fatal"
    assert src.severity_scheme == SEVERITY_SCHEME_FATAL_ONLY
    assert not src.supports_ksi


@has_fars
def test_fars_coordinates_survive_the_audit_thresholds():
    """The check that gated the whole multi-city plan."""
    src = get_adapter("fars").load(FARS_DIR, years=[2022])
    q = src.quality
    assert q["coord_coverage"] > 0.95
    assert q["pct_duplicate_coords"] < 0.05, (
        "duplicate coordinates above a few percent would mean centroid snapping "
        "and make 76.2 m intersection assignment unreliable"
    )


@has_fars
def test_fars_sentinel_coordinates_are_removed():
    """FARS encodes unknown as 77.7777/88.8888/99.9999 rather than leaving blank."""
    src = get_adapter("fars").load(FARS_DIR, years=[2022])
    lat = src.crashes["lat"]
    assert lat.between(17, 72).all(), "sentinel latitudes leaked through"


@has_fars
def test_fars_place_filter_selects_one_city():
    src = get_adapter("fars").load(
        FARS_DIR, years=[2022], state="California", place="SAN DIEGO"
    )
    places = src.crashes["place_name"].astype(str).str.upper().unique()
    assert set(places) == {"SAN DIEGO"}
    assert len(src.crashes) > 0


@has_fars
def test_fars_marks_unavailable_flags_rather_than_faking_them():
    """FARS cannot populate these three; they must be NA, not False."""
    src = get_adapter("fars").load(FARS_DIR, years=[2022])
    for col in ("is_left_turn", "is_dui", "is_ped_row_violation"):
        assert col in src.quality["unavailable_flags"]
        assert src.crashes[col].isna().all(), f"{col} should be NA, not a fabricated value"
