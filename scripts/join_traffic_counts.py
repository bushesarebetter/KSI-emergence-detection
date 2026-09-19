"""Join City of San Diego traffic counts (average daily traffic) to the
exported intersections and write dashboard/public/data/traffic.json.

Source: City of San Diego open data, "Traffic Volumes (ADT)":
  https://data.sandiego.gov/datasets/traffic-adt-counts/
The CSV is cached under data/raw/traffic/ (gitignored) and re-downloaded with
--refresh. Matching rules live in src/traffic/counts.py and are unit-tested;
this script is the I/O around them.

The dashboard reads traffic.json to show vehicles per day at a corner and a
crash rate per million entering vehicles. Sites without a City count near them
simply have no entry, and the interface says so.

Usage
  python scripts/join_traffic_counts.py            # use the cached CSV if present
  python scripts/join_traffic_counts.py --refresh  # re-download first
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.traffic.counts import Count, GEO_MAX_M, index_counts, parse_location, site_record  # noqa: E402

DATASET_PAGE = "https://data.sandiego.gov/datasets/traffic-adt-counts/"
CSV_URL = "https://seshat.datasd.org/traffic_adt_counts/traffic_counts_datasd.csv"
RAW = ROOT / "data" / "raw" / "traffic" / "traffic_counts_datasd.csv"
GEOJSON = ROOT / "dashboard" / "public" / "data" / "intersections.geojson"
OUT = ROOT / "dashboard" / "public" / "data" / "traffic.json"
USER_AGENT = "KSI-emergence-detection/join_traffic_counts (+https://github.com/bushesarebetter/KSI-emergence-detection)"


def download(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(CSV_URL, headers={"User-Agent": USER_AGENT}, timeout=120)
    r.raise_for_status()
    dest.write_bytes(r.content)


def load_counts(path: Path) -> tuple[list[Count], int]:
    """Rows of the City CSV as Count records; returns (counts, rows skipped)."""
    counts: list[Count] = []
    skipped = 0
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            parsed = parse_location(r.get("location", ""))
            if not parsed:
                skipped += 1
                continue
            street, limits = parsed
            try:
                total = int(float(r.get("adt_total") or 0))
            except ValueError:
                total = 0
            try:
                lat = float(r["lat"]) if r.get("lat") else None
                lng = float(r["lng"]) if r.get("lng") else None
            except ValueError:
                lat = lng = None
            counts.append(Count(street, limits, total, r.get("date", ""), lat, lng))
    return counts, skipped


def point_key(lat: float, lon: float) -> str:
    # Same key the front end builds with toFixed(6), and the refine script uses.
    return f"{lat:.6f},{lon:.6f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="re-download the City CSV")
    ap.add_argument("--max-m", type=float, default=GEO_MAX_M,
                    help="radius for the same-street nearby fallback (metres)")
    args = ap.parse_args()

    if args.refresh or not RAW.exists():
        print(f"downloading {CSV_URL}")
        download(RAW)
    counts, skipped = load_counts(RAW)
    index = index_counts(counts)
    years = Counter(c.date[:4] for c in counts if c.date)
    print(f"{len(counts)} counts on {len(index)} streets ({skipped} rows without a parsable location); "
          f"count years: {dict(sorted(years.items()))}")

    fc = json.loads(GEOJSON.read_text(encoding="utf-8"))
    sites: dict[str, dict] = {}
    methods: Counter = Counter()
    complete = partial = 0
    top800 = 0
    for f in fc["features"]:
        lon, lat = f["geometry"]["coordinates"]
        rec = site_record(f["properties"].get("intersection_name", ""), index, lat, lon, args.max_m)
        if rec is None:
            continue
        sites[point_key(lat, lon)] = rec
        complete += rec["complete"]
        partial += not rec["complete"]
        top800 += f["properties"]["rank"] <= 800
        for leg in rec["legs"]:
            methods[leg["method"]] += 1

    n = len(fc["features"])
    print(f"matched {len(sites)}/{n} sites ({complete} both streets, {partial} one street); "
          f"{top800} of the top 800; legs by method: {dict(methods)}")

    out = {
        "source": {
            "name": "City of San Diego traffic counts (average daily traffic)",
            "page": DATASET_PAGE,
            "file": CSV_URL,
            "retrieved": date.today().isoformat(),
            "rows": len(counts),
            "nearby_radius_m": args.max_m,
        },
        "sites": sites,
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
