"""Run every after-export step for the dashboard, in order, and stop on the
first failure. One command instead of five, so a new export never ships with
some of its context missing.

  python scripts/refresh_site_data.py            # everything
  python scripts/refresh_site_data.py --skip control,schools   # e.g. when Overpass is down

Steps (each is its own script and can be run alone):
  traffic   join_traffic_counts.py        City daily traffic counts -> traffic.json
  police    join_recent_collisions.py     police reports since the cutoff -> recent.json
  control   fetch_intersection_control.py signals / stop signs from OSM -> control.json
  schools   fetch_school_proximity.py     schools within 300 m from OSM -> near_school in the geojson
  names     refine_intersection_names.py  cross-street names from OSM -> the geojson
  check     npm run check (in dashboard/)  what the interface will be able to say
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    ("traffic", [sys.executable, "scripts/join_traffic_counts.py"]),
    ("police", [sys.executable, "scripts/join_recent_collisions.py"]),
    ("control", [sys.executable, "scripts/fetch_intersection_control.py", "--batch-size", "50"]),
    ("schools", [sys.executable, "scripts/fetch_school_proximity.py", "--batch-size", "50"]),
    ("names", [sys.executable, "scripts/refine_intersection_names.py"]),
    ("check", ["npm", "run", "check"]),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip", default="", help="comma-separated step names to skip")
    args = ap.parse_args()
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}

    for name, cmd in STEPS:
        if name in skip:
            print(f"== {name}: skipped")
            continue
        cwd = ROOT / "dashboard" if name == "check" else ROOT
        print(f"== {name}: {' '.join(cmd)}")
        t0 = time.time()
        rc = subprocess.call(cmd, cwd=cwd, shell=(name == "check" and sys.platform == "win32"))
        print(f"== {name}: {'ok' if rc == 0 else f'FAILED ({rc})'} in {time.time() - t0:.0f}s")
        if rc != 0:
            sys.exit(rc)
    print("all steps done; rebuild the dashboard with `npm run build` and commit public/data/")


if __name__ == "__main__":
    main()
