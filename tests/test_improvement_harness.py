"""Tests for the model-improvement harness.

The point of these is not to check that any modelling idea works -- that needs
real SWITRS data. It is to check that the harness would *notice* if something were
wrong, which is the property that makes it worth trusting later.

Three things are verified:

  1. The paired bootstrap is actually tighter than the marginal CIs it replaces.
     That is the entire justification for adding it, so it should be asserted
     rather than assumed.
  2. A deliberately leaky feature produces an implausibly high score. If the
     harness could not detect an obvious leak, it could not detect a subtle one.
  3. Grouping by intersection prevents cross-window leakage in a stacked panel.
     This is improvement #3 in docs/MODEL_IMPROVEMENTS.md and the one with a real
     trap in it: stacking overlapping feature/label windows repeats intersections,
     and an ungrouped split puts the same intersection in train and test.

These run on small generated arrays, so they need no TIMS data and no parquet
files -- they are fast enough for CI.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load_harness():
    """Import improvement_bakeoff.py by path.

    It lives in scripts/ rather than src/, so it is not importable as a package
    module. Loading by spec keeps it that way instead of restructuring the repo
    just to satisfy a test.
    """
    spec = importlib.util.spec_from_file_location(
        "improvement_bakeoff", ROOT / "scripts" / "improvement_bakeoff.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bakeoff = _load_harness()


# ────────────────────────────────────────────────────────────────────────────────
# 1. The paired bootstrap does what it is for
# ────────────────────────────────────────────────────────────────────────────────

def _marginal_recall_ci(scores, y, k, threshold, resamples=2000, seed=0):
    """The OLD approach, as in refit_verified_run_oof.py: resample positives
    against one fixed ranking and report a CI on the LEVEL."""
    rng = np.random.RandomState(seed)
    pos = np.where(y >= threshold)[0]
    rank = np.empty(len(y), dtype=int)
    rank[np.argsort(-scores)] = np.arange(len(y))
    vals = [(rank[rng.choice(pos, len(pos), replace=True)] < k).mean()
            for _ in range(resamples)]
    return np.percentile(vals, 2.5), np.percentile(vals, 97.5)


def test_paired_bootstrap_is_tighter_than_marginal_cis():
    """Two highly correlated rankings should yield a delta CI much narrower than
    the width of either arm's own CI.

    This is the whole argument for the change: at n=21 the marginal intervals
    overlap for everything, so every comparison reads as a tie even when one
    ranking is consistently better.
    """
    rng = np.random.RandomState(7)
    n, n_pos = 5000, 200

    truth = rng.gamma(2.0, 1.0, n)
    y = (rng.poisson(truth * (n_pos / truth.sum())) >= 1).astype(float)

    # Two arms that mostly agree -- the realistic case, and the one where pairing
    # helps most.
    a = truth + rng.normal(0, 0.5, n)
    b = truth + rng.normal(0, 0.5, n) + rng.normal(0, 0.05, n)

    k, thr = 500, 1
    lo_a, hi_a = _marginal_recall_ci(a, y, k, thr)
    lo_b, hi_b = _marginal_recall_ci(b, y, k, thr)
    marginal_width = max(hi_a - lo_a, hi_b - lo_b)

    d = bakeoff.paired_bootstrap_delta(a, b, y, k, thr)
    paired_width = d["ci95"][1] - d["ci95"][0]

    assert paired_width < marginal_width, (
        f"paired CI ({paired_width:.4f}) should be narrower than the marginal "
        f"CI ({marginal_width:.4f}); if it is not, pairing is buying nothing"
    )
    # Correlated arms make the gain large, not marginal.
    assert paired_width < 0.6 * marginal_width


def test_paired_bootstrap_detects_a_clearly_better_ranking():
    """A ranking built from the truth must beat a random one, with a CI that
    excludes zero. A harness that cannot see a real effect is useless."""
    rng = np.random.RandomState(11)
    n = 5000
    truth = rng.gamma(2.0, 1.0, n)
    y = (rng.poisson(truth * (200 / truth.sum())) >= 1).astype(float)

    good = truth + rng.normal(0, 0.2, n)
    noise = rng.normal(0, 1, n)

    d = bakeoff.paired_bootstrap_delta(good, noise, y, 500, 1)
    assert d["delta"] > 0
    assert d["ci95"][0] > 0, "a genuinely better ranking should have a CI above zero"
    assert d["p_better"] > 0.99


def test_paired_bootstrap_reports_no_difference_for_identical_rankings():
    """Identical arms must give delta exactly 0 with a degenerate CI -- a useful
    guard against the comparison silently reading noise."""
    rng = np.random.RandomState(3)
    n = 2000
    y = (rng.random(n) < 0.05).astype(float)
    s = rng.normal(0, 1, n)

    d = bakeoff.paired_bootstrap_delta(s, s.copy(), y, 200, 1)
    assert d["delta"] == pytest.approx(0.0, abs=1e-12)
    assert d["ci95"] == pytest.approx([0.0, 0.0], abs=1e-12)


# ────────────────────────────────────────────────────────────────────────────────
# 2 + 3. Leak detection
# ────────────────────────────────────────────────────────────────────────────────

def _oof_recall(X, y, groups, mode, seed=42, k=500, threshold=1):
    params = {
        "objective": "reg:tweedie", "tweedie_variance_power": 1.3,
        "max_depth": 4, "learning_rate": 0.1, "n_estimators": 60,
        "reg_alpha": 0.5, "reg_lambda": 2.0, "min_child_weight": 5,
        "subsample": 0.8, "colsample_bytree": 0.8,
        "random_state": 42, "verbosity": 0,
    }
    oof = bakeoff.oof_predict(X, y, groups, params, mode, seed)
    return bakeoff.recall_at_k(oof, y, k, threshold)


def _toy_panel(n=6000, seed=5):
    """A small panel in the same regime: one latent driver, a noisy observable
    feature derived from it, and a sparse count label."""
    rng = np.random.RandomState(seed)
    latent = rng.gamma(2.0, 1.0, n)
    feature = latent + rng.normal(0, 1.0, n)
    y = rng.poisson(latent * (250 / latent.sum())).astype(float)
    return rng, latent, feature, y


def test_harness_flags_an_obviously_leaky_feature():
    """Put the label in the feature matrix; recall must jump to near-perfect.

    This is the canary. The synthetic panel's honest ceiling is modest, so an arm
    that scores far above it is leaking -- and this test pins down that the
    harness is capable of showing that, rather than washing it out.
    """
    rng, latent, feature, y = _toy_panel()

    X_clean = feature.reshape(-1, 1)
    X_leaky = np.c_[feature, y]          # the label itself, straight in

    clean = _oof_recall(X_clean, y, None, "random")
    leaky = _oof_recall(X_leaky, y, None, "random")

    assert leaky > 0.9, f"a label-in-features leak should be near-perfect, got {leaky:.3f}"
    assert leaky > clean + 0.5, (
        f"leak ({leaky:.3f}) must be dramatically above clean ({clean:.3f}); "
        "if it is not, the harness cannot detect leakage"
    )


def test_stacked_windows_leak_without_intersection_grouping():
    """Improvement #3's trap, demonstrated.

    A stacked panel repeats each intersection across overlapping feature/label
    windows. Rows for the same intersection share a label, so an ungrouped split
    can train on one window and test on another for the SAME site -- which is
    leakage dressed up as cross-validation.

    Grouping by intersection_id closes it. Both numbers come from the same data
    and the same model; only the fold construction differs.
    """
    rng, latent, feature, y = _toy_panel(n=3000, seed=9)

    # Three windows per intersection: same label, feature re-measured with noise.
    n_windows = 3
    ids = np.tile(np.arange(len(y)), n_windows)
    y_stack = np.tile(y, n_windows)
    X_stack = np.concatenate(
        [(feature + rng.normal(0, 0.3, len(feature))) for _ in range(n_windows)]
    ).reshape(-1, 1)

    k = 500 * n_windows  # keep the shortlist the same FRACTION of the panel

    ungrouped = _oof_recall(X_stack, y_stack, None, "random", k=k)
    grouped = _oof_recall(X_stack, y_stack, ids, "random", k=k)

    assert ungrouped > grouped, (
        f"ungrouped CV ({ungrouped:.3f}) should be optimistically biased relative "
        f"to intersection-grouped CV ({grouped:.3f}) on a stacked panel"
    )


def test_make_splits_never_puts_a_group_in_both_train_and_test():
    """Direct structural check on the guard, independent of any model fit."""
    rng = np.random.RandomState(13)
    n = 2000
    y = rng.poisson(0.1, n).astype(float)
    groups = np.repeat(np.arange(n // 4), 4)   # 4 rows per intersection

    for mode in ("random", "spatial"):
        for train_idx, test_idx in bakeoff.make_splits(y, groups, mode, seed=42):
            overlap = set(groups[train_idx]) & set(groups[test_idx])
            assert not overlap, (
                f"{mode} split leaked {len(overlap)} group(s) across the fold boundary"
            )
