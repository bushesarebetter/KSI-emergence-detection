"""Honest, like-for-like model-vs-city comparison for the verified run
(2022-2024 label window, 21 emergent sites at >=2 KSI).

Corrections vs. scripts/city_screen_overlap.py:
  (A) Ranks come from genuine out-of-fold scores (data/model/verified_run/
      oof_scores.parquet, column oof_score_random), not the in-sample
      xgb_tweedie_score used previously. Verified against
      results/oof_verified_run_results.json: random-split OOF recall@500 for
      >=2 KSI is reported there as 10/21 -- recomputing rank from
      oof_score_random and counting (rank<=500) for y_ge2==1 reproduces
      exactly 10/21, confirming this is the canonical per-row OOF score.
      (oof_score_spatial gives 9/21 at top-500 -- the spatial-block split
      reported alongside it -- and is not used here since the user asked for
      "the" canonical OOF ranking, i.e. the random-split one matching 10/21.)
  (B) The city screen is recomputed at three temporal granularities instead
      of only the 6-year feature window.

Per docs/METHODOLOGY.md L25-27, the verified run's feature window is
2016-01-01 to 2021-12-31 (cutoff 2022-01-01) -- config.yaml's windows.* keys
now hold the *forward* run's window (2016-2024 / 2025-2027) and do not apply
to this archived run, exactly as in the previous script. The specific years
for the three screen definitions (2021; 2019-2021; 2016-2021) are therefore
taken from the request / METHODOLOGY.md, not from config.yaml. Buffer, CRS,
crash-assignment mode, and the state-highway exclusion ARE read from
config.yaml since those are unchanged between runs.

crashes_4326.parquet (src/ingest/crash_loader.py) already excludes
STATE_HWY_IND='Y' crashes and already contains only severity 1-4 (this
SWITRS extract has no PDO records at all -- verified by inspecting the raw
CSV), so it is exactly the injury-or-fatal, surface-street universe with no
further filtering needed.

Run via: python -m scripts.city_screen_overlap_oof
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree

from src.utils import buffer_feet, load_config, project_root

CITY_SCREEN_MIN = 5
SCREEN_WINDOWS = {
    "screen_2021": [(pd.Timestamp("2021-01-01"), pd.Timestamp("2022-01-01"))],
    "screen_any_single_year": [
        (pd.Timestamp("2019-01-01"), pd.Timestamp("2020-01-01")),
        (pd.Timestamp("2020-01-01"), pd.Timestamp("2021-01-01")),
        (pd.Timestamp("2021-01-01"), pd.Timestamp("2022-01-01")),
    ],
    "screen_6yr": [(pd.Timestamp("2016-01-01"), pd.Timestamp("2022-01-01"))],
}


def _snap_count(crashes: gpd.GeoDataFrame, node_xy: np.ndarray,
                 iids: np.ndarray, buf_ft: float, start: pd.Timestamp,
                 end: pd.Timestamp) -> pd.Series:
    """Counts of crashes-in-[start,end) snapped nearest-within-buffer, per node."""
    sub = crashes[(crashes["date"] >= start) & (crashes["date"] < end)]
    if len(sub) == 0:
        return pd.Series(dtype=int)
    crash_xy = np.column_stack([sub.geometry.x, sub.geometry.y])
    dists, idxs = cKDTree(node_xy).query(crash_xy, k=1, workers=-1)
    within = dists <= buf_ft
    return pd.Series(iids[idxs[within]]).value_counts()


def main() -> None:
    cfg = load_config()
    root = project_root()
    buf_ft = buffer_feet(cfg)
    mode = cfg["geometry"]["crash_assignment"]
    assert mode == "nearest_within_buffer", f"unexpected crash_assignment mode: {mode}"

    oof = pd.read_parquet(root / "data/model/verified_run/oof_scores.parquet")
    panel = gpd.read_parquet(root / "data/model/verified_run/candidate_panel.parquet")
    print("oof_scores.parquet columns:", list(oof.columns))
    score_col = "oof_score_random"
    print(f"using '{score_col}' for OOF rank (reproduces 10/21 @top-500 from "
          f"results/oof_verified_run_results.json random['>=2']['500'])")

    df = panel.merge(oof[[score_col, "intersection_id"]], on="intersection_id", how="left")
    assert df[score_col].notna().all(), "missing OOF scores for some candidates"
    df["oof_rank"] = df[score_col].rank(ascending=False, method="first").astype(int)

    check = int((df.loc[df["y_ge2"] == 1, "oof_rank"] <= 500).sum())
    assert check == 10, f"sanity check failed: got {check}/21 @top-500, expected 10/21"

    crashes = gpd.read_parquet(root / "data/proc/crashes_4326.parquet")
    crashes = crashes.to_crs(cfg["crs"]["analysis"])
    node_xy = np.column_stack([df.geometry.x, df.geometry.y])
    iids = df["intersection_id"].values

    for name, windows in SCREEN_WINDOWS.items():
        counts = pd.Series(0, index=df["intersection_id"], dtype=int)
        if name == "screen_any_single_year":
            max_count = pd.Series(0, index=df["intersection_id"], dtype=int)
            for start, end in windows:
                c = _snap_count(crashes, node_xy, iids, buf_ft, start, end)
                max_count = max_count.combine(c.reindex(max_count.index, fill_value=0), max)
            counts = max_count
        else:
            (start, end), = windows
            c = _snap_count(crashes, node_xy, iids, buf_ft, start, end)
            counts = c.reindex(counts.index, fill_value=0)
        df[f"{name}_count"] = df["intersection_id"].map(counts).fillna(0).astype(int)
        df[name] = df[f"{name}_count"] >= CITY_SCREEN_MIN

    print()
    for name in SCREEN_WINDOWS:
        n = int(df[name].sum())
        print(f"citywide candidates meeting {name}: {n} / {len(df)} ({100*n/len(df):.2f}%)")

    emergent = df[df["y_ge2"] == 1].copy()
    print("\n=== model (OOF rank) vs city screen, 21 emergent sites ===")
    rows = []
    for k in (200, 500, 1000):
        caught = emergent[emergent["oof_rank"] <= k]
        row = {"top_k": k, "model_catches": len(caught)}
        for name in SCREEN_WINDOWS:
            missed_by_city = caught[~caught[name]]
            row[f"{name}_model_unique_n"] = len(missed_by_city)
            row[f"{name}_model_unique_detail"] = "; ".join(
                f"rank={r.oof_rank} count={getattr(r, f'{name}_count')}"
                for r in missed_by_city.itertuples()
            )
        rows.append(row)
    table = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(table.to_string(index=False))

    out_cols = [
        "intersection_id", "y_ge2", "oof_score_random", "oof_rank",
        "screen_2021_count", "screen_2021",
        "screen_any_single_year_count", "screen_any_single_year",
        "screen_6yr_count", "screen_6yr",
    ]
    out_path = root / "results/city_screen_overlap_oof.csv"
    df[out_cols].to_csv(out_path, index=False)
    print(f"\nwrote {out_path}")

    print("\n--- summary (OOF rank x single-year screen) ---")
    for k in (200, 500, 1000):
        caught = emergent[emergent["oof_rank"] <= k]
        n_unique = int((~caught["screen_any_single_year"]).sum())
        print(
            f"At top-{k} by genuine OOF rank, the model flags {len(caught)} of the 21 "
            f"emergent sites; {n_unique} of those would NOT have been on the city's own "
            f"single-year (>=5 in 2019, 2020, or 2021) screen."
        )


if __name__ == "__main__":
    main()
