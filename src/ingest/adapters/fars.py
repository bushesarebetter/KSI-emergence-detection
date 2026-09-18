"""FARS adapter — NHTSA Fatality Analysis Reporting System.

FARS is the only genuinely national US crash dataset: all 50 states plus DC and
Puerto Rico, one standardized schema, free, no account required, annual CSV bundles
from 1975 and an API from 2010. That makes it the spine of any multi-city version
of this project.

The cost is that it is **fatal-only**. There is no national serious-injury
database -- NHTSA is explicit that serious-injury data lives in individual state
systems of widely varying quality. So this adapter reports
`severity_scheme="fatal_only"`, and anything built on it predicts *fatal* crashes,
not KSI. `CrashSource.supports_ksi` is the guard; do not route around it.

Coordinate quality (audited on the 2022 national file, 39,422 crashes):
  - 99.46% have plausible US coordinates
  - 87% carry 8 decimal places
  - only 0.11% share an exact coordinate with another crash
That last figure is the important one. It rules out the centroid snapping that
would make a 76.2 m intersection buffer meaningless, and it is far better than
SWITRS's LATITUDE/LONGITUDE field.

Input layout
------------
    data/raw/fars/FARS2022NationalCSV.zip     (as downloaded, unextracted)
    data/raw/fars/FARS2021NationalCSV.zip
    ...
Download from:
    https://static.nhtsa.gov/nhtsa/downloads/FARS/<YEAR>/National/FARS<YEAR>NationalCSV.zip
"""
from __future__ import annotations

import logging
import re
import zipfile
from pathlib import Path

import pandas as pd

from src.ingest.adapters.base import (
    SEVERITY_FATAL,
    SEVERITY_SCHEME_FATAL_ONLY,
    CrashAdapter,
    CrashSource,
)

log = logging.getLogger(__name__)

# FARS encodes "unknown" as repeated-digit sentinels (77.7777, 88.8888, 99.9999
# for latitude; the negative equivalents for longitude) rather than leaving the
# field blank. Filtering to a plausible US envelope removes them without having to
# enumerate every sentinel, and also catches the occasional transposed sign.
US_LAT_RANGE = (17.0, 72.0)     # Puerto Rico through northern Alaska
US_LON_RANGE = (-180.0, -64.0)  # Aleutians through Puerto Rico

# RELJCT2 — relation to junction. These are the values that place a crash at or
# near an intersection. "Intersection-Related" means the crash occurred on an
# approach and is attributable to the intersection, which is exactly the kind of
# event this project wants to attribute to a node.
INTERSECTION_RELJCT2 = {"Intersection", "Intersection-Related"}

# FUNC_SYS — road classification. The project excludes freeway/ramp crashes so
# they are not attributed to surface-street intersection nodes; this mirrors the
# STATE_HWY_IND filter used for SWITRS.
FREEWAY_FUNC_SYS_PATTERN = re.compile(r"interstate|freeway|expressway", re.IGNORECASE)

# MAN_COLL — manner of collision. FARS spells broadside as "Angle".
BROADSIDE_MAN_COLL_PATTERN = re.compile(r"angle", re.IGNORECASE)

# LGT_COND — light condition.
NIGHT_LGT_COND_PATTERN = re.compile(r"dark|dusk|dawn", re.IGNORECASE)


def _read_zip_csv(zf: zipfile.ZipFile, basename: str) -> pd.DataFrame | None:
    """Read one CSV out of a FARS bundle.

    The folder inside the zip is named after the year, and the casing of the
    member files has changed across FARS releases (`accident.csv` vs
    `ACCIDENT.CSV`), so match case-insensitively on the basename rather than
    assuming a path. FARS ships latin-1, not UTF-8.
    """
    target = basename.lower()
    for member in zf.namelist():
        if Path(member).name.lower() == target:
            return pd.read_csv(zf.open(member), low_memory=False, encoding="latin-1")
    return None


