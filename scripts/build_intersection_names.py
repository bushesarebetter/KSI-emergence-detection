"""Build intersection_names.csv from the OSM graph and the node spine.

Labelling logic lives in src/gis/intersection_names.py so the same rules are
shared with scripts/refine_intersection_names.py (which patches already-exported
dashboard data from live OSM when the pipeline cannot be re-run). See that
module's docstring for the rules and for why an unnamed cross road is described
("& alley") rather than borrowed from a neighbouring node.
"""
import pickle
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.gis.intersection_names import (
    build_generic_tokens,
    build_name_index,
    label_for_nodes,
)
from src.utils import load_config, project_root


def load_graph(cfg: dict) -> tuple:
    root = project_root()
    graph_path = root / cfg["paths"]["proc"] / "osm_graph.pkl"
    spine_path = root / cfg["paths"]["proc"] / "nodes_spine_2230.parquet"

    # pickle is acceptable here: osm_graph.pkl is produced by this repo's own
    # src/ingest/osm_loader.py in the previous pipeline stage and lives in the
    # gitignored data/proc/ -- it is never downloaded or user-supplied.
    with open(graph_path, "rb") as f:
        G = pickle.load(f)

    spine = pd.read_parquet(spine_path, columns=["osm_id", "osm_id_members", "intersection_id"])
    return G, spine


def resolve_names(G, spine: pd.DataFrame, name_index: dict, generic_tokens: set[str]) -> tuple[pd.DataFrame, Counter]:
    records, methods = [], Counter()
    for _, row in spine.iterrows():
        iid = row["intersection_id"]
        member_str = str(row["osm_id_members"]) if pd.notna(row["osm_id_members"]) else str(row["osm_id"])
        members = [int(x.strip()) for x in member_str.split(",") if x.strip()]

        label, method = label_for_nodes(
            G, members, name_index, generic_tokens, fallback="Intersection " + iid[:8]
        )
        methods[method] += 1
        records.append({"intersection_id": iid, "intersection_name": label})

    return pd.DataFrame(records), methods


def main() -> None:
    try:
        cfg = load_config()
        root = project_root()

        G, spine = load_graph(cfg)
        name_index = build_name_index(G)
        generic_tokens = build_generic_tokens(name_index)
        names_df, methods = resolve_names(G, spine, name_index, generic_tokens)

        # Name EVERY spine node, not only the model's candidates. The combined
        # export (build_export_panel_verified.py --combined N) also publishes
        # known-KSI and City-screen sites, which lie outside the candidate set
        # by construction and would otherwise come out as "Unnamed intersection".
        n_candidates = None
        candidate_path = root / cfg["paths"]["model"] / "candidate_panel.parquet"
        if candidate_path.exists():
            cand_ids = set(
                pd.read_parquet(candidate_path, columns=["intersection_id"])["intersection_id"].astype(str)
            )
            n_candidates = int(names_df["intersection_id"].astype(str).isin(cand_ids).sum())

        out_path = root / cfg["paths"]["proc"] / "intersection_names.csv"
        names_df.to_csv(out_path, index=False)

        print(f"Intersection names built: {len(names_df)} spine nodes"
              + (f" ({n_candidates:,} are model candidates)" if n_candidates is not None else ""))
        for method in ("cross", "unnamed_cross", "single", "fallback"):
            print(f"  {method:14s} {methods.get(method, 0):>7,}")
        print(f"-> {out_path}")
        sys.exit(0)
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
