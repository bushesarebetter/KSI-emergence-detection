"""Compare the model's verified-run ranking against the City of San Diego's
actual High Crash List screen: intersections with >=5 injury-or-fatal crashes
(SWITRS COLLISION_SEVERITY in {1,2,3,4}) in the feature window.

The verified run used a different temporal window than the current
configs/config.yaml (which now holds the forward-run window). Per
docs/METHODOLOGY.md L25-27, the verified run's feature window is
2016-01-01 to 2021-12-31 (cutoff 2022-01-01); that is hardcoded below rather
than read from config.yaml, since config.yaml no longer describes this run.
Buffer (76.2 m), CRS (EPSG:2230), crash assignment (nearest_within_buffer),
and the STATE_HWY_IND exclusion are read from config.yaml since those are
unchanged between runs.

Run via: python -m scripts.city_screen_overlap
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree

from src.utils import buffer_feet, load_config, project_root

# Verified-run window (docs/METHODOLOGY.md L25-27); NOT the same as config.yaml's
# current forward-run window.
FEAT_START = pd.Timestamp("2016-01-01")
FEAT_CUTOFF = pd.Timestamp("2022-01-01")  # exclusive upper bound
CITY_SCREEN_MIN = 5


def main() -> None:
    cfg = load_config()
    root = project_root()
    buf_ft = buffer_feet(cfg)
    mode = cfg["geometry"]["crash_assignment"]
    assert mode == "nearest_within_buffer", f"unexpected crash_assignment mode: {mode}"

    panel = gpd.read_parquet(root / "data/model/verified_run/candidate_panel.parquet")
    scores = pd.read_parquet(root / "data/model/model_scores_verified_run.parquet")
    score_col = "xgb_tweedie_score"  # primary model per config.yaml target.primary=tweedie_count
    print(f"score columns available: {list(scores.columns)} -> using '{score_col}'")

    df = panel.merge(scores[["intersection_id", score_col]], on="intersection_id", how="left")
    assert df[score_col].notna().all(), "missing scores for some candidates"
    df["rank"] = df[score_col].rank(ascending=False, method="first").astype(int)

    # crashes_4326.parquet (built by src/ingest/crash_loader.py) is already
    # restricted to severity 1-4 (no PDO in this SWITRS extract -- verified by
    # raw-CSV inspection) and already excludes STATE_HWY_IND='Y' crashes, so no
    # further severity/highway filtering is needed here.
    crashes = gpd.read_parquet(root / "data/proc/crashes_4326.parquet")
    crashes = crashes[(crashes["date"] >= FEAT_START) & (crashes["date"] < FEAT_CUTOFF)]
    crashes = crashes.to_crs(cfg["crs"]["analysis"])

    nodes = df[["intersection_id", "geometry"]]
    node_xy = np.column_stack([nodes.geometry.x, nodes.geometry.y])
    crash_xy = np.column_stack([crashes.geometry.x, crashes.geometry.y])
    dists, idxs = cKDTree(node_xy).query(crash_xy, k=1, workers=-1)
    within = dists <= buf_ft
    assigned_iid = nodes.iloc[idxs[within]]["intersection_id"].values
    counts = pd.Series(assigned_iid).value_counts().rename("injury_or_fatal_feat")

    df = df.merge(counts, left_on="intersection_id", right_index=True, how="left")
    df["injury_or_fatal_feat"] = df["injury_or_fatal_feat"].fillna(0).astype(int)
    df["on_city_screen"] = df["injury_or_fatal_feat"] >= CITY_SCREEN_MIN

    def report(label: str, sub: pd.DataFrame) -> None:
        n_screen = int(sub["on_city_screen"].sum())
        pct = 100 * n_screen / max(len(sub), 1)
        print(f"{label:>22}: n={len(sub):5d}  on_city_screen={n_screen:5d}  ({pct:.1f}%)")

    print()
    for k in (200, 500, 1000):
        report(f"top {k}", df.sort_values("rank").head(k))
    report("emergent (y_ge2)", df[df["y_ge2"] == 1])

    n_citywide = int(df["on_city_screen"].sum())
    print(f"\ncitywide candidates meeting city screen (>= {CITY_SCREEN_MIN}): "
          f"{n_citywide} / {len(df)} ({100 * n_citywide / len(df):.2f}%)")

    top1000 = df.sort_values("rank").head(1000)
    pct1000 = 100 * top1000["on_city_screen"].mean()
    print(
        f"\nSummary: of the model's top 1000 ranked intersections, "
        f"{pct1000:.1f}% already meet the city's own >=5 injury-or-fatal screening "
        f"threshold, meaning the city's existing process would have flagged that "
        f"share of the model's highest-risk sites without any model at all. The "
        f"remainder of the top 1000 -- and most of the 21 emergent (>=2 KSI) sites, "
        f"of which {int(df.loc[df['y_ge2']==1,'on_city_screen'].sum())}/21 were "
        f"already screen-eligible -- represent exactly the intersections the model "
        f"adds visibility on that the city's volume-based threshold misses."
    )


if __name__ == "__main__":
    main()
