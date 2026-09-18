"""The combined "most unsafe intersections" list.

The model ranks only intersections with NO serious-crash history -- that is its
whole point: they are the sites the City's screening cannot see. But a resident
asking "is my corner dangerous?" also wants the corners where harm has already
happened. The combined list answers both, in three tiers, each row tagged with
the tier that admitted it so the model's contribution never dissolves into an
undifferentiated "unsafe":

    known      a fatal or serious-injury crash occurred here in the history window
    screen     the City's own rule (>=5 crashes in a year) flags it
    predicted  the model ranks it, and nothing above applied

Tiers are stacked, not blended: every known site outranks every screen-only
site, which outranks every model-only site. That is deliberately transparent.
A blended score would have to pretend that "one serious crash happened" and
"the model thinks one is likely" are commensurable, and they are not.

Pure pandas; no I/O. scripts/build_export_panel_verified.py feeds it and
writes the result; tests/test_combined_list.py pins the tiering rules.
"""
from __future__ import annotations

import pandas as pd

SOURCE_KNOWN = "known"
SOURCE_SCREEN = "screen"
SOURCE_PREDICTED = "predicted"
SOURCES = (SOURCE_KNOWN, SOURCE_SCREEN, SOURCE_PREDICTED)

ID = "intersection_id"


def assemble_combined(
    known: pd.DataFrame,
    screen: pd.DataFrame,
    predicted: pd.DataFrame,
    n: int,
) -> pd.DataFrame:
    """Stack the three tiers, deduplicate, cut at `n`.

    Inputs (extra columns are ignored):
      known      [intersection_id, ksi_history, crashes_history]
                 sites with >=1 KSI crash in the history window; sorted by
                 ksi_history desc, then crashes_history desc
      screen     [intersection_id, screen_count]
                 sites the City rule flags (>=5 crashes); sorted by count desc
      predicted  [intersection_id, model_rank]
                 the model's candidates; sorted by model_rank asc

    Output, one row per intersection, in list order:
      intersection_id, rank (1..n), source, model_rank (nullable Int64),
      ksi_history (int, 0 if none), screen_count (int, 0 if none),
      city_screen (bool: flagged by the City rule regardless of tier)

    An intersection present in several inputs is admitted by the highest tier
    and keeps every attribute from the others, so a known site that the model
    also ranks retains its model_rank.
    """
    if n < 0:
        raise ValueError("n must be >= 0")

    k = _prep(known, ["ksi_history", "crashes_history"])
    s = _prep(screen, ["screen_count"])
    p = _prep(predicted, ["model_rank"])

    # Attributes from every input, merged on id.
    attrs = (
        k[[ID, "ksi_history", "crashes_history"]]
        .merge(s[[ID, "screen_count"]], on=ID, how="outer")
        .merge(p[[ID, "model_rank"]], on=ID, how="outer")
    )
    attrs["ksi_history"] = attrs["ksi_history"].fillna(0).astype(int)
    attrs["crashes_history"] = attrs["crashes_history"].fillna(0).astype(int)
    attrs["screen_count"] = attrs["screen_count"].fillna(0).astype(int)
    attrs["model_rank"] = attrs["model_rank"].astype("Int64")
    attrs["city_screen"] = attrs[ID].isin(s[ID])

    # Tier order within each block.
    k_ids = (
        k.sort_values(["ksi_history", "crashes_history", ID], ascending=[False, False, True])[ID].tolist()
    )
    s_ids = s.sort_values(["screen_count", ID], ascending=[False, True])[ID].tolist()
    p_ids = p.sort_values(["model_rank", ID], ascending=[True, True])[ID].tolist()

    ordered: list[tuple[str, str]] = []
    seen: set = set()
    for source, ids in ((SOURCE_KNOWN, k_ids), (SOURCE_SCREEN, s_ids), (SOURCE_PREDICTED, p_ids)):
        for iid in ids:
            if iid in seen:
                continue
            seen.add(iid)
            ordered.append((iid, source))
            if len(ordered) >= n:
                break
        if len(ordered) >= n:
            break

    out = pd.DataFrame(ordered, columns=[ID, "source"])
    out["rank"] = range(1, len(out) + 1)
    out = out.merge(attrs, on=ID, how="left")
    out["city_screen"] = out["city_screen"].fillna(False).astype(bool)
    return out[[ID, "rank", "source", "model_rank", "ksi_history", "screen_count", "city_screen"]]


def composition(combined: pd.DataFrame) -> dict[str, int]:
    """How many rows each tier contributed -- reported in the export summary and
    written to meta.json so the UI can say 'N known · N screen · N predicted'."""
    counts = combined["source"].value_counts().to_dict() if len(combined) else {}
    return {src: int(counts.get(src, 0)) for src in SOURCES}


def _prep(df: pd.DataFrame | None, cols: list[str]) -> pd.DataFrame:
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=[ID, *cols])
    missing = [c for c in [ID, *cols] if c not in df.columns]
    if missing:
        raise KeyError(f"input is missing columns {missing}")
    out = df[[ID, *cols]].copy()
    out[ID] = out[ID].astype(str)
    if out[ID].duplicated().any():
        raise ValueError("duplicate intersection_id in tier input")
    return out
