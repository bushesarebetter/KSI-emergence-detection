"""Crash snapping, candidate eligibility, and label construction.

M3a changes vs M1/M2:
  - Coordinates: crashes loaded from POINT_X/POINT_Y in crash_loader (fixes M1/M2 bug).
    STATE_HWY_IND=Y crashes are excluded in crash_loader before this stage.
  - Buffer: 76.2 m primary (250 US survey feet); 30 m retained as sensitivity only.
  - Surface filter: only surface nodes (is_surface=True from build_spine) enter the
    candidate set.  Freeway nodes are excluded before any crash snapping.
  - Labels: all candidates have KSI_label count; binary @>=1 is the M3a secondary
    readout, @>=2 is the evaluation operating point. Build_panel writes both.

Crash -> node assignment rule (unchanged from M1):
  Nearest-within-buffer: one crash -> at most one node (avoids double-counting).

Candidate eligibility (2026-09: switched to the City-screen definition):
  Keep node i iff crashes_feat(i) < candidate_city_screen_min (default 5), i.e.
  the intersection is BELOW San Diego's High Crash List screen (>=5 injury-or-fatal
  crashes in the feature window) and therefore not something the City already reviews.
  The old rule (KSI_feat < 2 & not top-decile KSI density) is retained behind
  labels.candidate_screen='ksi_legacy' for sensitivity only. See docs/DECISIONS.md.

Run via:  python -m src.labels.build_panel
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

# geopandas imported lazily inside build_panel(): keeps the pure label logic
# (_apply_eligibility) importable without the heavy GIS stack.

from src.utils import buffer_feet, load_config, project_root

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _snap_crashes_to_nodes(
    crashes: gpd.GeoDataFrame,
    nodes: gpd.GeoDataFrame,
    buf_ft: float,
    mode: str,
) -> pd.DataFrame:
    """Return DataFrame with columns [intersection_id, crash_id]."""
    node_coords  = np.column_stack([nodes.geometry.x, nodes.geometry.y])
    crash_coords = np.column_stack([crashes.geometry.x, crashes.geometry.y])
    tree = cKDTree(node_coords)

    if mode == "nearest_within_buffer":
        dists, idxs = tree.query(crash_coords, k=1, workers=-1)
        within = dists <= buf_ft
        records = [
            {"intersection_id": nodes.iloc[idxs[i]]["intersection_id"],
             "crash_id": crashes.iloc[i]["id"]}
            for i in range(len(crashes)) if within[i]
        ]
    elif mode == "all_within_buffer":
        results = tree.query_ball_point(crash_coords, r=buf_ft, workers=-1)
        records = []
        for ci, node_indices in enumerate(results):
            for ni in node_indices:
                records.append({
                    "intersection_id": nodes.iloc[ni]["intersection_id"],
                    "crash_id": crashes.iloc[ci]["id"],
                })
    else:
        raise ValueError(f"Unknown crash_assignment mode: {mode!r}")

    return pd.DataFrame(records)


def _apply_eligibility(panel: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, str]:
    """Select the candidate universe: intersections currently invisible to the City.

    "city" (default): keep nodes below San Diego's High Crash List screen, i.e.
        crashes_feat < candidate_city_screen_min (>=5 injury-or-fatal crashes is
        what the City already reviews, so those are NOT the model's job to find).
    "ksi_legacy": the pre-2026-09 rule (KSI_feat < 2 and not top-decile KSI density),
        kept only so the old candidate set can be reproduced as a sensitivity row.
    """
    labels = cfg["labels"]
    mode = labels.get("candidate_screen", "city")
    if mode == "city":
        city_min = labels["candidate_city_screen_min"]
        eligible = panel["crashes_feat"] < city_min
        return panel[eligible].copy(), f"city screen: crashes_feat < {city_min}"
    if mode == "ksi_legacy":
        max_ksi_feat = labels["candidate_max_ksi_feat"]
        top_decile = labels["candidate_top_decile_drop"]
        c1 = panel["KSI_feat"] < max_ksi_feat
        pct_90 = float(np.percentile(panel["KSI_feat"].values, (1.0 - top_decile) * 100.0))
        c2 = panel["KSI_feat"] <= pct_90
        return panel[c1 & c2].copy(), f"legacy KSI: KSI_feat<{max_ksi_feat} & <=p90({pct_90:.1f})"
    raise ValueError(f"unknown labels.candidate_screen: {mode!r} (expected 'city' or 'ksi_legacy')")


def build_panel(cfg: dict) -> pd.DataFrame:
    import geopandas as gpd  # lazy: only the full pipeline needs GIS deps

    proc      = project_root() / cfg["paths"]["proc"]
    model_dir = project_root() / cfg["paths"]["model"]
    model_dir.mkdir(parents=True, exist_ok=True)

    crs_a     = cfg["crs"]["analysis"]
    buf_ft    = buffer_feet(cfg)
    mode      = cfg["geometry"]["crash_assignment"]
    ksi_codes = cfg["labels"]["ksi_severity_codes"]
    surface_only  = cfg.get("geometry", {}).get("surface_street_only", True)  # eligibility params read in _apply_eligibility

    feat_start  = pd.Timestamp(cfg["windows"]["feature_start"])
    feat_end    = pd.Timestamp(cfg["windows"]["feature_end"])
    cutoff      = pd.Timestamp(cfg["windows"]["feature_cutoff_date"])
    label_start = pd.Timestamp(cfg["windows"]["label_start"])
    label_end   = pd.Timestamp(cfg["windows"]["label_end"])

    # Load spine (includes is_surface tag from M3a build_spine)
    nodes = gpd.read_parquet(proc / "nodes_spine_2230.parquet")
    log.info("Loaded %d nodes from spine", len(nodes))

    # Surface filter: exclude freeway nodes from candidate universe
    if surface_only and "is_surface" in nodes.columns:
        n_before = len(nodes)
        nodes = nodes[nodes["is_surface"]].copy()
        log.info(
            "Surface filter: %d -> %d nodes (%d freeway excluded)",
            n_before, len(nodes), n_before - len(nodes),
        )
    elif surface_only:
        log.warning(
            "surface_street_only=True but 'is_surface' column absent from spine -- "
            "rebuild the spine to enable freeway exclusion"
        )

    # Load crashes (STATE_HWY_IND=Y already excluded by crash_loader if configured)
    crashes_all = gpd.read_parquet(proc / "crashes_4326.parquet")
    crashes_all = crashes_all.to_crs(crs_a)
    log.info("Loaded %d crash records (post-loader filters)", len(crashes_all))

    # Filter to KSI
    ksi_all = crashes_all[crashes_all["severity"].isin(ksi_codes)].copy()
    log.info("KSI crashes (severity in %s): %d", ksi_codes, len(ksi_all))

    # Split by date window (hard leakage wall)
    ksi_feat = ksi_all[
        (ksi_all["date"] >= feat_start) & (ksi_all["date"] <= feat_end)
    ].copy()
    ksi_label = ksi_all[
        (ksi_all["date"] >= label_start) & (ksi_all["date"] <= label_end)
    ].copy()

    if (ksi_feat["date"] >= cutoff).any():
        raise ValueError(
            "LEAKAGE: feature-window KSI records dated on/after feature_cutoff_date!"
        )

    log.info(
        "Feature-window KSI: %d   Label-window KSI: %d",
        len(ksi_feat), len(ksi_label),
    )

    # Snap crashes to surface nodes
    log.info("Snapping feature-window crashes (mode=%s, buf=%.2f ft) ...", mode, buf_ft)
    feat_assignments = _snap_crashes_to_nodes(ksi_feat, nodes, buf_ft, mode)
    ksi_feat_counts  = feat_assignments.groupby("intersection_id").size().rename("KSI_feat")

    log.info("Snapping label-window crashes ...")
    label_assignments = _snap_crashes_to_nodes(ksi_label, nodes, buf_ft, mode)
    ksi_label_counts  = label_assignments.groupby("intersection_id").size().rename("KSI_label")

    # All-severity feature-window crashes for the City-screen eligibility rule.
    # crashes_all is already severity 1-4 (injury-or-fatal), so this count IS the
    # City's ">=5 injury-or-fatal" screen input.
    crashes_feat = crashes_all[
        (crashes_all["date"] >= feat_start) & (crashes_all["date"] <= feat_end)
    ].copy()
    feat_all_assignments = _snap_crashes_to_nodes(crashes_feat, nodes, buf_ft, mode)
    crashes_feat_counts  = feat_all_assignments.groupby("intersection_id").size().rename("crashes_feat")

    # Build panel
    keep_cols = ["intersection_id", "lon", "lat", "geometry"]
    if "geometry_4326" in nodes.columns:
        keep_cols.append("geometry_4326")
    if "is_trunk_borderline" in nodes.columns:
        keep_cols.append("is_trunk_borderline")
    panel = nodes[keep_cols].copy()
    panel = panel.merge(ksi_feat_counts,     on="intersection_id", how="left")
    panel = panel.merge(ksi_label_counts,    on="intersection_id", how="left")
    panel = panel.merge(crashes_feat_counts, on="intersection_id", how="left")
    panel["KSI_feat"]     = panel["KSI_feat"].fillna(0).astype(int)
    panel["KSI_label"]    = panel["KSI_label"].fillna(0).astype(int)
    panel["crashes_feat"] = panel["crashes_feat"].fillna(0).astype(int)

    log.info(
        "Before eligibility: %d nodes | KSI_feat>0: %d | KSI_label>0: %d | KSI_label>=2: %d",
        len(panel),
        (panel["KSI_feat"] > 0).sum(),
        (panel["KSI_label"] > 0).sum(),
        (panel["KSI_label"] >= 2).sum(),
    )

    # Candidate eligibility: intersections currently invisible to the City screen.
    candidates, elig_desc = _apply_eligibility(panel, cfg)
    log.info(
        "Eligibility [%s]: %d nodes -> %d candidates (%d excluded as already screen-visible)",
        elig_desc, len(panel), len(candidates), len(panel) - len(candidates),
    )

    # Label columns
    candidates["y_ge2"] = (candidates["KSI_label"] >= 2).astype(int)  # 22 positives
    candidates["y_ge1"] = (candidates["KSI_label"] >= 1).astype(int)  # 391 positives
    # Keep 'y' as M1/M2 compat alias = y_ge2
    candidates["y"] = candidates["y_ge2"]

    n_pos2 = candidates["y_ge2"].sum()
    n_pos1 = candidates["y_ge1"].sum()
    log.info(
        "Candidates: %d | pos@>=2: %d (%.4f%%) | pos@>=1: %d (%.4f%%)",
        len(candidates),
        n_pos2, 100 * n_pos2 / max(len(candidates), 1),
        n_pos1, 100 * n_pos1 / max(len(candidates), 1),
    )

    # Re-scope trigger (informational only -- M3a already uses Tweedie primary)
    POSITIVE_THRESHOLD = 300
    if n_pos1 < POSITIVE_THRESHOLD:
        log.warning(
            "GATE ADVISORY: pos@>=1 (%d) < 300 adequacy bar. "
            "Signal validation may be unreliable.",
            n_pos1,
        )
    else:
        log.info(
            "Adequacy bar (>=1): %d positives >= %d threshold. OK.",
            n_pos1, POSITIVE_THRESHOLD,
        )

    if n_pos2 < 150:
        log.info(
            "pos@>=2 = %d < 150 (evaluation operating point, not training label). "
            "Expect wide CIs on @>=2 metrics.",
            n_pos2,
        )

    out_path = model_dir / "candidate_panel.parquet"
    candidates.to_parquet(out_path, index=False)
    log.info("Wrote candidate panel to %s", out_path)

    # Audit artifacts
    feat_assignments.to_parquet(proc / "feat_crash_assignments.parquet", index=False)
    label_assignments.to_parquet(proc / "label_crash_assignments.parquet", index=False)
    ksi_feat.to_parquet(proc / "ksi_feat_crashes.parquet", index=False)
    ksi_label.to_parquet(proc / "ksi_label_crashes.parquet", index=False)

    return candidates


def main() -> None:
    cfg = load_config()
    build_panel(cfg)


if __name__ == "__main__":
    main()
