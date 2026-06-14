"""Download MTS GTFS and extract transit stop locations.

Attempts to fetch a static GTFS feed for San Diego MTS.  Transit stop
locations are treated as approximately-static (networks don't change
rapidly), but we prefer a feed dated ≤ 2021-12-31 if obtainable.

Saves stops as stops.parquet to data/raw/gtfs/<YYYYMMDD>/ with manifest.json.

Run via:  python -m src.ingest.gtfs_loader
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from src.utils import load_config, project_root

log = logging.getLogger(__name__)

# MTS current GTFS feed (static, publicly available)
_MTS_GTFS_URL = "https://www.sdmts.com/google_transit_files/google_transit.zip"

# Fallback: Transitland / Mobility Database archived feeds for SDMTS (operator onestop id)
# These are publicly available snapshots.  We try to get the closest ≤ 2021 one.
_TRANSITLAND_FEED = "https://transit.land/api/v2/rest/feeds/f-9muey-sdmts"

_TIMEOUT_S = 120


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_gtfs_zip(content: bytes, out_dir: Path) -> pd.DataFrame | None:
    """Extract stops.txt from GTFS zip; return DataFrame."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = zf.namelist()
            stops_name = next((n for n in names if n.endswith("stops.txt")), None)
            if stops_name is None:
                log.error("No stops.txt in GTFS zip (files: %s)", names[:10])
                return None
            with zf.open(stops_name) as f:
                stops = pd.read_csv(f)
        required = {"stop_id", "stop_lat", "stop_lon"}
        if not required.issubset(stops.columns):
            log.error("stops.txt missing columns %s (have %s)", required - set(stops.columns), list(stops.columns))
            return None
        stops = stops.dropna(subset=["stop_lat", "stop_lon"])
        log.info("Parsed %d stops from GTFS zip", len(stops))
        return stops
    except Exception as exc:
        log.error("Failed to parse GTFS zip: %s", exc)
        return None


def fetch_stops(cfg: dict) -> Path | None:
    """Download GTFS and save stops.parquet; return path or None."""
    today = date.today().strftime("%Y%m%d")
    out_dir = project_root() / cfg["paths"]["raw"] / "gtfs" / today
    out_dir.mkdir(parents=True, exist_ok=True)

    stops_path = out_dir / "stops.parquet"
    manifest_path = out_dir / "manifest.json"

    if stops_path.exists():
        log.info("GTFS stops already present: %s", stops_path)
        return stops_path

    # Try MTS direct feed
    log.info("Fetching MTS GTFS from %s …", _MTS_GTFS_URL)
    stops = None
    vintage_note = "current MTS static GTFS (approximately-static; no dated ≤2021 snapshot obtained)"

    try:
        resp = requests.get(_MTS_GTFS_URL, timeout=_TIMEOUT_S)
        if resp.status_code == 200:
            stops = _parse_gtfs_zip(resp.content, out_dir)
        else:
            log.warning("MTS GTFS HTTP %d", resp.status_code)
    except Exception as exc:
        log.warning("MTS GTFS fetch failed: %s", exc)

    if stops is None:
        log.warning("Could not obtain GTFS stops — transit feature will be unavailable")
        manifest = {
            "source": "MTS GTFS",
            "url": _MTS_GTFS_URL,
            "status": "FAILED",
            "note": "Network unavailable or feed moved. Transit feature marked unavailable.",
            "temporal_note": "Transit stops treated as approximately-static.",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2))
        return None

    stops.to_parquet(stops_path, index=False)
    sha = _sha256(stops_path)

    manifest = {
        "source": "MTS GTFS",
        "url": _MTS_GTFS_URL,
        "fetch_date": today,
        "n_stops": len(stops),
        "sha256": sha,
        "status": "OK",
        "temporal_note": vintage_note,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    log.info("Saved %d stops to %s", len(stops), stops_path)
    return stops_path


def load_stops(cfg: dict) -> pd.DataFrame | None:
    """Load most recent GTFS stops snapshot; return DataFrame or None."""
    gtfs_raw = project_root() / cfg["paths"]["raw"] / "gtfs"
    dated_dirs = sorted(gtfs_raw.glob("*/stops.parquet"), reverse=True)
    if not dated_dirs:
        return None
    stops = pd.read_parquet(dated_dirs[0])
    log.info("Loaded %d GTFS stops from %s", len(stops), dated_dirs[0])
    return stops


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    path = fetch_stops(cfg)
    if path:
        stops = pd.read_parquet(path)
        log.info("GTFS stops loaded: %d rows, columns: %s", len(stops), list(stops.columns))
    else:
        log.warning("GTFS fetch failed — no stops available")


if __name__ == "__main__":
    main()
