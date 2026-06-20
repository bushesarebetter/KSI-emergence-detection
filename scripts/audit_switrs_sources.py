"""
Audit all three SWITRS downloads and compare 20260615 vs 20260608.

Writes: reports/switrs_audit.json

Run from project root:
    python scripts/audit_switrs_sources.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SWITRS_BASE = ROOT / "data" / "raw" / "switrs"
REPORTS_DIR = ROOT / "reports"
OUT = REPORTS_DIR / "switrs_audit.json"

DIRS = ["20260608", "20260610", "20260615"]
KSI_CODES = {1, 2}


def load_dir(name: str) -> pd.DataFrame:
    for fname in ("Crashes.csv", "crashes.csv"):
        p = SWITRS_BASE / name / fname
        if p.exists():
            df = pd.read_csv(p, dtype=str, low_memory=False)
            df.columns = [c.strip() for c in df.columns]
            return df
    raise FileNotFoundError(f"No Crashes.csv in {SWITRS_BASE / name}")


def per_dir_stats(name: str, df: pd.DataFrame) -> dict:
    total = len(df)

    # Parse dates
    dates = pd.to_datetime(df["COLLISION_DATE"], errors="coerce")
    date_min = str(dates.min().date()) if not dates.isna().all() else None
    date_max = str(dates.max().date()) if not dates.isna().all() else None

    # Geocoding: POINT_X not null
    px = pd.to_numeric(df["POINT_X"], errors="coerce") if "POINT_X" in df.columns else pd.Series(dtype=float)
    pct_geocoded = round(px.notna().sum() / total * 100, 2) if total else 0

    # Freeway
    hwy = df["STATE_HWY_IND"] if "STATE_HWY_IND" in df.columns else pd.Series(dtype=str)
    pct_freeway = round((hwy == "Y").sum() / total * 100, 2) if total else 0

    # KSI
    sev = pd.to_numeric(df["COLLISION_SEVERITY"], errors="coerce") if "COLLISION_SEVERITY" in df.columns else pd.Series(dtype=float)
    ksi_mask = sev.isin(KSI_CODES)
    ksi_rows = int(ksi_mask.sum())

    # KSI by year
    df["_year"] = dates.dt.year
    ksi_by_year = {}
    for yr in range(2016, 2026):
        ksi_by_year[str(yr)] = int((ksi_mask & (df["_year"] == yr)).sum())

    # Top-5 CITY values
    city_col = "CITY" if "CITY" in df.columns else "JURIS"
    top_cities = df[city_col].value_counts().head(5).to_dict() if city_col in df.columns else {}

    return {
        "directory": name,
        "total_rows": total,
        "date_min": date_min,
        "date_max": date_max,
        "pct_geocoded": pct_geocoded,
        "pct_freeway": pct_freeway,
        "ksi_rows": ksi_rows,
        "ksi_by_year": ksi_by_year,
        "top5_city": {str(k): int(v) for k, v in top_cities.items()},
    }


def compare_dirs(df08: pd.DataFrame, df15: pd.DataFrame) -> dict:
    dates08 = pd.to_datetime(df08["COLLISION_DATE"], errors="coerce")
    dates15 = pd.to_datetime(df15["COLLISION_DATE"], errors="coerce")
    df08 = df08.copy()
    df15 = df15.copy()
    df08["_year"] = dates08.dt.year
    df15["_year"] = dates15.dt.year

    rows_by_year = {}
    total_08 = 0
    total_15 = 0
    for yr in range(2016, 2025):
        c08 = int((df08["_year"] == yr).sum())
        c15 = int((df15["_year"] == yr).sum())
        diff = c08 - c15
        pct_diff = round(abs(diff) / c08 * 100, 2) if c08 else None
        rows_by_year[str(yr)] = {"count_08": c08, "count_15": c15, "diff": diff, "pct_diff": pct_diff}
        total_08 += c08
        total_15 += c15

    overall_pct_diff = round(abs(total_08 - total_15) / total_08 * 100, 4) if total_08 else None

    # CASE_ID comparison for 2016-2024
    mask08 = df08["_year"].between(2016, 2024)
    mask15 = df15["_year"].between(2016, 2024)
    ids08 = set(df08.loc[mask08, "CASE_ID"].dropna())
    ids15 = set(df15.loc[mask15, "CASE_ID"].dropna())
    in_08_not_15 = len(ids08 - ids15)
    in_15_not_08 = len(ids15 - ids08)

    return {
        "rows_by_year_2016_2024": rows_by_year,
        "total_2016_2024_08": total_08,
        "total_2016_2024_15": total_15,
        "overall_pct_diff": overall_pct_diff,
        "case_id_in_08_not_15": in_08_not_15,
        "case_id_in_15_not_08": in_15_not_08,
    }


def main() -> None:
    frames = {}
    stats_list = []

    print("Loading SWITRS directories...")
    for name in DIRS:
        try:
            df = load_dir(name)
            frames[name] = df
            s = per_dir_stats(name, df)
            stats_list.append(s)
            print(f"  {name}: {s['total_rows']:,} rows  ({s['date_min']} to {s['date_max']})")
        except FileNotFoundError as e:
            print(f"  {name}: MISSING — {e}")

    print()
    print("=== 0A — Per-directory statistics ===")
    hdr = f"{'directory':<12} | {'rows':>7} | {'date_min':<12} | {'date_max':<12} | {'pct_geocod':>10} | {'pct_fwy':>7} | {'ksi_rows':>8}"
    print(hdr)
    print("-" * len(hdr))
    for s in stats_list:
        print(
            f"{s['directory']:<12} | {s['total_rows']:>7,} | {str(s['date_min']):<12} | "
            f"{str(s['date_max']):<12} | {s['pct_geocoded']:>9.2f}% | {s['pct_freeway']:>6.2f}% | {s['ksi_rows']:>8,}"
        )

    for s in stats_list:
        print(f"\n  Top-5 CITY for {s['directory']}: {s['top5_city']}")

    print()
    print("=== 0A — KSI by year ===")
    all_dirs = [s["directory"] for s in stats_list]
    print(f"{'year':<6} " + " ".join(f"{d:>10}" for d in all_dirs))
    for yr in range(2016, 2026):
        row = f"{yr:<6} "
        for s in stats_list:
            row += f"{s['ksi_by_year'].get(str(yr), 0):>10,}"
        print(row)

    if "20260608" in frames and "20260615" in frames:
        print()
        print("=== 0B — Deep comparison: 20260615 vs 20260608 (2016-2024 overlap) ===")
        cmp = compare_dirs(frames["20260608"], frames["20260615"])
        print(f"{'year':<6} | {'count_08':>9} | {'count_15':>9} | {'diff':>7} | {'pct_diff':>9}")
        print("-" * 50)
        for yr in range(2016, 2025):
            v = cmp["rows_by_year_2016_2024"][str(yr)]
            print(f"{yr:<6} | {v['count_08']:>9,} | {v['count_15']:>9,} | {v['diff']:>7,} | {str(v['pct_diff']) + '%':>9}")
        print(f"\n  Total 2016-2024: 20260608={cmp['total_2016_2024_08']:,}  20260615={cmp['total_2016_2024_15']:,}")
        print(f"  Overall pct_diff: {cmp['overall_pct_diff']:.4f}%")
        print(f"  CASE_IDs in 08 not 15: {cmp['case_id_in_08_not_15']:,}")
        print(f"  CASE_IDs in 15 not 08: {cmp['case_id_in_15_not_08']:,}")

        print()
        print("=== 0C — Decision ===")
        threshold = 2.0
        pct = cmp["overall_pct_diff"]
        if pct is not None and pct <= threshold:
            decision = "use_20260615"
            print(f"DECISION: 20260615 is clean. Safe to use for 2025 label data.")
            print(f"  ({pct:.4f}% row difference for 2016-2024 — within {threshold}% threshold)")

            # 2025 stats from 20260615
            df15 = frames["20260615"]
            dates15 = pd.to_datetime(df15["COLLISION_DATE"], errors="coerce")
            mask25 = dates15.dt.year == 2025
            px15 = pd.to_numeric(df15["POINT_X"], errors="coerce")
            geocoded_25 = int((mask25 & px15.notna()).sum())
            sev15 = pd.to_numeric(df15["COLLISION_SEVERITY"], errors="coerce")
            ksi_25 = int((mask25 & sev15.isin(KSI_CODES)).sum())
            ksi_geocoded_25 = int((mask25 & sev15.isin(KSI_CODES) & px15.notna()).sum())
            print(f"  2025 crashes (geocoded): {geocoded_25:,}")
            print(f"  2025 KSI events available: {ksi_25} (geocoded: {ksi_geocoded_25})")
        else:
            decision = "defer_2025"
            print(f"DECISION: 20260615 anomalous ({pct:.1f}% row difference for 2016-2024).")
            print("  Do not use for label data.")
            print("  Possible cause: different geographic filter or city boundary query.")
            print(f"  Top CITY comparison:")
            for s in stats_list:
                if s["directory"] in ("20260608", "20260615"):
                    print(f"    {s['directory']}: {s['top5_city']}")
            print("  Forward run will use 2016-2024 features from 20260608.")
            print("  Label evaluation deferred until clean 2025 SWITRS pull.")
    else:
        decision = "defer_2025"
        cmp = {}

    # Save audit JSON
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    audit = {
        "generated": "2026-06-16",
        "switrs_decision": decision,
        "per_directory": stats_list,
        "comparison_08_vs_15": cmp if "20260608" in frames and "20260615" in frames else None,
    }
    OUT.write_text(json.dumps(audit, indent=2))
    print(f"\nAudit written: {OUT}")
    print(f"SWITRS_DECISION = {decision}")


if __name__ == "__main__":
    main()
