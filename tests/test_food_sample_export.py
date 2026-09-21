"""The invented food-safety export keeps the shape the site and the contract expect."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOCAB_PREFIXES = (
    "Last routine score", "Grade ", " major violation", "cited ", "Closed by the County", "Reinspection required",
    "Risk category", "Facility type:", "Score falling", "months since last inspection", "complaints in", "Neighbours' average score",
    "Change of ownership",
)


def load():
    spec = importlib.util.spec_from_file_location("make_sample_export", ROOT / "scripts" / "food" / "make_sample_export.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_export_is_deterministic_and_well_formed():
    mod = load()
    fc, meta = mod.build(120, seed=3)
    fc2, _ = mod.build(120, seed=3)
    assert json.dumps(fc) == json.dumps(fc2), "same seed, same export"
    ranks = sorted(f["properties"]["rank"] for f in fc["features"])
    assert ranks == list(range(1, 121))
    assert meta["sample"] is True
    assert meta["candidates"] > 120
    for f in fc["features"]:
        p = f["properties"]
        assert p["name"].startswith("Sample "), "every invented place says so in its name"
        assert p["address"].endswith("CA " + p["address"][-5:])
        assert p["facility_type"] in {"restaurant", "market", "mobile", "bar", "bakery", "school", "caterer", "other"}
        assert p["risk_category"] in (1, 2, 3)
        dates = [i["date"] for i in p["inspections"]]
        assert dates == sorted(dates)
        for i in p["inspections"]:
            if i["score"] is not None:
                assert i["grade"] == mod.grade(i["score"])
            else:
                assert i["type"] == "complaint"
        assert p["last_inspection"] == p["inspections"][-1]
        assert len(p["violations"]) <= 60
        majors_listed = sum(1 for v in p["violations"] if v["severity"] == "major")
        assert majors_listed <= sum(i["major"] for i in p["inspections"])
        for v in p["violations"]:
            assert v["theme"] in mod.ITEMS and v["severity"] in ("major", "minor")
        assert 1 <= len(p["shap_features"]) <= 5
        for s in p["shap_features"]:
            assert any(tok in s["display_label"] for tok in VOCAB_PREFIXES), s["display_label"]
        lon, lat = f["geometry"]["coordinates"]
        assert 32.4 < lat < 33.2 and -117.4 < lon < -116.8


def test_rank_follows_the_record_and_catch_is_monotone():
    mod = load()
    fc, meta = mod.build(400, seed=11)
    top = fc["features"][:100]
    bottom = fc["features"][-100:]
    majors = lambda fs: sum(i["major"] for f in fs for i in f["properties"]["inspections"]) / len(fs)
    assert majors(top) > majors(bottom), "higher-ranked places carry worse records"
    ks = sorted(int(k) for k in meta["catch"])
    caught = [meta["catch"][str(k)]["caught"] for k in ks]
    assert caught == sorted(caught)
    assert all(meta["catch"][str(k)]["total"] == meta["catch"][str(ks[0])]["total"] for k in ks)
