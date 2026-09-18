"""Tiering rules for the combined "most unsafe" list.

The property that matters: the list is stacked, not blended. A known
serious-crash site always outranks a City-screen-only site, which always
outranks a model-only site -- and a site in several tiers is admitted once, by
the highest, keeping its other attributes so the UI can say "known, and also
ranked #12 by the model".
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.export.combined_list import (
    SOURCE_KNOWN,
    SOURCE_PREDICTED,
    SOURCE_SCREEN,
    assemble_combined,
    composition,
)


def _known(*rows):
    return pd.DataFrame(rows, columns=["intersection_id", "ksi_history", "crashes_history"])


def _screen(*rows):
    return pd.DataFrame(rows, columns=["intersection_id", "screen_count"])


def _pred(*rows):
    return pd.DataFrame(rows, columns=["intersection_id", "model_rank"])


def test_tiers_are_stacked_known_then_screen_then_predicted():
    out = assemble_combined(
        known=_known(("K1", 1, 4)),
        screen=_screen(("S1", 7)),
        predicted=_pred(("P1", 1), ("P2", 2)),
        n=10,
    )
    assert out["intersection_id"].tolist() == ["K1", "S1", "P1", "P2"]
    assert out["source"].tolist() == [SOURCE_KNOWN, SOURCE_SCREEN, SOURCE_PREDICTED, SOURCE_PREDICTED]
    assert out["rank"].tolist() == [1, 2, 3, 4]


def test_within_tier_ordering():
    out = assemble_combined(
        known=_known(("K_low", 1, 9), ("K_high", 3, 2), ("K_tie", 1, 20)),
        screen=_screen(("S5", 5), ("S9", 9)),
        predicted=_pred(("P3", 3), ("P1", 1)),
        n=10,
    )
    ids = out["intersection_id"].tolist()
    # known: most serious crashes first, then most crashes
    assert ids[:3] == ["K_high", "K_tie", "K_low"]
    # screen: highest count first
    assert ids[3:5] == ["S9", "S5"]
    # predicted: best model rank first
    assert ids[5:] == ["P1", "P3"]


def test_site_in_every_tier_is_admitted_once_by_the_highest_and_keeps_attributes():
    out = assemble_combined(
        known=_known(("X", 2, 11)),
        screen=_screen(("X", 8)),
        predicted=_pred(("X", 12), ("P", 1)),
        n=10,
    )
    assert out["intersection_id"].tolist() == ["X", "P"]
    x = out.iloc[0]
    assert x["source"] == SOURCE_KNOWN
    assert x["model_rank"] == 12
    assert x["ksi_history"] == 2
    assert x["screen_count"] == 8
    assert bool(x["city_screen"]) is True


def test_screen_site_that_is_also_predicted_is_flagged_both_ways():
    out = assemble_combined(
        known=_known(),
        screen=_screen(("B", 6)),
        predicted=_pred(("B", 3), ("P", 1)),
        n=10,
    )
    b = out.set_index("intersection_id").loc["B"]
    assert b["source"] == SOURCE_SCREEN
    assert b["model_rank"] == 3
    assert bool(b["city_screen"]) is True
    p = out.set_index("intersection_id").loc["P"]
    assert bool(p["city_screen"]) is False
    assert p["screen_count"] == 0


def test_cut_at_n_is_exact_and_ranks_are_contiguous():
    out = assemble_combined(
        known=_known(*[(f"K{i}", 1, 1) for i in range(3)]),
        screen=_screen(*[(f"S{i}", 5) for i in range(3)]),
        predicted=_pred(*[(f"P{i}", i + 1) for i in range(10)]),
        n=8,
    )
    assert len(out) == 8
    assert out["rank"].tolist() == list(range(1, 9))
    assert composition(out) == {SOURCE_KNOWN: 3, SOURCE_SCREEN: 3, SOURCE_PREDICTED: 2}


def test_known_and_screen_can_crowd_out_the_model_entirely():
    """If n is small, the predicted tier gets nothing -- and the composition
    makes that visible rather than silently dropping the model."""
    out = assemble_combined(
        known=_known(*[(f"K{i}", 1, 1) for i in range(5)]),
        screen=_screen(),
        predicted=_pred(("P", 1)),
        n=3,
    )
    assert composition(out) == {SOURCE_KNOWN: 3, SOURCE_SCREEN: 0, SOURCE_PREDICTED: 0}


def test_n_larger_than_everything_returns_everything():
    out = assemble_combined(_known(("K", 1, 1)), _screen(("S", 5)), _pred(("P", 1)), n=1000)
    assert len(out) == 3


def test_empty_and_none_inputs():
    out = assemble_combined(None, None, _pred(("P", 1)), n=5)
    assert out["intersection_id"].tolist() == ["P"]
    assert out["ksi_history"].tolist() == [0]
    assert out["screen_count"].tolist() == [0]
    assert bool(out["city_screen"].iloc[0]) is False
    assert len(assemble_combined(None, None, None, n=5)) == 0
    assert composition(assemble_combined(None, None, None, n=5)) == {s: 0 for s in (SOURCE_KNOWN, SOURCE_SCREEN, SOURCE_PREDICTED)}


def test_model_rank_is_nullable_for_non_candidates():
    out = assemble_combined(_known(("K", 1, 1)), None, _pred(("P", 1)), n=5)
    ranks = out.set_index("intersection_id")["model_rank"]
    assert pd.isna(ranks["K"])
    assert ranks["P"] == 1


def test_rejects_duplicate_ids_within_a_tier():
    with pytest.raises(ValueError, match="duplicate"):
        assemble_combined(None, None, _pred(("P", 1), ("P", 2)), n=5)


def test_rejects_missing_columns():
    with pytest.raises(KeyError):
        assemble_combined(pd.DataFrame({"intersection_id": ["K"]}), None, None, n=5)
