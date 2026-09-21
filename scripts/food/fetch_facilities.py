"""Download the County's food facility permit list: the candidate universe for
the food-safety model.

Source: "Food Facility Permits", San Diego County open data portal, dataset
c5ez-ufrd (public domain, updated monthly). About 15,900 rows with record id,
business type, address, city, permit status and coordinates. Inspection results
are not in this dataset; they come from SD Food Info and are the pipeline's job.

Usage
  python scripts/food/fetch_facilities.py                 # all of the county
  python scripts/food/fetch_facilities.py --city "SAN DIEGO"
Writes data/raw/food/permits.json (gitignored) and prints counts by type.
"""
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "raw" / "food" / "permits.json"
ENDPOINT = "https://data.sandiegocounty.gov/resource/c5ez-ufrd.json"
PAGE = 5000


def fetch_page(offset: int, limit: int = PAGE, opener=None) -> list[dict]:
    q = urllib.parse.urlencode({"$limit": limit, "$offset": offset, "$order": ":id"})
    req = urllib.request.Request(f"{ENDPOINT}?{q}", headers={"User-Agent": "KSI-emergence-detection food pipeline"})
    open_ = opener or urllib.request.urlopen
    with open_(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_all(fetch=fetch_page) -> list[dict]:
    rows, offset = [], 0
    while True:
        page = fetch(offset)
        rows.extend(page)
        if len(page) < PAGE:
            return rows
        offset += PAGE


def normalise(row: dict) -> dict | None:
    """One permit as the pipeline wants it, or None when it has no location."""
    try:
        lat, lon = float(row.get("latitude")), float(row.get("longitude"))
    except (TypeError, ValueError):
        return None
    return {
        "facility_id": row.get("record_id"),
        "name": row.get("record_name"),
        "business_type": row.get("business_type"),
        "address": row.get("address"),
        "city": (row.get("city") or "").upper(),
        "zip": row.get("zip"),
        "permit_status": row.get("permit_status"),
        "active": (row.get("active_permit") or "").upper() in ("Y", "YES", "TRUE"),
        "opened": row.get("record_open_date"),
        "lat": lat,
        "lon": lon,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--city", default=None, help="keep one city only, e.g. 'SAN DIEGO'")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    rows = [n for n in (normalise(r) for r in fetch_all()) if n]
    if args.city:
        rows = [r for r in rows if r["city"] == args.city.upper()]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    types = Counter(r["business_type"] for r in rows)
    print(f"{len(rows)} permits with coordinates{f' in {args.city}' if args.city else ''}; active {sum(r['active'] for r in rows)}")
    for t, n in types.most_common(12):
        print(f"  {n:6d}  {t}")


if __name__ == "__main__":
    main()
