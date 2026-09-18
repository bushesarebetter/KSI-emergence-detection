"""Candidate-structure (spatial-neighbor) features.

For each intersection, summarize the surrounding area over the FEATURE window only
(leakage-safe): local crash pressure, proximity/adjacency to the City's >=5-crash
High Crash List sites, and street-grid density. These complement the per-site
crash-history features with signal the persistence baseline can't see -- an
intersection can be quiet itself yet sit one block from a dangerous corridor.

Leakage: every input is feature-window crashes (< feature_cutoff) and static node
geometry. Hotspot nodes are defined by feature-window counts, i.e. what the City's
screen would have seen at prediction time. No label-window data is touched.

Distances use a local equirectangular projection from lon/lat (metres); at San Diego
latitudes the error over <=400 m is well under a metre, so no GIS deps are needed and
this runs anywhere (including Colab) with only numpy/scipy/pandas.

Run:  python -m src.features.build_spatial_features [--feat-start YYYY-MM-DD --feat-end YYYY-MM-DD] [--out PATH]
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from src.utils import load_config, project_root

R_TIGHT = 150.0          # immediate-vicinity radius (m)
R_WIDE = 400.0           # corridor/area radius (m)
BUF_SNAP = 76.2          # crash->node assignment buffer (m), matches build_panel
CITY_SCREEN_MIN = 5      # >= this many feature-window crashes = on the City's screen
HOTSPOT_CAP_M = 2000.0   # cap the distance-to-hotspot feature


def _xy(lon: np.ndarray, lat: np.ndarray, lat0: float) -> np.ndarray:
    R = 6_371_000.0
    return np.column_stack([R * np.cos(lat0) * np.deg2rad(lon), R * np.deg2rad(lat)])


def build_spatial_features(cfg: dict, feat_start: pd.Timestamp, feat_end: pd.Timestamp) -> pd.DataFrame:
    root = project_root()
    proc = root / cfg["paths"]["proc"]

    nodes = pd.read_parquet(proc / "nodes_spine_2230.parquet",
                            columns=["intersection_id", "is_surface", "lon", "lat"])
    nodes = nodes[nodes["is_surface"]].reset_index(drop=True)

    cr = pd.read_parquet(proc / "crashes_4326.parquet",
                         columns=["date", "severity", "STATE_HWY_IND", "lon", "lat"])
    cr["date"] = pd.to_datetime(cr["date"])
    cr = cr[(cr["STATE_HWY_IND"].astype(str).str.upper() != "Y")
            & (cr["date"] >= feat_start) & (cr["date"] <= feat_end)]
    ksi = cr[cr["severity"].isin(cfg["labels"]["ksi_severity_codes"])]

    lat0 = np.deg2rad(float(nodes["lat"].mean()))
    nxy = _xy(nodes["lon"].values, nodes["lat"].values, lat0)
    cxy = _xy(cr["lon"].values, cr["lat"].values, lat0)
    kxy = _xy(ksi["lon"].values, ksi["lat"].values, lat0)

    node_tree = cKDTree(nxy)
    crash_tree = cKDTree(cxy) if len(cxy) else None
    ksi_tree = cKDTree(kxy) if len(kxy) else None

    # Per-node feature-window crash count (nearest-within-buffer) -> City-screen hotspots.
    # Also emitted as crashes_feat so downstream can define the <5 candidate set from this
    # one file (no re-snapping, no raw crash parquet needed).
    node_crashes = np.zeros(len(nodes), dtype=int)
    hotspot_xy = np.empty((0, 2))
    if crash_tree is not None:
        d, i = node_tree.query(cxy, k=1, workers=-1)
        within = d <= BUF_SNAP
        node_crashes = np.bincount(i[within], minlength=len(nodes))
        hotspot_xy = nxy[node_crashes >= CITY_SCREEN_MIN]
    hot_tree = cKDTree(hotspot_xy) if len(hotspot_xy) else None

    def n_within(tree, radius):
        if tree is None:
            return np.zeros(len(nodes), dtype=int)
        return tree.query_ball_point(nxy, radius, workers=-1, return_length=True)

    f = pd.DataFrame({"intersection_id": nodes["intersection_id"].values})
    f["crashes_feat"] = node_crashes                                  # for the <5 candidate screen
    f["nbr_crashes_150m"] = n_within(crash_tree, R_TIGHT)
    f["nbr_crashes_400m"] = n_within(crash_tree, R_WIDE)
    f["nbr_ksi_400m"] = n_within(ksi_tree, R_WIDE)
    f["node_density_400m"] = n_within(node_tree, R_WIDE) - 1          # exclude self
    f["n_hotspots_400m"] = n_within(hot_tree, R_WIDE)
    if hot_tree is not None:
        dh, _ = hot_tree.query(nxy, k=1, workers=-1)
        f["dist_nearest_hotspot_m"] = np.minimum(dh, HOTSPOT_CAP_M)
    else:
        f["dist_nearest_hotspot_m"] = HOTSPOT_CAP_M
    return f


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--feat-start", default=cfg["windows"]["feature_start"])
    ap.add_argument("--feat-end", default=cfg["windows"]["feature_end"])
    ap.add_argument("--out", default=str(project_root() / cfg["paths"]["model"] / "spatial_features.parquet"))
    a = ap.parse_args()
    feats = build_spatial_features(cfg, pd.Timestamp(a.feat_start), pd.Timestamp(a.feat_end))
    feats.to_parquet(a.out, index=False)
    print(f"wrote {a.out}: {len(feats)} rows, {feats.shape[1]-1} features "
          f"[{a.feat_start}..{a.feat_end}]")
    print(feats.drop(columns=['intersection_id']).describe().T[['mean', 'min', 'max']].to_string())


if __name__ == "__main__":
    main()
