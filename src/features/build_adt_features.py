"""Traffic-volume (ADT / exposure) features from City of San Diego open data.

Source: https://seshat.datasd.org/traffic_adt_counts/traffic_counts_datasd.csv
(City of San Diego "Traffic Volumes", ~2,535 geolocated count locations, adt_total).

For each intersection: aadt = the busiest count within a radius (max adt_total within
ADT_RADIUS_M), a proxy for the traffic exposure of the corridor it sits on. Missing where
no count is nearby (local streets), imputed by functional_class-group median with an
aadt_missing flag. log1p(aadt) is the model feature.

ADT is treated as a STATIC road attribute (like functional_class from current OSM): traffic
volume is a structural property of the road, slowly varying, not an endogenous response to
crashes. The public dump is a rolling recent window (2023+), so this is an exposure proxy for
the feature windows, not a time-stamped feature -- more mutable than geometry, less than a
crash count. Flag: adt_features are static/exposure, not leakage-walled like crash features.

Run:  python -m src.features.build_adt_features
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from src.utils import load_config, project_root

ADT_URL = "https://seshat.datasd.org/traffic_adt_counts/traffic_counts_datasd.csv"
ADT_RADIUS_M = 250.0


def _xy(lon, lat, lat0):
    R = 6_371_000.0
    return np.column_stack([R * np.cos(lat0) * np.deg2rad(lon), R * np.deg2rad(lat)])


def build_adt_features(nodes: pd.DataFrame, adt: pd.DataFrame, func_class: pd.Series | None = None) -> pd.DataFrame:
    """nodes: intersection_id, lon, lat. adt: lat, lng, adt_total. func_class: optional per-node."""
    lat0 = np.deg2rad(float(nodes["lat"].mean()))
    tree = cKDTree(_xy(adt["lng"].values, adt["lat"].values, lat0))
    nbrs = tree.query_ball_point(_xy(nodes["lon"].values, nodes["lat"].values, lat0), ADT_RADIUS_M, workers=-1)
    vals = adt["adt_total"].values
    aadt = np.array([vals[ix].max() if len(ix) else np.nan for ix in nbrs])

    out = pd.DataFrame({"intersection_id": nodes["intersection_id"].values, "aadt": aadt})
    out["aadt_missing"] = out["aadt"].isna().astype(int)

    # impute missing by functional_class-group median, else global median
    if func_class is not None:
        out["_fc"] = func_class.values
        gm = out.groupby("_fc")["aadt"].transform("median")
        out["aadt"] = out["aadt"].fillna(gm)
        out = out.drop(columns="_fc")
    out["aadt"] = out["aadt"].fillna(out["aadt"].median())
    out["log_aadt"] = np.log1p(out["aadt"])
    return out[["intersection_id", "aadt", "log_aadt", "aadt_missing"]]


def main() -> None:
    cfg = load_config()
    root = project_root()
    adt = pd.read_csv(ADT_URL) if False else pd.read_csv(root / "data/raw/adt/traffic_counts_datasd.csv")
    nodes = pd.read_parquet(root / cfg["paths"]["proc"] / "nodes_spine_2230.parquet",
                            columns=["intersection_id", "is_surface", "lon", "lat"])
    nodes = nodes[nodes["is_surface"]].reset_index(drop=True)
    feats = build_adt_features(nodes, adt)
    out = root / cfg["paths"]["model"] / "adt_features.parquet"
    feats.to_parquet(out, index=False)
    print(f"wrote {out}: {len(feats)} nodes | ADT present {int((feats.aadt_missing==0).sum())} "
          f"({100*(feats.aadt_missing==0).mean():.0f}%) | median aadt {feats.aadt.median():.0f}")


if __name__ == "__main__":
    main()
