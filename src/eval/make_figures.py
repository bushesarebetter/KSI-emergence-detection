"""Generate Milestone 1 figures.

Fig 1: Map of candidate nodes (blue) with excluded known-hotspot overlay (red).
Fig 2: Histogram of KSI_label count per node (candidate set only).
Fig 3: Candidate nodes coloured by spatial block.

Run via:  python -m src.eval.make_figures
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

from src.utils import load_config, project_root

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def _load_data(cfg: dict):
    proc = project_root() / cfg["paths"]["proc"]
    model_dir = project_root() / cfg["paths"]["model"]
    nodes = gpd.read_parquet(proc / "nodes_spine_2230.parquet")
    candidates = gpd.read_parquet(model_dir / "candidate_panel.parquet")
    return nodes, candidates


def fig1_candidate_map(nodes: gpd.GeoDataFrame, candidates: gpd.GeoDataFrame, out: Path) -> None:
    """Candidate nodes (blue) vs excluded hotspot nodes (red)."""
    cand_ids = set(candidates["intersection_id"])
    excluded = nodes[~nodes["intersection_id"].isin(cand_ids)]

    # Use 4326 geometry for plotting
    cand_4326 = candidates.set_geometry("geometry_4326").set_crs("EPSG:4326")
    excl_4326 = excluded.set_geometry("geometry_4326").set_crs("EPSG:4326") if "geometry_4326" in excluded.columns else excluded.to_crs("EPSG:4326")

    fig, ax = plt.subplots(figsize=(10, 9))
    cand_4326.plot(ax=ax, color="steelblue", markersize=1.5, alpha=0.5, label="Candidates")
    excl_4326.plot(ax=ax, color="crimson", markersize=3, alpha=0.8, label="Excluded (known hotspot)")
    ax.set_title("Fig 1 — SD Intersection Candidates vs Known Hotspots", fontsize=12)
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    ax.legend(markerscale=4, fontsize=9)
    plt.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info("Wrote %s", out)


def fig2_label_histogram(candidates: gpd.GeoDataFrame, out: Path) -> None:
    """Histogram of KSI_label count per candidate node."""
    ksi_label = candidates["KSI_label"].values
    fig, ax = plt.subplots(figsize=(8, 5))
    counts = np.arange(0, ksi_label.max() + 2)
    freq = [(ksi_label == k).sum() for k in counts]
    ax.bar(counts, freq, color="steelblue", edgecolor="white", width=0.8)
    ax.set_xlabel("KSI_label count (label window 2022–2024)")
    ax.set_ylabel("Number of candidate intersections")
    ax.set_title("Fig 2 — Distribution of label-window KSI crashes per candidate")
    n_pos = (ksi_label >= 2).sum()
    ax.axvline(2, color="crimson", linestyle="--", label=f"y=1 threshold (n={n_pos})")
    ax.legend()
    plt.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info("Wrote %s", out)


def fig3_spatial_blocks(candidates: gpd.GeoDataFrame, out: Path) -> None:
    """Candidate nodes coloured by spatial block."""
    if "spatial_block" not in candidates.columns:
        log.warning("spatial_block column not present; skipping Fig 3")
        return
    cand_4326 = candidates.set_geometry("geometry_4326").set_crs("EPSG:4326")
    n_blocks = cand_4326["spatial_block"].nunique()
    cmap = plt.get_cmap("tab20", min(n_blocks, 20))

    fig, ax = plt.subplots(figsize=(10, 9))
    for i, (block_id, grp) in enumerate(cand_4326.groupby("spatial_block")):
        grp.plot(ax=ax, color=cmap(i % 20), markersize=1.5, alpha=0.6)
    ax.set_title(f"Fig 3 — Spatial blocks ({n_blocks} blocks)", fontsize=12)
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    plt.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info("Wrote %s", out)


def main() -> None:
    cfg = load_config()
    reports = project_root() / cfg["paths"]["reports"]
    reports.mkdir(parents=True, exist_ok=True)

    nodes, candidates = _load_data(cfg)

    fig1_candidate_map(nodes, candidates, reports / "fig1_candidate_map.png")
    fig2_label_histogram(candidates, reports / "fig2_label_histogram.png")
    fig3_spatial_blocks(candidates, reports / "fig3_spatial_blocks.png")
    log.info("All figures written to %s", reports)


if __name__ == "__main__":
    main()
