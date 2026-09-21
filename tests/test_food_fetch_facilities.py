"""The permit download pages through the County's endpoint and normalises rows."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("fetch_facilities", ROOT / "scripts" / "food" / "fetch_facilities.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_fetch_all_pages_until_a_short_page():
    mod = load()
    calls = []

    def fake(offset):
        calls.append(offset)
        n = mod.PAGE if offset == 0 else 3
        return [{"record_id": f"PR{offset + i}"} for i in range(n)]

    rows = mod.fetch_all(fetch=fake)
    assert calls == [0, mod.PAGE]
    assert len(rows) == mod.PAGE + 3


def test_normalise_keeps_located_rows_only():
    mod = load()
    row = {"record_id": "PR0001", "record_name": "A CAFE", "business_type": "Restaurant Food Facility", "address": "1 Main St",
           "city": "San Diego", "zip": "92101", "permit_status": "Active", "active_permit": "Y", "record_open_date": "2020-01-01",
           "latitude": "32.71", "longitude": "-117.16"}
    n = mod.normalise(row)
    assert n["city"] == "SAN DIEGO" and n["active"] is True and n["lat"] == 32.71
    assert mod.normalise({**row, "latitude": None}) is None
    assert mod.normalise({**row, "longitude": "n/a"}) is None
