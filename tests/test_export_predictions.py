"""The dashboard export writers, on a synthetic panel.

They cannot be exercised end-to-end without pipeline artefacts, but everything
that decides what the map shows is a pure function of the panel frame and can
be pinned here: combined fields pass through only when present, a known site
with no model score serialises as null (not NaN, which is invalid JSON),
district counts follow the upstream rank at every K including 800, and catch
stats score the MODEL's rank -- never the combined list's position.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "export_predictions", ROOT / "scripts" / "export_predictions.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ep = _load()


def _row(iid, rank, district, *, source=None, model_rank=None, score=None, pct=None,
         emergent=False, ksi=0, screen=0, city_screen=False, oof=None):
    r = {
        "intersection_id": iid, "node_id": hash(iid) % 10_000_000, "rank": rank,
        "lon": -117.1, "lat": 32.7, "tweedie_score": score, "percentile": pct,
        "council_district": district, "is_known_emergent": emergent, "oof_rank": oof,
        "is_crash_active": True, "crashes_training": 3,
        "crash_history_json": "[]", "shap_json": "[]",
    }
    if source is not None:
        r.update(source=source, model_rank=model_rank, ksi_history=ksi,
                 screen_count=screen, city_screen=city_screen)
    return r


def _combined_panel():
    return pd.DataFrame([
        _row("K1", 1, 3, source="known", ksi=2, emergent=True),                       # no model score
        _row("K2", 2, 9, source="known", ksi=1, model_rank=7, score=0.2, pct=99.0),   # known AND ranked
        _row("S1", 3, 3, source="screen", screen=6, city_screen=True),
        _row("P1", 4, 1, source="predicted", model_rank=1, score=0.9, pct=100.0, oof=1),
        _row("P2", 5, 2, source="predicted", model_rank=3, score=0.5, pct=99.9, oof=3, emergent=True),
        _row("P3", 6, 2, source="predicted", model_rank=60, score=0.1, pct=90.0, oof=60, emergent=True),
    ])


def _names(panel):
    return pd.DataFrame({"intersection_id": panel["intersection_id"],
                         "intersection_name": [f"{i} Street & Test Avenue" for i in panel["intersection_id"]]})


def test_combined_fields_pass_through_and_scoreless_rows_are_null(tmp_path):
    panel = _combined_panel()
    ep.write_geojson(panel, _names(panel), output_dir=tmp_path, top_n=10)
    fc = json.loads((tmp_path / "intersections.geojson").read_text())
    by = {f["properties"]["rank"]: f["properties"] for f in fc["features"]}

    k1 = by[1]
    assert k1["source"] == "known" and k1["ksi_history"] == 2
    assert k1["model_rank"] is None and k1["percentile"] is None and k1["oof_rank"] is None
    assert k1["is_known_emergent"] is True

    k2 = by[2]
    assert k2["source"] == "known" and k2["model_rank"] == 7 and k2["percentile"] == 99.0

    assert by[3]["source"] == "screen" and by[3]["screen_count"] == 6 and by[3]["city_screen"] is True
    assert by[4]["source"] == "predicted" and by[4]["model_rank"] == 1 and by[4]["city_screen"] is False

    # The whole file is strict JSON -- json.loads above would have failed on NaN.
    assert "NaN" not in (tmp_path / "intersections.geojson").read_text()


def test_classic_panel_has_no_combined_fields(tmp_path):
    panel = pd.DataFrame([_row("P1", 1, 1, score=0.9, pct=100.0), _row("P2", 2, 2, score=0.5, pct=99.0)])
    ep.write_geojson(panel, _names(panel), output_dir=tmp_path, top_n=10)
    fc = json.loads((tmp_path / "intersections.geojson").read_text())
    props = fc["features"][0]["properties"]
    for col in ep.COMBINED_COLUMNS:
        assert col not in props


def test_geojson_keeps_emergents_beyond_top_n(tmp_path):
    panel = _combined_panel()
    ep.write_geojson(panel, _names(panel), output_dir=tmp_path, top_n=2)
    fc = json.loads((tmp_path / "intersections.geojson").read_text())
    ranks = sorted(f["properties"]["rank"] for f in fc["features"])
    # ranks 1-2 by the cut, plus 5 and 6 because they are emergent
    assert ranks == [1, 2, 5, 6]


def test_districts_follow_upstream_rank_not_score_and_include_800(tmp_path):
    # rank is deliberately the REVERSE of tweedie_score
    panel = pd.DataFrame([
        _row("A", 1, 1, score=0.1, pct=1.0),
        _row("B", 2, 2, score=0.9, pct=99.0),
    ])
    ep.write_districts(panel, output_dir=tmp_path)
    d = {row["district"]: row for row in json.loads((tmp_path / "districts.json").read_text())}
    assert set(d[1]) == {"district", *[f"top_{k}_count" for k in ep.KS]}
    assert "top_800_count" in d[1] and "top_1000_count" in d[1]
    assert d[1]["top_50_count"] == 1 and d[2]["top_50_count"] == 1
    assert len(d) == 9


def test_meta_scores_model_rank_not_list_position(tmp_path):
    panel = _combined_panel()
    ep.write_meta(panel, output_dir=tmp_path, extra={"run": "forward", "top_n": 800})
    meta = json.loads((tmp_path / "meta.json").read_text())

    # Only model-scored rows count: K1 is emergent but has no model_rank, so it is
    # excluded from both numerator and denominator. Scored emergents: P2 (rank 3),
    # P3 (rank 60). Nothing scored is emergent at K=... K2 is not emergent.
    assert meta["catch"]["50"] == {"caught": 1, "total": 2}
    assert meta["catch"]["100"] == {"caught": 2, "total": 2}
    assert meta["list"] == "combined"
    assert meta["composition"] == {"known": 2, "screen": 1, "predicted": 3}
    assert meta["run"] == "forward" and meta["top_n"] == 800
    assert set(meta["catch"]) == {str(k) for k in ep.KS}


def test_meta_on_classic_panel_uses_rank(tmp_path):
    panel = pd.DataFrame([
        _row("P1", 1, 1, score=0.9, pct=100.0, emergent=True),
        _row("P2", 2, 2, score=0.5, pct=99.0),
        _row("P3", 70, 2, score=0.1, pct=50.0, emergent=True),
    ])
    ep.write_meta(panel, output_dir=tmp_path)
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["list"] == "predicted"
    assert meta["catch"]["50"] == {"caught": 1, "total": 2}
    assert meta["catch"]["100"] == {"caught": 2, "total": 2}
    assert meta["composition"] == {"predicted": 3, "known": 0, "screen": 0}


def test_validate_panel_accepts_null_scores():
    """A combined panel has scoreless known rows; validation must not reject NaN."""
    panel = _combined_panel()
    ep.validate_panel(panel)  # must not sys.exit


def test_validate_panel_rejects_missing_columns():
    with pytest.raises(SystemExit):
        ep.validate_panel(pd.DataFrame({"node_id": [1]}))
