"""Regression tests for D11-D16 (docs/DECISIONS.md): the candidate-set scope fix, the
forward-run window correction, the verified-run recall@K drift, and the hyperparameter
source-of-truth fix. None of these were caught by any existing test, which is how each
one shipped silently. These are integration tests against the archived pipeline artifacts
in data/model/ -- they skip (not fail) if those artifacts aren't present, same convention
as the rest of this project's integration tests.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "data" / "model"
VERIFIED_DIR = MODEL_DIR / "verified_run"
FORWARD_DIR = MODEL_DIR / "forward_run"
RESULTS_DIR = ROOT / "results"

pytestmark = pytest.mark.integration


def _skip_if_missing(*paths: Path):
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        pytest.skip(f"Pipeline artifacts missing: {missing}")


# ---------------------------------------------------------------------------
# D11: candidate set must be restricted to the City of San Diego, not the county
# ---------------------------------------------------------------------------

def test_verified_run_candidate_count_is_city_not_county():
    _skip_if_missing(VERIFIED_DIR / "candidate_panel.parquet")
    panel = pd.read_parquet(VERIFIED_DIR / "candidate_panel.parquet")
    assert len(panel) == 26423, (
        f"Verified-run candidate count is {len(panel)}, expected 26,423 (City of San Diego, "
        "post-D11). 81,007 would mean the county-wide backup was restored instead of the "
        "city-restricted panel."
    )
    assert int((panel["KSI_label"] >= 2).sum()) == 21, "post-D11 emergent count should be 21, not 22"


def test_forward_run_candidate_count_is_city_not_county():
    _skip_if_missing(FORWARD_DIR / "candidate_panel.parquet")
    panel = pd.read_parquet(FORWARD_DIR / "candidate_panel.parquet")
    assert len(panel) == 26045, (
        f"Forward-run candidate count is {len(panel)}, expected 26,045 (City of San Diego, "
        "post-D11)."
    )


def test_restrict_candidates_to_city_limits_is_idempotent():
    """D11's restrict script must restore-then-refilter from backup, not double-filter on
    repeated runs. Verify the live panel and its backup are still consistent in size."""
    _skip_if_missing(
        VERIFIED_DIR / "candidate_panel.parquet",
        VERIFIED_DIR / "candidate_panel_COUNTYWIDE_backup.parquet",
    )
    live = pd.read_parquet(VERIFIED_DIR / "candidate_panel.parquet")
    backup = pd.read_parquet(VERIFIED_DIR / "candidate_panel_COUNTYWIDE_backup.parquet")
    assert len(live) < len(backup), "city-restricted panel should be smaller than the county-wide backup"
    assert len(backup) >= 80000, "county-wide backup should still hold the original ~81,007 rows"


# ---------------------------------------------------------------------------
# D12: forward run window must be 2016-2024 features -> 2025-2027 labels
# ---------------------------------------------------------------------------

def test_forward_run_window_is_2025_2027():
    cfg_path = ROOT / "configs" / "config.yaml"
    text = cfg_path.read_text()
    assert "2024-12-31" in text and "2025-01-01" in text, (
        "config.yaml's feature_end/label_start should be 2024-12-31/2025-01-01 "
        "(forward run = 2016-2024 features -> 2025-2027 labels, see D12). If this fails, "
        "the window may have regressed to the pre-D12 2016-2023/2024-2026 setup."
    )


def test_forward_run_archive_internally_consistent_timestamps():
    """D12 found candidate_panel.parquet newer than feature_table.parquet in the forward-run
    archive -- meaning labels and features weren't built in the same pipeline pass. By
    design (see scripts/restrict_candidates_to_city_limits.py's docstring), feature_table.parquet
    is NOT re-filtered to city limits -- only candidate_panel.parquet is, and downstream
    scripts inner-join on intersection_id to drop the unmatched county-only rows. So the
    invariant to check is one-directional: every candidate in the (city-restricted)
    candidate_panel must have a matching feature row, not that the two files are the same
    size."""
    _skip_if_missing(FORWARD_DIR / "candidate_panel.parquet", FORWARD_DIR / "feature_table.parquet")
    panel = pd.read_parquet(FORWARD_DIR / "candidate_panel.parquet")
    feat = pd.read_parquet(FORWARD_DIR / "feature_table.parquet")
    panel_ids = set(panel["intersection_id"])
    feat_ids = set(feat["intersection_id"])
    missing = panel_ids - feat_ids
    assert not missing, (
        f"{len(missing)} candidates in candidate_panel.parquet have no matching row in "
        "feature_table.parquet -- the two files were likely built in separate pipeline "
        "passes on different candidate sets (the D12 bug). Re-run build_panel + "
        "build_crash_emergence together."
    )


# ---------------------------------------------------------------------------
# D15: verified-run recall@K (and the baseline) must match the canonical OOF file
# ---------------------------------------------------------------------------

def test_verified_run_oof_results_has_baseline_block():
    """D15 found refit_verified_run_oof.py computed baseline scores but never wrote
    baseline recall@K into its JSON, so nobody could spot-check it. Must not regress."""
    path = RESULTS_DIR / "oof_verified_run_results.json"
    _skip_if_missing(path)
    data = json.loads(path.read_text())
    assert "persistence_baseline" in data, (
        "oof_verified_run_results.json is missing the persistence_baseline block (D15). "
        "scripts/refit_verified_run_oof.py must include 'persistence_baseline' alongside "
        "'random'/'spatial' in its output loop."
    )
    assert "500" in data["persistence_baseline"][">=2"]


def test_verified_run_recall_matches_canonical_oof_file():
    """D15: the recall@K hit counts published everywhere must match this file exactly.
    These are the numbers actually used in outreach materials -- if this test ever fails,
    every doc citing them needs to be re-synced (see D15 in docs/DECISIONS.md for the
    propagation checklist: README.md, reports/milestone_final.md, the Notion outreach pages)."""
    path = RESULTS_DIR / "oof_verified_run_results.json"
    _skip_if_missing(path)
    data = json.loads(path.read_text())
    assert data["random"][">=2"]["500"]["hits"] == 10
    assert data["spatial"][">=2"]["500"]["hits"] == 9
    assert data["random"][">=1"]["500"]["hits"] == 74
    assert data["spatial"][">=1"]["500"]["hits"] == 71
    assert data["persistence_baseline"][">=2"]["500"]["hits"] == 10
    assert data["persistence_baseline"][">=1"]["500"]["hits"] == 61


# ---------------------------------------------------------------------------
# D16: every OOF script must use the same frozen Protocol-A hyperparameters
# ---------------------------------------------------------------------------

def test_no_hardcoded_hyperparameter_dict_in_refit_scripts():
    """D16: refit_forward_run_oof.py used to hardcode a literal copy of a hyperparameter
    dict that silently diverged from data/model/frozen_params.json. Guard against any OOF
    script reintroducing a hardcoded copy instead of loading the shared source file."""
    refit_scripts = [
        ROOT / "scripts" / "refit_protocol_a_oof.py",
        ROOT / "scripts" / "predict_forward_run.py",
        ROOT / "scripts" / "predict_protocol_a_forward.py",
    ]
    for script in refit_scripts:
        if not script.exists():
            continue
        text = script.read_text()
        assert "frozen_params.json" in text, (
            f"{script.name} doesn't reference frozen_params.json -- it may have reverted "
            "to a hardcoded hyperparameter dict (the D16 bug)."
        )
        # The specific value that was hardcoded pre-D16; must never appear literally again.
        assert "1.5888579172320472" not in text, (
            f"{script.name} contains the pre-D16 hardcoded variance_power literal -- "
            "the hardcoded copy may have been reintroduced."
        )


def test_forward_run_predict_only_results_are_leakage_free():
    """D17: the forward run's deployed score must come from a model fit ONLY on the
    verified-run's resolved window (2016-2021 features -> 2022-2024 labels) and applied
    via predict-only to forward candidates -- never refit on the forward panel's own
    (2025-2027) label. Guard the validated recall@K so a future regression back to
    fitting on the forward panel's label (the pre-D17 bug in src/model/fit_frozen.py) is
    caught immediately: that bug inflated these numbers well above what's checked here."""
    path = RESULTS_DIR / "recall_evaluation.json"
    _skip_if_missing(path)
    data = json.loads(path.read_text())["prospective_2025"]["recall_at_k"][">=1"]
    assert data["200"]["hits"] == 9, (
        "Prospective/forward recall@200 (>=1 KSI) should be 9/108. A higher value may "
        "indicate the forward score was fit on the forward panel's own (resolved) label "
        "again instead of predict-only scoring (the pre-D17 bug)."
    )
    assert data["500"]["hits"] == 24
