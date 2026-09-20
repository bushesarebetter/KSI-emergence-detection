"""Flag exported intersections that sit near a school, from OpenStreetMap, and
write the flag into dashboard/public/data/intersections.geojson as
`near_school: {name, meters, kind}`.

Why: a corner within a few hundred metres of a school carries children on foot
at fixed hours, changes the advice a driver needs, and qualifies for Safe Routes
to School money (part of California's Active Transportation Program). The flag
therefore feeds the advice, a filter chip, and the funding case.

One Overpass request per BATCH_SIZE points, with `out center` so school
grounds mapped as areas come back as a single point. Results are cached per
site so a rerun after a new export only fetches what is missing. The geojson is
backed up under data/proc before it is written; the export script does not
carry this field, so rerun this after every export.

Usage
  python scripts/fetch_school_proximity.py
  python scripts/fetch_school_proximity.py --refresh    # ignore the cache
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.gis.overpass import chunks, fetch  # noqa: E402

GEOJSON = ROOT / "dashboard" / "public" / "data" / "intersections.geojson"
CACHE = ROOT / "data" / "proc" / "school_cache.json"
BACKUP = ROOT / "data" / "proc" / "intersections.geojson.before-schools"

RADIUS_M = 300      # a school this close makes the corner a school corner
BATCH_SIZE = 100
PAUSE_S = 2.0
KINDS = {"school": "school", "kindergarten": "preschool", "college": "college", "university": "university"}


def meters(lat1, lon1, lat2, lon2):
    k = math.cos(math.radians(lat1))
    return math.hypot((lon2 - lon1) * 111_320 * k, (lat2 - lat1) * 110_540)


def query_for(points) -> str:
    parts = "".join(
        f'nwr(around:{RADIUS_M},{lat:.6f},{lon:.6f})[amenity~"^(school|kindergarten|college|university)$"];'
        for lat, lon in points
    )
    return f"[out:json][timeout:180];({parts});out center tags;"


def as_point(el):
    if el.get("type") == "node":
        return el.get("lat"), el.get("lon")
    c = el.get("center") or {}
    return c.get("lat"), c.get("lon")


def nearest_school(lat, lon, schools):
    best = None
    for s in schools:
        slat, slon = as_point(s)
        if slat is None:
            continue
        d = meters(lat, lon, slat, slon)
        if d <= RADIUS_M and (best is None or d < best["meters"]):
            tags = s.get("tags", {})
            best = {
                "name": tags.get("name") or "a school",
                "kind": KINDS.get(tags.get("amenity"), "school"),
                "meters": round(d),
            }
    return best


def point_key(lat, lon) -> str:
    return f"{lat:.6f},{lon:.6f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="ignore the per-site cache")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    ap.add_argument("--dry-run", action="store_true", help="fetch and report; do not write the geojson")
    args = ap.parse_args()

    fc = json.loads(GEOJSON.read_text(encoding="utf-8"))
    points = [(f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0]) for f in fc["features"]]

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
        schools = data.get("elements", [])
        for lat, lon in batch:
            cache[point_key(lat, lon)] = nearest_school(lat, lon, schools)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache), encoding="utf-8")
        print(f"  batch {i}/{len(batches)}: {len(schools)} school features in {time.time() - tb:.0f}s")
        if i < len(batches):
            time.sleep(PAUSE_S)

    flagged = 0
    kinds: Counter = Counter()
    for f in fc["features"]:
        lat, lon = f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0]
        rec = cache.get(point_key(lat, lon))
        if rec:
            f["properties"]["near_school"] = rec
            flagged += 1
            kinds[rec["kind"]] += 1
        else:
            f["properties"].pop("near_school", None)
    top800 = sum(1 for f in fc["features"] if f["properties"]["rank"] <= 800 and f["properties"].get("near_school"))
    print(f"{flagged}/{len(points)} sites within {RADIUS_M} m of a school ({top800} of the top 800): {dict(kinds)} "
          f"({time.time() - t0:.0f}s)")

    if args.dry_run:
        print("--dry-run: geojson not written")
        return
    if not BACKUP.exists():
        shutil.copy2(GEOJSON, BACKUP)
    GEOJSON.write_text(json.dumps(fc), encoding="utf-8")
    meta = {"source": "OpenStreetMap contributors (ODbL)", "retrieved": date.today().isoformat(), "radius_m": RADIUS_M}
    (GEOJSON.parent / "schools.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"wrote near_school into {GEOJSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
