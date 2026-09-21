"""The treatment log records a listed corner with matched controls."""
import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_module():
    spec = importlib.util.spec_from_file_location("log_treatment", ROOT / "scripts" / "log_treatment.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def feature(rank, lat, lon, district=3, name=None):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"rank": rank, "council_district": district, "intersection_name": name or f"Corner {rank}"},
    }


@pytest.fixture
def export(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    feats = [feature(r, 32.7 + r / 1000, -117.1, district=3 if r % 2 else 5) for r in range(1, 13)]
    (data / "intersections.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    (data / "meta.json").write_text(json.dumps({"generated": "2026-09-18"}), encoding="utf-8")
    keys = {r: f"{32.7 + r / 1000:.6f},{-117.1:.6f}" for r in range(1, 13)}
    control = {keys[r]: {"control": "signals" if r <= 8 else "stop"} for r in range(1, 13)}
    traffic = {keys[r]: {"entering": 20000 if r != 7 else 90000} for r in range(1, 13)}
    (data / "control.json").write_text(json.dumps({"sites": control}), encoding="utf-8")
    (data / "traffic.json").write_text(json.dumps({"sites": traffic}), encoding="utf-8")
    return data, tmp_path / "log" / "treatments.csv"


def run(mod, export, monkeypatch, rank, treatment="engineering review requested"):
    data, log = export
    monkeypatch.setattr(mod, "DATA", data)
    monkeypatch.setattr(mod, "LOG", log)
    monkeypatch.setattr(sys, "argv", ["log_treatment", "--rank", str(rank), "--treatment", treatment,
                                      "--date", "2026-11-04", "--via", "District 3 office"])
    mod.main()
    with open(log, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_logs_the_corner_with_up_to_three_matched_controls(export, monkeypatch):
    mod = load_module()
    rows = run(mod, export, monkeypatch, rank=3)
    assert len(rows) == 1
    row = rows[0]
    assert row["rank_at_listing"] == "3"
    assert row["export_generated"] == "2026-09-18"
    controls = row["matched_controls"].split(";")
    assert len(controls) == 3
    ranks = [int(c.split("@")[1]) for c in controls]
    # Same stratum (1 to 100), same control (signals: ranks 1 to 8), traffic within 2x (rank 7 is out).
    assert all(1 <= r <= 8 and r != 3 and r != 7 for r in ranks)
    # Same district (odd ranks are district 3) is preferred.
    assert ranks[:2] == [1, 5]


def test_controls_are_not_reused_across_treatments(export, monkeypatch):
    mod = load_module()
    run(mod, export, monkeypatch, rank=3)
    rows = run(mod, export, monkeypatch, rank=1, treatment="protected left-turn phase")
    assert len(rows) == 2
    first = {c.split("@")[0] for c in rows[0]["matched_controls"].split(";")}
    second = {c.split("@")[0] for c in rows[1]["matched_controls"].split(";")}
    assert not (first & second)
    assert rows[0]["corner_key"] not in second


def test_unknown_rank_is_refused(export, monkeypatch):
    mod = load_module()
    with pytest.raises(SystemExit):
        run(mod, export, monkeypatch, rank=999)
