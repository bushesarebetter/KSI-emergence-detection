"""Audit a crash data source before trusting it for intersection-level modelling.

Run this on any new source BEFORE building a panel from it. The project has
already been burned once by skipping this: SWITRS's LATITUDE/LONGITUDE field looks
like the obvious geocode column but is only ~44% populated and ~98.5% freeway
crashes, so a model built on it would have quietly become a freeway model.

Four questions, in the order that matters:

  1. Coverage     What fraction of crashes have usable coordinates?
  2. Precision    Enough decimal places to resolve a 76.2 m buffer?
  3. Snapping     Are coordinates centroid-snapped or heavily rounded? This is the
                  one that silently ruins intersection assignment, and duplicate
                  coordinate share is the tell.
  4. Volume       How many intersection-attributable crashes per city? Below a few
                  dozen, nothing downstream can be measured.

Usage
-----
    python scripts/audit_crash_source.py --adapter fars --raw-dir data/raw/fars
    python scripts/audit_crash_source.py --region san_diego_fars
    python scripts/audit_crash_source.py --adapter fars --top-cities 40

Writes reports/crash_source_audit_<source>.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"

# Below this many crashes a city cannot support a measurable evaluation: the
# San Diego verified run had 21 positives and every comparison came back a tie.
MIN_VIABLE_CRASHES = 25
# Enough decimal places to distinguish points inside a 76.2 m buffer. 3 decimals
# of latitude is ~111 m, already coarser than the buffer; 4 is ~11 m.
MIN_USEFUL_DECIMALS = 4


def decimals(s: pd.Series) -> pd.Series:
    return s.astype(str).str.split(".").str[1].fillna("").str.len()


def audit(df: pd.DataFrame, source_name: str, top_cities: int) -> dict:
    n = len(df)
    out: dict = {"source": source_name, "n_crashes": int(n)}

    # ── 1. coverage ─────────────────────────────────────────────────────────────
    ok = df["lat"].between(-90, 90) & df["lon"].between(-180, 180)
    ok &= df["lat"].notna() & df["lon"].notna()
    out["coord_coverage"] = round(float(ok.mean()), 4)
    out["n_missing_coords"] = int((~ok).sum())

    good = df[ok]

    # ── 2. precision ────────────────────────────────────────────────────────────
    d = decimals(good["lat"])
    out["decimal_places"] = {str(k): int(v) for k, v in d.value_counts().sort_index().items()}
    out["pct_at_or_above_4_decimals"] = round(float((d >= MIN_USEFUL_DECIMALS).mean()), 4)

    # ── 3. snapping ─────────────────────────────────────────────────────────────
    dup = good.duplicated(subset=["lat", "lon"], keep=False)
    out["pct_duplicate_coords"] = round(float(dup.mean()), 4)
    counts = good.groupby(["lat", "lon"]).size()
    out["max_crashes_at_one_coord"] = int(counts.max()) if len(counts) else 0

    # ── 4. volume by city ───────────────────────────────────────────────────────
    if good["place_name"].notna().any():
        place = good["place_name"].astype(str)
        named = good[place.str.upper().ne("NOT APPLICABLE") & place.ne("nan") & place.ne("<NA>")]
        key = (named["place_name"].astype(str).str.title()
               + ", " + named["state_name"].astype(str))
        vc = key.value_counts()
        out["n_cities"] = int(len(vc))
        out["n_cities_above_min"] = int((vc >= MIN_VIABLE_CRASHES).sum())
        out["min_viable_threshold"] = MIN_VIABLE_CRASHES
        out["top_cities"] = {k: int(v) for k, v in vc.head(top_cities).items()}

    # ── verdict ─────────────────────────────────────────────────────────────────
    problems = []
    if out["coord_coverage"] < 0.80:
        problems.append(
            f"coordinate coverage {out['coord_coverage']:.1%} is low — check whether "
            "this source has a second, better geocode field"
        )
    if out["pct_at_or_above_4_decimals"] < 0.50:
        problems.append(
            f"only {out['pct_at_or_above_4_decimals']:.1%} of coordinates carry >=4 "
            "decimal places; below that, resolution is coarser than the 76.2 m buffer"
        )
    if out["pct_duplicate_coords"] > 0.20:
        problems.append(
            f"{out['pct_duplicate_coords']:.1%} of crashes share an exact coordinate — "
            "likely centroid snapping, which makes intersection assignment unreliable"
        )
    out["problems"] = problems
    out["verdict"] = "USABLE" if not problems else "REVIEW REQUIRED"
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--adapter", help="adapter name (fars, switrs)")
    ap.add_argument("--raw-dir", help="source directory; defaults to data/raw/<adapter>")
    ap.add_argument("--region", help="audit through a region config instead")
    ap.add_argument("--intersection-only", action="store_true",
                    help="count only crashes the source marks intersection-related")
    ap.add_argument("--top-cities", type=int, default=25)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from src.ingest.adapters import get_adapter

    filters: dict = {}
    if args.region:
        from src.ingest.region import Region
        region = Region.load(args.region)
        adapter_name = region.adapter
        filters = dict(region.source_filters)
        label = f"{region.display_name} [{adapter_name}]"
    elif args.adapter:
        adapter_name = args.adapter
        label = adapter_name
    else:
        ap.error("pass --adapter or --region")

    raw_dir = Path(args.raw_dir) if args.raw_dir else ROOT / "data" / "raw" / adapter_name
    if args.intersection_only:
        filters["intersection_only"] = True

    print(f"Auditing {label}\n  raw_dir: {raw_dir}\n  filters: {filters}\n")

    src = get_adapter(adapter_name).load(raw_dir, **filters)
    result = audit(src.crashes, src.source_name, args.top_cities)
    result["severity_scheme"] = src.severity_scheme
    result["supports_ksi"] = src.supports_ksi
    result["label_name"] = src.label_name()
    result["available_flags"] = sorted(src.available_flags)
    result["unavailable_flags"] = src.quality.get("unavailable_flags", [])
    result["filters"] = {k: str(v) for k, v in filters.items()}

    print(f"\n{'=' * 70}")
    print(f"VERDICT: {result['verdict']}")
    print("=" * 70)
    print(f"  crashes                {result['n_crashes']:,}")
    print(f"  label                  {result['label_name']} "
          f"(scheme: {result['severity_scheme']})")
    print(f"  coordinate coverage    {result['coord_coverage']:.2%}")
    print(f"  >=4 decimal places     {result['pct_at_or_above_4_decimals']:.2%}")
    print(f"  duplicate coordinates  {result['pct_duplicate_coords']:.2%} "
          f"(max {result['max_crashes_at_one_coord']} at one point)")
    if "n_cities_above_min" in result:
        print(f"  cities with >={MIN_VIABLE_CRASHES} crashes  "
              f"{result['n_cities_above_min']:,} of {result['n_cities']:,}")
    if result["unavailable_flags"]:
        print(f"  UNAVAILABLE features   {', '.join(result['unavailable_flags'])}")
    for p in result["problems"]:
        print(f"  ! {p}")

    if result.get("top_cities"):
        print(f"\n  Top {min(args.top_cities, len(result['top_cities']))} cities:")
        for city, cnt in list(result["top_cities"].items())[:args.top_cities]:
            print(f"    {cnt:6,}  {city}")

    REPORTS.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS / f"crash_source_audit_{src.source_name}.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(f"\nWrote {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
