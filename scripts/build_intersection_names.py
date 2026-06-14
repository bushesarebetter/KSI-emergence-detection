import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.utils import load_config, project_root

GENERIC_TOKEN_THRESHOLD = 40_000


def load_graph(cfg: dict) -> tuple:
    root = project_root()
    graph_path = root / cfg["paths"]["proc"] / "osm_graph.pkl"
    spine_path = root / cfg["paths"]["proc"] / "nodes_spine_2230.parquet"

    with open(graph_path, "rb") as f:
        G = pickle.load(f)

    spine = pd.read_parquet(spine_path, columns=["osm_id", "osm_id_members", "intersection_id"])
    return G, spine


def build_name_index(G) -> dict[int, set[str]]:
    index: dict[int, set[str]] = {}
    for n in G.nodes():
        names: set[str] = set()
        all_edges = list(G.edges(n, data=True)) + list(G.in_edges(n, data=True))
        for edge in all_edges:
            raw = edge[2].get("name")
            if raw is None:
                continue
            if isinstance(raw, list):
                candidates = raw
            elif isinstance(raw, str):
                candidates = [raw]
            else:
                continue
            for candidate in candidates:
                stripped = candidate.strip()
                if stripped:
                    names.add(stripped)
        index[n] = names
    return index


def build_generic_tokens(name_index: dict[int, set[str]]) -> set[str]:
    freq: dict[str, int] = {}
    for names in name_index.values():
        for name in names:
            freq[name] = freq.get(name, 0) + 1
    return {name for name, count in freq.items() if count > GENERIC_TOKEN_THRESHOLD}


def resolve_names(
    spine: pd.DataFrame,
    name_index: dict[int, set[str]],
    generic_tokens: set[str],
) -> pd.DataFrame:
    records = []
    for _, row in spine.iterrows():
        iid = row["intersection_id"]
        member_str = str(row["osm_id_members"]) if pd.notna(row["osm_id_members"]) else str(row["osm_id"])
        members = [int(x.strip()) for x in member_str.split(",") if x.strip()]

        all_names: set[str] = set()
        for osm_id in members:
            all_names |= name_index.get(osm_id, set())

        filtered = [n for n in all_names if n not in generic_tokens]
        filtered.sort(key=len, reverse=True)

        seen: list[str] = []
        for name in filtered:
            if name not in seen:
                seen.append(name)

        top2 = seen[:2]
        if len(top2) == 2:
            label = " & ".join(sorted(top2))
        elif len(top2) == 1:
            label = top2[0]
        else:
            label = "Intersection " + iid[:8]

        records.append({"intersection_id": iid, "intersection_name": label})

    return pd.DataFrame(records)


def main() -> None:
    try:
        cfg = load_config()
        root = project_root()

        G, spine = load_graph(cfg)
        name_index = build_name_index(G)
        generic_tokens = build_generic_tokens(name_index)
        names_df = resolve_names(spine, name_index, generic_tokens)

        candidate_path = root / cfg["paths"]["model"] / "candidate_panel.parquet"
        candidates = pd.read_parquet(candidate_path, columns=["intersection_id"])
        names_df = names_df.merge(candidates, on="intersection_id", how="inner")

        fallback_count = names_df["intersection_name"].str.startswith("Intersection ").sum()
        osm_count = len(names_df) - fallback_count

        out_path = root / cfg["paths"]["proc"] / "intersection_names.csv"
        names_df.to_csv(out_path, index=False)

        print(
            f"Intersection names built: {len(names_df)} nodes | "
            f"{osm_count} with OSM street names | {fallback_count} fallbacks"
        )
        print(f"-> {out_path}")
        sys.exit(0)
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
