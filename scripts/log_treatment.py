"""Record a review or a fix that can be traced to the list, with its matched
controls, so the pre-registered evaluation (docs/EVALUATION_PLAN.md) has a
treatment log from day one.

Matching is done at logging time and never revised: up to three control corners
from the same export that share the rank stratum and the control type, with
daily traffic within a factor of two where both have a count, preferring the
same council district.

Usage
  python scripts/log_treatment.py --rank 12 --treatment "protected left-turn phase" \
      --date 2027-03-01 --via "District 3 office, email of 2026-11-04"
  python scripts/log_treatment.py --rank 12 --treatment "engineering review requested" --date 2026-11-04 --via "council office"
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dashboard" / "public" / "data"
LOG = ROOT / "data" / "evaluation" / "treatments.csv"
STRATA = [(1, 100), (101, 300), (301, 800), (801, 10_000)]


def stratum(rank: int) -> tuple[int, int]:
    return next(s for s in STRATA if s[0] <= rank <= s[1])


def point_key(f) -> str:
    lon, lat = f["geometry"]["coordinates"]
    return f"{lat:.6f},{lon:.6f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rank", type=int, required=True, help="the corner's rank in the current export")
    ap.add_argument("--treatment", required=True, help="what was done, e.g. 'engineering review requested'")
    ap.add_argument("--date", required=True, help="date the treatment was requested or in place, YYYY-MM-DD")
    ap.add_argument("--via", required=True, help="how the treatment traces to the list (who cited it, when)")
    ap.add_argument("--notes", default="")
    args = ap.parse_args()

    fc = json.loads((DATA / "intersections.geojson").read_text(encoding="utf-8"))
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
    control = json.loads((DATA / "control.json").read_text(encoding="utf-8"))["sites"] if (DATA / "control.json").exists() else {}
    traffic = json.loads((DATA / "traffic.json").read_text(encoding="utf-8"))["sites"] if (DATA / "traffic.json").exists() else {}

    by_rank = {f["properties"]["rank"]: f for f in fc["features"]}
    treated = by_rank.get(args.rank)
    if treated is None:
        raise SystemExit(f"no corner ranked {args.rank} in the current export")
    tkey = point_key(treated)
    tctrl = control.get(tkey, {}).get("control")
    tadt = traffic.get(tkey, {}).get("entering")
    lo, hi = stratum(args.rank)

    already = set()
    if LOG.exists():
        with open(LOG, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                already.add(row["corner_key"])
                for c in row["matched_controls"].split(";"):
                    if c:
                        already.add(c.split("@")[0])

    def eligible(f):
        r = f["properties"]["rank"]
        k = point_key(f)
        if k == tkey or k in already or not (lo <= r <= hi):
            return False
        if tctrl and control.get(k, {}).get("control") != tctrl:
            return False
        adt = traffic.get(k, {}).get("entering")
        if tadt and adt and not (tadt / 2 <= adt <= tadt * 2):
            return False
        return True

    pool = [f for f in fc["features"] if eligible(f)]
    same_district = [f for f in pool if f["properties"]["council_district"] == treated["properties"]["council_district"]]
    chosen = (same_district + [f for f in pool if f not in same_district])[:3]
    controls = ";".join(f"{point_key(f)}@{f['properties']['rank']}" for f in chosen)

    LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG.exists()
    with open(LOG, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["logged_on", "corner_key", "intersection_name", "rank_at_listing", "export_generated",
                        "treatment", "treatment_date", "traced_to_list_via", "matched_controls", "notes"])
        w.writerow([date.today().isoformat(), tkey, treated["properties"]["intersection_name"], args.rank,
                    meta.get("generated", ""), args.treatment, args.date, args.via, controls, args.notes])
    print(f"logged #{args.rank} {treated['properties']['intersection_name']}: {args.treatment} on {args.date}")
    print(f"matched controls ({len(chosen)}): " + ", ".join(f"#{f['properties']['rank']} {f['properties']['intersection_name']}" for f in chosen))


if __name__ == "__main__":
    main()
