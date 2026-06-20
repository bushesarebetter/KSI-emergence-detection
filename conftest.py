"""pytest configuration: add project root to sys.path."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

REQUIRED_ARTIFACTS = [
    "data/model/model_scores.parquet",
    "data/model/candidate_panel.parquet",
    "data/model/feature_table.parquet",
]


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: requires real pipeline artifacts in data/model/ and data/proc/",
    )


@pytest.fixture(autouse=False)
def require_pipeline_artifacts():
    missing = [p for p in REQUIRED_ARTIFACTS if not Path(p).exists()]
    if missing:
        pytest.skip(f"Pipeline artifacts missing: {missing}")
