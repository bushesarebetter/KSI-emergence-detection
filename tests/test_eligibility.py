"""Candidate-eligibility rule: City-screen (default) vs legacy KSI.

Guards the 2026-09 switch from KSI_feat<2 to the City's ">=5 injury-or-fatal"
High Crash List screen (crashes_feat < candidate_city_screen_min).
"""
import numpy as np
import pandas as pd

from src.labels.build_panel import _apply_eligibility


def _panel():
    # crashes_feat, KSI_feat chosen to separate the two rules:
    #  A: 0 crashes, 0 KSI   -> in both
    #  B: 4 crashes, 1 KSI   -> in city (4<5) AND legacy (1<2)
    #  C: 5 crashes, 1 KSI   -> OUT city (5>=5, on screen), IN legacy (1<2)
    #  D: 2 crashes, 2 KSI   -> IN city (2<5), OUT legacy (KSI 2>=2)
    #  E: 9 crashes, 3 KSI   -> OUT of both
    return pd.DataFrame({
        "intersection_id": ["A", "B", "C", "D", "E"],
        "crashes_feat":    [0, 4, 5, 2, 9],
        "KSI_feat":        [0, 1, 1, 2, 3],
    })


def test_city_screen_default():
    cfg = {"labels": {"candidate_screen": "city", "candidate_city_screen_min": 5}}
    cand, desc = _apply_eligibility(_panel(), cfg)
    assert set(cand["intersection_id"]) == {"A", "B", "D"}, desc
    # Every candidate is genuinely below the City screen.
    assert (cand["crashes_feat"] < 5).all()


def test_legacy_ksi_rule():
    cfg = {"labels": {
        "candidate_screen": "ksi_legacy",
        "candidate_max_ksi_feat": 2,
        "candidate_top_decile_drop": 0.10,
    }}
    cand, _ = _apply_eligibility(_panel(), cfg)
    # KSI_feat<2 keeps A,B,C; the top-decile(90th pct=2.6) drop removes nothing extra here.
    assert set(cand["intersection_id"]) == {"A", "B", "C"}


def test_city_and_legacy_disagree():
    """The whole point of the fix: C (on the City screen) and D (severe history)
    are treated oppositely by the two rules."""
    city, _ = _apply_eligibility(_panel(), {"labels": {"candidate_screen": "city", "candidate_city_screen_min": 5}})
    legacy, _ = _apply_eligibility(_panel(), {"labels": {"candidate_screen": "ksi_legacy", "candidate_max_ksi_feat": 2, "candidate_top_decile_drop": 0.10}})
    assert "D" in set(city["intersection_id"]) and "D" not in set(legacy["intersection_id"])
    assert "C" in set(legacy["intersection_id"]) and "C" not in set(city["intersection_id"])


def test_unknown_mode_raises():
    import pytest
    with pytest.raises(ValueError):
        _apply_eligibility(_panel(), {"labels": {"candidate_screen": "nope"}})
