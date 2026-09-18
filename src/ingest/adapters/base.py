"""Canonical crash schema and the adapter contract.

WHY
---
The pipeline was written against SWITRS column names. 13 of the 20 crash-history
features need only date, severity, and coordinates -- those are portable to any
crash dataset on Earth. The other 7 (`ped_`, `bike_`, `broadside_`, `left_turn_`,
`dui_`, `night_`, `ped_row_violation_`) read SWITRS codebook values directly, and
that is the only thing standing between this project and any other jurisdiction.

An adapter's job is to translate one source into the canonical frame below. Once
it does, every downstream stage -- node spine, buffering, panel, features, model,
evaluation -- works unchanged.

THE TWO-TIER SEVERITY PROBLEM
-----------------------------
There is no national US database of serious-injury crashes. NHTSA states plainly
that serious injury data is maintained by individual states with widely varying
quality. FARS is national, standardized, and free, but fatal-only.

So the canonical schema carries `severity` on a fixed ordinal scale AND a
`severity_scheme` marker saying which tiers the source can actually populate:

    "ksi"        source distinguishes fatal from serious injury (e.g. SWITRS)
    "fatal_only" source contains fatal crashes only (e.g. FARS)

Nothing downstream may silently mix the two. A model trained on `fatal_only` data
is predicting fatal crashes, not KSI, and must be reported that way.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# ── Canonical severity scale ────────────────────────────────────────────────────
# Deliberately identical to SWITRS COLLISION_SEVERITY so the existing San Diego
# results need no relabelling. Other sources map onto it.
SEVERITY_FATAL = 1
SEVERITY_SEVERE = 2
SEVERITY_OTHER_INJURY = 3
SEVERITY_COMPLAINT_OF_PAIN = 4
SEVERITY_PDO = 5

KSI_SEVERITIES = frozenset({SEVERITY_FATAL, SEVERITY_SEVERE})

SEVERITY_SCHEME_KSI = "ksi"
SEVERITY_SCHEME_FATAL_ONLY = "fatal_only"
VALID_SEVERITY_SCHEMES = frozenset({SEVERITY_SCHEME_KSI, SEVERITY_SCHEME_FATAL_ONLY})

# ── The canonical frame ─────────────────────────────────────────────────────────
# Required of every adapter. Missing any of these is a hard error, because every
# one of them is load-bearing for some downstream stage.
REQUIRED_COLUMNS = {
    "crash_id": "str",     # unique within the source
    "date": "datetime64[ns]",
    "lat": "float",        # WGS84
    "lon": "float",        # WGS84
    "severity": "int",     # the canonical scale above
}

# Optional. An adapter supplies what its source supports; anything absent is
# filled with pd.NA and recorded in `available_flags` so feature code can emit a
# `*_missing` indicator instead of silently treating "unknown" as "no".
OPTIONAL_FLAGS = (
    "is_ped",                # pedestrian involved
    "is_bike",               # cyclist involved
    "is_broadside",          # angle / broadside collision
    "is_left_turn",          # a party was turning left
    "is_dui",                # alcohol or drugs involved
    "is_night",              # dark / dusk lighting
    "is_ped_row_violation",  # pedestrian right-of-way violation
    "at_intersection",       # source says the crash is intersection-related
    "is_state_highway",      # for the surface-street filter
)

OPTIONAL_ATTRS = (
    "functional_class",      # source's road classification, free text
    "place_name",            # city / municipality, for regional subsetting
    "state_name",
)


@dataclass(frozen=True)
class CrashSource:
    """What an adapter returns: the frame plus everything needed to interpret it."""

    crashes: pd.DataFrame
    severity_scheme: str
    source_name: str
    available_flags: frozenset[str]
    quality: dict

    def __post_init__(self) -> None:
        if self.severity_scheme not in VALID_SEVERITY_SCHEMES:
            raise ValueError(
                f"severity_scheme must be one of {sorted(VALID_SEVERITY_SCHEMES)}, "
                f"got {self.severity_scheme!r}"
            )

    @property
    def supports_ksi(self) -> bool:
        """True only if the source can distinguish serious injury from fatal.

        Guard every KSI-labelled output on this. A `fatal_only` source silently
        treated as KSI would produce numbers that look like the San Diego results
        but mean something different, which is the single worst failure mode of
        going multi-source.
        """
        return self.severity_scheme == SEVERITY_SCHEME_KSI

    def label_name(self) -> str:
        return "KSI" if self.supports_ksi else "fatal"


class CrashAdapter(ABC):
    """Translate one crash data source into the canonical frame."""

    #: short lowercase identifier, used in paths and configs
    name: str
    #: which severity tiers this source can populate
    severity_scheme: str

    @abstractmethod
    def load(self, raw_dir: Path, **kwargs) -> CrashSource:
        """Read the source from `raw_dir` and return the canonical frame."""

    # ── shared helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def validate(df: pd.DataFrame, source_name: str) -> dict:
        """Enforce the contract and return coordinate/date quality stats.

        Runs on every adapter so a new source cannot quietly skip the checks that
        this project learned the hard way. SWITRS's LATITUDE/LONGITUDE field is
        44% populated and 98.5% freeway crashes -- using it would have silently
        wrecked the analysis, and only an explicit coverage check caught it.
        """
        missing = set(REQUIRED_COLUMNS) - set(df.columns)
        if missing:
            raise ValueError(f"[{source_name}] adapter omitted required columns: {sorted(missing)}")

        n = len(df)
        if n == 0:
            raise ValueError(f"[{source_name}] adapter returned zero crashes")

        stats: dict = {"n_raw": int(n)}

        bad_coord = ~(df["lat"].between(-90, 90) & df["lon"].between(-180, 180))
        bad_coord |= df["lat"].isna() | df["lon"].isna()
        stats["n_bad_coords"] = int(bad_coord.sum())
        stats["coord_coverage"] = round(float(1 - bad_coord.mean()), 4)

        bad_date = df["date"].isna()
        stats["n_bad_dates"] = int(bad_date.sum())

        bad_sev = ~df["severity"].isin(range(1, 6))
        stats["n_bad_severity"] = int(bad_sev.sum())

        # Exact duplicate coordinates are the signature of centroid snapping or
        # over-rounding -- the thing that would break a 76.2 m intersection buffer.
        ok = df.loc[~bad_coord, ["lat", "lon"]]
        stats["pct_duplicate_coords"] = (
            round(float(ok.duplicated(keep=False).mean()), 4) if len(ok) else 0.0
        )

        log.info(
            "[%s] %d crashes | coord coverage %.2f%% | duplicate coords %.2f%% | "
            "bad dates %d | bad severity %d",
            source_name, n, 100 * stats["coord_coverage"],
            100 * stats["pct_duplicate_coords"], stats["n_bad_dates"], stats["n_bad_severity"],
        )

        if stats["coord_coverage"] < 0.80:
            log.warning(
                "[%s] coordinate coverage is only %.1f%%. Check whether a better "
                "geocode field exists in this source before proceeding -- SWITRS "
                "has two coordinate fields and the obvious one is the wrong one.",
                source_name, 100 * stats["coord_coverage"],
            )
        if stats["pct_duplicate_coords"] > 0.20:
            log.warning(
                "[%s] %.1f%% of crashes share an exact coordinate with another. "
                "That suggests centroid snapping or heavy rounding, which makes "
                "intersection-level assignment unreliable.",
                source_name, 100 * stats["pct_duplicate_coords"],
            )

        return stats

    @staticmethod
    def finalize(
        df: pd.DataFrame, available_flags: set[str], drop_invalid: bool = True
    ) -> pd.DataFrame:
        """Add absent optional columns as NA and coerce dtypes."""
        for col in OPTIONAL_FLAGS:
            if col not in df.columns:
                df[col] = pd.NA
            elif col in available_flags:
                df[col] = df[col].astype("boolean")
        for col in OPTIONAL_ATTRS:
            if col not in df.columns:
                df[col] = pd.NA

        df["crash_id"] = df["crash_id"].astype(str)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        if drop_invalid:
            before = len(df)
            df = df[
                df["lat"].between(-90, 90)
                & df["lon"].between(-180, 180)
                & df["date"].notna()
                & df["severity"].isin(range(1, 6))
            ].copy()
            if before != len(df):
                log.info("dropped %d rows failing the canonical contract", before - len(df))

        ordered = list(REQUIRED_COLUMNS) + list(OPTIONAL_FLAGS) + list(OPTIONAL_ATTRS)
        return df[[c for c in ordered if c in df.columns]].reset_index(drop=True)
