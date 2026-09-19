"""Fetch how each exported intersection is controlled (traffic signals, stop
signs, or neither) from OpenStreetMap and write dashboard/public/data/control.json.

Why: the advice for a left-turn crash differs at a signal ("wait for the arrow")
and at a stop sign ("stop fully, then wait for a gap"). OSM tags the node at an
intersection with highway=traffic_signals or highway=stop, and tags stop signs
with stop=all for an all-way stop.

One Overpass request per BATCH_SIZE points: node queries are light, and the
public mirrors were slow per request on 2026-09-17. Results are keyed by the
site's coordinates, like traffic.json, and cached per point so a rerun only
fetches what is missing.

Usage
  python scripts/fetch_intersection_control.py
  python scripts/fetch_intersection_control.py --refresh   # ignore the cache
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.gis.overpass import chunks, fetch  # noqa: E402

GEOJSON = ROOT / "dashboard" / "public" / "data" / "intersections.geojson"
OUT = ROOT / "dashboard" / "public" / "data" / "control.json"
CACHE = ROOT / "data" / "proc" / "control_cache.json"

RADIUS_M = 25     # a signal or stop node within this distance belongs to the corner
BATCH_SIZE = 100
PAUSE_S = 2.0


def meters(lat1, lon1, lat2, lon2):
    k = math.cos(math.radians(lat1))
    return math.hypot((lon2 - lon1) * 111_320 * k, (lat2 - lat1) * 110_540)


def query_for(points) -> str:
    parts = "".join(
        f'node(around:{RADIUS_M},{lat:.6f},{lon:.6f})[highway~"^(traffic_signals|stop|give_way)$"];'
        for lat, lon in points
    )
    return f"[out:json][timeout:180];({parts});out body;"


def classify(lat, lon, nodes) -> dict:
    """The control at one point from the fetched nodes near it."""
    near = [n for n in nodes if meters(lat, lon, n["lat"], n["lon"]) <= RADIUS_M]
    kinds = Counter(n.get("tags", {}).get("highway") for n in near)
    if kinds.get("traffic_signals"):
        return {"control": "signals", "nodes": len(near)}
    if kinds.get("stop"):
        all_way = any(n.get("tags", {}).get("stop") == "all" for n in near)
        return {"control": "stop", "all_way": all_way, "nodes": len(near)}
    if kinds.get("give_way"):
        return {"control": "yield", "nodes": len(near)}
    return {"control": "none", "nodes": 0}


def point_key(lat, lon) -> str:
    return f"{lat:.6f},{lon:.6f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="ignore the per-point cache")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = ap.parse_args()

    fc = json.loads(GEOJSON.read_text(encoding="utf-8"))
    points = []
    for f in fc["features"]:
        lon, lat = f["geometry"]["coordinates"]
        points.append((lat, lon))

    cache = {} if args.refresh or not CACHE.exists() else json.loads(CACHE.read_text(encoding="utf-8"))
    pending = [(lat, lon) for lat, lon in points if point_key(lat, lon) not in cache]
    batches = list(chunks(pending, args.batch_size))
    print(f"{len(points)} sites; {len(pending)} not cached -> {len(batches)} request(s)")

    t0 = time.time()
    for i, batch in enumerate(batches, 1):
        tb = time.time()
        data, err = fetch(query_for(batch))
        if data is None:
            print(f"  batch {i}/{len(batches)}: failed after {time.time() - tb:.0f}s: {type(err).__name__}: {str(err)[:120]}")
            continue
        nodes = [el for el in data.get("elements", []) if el.get("type") == "node"]
        for lat, lon in batch:
            cache[point_key(lat, lon)] = classify(lat, lon, nodes)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache), encoding="utf-8")
        print(f"  batch {i}/{len(batches)}: {len(nodes)} control nodes in {time.time() - tb:.0f}s")
        if i < len(batches):
            time.sleep(PAUSE_S)

    sites = {point_key(lat, lon): cache[point_key(lat, lon)] for lat, lon in points if point_key(lat, lon) in cache}
    tally = Counter(v["control"] for v in sites.values())
    print(f"{len(sites)}/{len(points)} sites classified: {dict(tally)} ({time.time() - t0:.0f}s)")

    OUT.write_text(json.dumps({
        "source": {"name": "OpenStreetMap contributors (ODbL)", "retrieved": date.today().isoformat(),
                   "radius_m": RADIUS_M},
        "sites": sites,
    }, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
