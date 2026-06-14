"""Download historical OSM snapshots via Overpass attic API.

Fetches features as of 2021-12-31T23:59:59Z for endogenous infrastructure
features that must not use post-2021 values (signals, stop signs, speed limits,
bike lanes may be countermeasure installations).

Saves immutable dated snapshots to data/raw/osm_history/<YYYYMMDD>/ with
a manifest.json.  Subsequent calls skip the download if the snapshot exists.

Run via:  python -m src.ingest.osm_history_loader
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

import requests

from src.utils import load_config, project_root

log = logging.getLogger(__name__)

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_RETRY_WAIT_S = 60   # wait before retrying on 429 / 5xx


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _overpass_query(query: str, timeout_s: int = 300) -> dict | None:
    """Execute an Overpass query; return parsed JSON or None on failure."""
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json, */*;q=0.5",
        "User-Agent": "sd-hotspot-emergence-research/1.0",
    }
    for attempt in range(3):
        try:
            resp = requests.post(
                _OVERPASS_URL,
                data={"data": query},
                headers=headers,
                timeout=timeout_s + 30,
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 503):
                log.warning("Overpass rate-limited (%d); sleeping %ds", resp.status_code, _RETRY_WAIT_S)
                time.sleep(_RETRY_WAIT_S)
                continue
            log.error("Overpass HTTP %d: %s", resp.status_code, resp.text[:200])
            return None
        except requests.exceptions.Timeout:
            log.warning("Overpass timeout on attempt %d", attempt + 1)
        except Exception as exc:
            log.error("Overpass request failed: %s", exc)
            return None
    return None


def _build_node_query(tag_filter: str, bbox: list[float], date: str, timeout: int) -> str:
    s, w, n, e = bbox
    return (
        f'[out:json][timeout:{timeout}][date:"{date}"];\n'
        f'node{tag_filter}({s},{w},{n},{e});\n'
        f'out body;\n'
    )


def _build_way_query(tag_filter: str, bbox: list[float], date: str, timeout: int) -> str:
    s, w, n, e = bbox
    return (
        f'[out:json][timeout:{timeout}][date:"{date}"];\n'
        f'way{tag_filter}({s},{w},{n},{e});\n'
        f'out body geom;\n'
    )


# Feature specs: (filename, query_builder, tag_filter, description)
_FEATURE_SPECS: list[tuple[str, Any, str, str]] = [
    (
        "traffic_signals.geojson",
        _build_node_query,
        '["highway"="traffic_signals"]',
        "Traffic signal nodes (endogenous: may be installed as crash countermeasures)",
    ),
    (
        "stop_signs.geojson",
        _build_node_query,
        '["highway"~"stop|give_way"]',
        "Stop/give-way signs (endogenous)",
    ),
    (
        "speed_limits.geojson",
        _build_way_query,
        '["maxspeed"]',
        "Ways with maxspeed tag (endogenous: speed limit enforcement changes)",
    ),
    (
        "bike_lanes.geojson",
        _build_way_query,
        '["cycleway"]',
        "Ways with cycleway tag (endogenous: bike infrastructure installed over time)",
    ),
]


def _overpass_to_geojson(result: dict) -> dict:
    """Convert Overpass JSON to minimal GeoJSON FeatureCollection."""
    features = []
    for elem in result.get("elements", []):
        etype = elem.get("type")
        props = {k: v for k, v in elem.items() if k not in ("type", "lat", "lon", "geometry", "nodes")}
        props.update(elem.get("tags", {}))
        props.pop("tags", None)

        if etype == "node":
            geom = {"type": "Point", "coordinates": [elem["lon"], elem["lat"]]}
        elif etype == "way":
            coords = [[pt["lon"], pt["lat"]] for pt in elem.get("geometry", [])]
            if not coords:
                continue
            geom = {"type": "LineString", "coordinates": coords}
        else:
            continue

        features.append({"type": "Feature", "geometry": geom, "properties": props})
    return {"type": "FeatureCollection", "features": features}


def fetch_all(cfg: dict) -> dict[str, Path | None]:
    """Download all endogenous OSM history features; return {name: path_or_None}."""
    icfg = cfg["infrastructure"]
    bbox     = icfg["overpass_bbox"]
    date     = icfg["overpass_date"]
    timeout  = icfg["overpass_timeout_s"]

    date_tag  = date[:10].replace("-", "")  # e.g. "20211231"
    raw_dir   = project_root() / cfg["paths"]["raw"] / "osm_history" / date_tag
    raw_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = raw_dir / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
    else:
        manifest = {"source": "Overpass attic API", "date": date, "bbox": bbox, "files": {}}

    results: dict[str, Path | None] = {}

    for fname, qbuilder, tag_filter, desc in _FEATURE_SPECS:
        out_path = raw_dir / fname
        feature_key = fname.replace(".geojson", "")

        if out_path.exists():
            log.info("Already have %s (%d bytes)", fname, out_path.stat().st_size)
            results[feature_key] = out_path
            continue

        log.info("Fetching %s …", fname)
        query = qbuilder(tag_filter, bbox, date, timeout)
        raw_json = _overpass_query(query, timeout_s=timeout)

        if raw_json is None:
            log.warning("Failed to fetch %s — feature will be marked unavailable", fname)
            results[feature_key] = None
            manifest["files"][feature_key] = {"status": "FAILED", "description": desc}
            continue

        n_elems = len(raw_json.get("elements", []))
        geojson  = _overpass_to_geojson(raw_json)
        out_path.write_text(json.dumps(geojson), encoding="utf-8")
        sha = _sha256(out_path)

        manifest["files"][feature_key] = {
            "filename": fname,
            "n_elements": n_elems,
            "sha256": sha,
            "description": desc,
            "status": "OK",
        }
        log.info("  → %d elements written to %s", n_elems, out_path)
        results[feature_key] = out_path

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info("Manifest written to %s", manifest_path)
    return results


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    results = fetch_all(cfg)
    for k, p in results.items():
        status = "OK" if p else "FAILED"
        log.info("  %s: %s", k, status)


if __name__ == "__main__":
    main()
