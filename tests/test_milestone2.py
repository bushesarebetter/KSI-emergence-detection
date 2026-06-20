"""Milestone 2 unit tests.

Tests:
  - Feature determinism (same input -> same output)
  - All-severity vs KSI count separation (all-severity varies; KSI constant)
  - Theil-Sen slope on known toy series
  - Mann-Kendall tau on known toy series
  - Dropped-feature zero-variance check (KSI_feat on candidates)
  - Tweedie head trains and predicts non-negative values
  - Changepoint prob is in [0,1]
  - Momentum ratio edge cases (zero early)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.features.build_crash_emergence import (
    _theil_sen_slope,
    _mann_kendall_tau,
    _changepoint_prob,
    _ewma_last,
    _momentum_ratio,
    _annual_counts,
    _build_node_features,
)
from src.utils import load_config


# ---------------------------------------------------------------------------
# Theil-Sen slope
# ---------------------------------------------------------------------------

class TestTheilSen:
    def test_increasing_series(self):
        y = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        slope = _theil_sen_slope(y)
        assert slope > 0

    def test_flat_series(self):
        y = np.zeros(6)
        assert _theil_sen_slope(y) == 0.0

    def test_decreasing_series(self):
        y = np.array([6.0, 5.0, 4.0, 3.0, 2.0, 1.0])
        assert _theil_sen_slope(y) < 0

    def test_single_element(self):
        # Should handle gracefully
        y = np.array([3.0])
        # linregress needs at least 2 points; if it errors, should return 0
        # (function uses len(y) < 2 guard)
        result = _theil_sen_slope(y)
        assert result == 0.0


# ---------------------------------------------------------------------------
# Mann-Kendall tau
# ---------------------------------------------------------------------------

class TestMannKendall:
    def test_monotone_increasing(self):
        y = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        tau = _mann_kendall_tau(y)
        assert tau == pytest.approx(1.0, abs=1e-6)

    def test_monotone_decreasing(self):
        y = np.array([6.0, 5.0, 4.0, 3.0, 2.0, 1.0])
        tau = _mann_kendall_tau(y)
        assert tau == pytest.approx(-1.0, abs=1e-6)

    def test_short_series(self):
        # len < 3 -> return 0
        tau = _mann_kendall_tau(np.array([1.0, 2.0]))
        assert tau == 0.0

    def test_constant_series(self):
        # kendall tau of constant series is 0 (no trend)
        tau = _mann_kendall_tau(np.zeros(6))
        assert tau == 0.0


# ---------------------------------------------------------------------------
# Changepoint prob
# ---------------------------------------------------------------------------

class TestChangepointProb:
    def test_result_in_unit_interval(self):
        for series in [
            np.zeros(6),
            np.array([1.0, 1.0, 1.0, 5.0, 5.0, 5.0]),
            np.array([3.0, 2.0, 1.0, 4.0, 3.0, 2.0]),
        ]:
            prob = _changepoint_prob(series)
            assert 0.0 <= prob <= 1.0

    def test_step_change_higher_than_flat(self):
        flat = _changepoint_prob(np.ones(6))
        step = _changepoint_prob(np.array([1.0, 1.0, 1.0, 5.0, 5.0, 5.0]))
        # Step change should give higher probability
        assert step > flat

    def test_short_series(self):
        # len < 4 -> 0
        assert _changepoint_prob(np.array([1.0, 2.0, 3.0])) == 0.0


# ---------------------------------------------------------------------------
# Momentum ratio edge cases
# ---------------------------------------------------------------------------

class TestMomentumRatio:
    def test_zero_early_returns_late_count(self):
        counts = np.array([0.0, 0.0, 1.0, 3.0, 2.0, 4.0])
        r = _momentum_ratio(counts)
        # early=0, late=mean([2,4])=3 -> should return late count as proxy
        assert r == pytest.approx(3.0, abs=1e-6)

    def test_normal_ratio(self):
        counts = np.array([2.0, 2.0, 1.0, 1.0, 4.0, 4.0])
        r = _momentum_ratio(counts)
        # early mean = 2, late mean = 4
        assert r == pytest.approx(2.0, abs=1e-6)

    def test_short_series(self):
        assert _momentum_ratio(np.array([1.0, 2.0, 3.0])) == 0.0


# ---------------------------------------------------------------------------
# Feature determinism
# ---------------------------------------------------------------------------

class TestFeatureDeterminism:
    def _make_dummy_crashes(self) -> pd.DataFrame:
        return pd.DataFrame({
            "CASE_ID": ["A", "B", "C", "D", "E"],
            "date": pd.to_datetime(["2017-03-01", "2018-06-15", "2019-11-30",
                                    "2020-04-01", "2021-08-20"]),
            "severity": [3, 4, 2, 3, 4],
            "PEDESTRIAN_ACCIDENT": ["N", "Y", "N", "N", "N"],
            "BICYCLE_ACCIDENT": ["N", "N", "N", "Y", "N"],
            "TYPE_OF_COLLISION": ["C", "D", "A", "D", "C"],
            "LIGHTING": ["A", "C", "A", "B", "D"],
            "ALCOHOL_INVOLVED": ["N", "N", "Y", "N", "N"],
            "PCF_VIOL_CATEGORY": [None, "09", None, None, None],
        })

    def test_same_input_same_output(self):
        crashes = self._make_dummy_crashes()
        cutoff = pd.Timestamp("2022-01-01")
        left_turn_ids: set = set()
        feat1 = _build_node_features(crashes, left_turn_ids, cutoff)
        feat2 = _build_node_features(crashes, left_turn_ids, cutoff)
        for k in feat1:
            assert feat1[k] == feat2[k], f"Feature {k} is not deterministic"

    def test_ped_crash_counted(self):
        crashes = self._make_dummy_crashes()
        feat = _build_node_features(crashes, set(), pd.Timestamp("2022-01-01"))
        assert feat["ped_crashes_72mo"] >= 1

    def test_broadside_counted(self):
        crashes = self._make_dummy_crashes()
        feat = _build_node_features(crashes, set(), pd.Timestamp("2022-01-01"))
        # TYPE_OF_COLLISION D appears twice
        assert feat["broadside_72mo"] == 2

    def test_night_crashes_counted(self):
        crashes = self._make_dummy_crashes()
        feat = _build_node_features(crashes, set(), pd.Timestamp("2022-01-01"))
        # LIGHTING: C and B and D = night
        assert feat["night_72mo"] == 3

    def test_all_severity_counts_non_ksi_crashes(self):
        """Verify crashes_72mo counts ALL severity, not just KSI."""
        crashes = self._make_dummy_crashes()  # severities 2,3,4 present
        feat = _build_node_features(crashes, set(), pd.Timestamp("2022-01-01"))
        # All 5 crashes in 2017-2021 within 72mo window
        assert feat["crashes_72mo"] == 5


# ---------------------------------------------------------------------------
# All-severity vs KSI count separation
# ---------------------------------------------------------------------------

class TestAllSeverityVsKSI:
    @pytest.mark.integration
    def test_ksi_feat_variance_zero_on_candidates(self):
        """KSI_feat must be constant-zero on the candidate set."""
        if not Path("data/model/model_scores.parquet").exists():
            pytest.skip("real pipeline output not present")
        cfg = load_config()
        panel = pd.read_parquet("data/model/candidate_panel.parquet")
        ksi_var = float(np.var(panel["KSI_feat"].values))
        assert ksi_var == 0.0, (
            f"KSI_feat has non-zero variance on candidates: {ksi_var}. "
            "This invalidates the zero-variance drop of KSI features."
        )

    @pytest.mark.integration
    def test_crashes_72mo_varies_on_candidates(self):
        """crashes_72mo (all-severity) must have non-zero variance on candidates."""
        if not Path("data/model/model_scores.parquet").exists():
            pytest.skip("real pipeline output not present")
        feat = pd.read_parquet("data/model/feature_table.parquet")
        c72_var = float(np.var(feat["crashes_72mo"].values))
        assert c72_var > 0.0, "crashes_72mo has zero variance — no signal possible"


# ---------------------------------------------------------------------------
# Tweedie model predictions non-negative
# ---------------------------------------------------------------------------

class TestTweedieModel:
    def test_xgb_tweedie_predicts_nonnegative(self):
        try:
            import xgboost as xgb
        except ImportError:
            pytest.skip("xgboost not installed")
        X = np.random.default_rng(0).random((100, 5))
        y = np.random.default_rng(0).poisson(lam=0.5, size=100).astype(float)
        m = xgb.XGBRegressor(
            objective="reg:tweedie",
            tweedie_variance_power=1.3,
            n_estimators=10,
            max_depth=3,
            verbosity=0,
        )
        m.fit(X, y)
        preds = m.predict(X)
        assert (preds >= 0).all(), "Tweedie predictions contain negatives"

    def test_xgb_tweedie_trains_without_error(self):
        try:
            import xgboost as xgb
        except ImportError:
            pytest.skip("xgboost not installed")
        X = np.random.default_rng(1).random((50, 3))
        y = np.array([0] * 45 + [1, 1, 2, 3, 5], dtype=float)
        m = xgb.XGBRegressor(
            objective="reg:tweedie",
            tweedie_variance_power=1.3,
            n_estimators=5,
            verbosity=0,
        )
        m.fit(X, y)  # should not raise
