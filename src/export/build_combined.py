"""Pipeline side of the combined list.

Builds the `known` and `screen` tiers from artefacts the pipeline already
writes, stacks them with the model's ranked candidates via
src/export/combined_list.py, restricts everything to City of San Diego limits,
and produces the export panel that scripts/export_predictions.py writes out.

Where each tier comes from
--------------------------
known   src/labels/build_panel.py assigns every KSI crash in the feature window
        to its nearest node within the buffer and saves the assignments for ALL
        spine nodes -- before candidate eligibility is applied -- as
        data/proc/feat_crash_assignments.parquet. Counting those per node gives
        every intersection that has already had a serious crash. Sites with a
        KSI in the LABEL window come from label_crash_assignments.parquet the
        same way, which is what lets a non-candidate row carry is_known_emergent.
screen  The City's rule -- five or more crashes in a year -- recomputed over the
        whole spine for the last full feature year, exactly as
        scripts/city_screen_overlap_oof.py does it for candidates: crashes
        snapped nearest-within-buffer, counted per node.

City restriction. The candidate set is already City-only (docs/DECISIONS.md
D11); the spine is county-wide. Known and screen sites are therefore filtered
to the council-district polygons BEFORE stacking, so the cut at N is taken over
City intersections only.

Nothing here can run without the pipeline artefacts, so the tiering itself is
kept pure in combined_list.py and tested there; this module is the glue.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from src.export.combined_list import SOURCE_PREDICTED, assemble_combined, composition
from src.utils import buffer_feet

CITY_SCREEN_MIN = 5
CATCH_KS = (50, 100, 200, 500, 800, 1000)

ID = "intersection_id"


# ── shared snap ─────────────────────────────────────────────────────────────────

def snap_counts(crashes_2230: gpd.GeoDataFrame, nodes_2230: gpd.GeoDataFrame, buf_ft: float,
                start: pd.Timestamp | None = None, end: pd.Timestamp | None = None) -> pd.Series:
    """Nearest-within-buffer crash counts per intersection_id, [start, end)."""
    sub = crashes_2230
    if start is not None:
        sub = sub[sub["date"] >= start]
    if end is not None:
        sub = sub[sub["date"] < end]
    if len(sub) == 0:
        return pd.Series(dtype=int)
    node_xy = np.column_stack([nodes_2230.geometry.x.values, nodes_2230.geometry.y.values])
    crash_xy = np.column_stack([sub.geometry.x.values, sub.geometry.y.values])
    dists, idxs = cKDTree(node_xy).query(crash_xy, k=1)
    within = dists <= buf_ft
    ids = nodes_2230[ID].astype(str).values[idxs[within]]
    return pd.Series(ids).value_counts()


def _assignment_counts(path: Path, name: str) -> pd.Series:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found -- run `python -m src.labels.build_panel` first")
    a = pd.read_parquet(path, columns=[ID])
    return a[ID].astype(str).value_counts().rename(name)


# ── tiers ───────────────────────────────────────────────────────────────────────

def build_known_tier(cfg: dict, root: Path, spine_2230: gpd.GeoDataFrame,
                     crashes_2230: gpd.GeoDataFrame) -> pd.DataFrame:
    """[intersection_id, ksi_history, crashes_history] for every node with >=1
    KSI crash in the feature window."""
    proc = root / cfg["paths"]["proc"]
    ksi = _assignment_counts(proc / "feat_crash_assignments.parquet", "ksi_history")
    df = ksi.reset_index().rename(columns={"index": ID})
    df.columns = [ID, "ksi_history"]

    fs = pd.Timestamp(cfg["windows"]["feature_start"])
    fe = pd.Timestamp(cfg["windows"]["feature_cutoff_date"])
    all_counts = snap_counts(crashes_2230, spine_2230, buffer_feet(cfg), fs, fe)
    df["crashes_history"] = df[ID].map(all_counts).fillna(0).astype(int)
    return df


def build_screen_tier(cfg: dict, spine_2230: gpd.GeoDataFrame,
                      crashes_2230: gpd.GeoDataFrame) -> pd.DataFrame:
    """[intersection_id, screen_count] for nodes the City rule flags in the
    last full feature year."""
    year_end = pd.Timestamp(cfg["windows"]["feature_cutoff_date"])
    year_start = year_end - pd.DateOffset(years=1)
    counts = snap_counts(crashes_2230, spine_2230, buffer_feet(cfg), year_start, year_end)
    flagged = counts[counts >= CITY_SCREEN_MIN]
    df = flagged.reset_index()
    df.columns = [ID, "screen_count"]
    return df


def label_window_ksi(cfg: dict, root: Path) -> pd.Series:
    """intersection_id -> KSI count in the label window, all spine nodes."""
    return _assignment_counts(root / cfg["paths"]["proc"] / "label_crash_assignments.parquet", "ksi_label_all")


# ── catch stats (model ranking only) ───────────────────────────────────────────

def model_catch_stats(merged: pd.DataFrame, rank_col: str = "rank") -> dict:
    """recall@K of the MODEL's ranking over its candidates, for meta.json. The
    combined list's own rank is not a prediction, so it is never scored."""
    emergent = merged["KSI_label"] >= 1
    total = int(emergent.sum())
    return {
        str(k): {"caught": int((emergent & (merged[rank_col] <= k)).sum()), "total": total}
        for k in CATCH_KS
    }


