"""SWITRS adapter — California Statewide Integrated Traffic Records System.

This is the source every existing result in the repo was produced from. The
adapter does not re-implement the loader; it reads the same TIMS export and
translates it into the canonical frame, so San Diego and any FARS-derived city
can be handled by identical downstream code.

Two things preserved verbatim from `src/ingest/crash_loader.py`, because both were
discovered the hard way and are easy to get wrong again:

1. **POINT_X/POINT_Y, never LATITUDE/LONGITUDE.** POINT_X/Y are SafeTREC
   street-geocoded WGS84 coordinates present for ~96% of records.
   LATITUDE/LONGITUDE is officer GPS or CHP postmile: ~44% populated and ~98.5%
   freeway crashes. Using it would bias the whole analysis toward freeways.
2. **STATE_HWY_IND='Y' exclusion.** Those are state-numbered highway crashes,
   mostly freeway and ramp KSI, which must not be attributed to surface-street
   intersection nodes.

Unlike FARS, SWITRS distinguishes fatal from severe injury, so this adapter
reports `severity_scheme="ksi"` and supports the project's original label.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src.ingest.adapters.base import SEVERITY_SCHEME_KSI, CrashAdapter, CrashSource

log = logging.getLogger(__name__)

# SWITRS COLLISION_SEVERITY already matches the canonical scale exactly:
#   1 fatal · 2 severe injury · 3 other visible injury
#   4 complaint of pain · 5 property damage only
# No remapping needed, which is why the canonical scale was defined this way.

NIGHT_LIGHTING_CODES = {"B", "C", "D", "E"}   # dusk/dark
BROADSIDE_COLLISION_CODES = {"D"}             # TYPE_OF_COLLISION D = broadside
LEFT_TURN_MOVE_CODES = {"E"}                  # MOVE_PRE_ACC E = making left turn
DUI_SOBRIETY_CODES = {"B", "C", "D", "G"}
PED_ROW_VIOLATION_CATEGORY = "09"

_CRASH_COLS = [
    "CASE_ID", "COLLISION_DATE", "COLLISION_SEVERITY",
    "POINT_X", "POINT_Y", "STATE_HWY_IND",
    "PEDESTRIAN_ACCIDENT", "BICYCLE_ACCIDENT",
    "TYPE_OF_COLLISION", "LIGHTING", "ALCOHOL_INVOLVED",
    "PCF_VIOL_CATEGORY",
]


class SwitrsAdapter(CrashAdapter):
    name = "switrs"
    severity_scheme = SEVERITY_SCHEME_KSI

    def load(
        self,
        raw_dir: Path,
        exclude_state_highway: bool = True,
        **kwargs,
    ) -> CrashSource:
        raw_dir = Path(raw_dir)
        snapshots = sorted(d for d in raw_dir.iterdir() if d.is_dir()) if raw_dir.exists() else []
        files = [d / "Crashes.csv" for d in snapshots]
        files = [f for f in files if f.exists()]
        if not files:
            raise FileNotFoundError(
                f"No Crashes.csv under {raw_dir}/<YYYYMMDD>/. SWITRS cannot be "
                "redistributed; download it from TIMS (tims.berkeley.edu) per "
                "docs/DATA_SOURCES.md."
            )

        frames = []
        for f in files:
            df = pd.read_csv(f, low_memory=False)
            keep = [c for c in _CRASH_COLS if c in df.columns]
            frames.append(df[keep])
        # Snapshots overlap by design (a later export adds a year and restates
        # earlier ones), so deduplicate on CASE_ID.
        raw = pd.concat(frames, ignore_index=True).drop_duplicates(subset="CASE_ID")

        left_turn_ids = self._left_turn_case_ids(snapshots)

        out = pd.DataFrame(index=raw.index)
        out["crash_id"] = raw["CASE_ID"].astype(str)
        out["date"] = pd.to_datetime(raw["COLLISION_DATE"], errors="coerce")
        out["severity"] = pd.to_numeric(raw["COLLISION_SEVERITY"], errors="coerce")

        # POINT_X is longitude, POINT_Y is latitude. See the module docstring
        # before changing this.
        out["lon"] = pd.to_numeric(raw["POINT_X"], errors="coerce")
        out["lat"] = pd.to_numeric(raw["POINT_Y"], errors="coerce")

        out["is_state_highway"] = raw.get("STATE_HWY_IND", pd.Series(index=raw.index)).eq("Y")
        out["is_ped"] = raw.get("PEDESTRIAN_ACCIDENT", pd.Series(index=raw.index)).eq("Y")
        out["is_bike"] = raw.get("BICYCLE_ACCIDENT", pd.Series(index=raw.index)).eq("Y")
        out["is_broadside"] = raw.get(
            "TYPE_OF_COLLISION", pd.Series(index=raw.index)
        ).isin(BROADSIDE_COLLISION_CODES)
        out["is_night"] = raw.get("LIGHTING", pd.Series(index=raw.index)).isin(NIGHT_LIGHTING_CODES)
        out["is_dui"] = raw.get("ALCOHOL_INVOLVED", pd.Series(index=raw.index)).eq("Y")
        out["is_ped_row_violation"] = (
            raw.get("PCF_VIOL_CATEGORY", pd.Series(index=raw.index))
            .astype(str).str.strip().eq(PED_ROW_VIOLATION_CATEGORY)
        )
        out["is_left_turn"] = out["crash_id"].isin(left_turn_ids) if left_turn_ids else pd.NA

        # SWITRS has no direct intersection flag; attribution is geometric, via
        # the 76.2 m buffer in the node-spine stage.
        out["at_intersection"] = pd.NA
        out["place_name"] = pd.NA
        out["state_name"] = "California"

        if exclude_state_highway:
            before = len(out)
            out = out[out["is_state_highway"] != True]  # noqa: E712
            log.info("STATE_HWY_IND filter removed %d crashes (%d remain)",
                     before - len(out), len(out))

        available = {
            "is_ped", "is_bike", "is_broadside", "is_night", "is_dui",
            "is_ped_row_violation", "is_state_highway",
        }
        if left_turn_ids:
            available.add("is_left_turn")

        out = self.finalize(out, available)
        quality = self.validate(out, self.name)
        quality["snapshots"] = [d.name for d in snapshots]
        quality["unavailable_flags"] = sorted({"at_intersection"} | (
            set() if left_turn_ids else {"is_left_turn"}
        ))

        return CrashSource(
            crashes=out,
            severity_scheme=self.severity_scheme,
            source_name=self.name,
            available_flags=frozenset(available),
            quality=quality,
        )

    @staticmethod
    def _left_turn_case_ids(snapshots: list[Path]) -> set[str]:
        """Left-turn involvement lives in Parties.csv, one row per party."""
        frames = []
        for d in snapshots:
            p = d / "Parties.csv"
            if p.exists():
                frames.append(pd.read_csv(p, usecols=["CASE_ID", "MOVE_PRE_ACC"], low_memory=False))
        if not frames:
            log.info("no Parties.csv found — is_left_turn will be reported as unavailable")
            return set()
        parties = pd.concat(frames, ignore_index=True)
        return set(
            parties.loc[parties["MOVE_PRE_ACC"].isin(LEFT_TURN_MOVE_CODES), "CASE_ID"].astype(str)
        )