def _name_col(df: pd.DataFrame, code: str) -> pd.Series:
    """Prefer FARS's decoded `<CODE>NAME` column over the numeric code.

    The numeric codes are not stable across FARS years -- category definitions
    have been revised -- but the decoded text labels are consistent enough to
    match on. Matching text is the more durable choice here.
    """
    if f"{code}NAME" in df.columns:
        return df[f"{code}NAME"].astype(str)
    if code in df.columns:
        return df[code].astype(str)
    return pd.Series(pd.NA, index=df.index, dtype="object")


class FarsAdapter(CrashAdapter):
    name = "fars"
    severity_scheme = SEVERITY_SCHEME_FATAL_ONLY

    def load(
        self,
        raw_dir: Path,
        years: list[int] | None = None,
        state: str | None = None,
        place: str | None = None,
        exclude_freeway: bool = True,
        intersection_only: bool = False,
        **kwargs,
    ) -> CrashSource:
        """Load one or more FARS annual bundles into the canonical frame.

        Parameters
        ----------
        years
            Restrict to these calendar years. Default: every bundle present.
        state, place
            Case-insensitive filters on STATENAME / CITYNAME, for cutting a
            single city out of the national file.
        exclude_freeway
            Drop Interstate/freeway/expressway crashes, mirroring the
            STATE_HWY_IND filter applied to SWITRS.
        intersection_only
            Keep only crashes FARS marks as at or related to an intersection.
            Leave this False for the main pipeline -- the 76.2 m buffer decides
            attribution geometrically, and pre-filtering on the source's own
            judgement would discard crashes the buffer would legitimately catch.
        """
        raw_dir = Path(raw_dir)
        bundles = sorted(raw_dir.glob("FARS*NationalCSV.zip"))
        if not bundles:
            raise FileNotFoundError(
                f"No FARS bundles in {raw_dir}. Download them with:\n"
                "  curl -sLO https://static.nhtsa.gov/nhtsa/downloads/FARS/"
                "2022/National/FARS2022NationalCSV.zip"
            )

        frames, per_year = [], {}
        for bundle in bundles:
            m = re.search(r"FARS(\d{4})", bundle.name)
            if not m:
                continue
            year = int(m.group(1))
            if years and year not in years:
                continue

            with zipfile.ZipFile(bundle) as zf:
                acc = _read_zip_csv(zf, "accident.csv")
                if acc is None:
                    log.warning("no accident.csv inside %s — skipping", bundle.name)
                    continue
                pbtype = _read_zip_csv(zf, "pbtype.csv")

            df = self._normalize(acc, pbtype, year)
            per_year[year] = len(df)
            frames.append(df)

        if not frames:
            raise ValueError(f"No FARS data matched years={years} in {raw_dir}")

        crashes = pd.concat(frames, ignore_index=True)

        # ── geographic and roadway filters ──────────────────────────────────────
        if state:
            crashes = crashes[
                crashes["state_name"].astype(str).str.casefold() == state.casefold()
            ]
        if place:
            crashes = crashes[
                crashes["place_name"].astype(str).str.casefold() == place.casefold()
            ]
        if exclude_freeway:
            before = len(crashes)
            crashes = crashes[crashes["is_state_highway"] != True]  # noqa: E712
            log.info("freeway filter removed %d crashes (%d remain)",
                     before - len(crashes), len(crashes))
        if intersection_only:
            before = len(crashes)
            crashes = crashes[crashes["at_intersection"] == True]  # noqa: E712
            log.info("intersection filter removed %d crashes (%d remain)",
                     before - len(crashes), len(crashes))

        available = {
            "is_ped", "is_bike", "is_broadside", "is_night",
            "at_intersection", "is_state_highway",
        }
        crashes = self.finalize(crashes, available)
        quality = self.validate(crashes, self.name)
        quality["years"] = per_year
        quality["filters"] = {
            "state": state, "place": place,
            "exclude_freeway": exclude_freeway,
            "intersection_only": intersection_only,
        }
        # Recorded so downstream code can emit *_missing flags rather than
        # treating "FARS does not carry this" as "this did not happen".
        quality["unavailable_flags"] = sorted(
            {"is_left_turn", "is_dui", "is_ped_row_violation"}
        )

        return CrashSource(
            crashes=crashes,
            severity_scheme=self.severity_scheme,
            source_name=self.name,
            available_flags=frozenset(available),
            quality=quality,
        )

    # ── translation ─────────────────────────────────────────────────────────────

    def _normalize(
        self, acc: pd.DataFrame, pbtype: pd.DataFrame | None, year: int
    ) -> pd.DataFrame:
        out = pd.DataFrame(index=acc.index)

        # ST_CASE is unique only within a year, so namespace it.
        out["crash_id"] = f"{year}-" + acc["ST_CASE"].astype(str)

        out["date"] = pd.to_datetime(
            {
                "year": acc.get("YEAR", pd.Series(year, index=acc.index)),
                "month": pd.to_numeric(acc["MONTH"], errors="coerce"),
                "day": pd.to_numeric(acc["DAY"], errors="coerce"),
            },
            errors="coerce",
        )

        lat = pd.to_numeric(acc["LATITUDE"], errors="coerce")
        lon = pd.to_numeric(acc["LONGITUD"], errors="coerce")
        in_us = lat.between(*US_LAT_RANGE) & lon.between(*US_LON_RANGE)
        out["lat"] = lat.where(in_us)
        out["lon"] = lon.where(in_us)

        # Every FARS record is, by definition, a fatal crash.
        out["severity"] = SEVERITY_FATAL

        # ── optional flags ──────────────────────────────────────────────────────
        reljct2 = _name_col(acc, "RELJCT2")
        out["at_intersection"] = reljct2.isin(INTERSECTION_RELJCT2)

        func_sys = _name_col(acc, "FUNC_SYS")
        out["is_state_highway"] = func_sys.str.contains(
            FREEWAY_FUNC_SYS_PATTERN, na=False
        )
        out["functional_class"] = func_sys

        out["is_broadside"] = _name_col(acc, "MAN_COLL").str.contains(
            BROADSIDE_MAN_COLL_PATTERN, na=False
        )
        out["is_night"] = _name_col(acc, "LGT_COND").str.contains(
            NIGHT_LGT_COND_PATTERN, na=False
        )

        # Pedestrian / cyclist involvement. PBTYPE enumerates non-motorists by
        # type, which separates the two cleanly; the PEDS column on `accident`
        # counts pedestrians only and is the fallback when PBTYPE is absent.
        out["is_ped"], out["is_bike"] = self._non_motorist_flags(acc, pbtype, out["crash_id"])

        out["place_name"] = acc.get("CITYNAME", pd.NA)
        out["state_name"] = acc.get("STATENAME", pd.NA)

        # Not derivable from `accident.csv`:
        #   is_left_turn          needs vehicle.csv pre-crash manoeuvre
        #   is_dui                needs person/drugs tables
        #   is_ped_row_violation  no direct FARS equivalent
        # Left as NA so feature code emits a *_missing flag instead of a false zero.
        return out

    @staticmethod
    def _non_motorist_flags(
        acc: pd.DataFrame, pbtype: pd.DataFrame | None, crash_id: pd.Series
    ) -> tuple[pd.Series, pd.Series]:
        if pbtype is not None and "PBPTYPENAME" in pbtype.columns and "ST_CASE" in pbtype.columns:
            kind = pbtype["PBPTYPENAME"].astype(str)
            ped_cases = set(pbtype.loc[kind.str.contains("pedestrian", case=False, na=False), "ST_CASE"])
            bike_cases = set(pbtype.loc[
                kind.str.contains("bicyclist|cyclist", case=False, na=False), "ST_CASE"
            ])
            st_case = acc["ST_CASE"]
            return st_case.isin(ped_cases), st_case.isin(bike_cases)

        # Fallback: PEDS counts pedestrians; there is no cyclist count on
        # `accident`, so is_bike stays unknown rather than being guessed at.
        peds = pd.to_numeric(acc.get("PEDS", 0), errors="coerce").fillna(0)
        return peds > 0, pd.Series(pd.NA, index=acc.index, dtype="object")
