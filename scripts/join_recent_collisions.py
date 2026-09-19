"""Join San Diego Police collision reports since the model's cutoff to the
exported intersections and write dashboard/public/data/recent.json.

Source: City of San Diego open data, "Traffic Collisions":
  https://data.sandiego.gov/datasets/traffic-collisions/
The CSV (about 12 MB) is cached under data/raw/collisions/ (gitignored) and
re-downloaded with --refresh. Matching lives in src/recent/collisions.py and is
unit-tested; this script is the I/O around it.

Usage
  python scripts/join_recent_collisions.py                  # since 2025-01-01
  python scripts/join_recent_collisions.py --since 2025-07-01
  python scripts/join_recent_collisions.py --refresh
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.recent.collisions import DEFAULT_SINCE, aggregate, parse_rows, site_key  # noqa: E402

DATASET_PAGE = "https://data.sandiego.gov/datasets/traffic-collisions/"
CSV_URL = "https://seshat.datasd.org/traffic_collisions/pd_collisions_datasd.csv"
RAW = ROOT / "data" / "raw" / "collisions" / "pd_collisions_datasd.csv"
GEOJSON = ROOT / "dashboard" / "public" / "data" / "intersections.geojson"
OUT = ROOT / "dashboard" / "public" / "data" / "recent.json"
USER_AGENT = "KSI-emergence-detection/join_recent_collisions (+https://github.com/bushesarebetter/KSI-emergence-detection)"


def download(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(CSV_URL, headers={"User-Agent": USER_AGENT}, timeout=300)
    r.raise_for_status()
    dest.write_bytes(r.content)


def point_key(lat: float, lon: float) -> str:
    return f"{lat:.6f},{lon:.6f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default=DEFAULT_SINCE, help="count reports on or after this date (YYYY-MM-DD)")
    ap.add_argument("--refresh", action="store_true", help="re-download the City CSV")
    args = ap.parse_args()

    if args.refresh or not RAW.exists():
        print(f"downloading {CSV_URL}")
        download(RAW)

    with open(RAW, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    latest = max((r.get("DATE_TIME") or r.get("date_time") or "")[:10] for r in rows)
    collisions = parse_rows(rows, since=args.since)
    agg = aggregate(collisions)
    print(f"{len(rows)} reports in file (latest {latest}); {len(collisions)} at an intersection since {args.since}, "
          f"at {len(agg)} distinct intersections")

    fc = json.loads(GEOJSON.read_text(encoding="utf-8"))
    sites = {}
    top800 = 0
    for feat in fc["features"]:
        key = site_key(feat["properties"].get("intersection_name", ""))
        rec = agg.get(key) if key else None
        if rec is None:
            continue
        lon, lat = feat["geometry"]["coordinates"]
        sites[point_key(lat, lon)] = rec
        top800 += feat["properties"]["rank"] <= 800
    total = sum(r["count"] for r in sites.values())
    print(f"{len(sites)}/{len(fc['features'])} exported sites have at least one report since {args.since} "
          f"({top800} of the top 800; {total} reports in all)")

    OUT.write_text(json.dumps({
        "source": {
            "name": "San Diego Police Department collision reports (City open data)",
            "page": DATASET_PAGE,
            "file": CSV_URL,
            "retrieved": date.today().isoformat(),
            "since": args.since,
            "through": latest,
        },
        "sites": sites,
    }, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