# ── assembly ────────────────────────────────────────────────────────────────────

def assemble_combined_panel(
    cfg: dict,
    root: Path,
    merged: gpd.GeoDataFrame,
    districts: gpd.GeoDataFrame | None,
    n: int,
    shap_map: dict[str, list[dict]],
    build_crash_history: Callable[[gpd.GeoDataFrame, dict, Path], dict],
    assign_council_districts: Callable[[gpd.GeoDataFrame, gpd.GeoDataFrame | None], gpd.GeoDataFrame],
    run_mode: str,
) -> tuple[pd.DataFrame, dict]:
    """Return (panel_df, meta).

    `merged` is the ranked candidate GeoDataFrame from build_export_panel_verified
    (rank, _score, percentile, oof_rank, KSI_label, crashes_72mo, feature columns,
    intersection_name, geometry in EPSG:2230, geometry_4326, lon, lat, osm_id).
    """
    proc = root / cfg["paths"]["proc"]
    spine = gpd.read_parquet(
        proc / "nodes_spine_2230.parquet",
        columns=[ID, "osm_id", "lon", "lat", "geometry", "geometry_4326"],
    )
    spine[ID] = spine[ID].astype(str)
    merged = merged.copy()
    merged[ID] = merged[ID].astype(str)

    crashes = gpd.read_parquet(proc / "crashes_4326.parquet").to_crs(cfg["crs"]["analysis"])

    logging.info("  combined: building known tier (KSI in feature window, all nodes)...")
    known = build_known_tier(cfg, root, spine, crashes)
    logging.info("  combined: building screen tier (>=%d crashes, last feature year)...", CITY_SCREEN_MIN)
    screen = build_screen_tier(cfg, spine, crashes)

    # City restriction for the non-candidate tiers: council district != 0.
    extra_ids = set(known[ID]) | set(screen[ID])
    extra_nodes = spine[spine[ID].isin(extra_ids)].copy()
    extra_nodes = assign_council_districts(extra_nodes, districts)
    in_city = set(extra_nodes.loc[extra_nodes["council_district"] != 0, ID])
    n_known_all, n_screen_all = len(known), len(screen)
    known = known[known[ID].isin(in_city)]
    screen = screen[screen[ID].isin(in_city)]
    logging.info("  combined: known %d (city %d) | screen %d (city %d)",
                 n_known_all, len(known), n_screen_all, len(screen))

    predicted = merged[[ID, "rank"]].rename(columns={"rank": "model_rank"})
    combined = assemble_combined(known, screen, predicted, n)
    comp = composition(combined)
    logging.info("  combined: %s", comp)

    # Node frame: candidates keep their computed columns; others come from the spine.
    cand_cols = [c for c in merged.columns if c not in ("geometry",)]
    cand = merged[cand_cols].copy()
    non_cand_ids = set(combined[ID]) - set(cand[ID])
    non_cand = spine[spine[ID].isin(non_cand_ids)].copy()
    non_cand = assign_council_districts(non_cand, districts)
    # Drop the spine geometry here: geometry is re-attached for ALL rows from the
    # spine below, and a pre-existing column would make that merge emit
    # geometry_x / geometry_y instead of one usable geometry.
    non_cand = pd.DataFrame(non_cand.drop(columns=["geometry"]))
    # Coordinates-only rows: no score, no percentile, no OOF rank, no features.
    for col in ("_score", "percentile", "oof_rank", "KSI_label", "crashes_72mo", "intersection_name"):
        if col not in non_cand.columns:
            non_cand[col] = np.nan

    nodes = pd.concat([cand, non_cand], ignore_index=True)
    nodes = nodes.merge(combined, on=ID, how="inner")
    nodes = gpd.GeoDataFrame(nodes.merge(spine[[ID, "geometry"]], on=ID, how="left"),
                             geometry="geometry", crs=spine.crs)

    # is_known_emergent for non-candidates: KSI in the label window from the
    # all-nodes assignments. Candidates already carry KSI_label.
    lbl = label_window_ksi(cfg, root)
    ksi_label_all = nodes[ID].map(lbl).fillna(0).astype(int)
    nodes["KSI_label"] = nodes["KSI_label"].fillna(ksi_label_all)

    # crashes_training: candidates use the model feature; others the feature-
    # window count computed for the known tier (recomputed here for screen rows).
    fs = pd.Timestamp(cfg["windows"]["feature_start"])
    fe = pd.Timestamp(cfg["windows"]["feature_cutoff_date"])
    hist_counts = snap_counts(crashes, nodes, buffer_feet(cfg), fs, fe)
    fallback_hist = nodes[ID].map(hist_counts).fillna(0)
    nodes["crashes_72mo"] = nodes["crashes_72mo"].fillna(fallback_hist)

    logging.info("  combined: crash history for %d nodes...", len(nodes))
    crash_history = build_crash_history(nodes, cfg, root)

    df = nodes.copy()
    df["node_id"] = df["osm_id"].fillna(0).astype("int64")
    df["tweedie_score"] = df["_score"].astype("float64")
    df["is_known_emergent"] = df["KSI_label"].fillna(0) >= 1
    df["is_crash_active"] = df["crashes_72mo"].fillna(0) > 0
    df["crashes_training"] = df["crashes_72mo"].fillna(0).round().astype("int64")
    df["crash_history_json"] = df[ID].map(lambda i: json.dumps(crash_history.get(str(i), [])))
    df["shap_json"] = df[ID].map(lambda i: json.dumps(shap_map.get(str(i), [])))
    df["model_rank"] = df["model_rank"].astype("Int64")

    keep = [
        ID, "node_id", "lon", "lat", "tweedie_score", "percentile", "rank",
        "council_district", "is_known_emergent", "oof_rank", "is_crash_active",
        "crashes_training", "crash_history_json", "shap_json",
        "source", "model_rank", "ksi_history", "screen_count", "city_screen",
    ]
    panel = df[keep].sort_values("rank").reset_index(drop=True)

    meta = {
        "run": run_mode,
        "list": "combined",
        "top_n": int(n),
        "candidates": int(len(merged)),
        "composition": comp,
        "tiers_before_cut": {"known_city": int(len(known)), "screen_city": int(len(screen)),
                             "predicted": int(len(predicted))},
        "catch": model_catch_stats(merged),
        "screen_rule": f">={CITY_SCREEN_MIN} crashes in {fe.year - 1}",
    }
    return panel, meta


def predicted_only_meta(merged: pd.DataFrame, run_mode: str, top_n: int) -> dict:
    """meta.json for the classic export, so the UI reads one shape either way."""
    return {
        "run": run_mode,
        "list": "predicted",
        "top_n": int(top_n),
        "candidates": int(len(merged)),
        "composition": {SOURCE_PREDICTED: int(min(top_n, len(merged))), "known": 0, "screen": 0},
        "catch": model_catch_stats(merged),
    }
