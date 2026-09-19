"""Refine single-street labels in the exported dashboard geojson from live OSM.

The export was produced from the pipeline's OSMnx graph, which is not present
on every machine. Where a label came out as a single street ("Park Boulevard"),
this script re-derives it from a fresh Overpass fetch around the point, applying
the same rules as src/gis/intersection_names.py, and patches
dashboard/public/data/intersections.geojson in place.

Sites are fetched in batches -- one Overpass query per BATCH_SIZE points -- not
one request per point. On 2026-09-17 the public mirrors took one to five minutes
per request under load, and a batch of twenty cost about the same as one point.
The query keeps the same road types as OSMnx's "drive" network, so the labels
agree with the graph the pipeline itself builds.

Guard rails
  * A new label is applied only when one of its streets is the original street
    (`same_road`), so a fetch snapped to the wrong node cannot relabel a site.
  * Results are cached per point in data/proc/refined_names_cache.json, so an
    interrupted run resumes. Fetch failures are never cached.
  * The original geojson is backed up under data/proc before it is written.

Usage
  python scripts/refine_intersection_names.py --dry-run     # report only
  python scripts/refine_intersection_names.py               # patch the export
  python scripts/refine_intersection_names.py --limit 20    # first 20 targets
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import time
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.gis.intersection_names import build_name_index, label_for_nodes  # noqa: E402
from src.gis.overpass import fetch  # noqa: E402

GEOJSON = ROOT / "dashboard" / "public" / "data" / "intersections.geojson"
CACHE = ROOT / "data" / "proc" / "refined_names_cache.json"

FETCH_RADIUS_M = 90    # ways this close to a point are fetched
MATCH_MAX_M = 15       # the point must lie this close to an OSM node
MERGE_RADIUS_M = 10    # nodes this close to the matched node form one intersection
BATCH_SIZE = 20
POLITE_PAUSE_S = 2.0

# Road types OSMnx's "drive" network filter drops. Mirrored here so a cross road
# is only something the pipeline's graph would also have contained.
DRIVE_EXCLUDE = (
    "abandoned|bridleway|bus_guideway|busway|construction|corridor|cycleway|"
    "elevator|escalator|footway|path|pedestrian|planned|platform|proposed|"
    "raceway|service|steps|track"
)

# ── Street-name comparison ──────────────────────────────────────────────────────

_DIRECTIONAL = re.compile(r"\b(north|south|east|west|n|s|e|w|ne|nw|se|sw)\b")
_SUFFIX = [
    ("boulevard", "blvd"), ("avenue", "ave"), ("street", "st"), ("drive", "dr"),
    ("road", "rd"), ("lane", "ln"), ("court", "ct"), ("place", "pl"),
    ("parkway", "pkwy"), ("highway", "hwy"), ("terrace", "ter"), ("circle", "cir"),
]


def _road_key(name: str) -> str:
    """Normalise a street name so spelling variants and directionals compare equal."""
    s = name.lower()
    s = _DIRECTIONAL.sub(" ", s)
    for long, short in _SUFFIX:
        s = re.sub(rf"\b{long}\b", short, s)
    return re.sub(r"[^a-z0-9]", "", s)


def same_road(original: str, live: str) -> bool:
    a, b = _road_key(original), _road_key(live)
    return bool(a) and bool(b) and (a == b or a in b or b in a)


def collapse_variants(names) -> set[str]:
    """Adjacent OSM ways may spell one road two ways ("Genesee Ave", "Genesee
    Avenue"). Keep the longest spelling per road so the two never both appear."""
    best: dict[str, str] = {}
    for n in names:
        k = _road_key(n)
        if k not in best or (len(n), n) > (len(best[k]), best[k]):
            best[k] = n
    return set(best.values())


# ── Overpass ────────────────────────────────────────────────────────────────────

def overpass_query(points) -> str:
    parts = "".join(
        f'way(around:{FETCH_RADIUS_M},{lat:.6f},{lon:.6f})'
        f'[highway][highway!~"^({DRIVE_EXCLUDE})$"][area!~"yes"];'
        for lat, lon in points
    )
    return f"[out:json][timeout:240];({parts});out body;>;out skel qt;"


# ── Geometry and graph ──────────────────────────────────────────────────────────

def meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Equirectangular distance; exact enough at 10-90 m."""
    k = math.cos(math.radians(lat1))
    dx = (lon2 - lon1) * 111_320 * k
    dy = (lat2 - lat1) * 110_540
    return math.hypot(dx, dy)


def graph_from_elements(elements) -> nx.MultiDiGraph:
    """A MultiDiGraph in the shape src.gis.intersection_names expects: node x/y,
    edges in both directions carrying name/highway/service from the way's tags."""
    G = nx.MultiDiGraph()
    for el in elements:
        if el.get("type") == "node":
            G.add_node(el["id"], y=el["lat"], x=el["lon"])
    for el in elements:
        if el.get("type") != "way":
            continue
        tags = el.get("tags", {})
        attrs = {k: tags[k] for k in ("name", "highway", "service") if k in tags}
        refs = [n for n in el.get("nodes", []) if n in G]
        for u, v in zip(refs, refs[1:]):
            G.add_edge(u, v, **attrs)
            G.add_edge(v, u, **attrs)
    return G


def relabel_point(lat: float, lon: float, G: nx.MultiDiGraph, name_index: dict) -> dict:
    """Label the intersection at (lat, lon) from the batch graph. A small record,
    cacheable as JSON."""
    best, best_d = None, None
    for n, d in G.nodes(data=True):
        dist = meters(lat, lon, d["y"], d["x"])
        if best_d is None or dist < best_d:
            best, best_d = n, dist
    if best is None:
        return {"status": "no_roads"}
    if best_d > MATCH_MAX_M:
        return {"status": "no_match", "nearest_m": round(best_d, 1)}

    ny, nx_ = G.nodes[best]["y"], G.nodes[best]["x"]
    members = [n for n, d in G.nodes(data=True) if meters(ny, nx_, d["y"], d["x"]) <= MERGE_RADIUS_M]
    label, method = label_for_nodes(G, members, name_index, generic=set(), fallback="")
    if not label:
        return {"status": "no_names", "nearest_m": round(best_d, 1)}
    return {"status": "ok", "label": label, "method": method,
            "nearest_m": round(best_d, 1), "members": len(members)}


# ── Cache ───────────────────────────────────────────────────────────────────────

def load_cache() -> dict:
    """Cached results, minus fetch failures: those are retried, not remembered."""
    if not CACHE.exists():
        return {}
    data = json.loads(CACHE.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if v.get("status") != "fetch_failed"}


def save_cache(cache: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    keep = {k: v for k, v in cache.items() if v.get("status") != "fetch_failed"}
    CACHE.write_text(json.dumps(keep, indent=1), encoding="utf-8")


def point_key(lat: float, lon: float) -> str:
    return f"{lat:.6f},{lon:.6f}"


# ── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="report proposed changes; write nothing")
    ap.add_argument("--limit", type=int, default=None, help="only process the first N single-name features")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="points per Overpass request")
    args = ap.parse_args()

    fc = json.loads(GEOJSON.read_text(encoding="utf-8"))
    targets = [f for f in fc["features"] if "&" not in (f["properties"].get("intersection_name") or "")]
    targets.sort(key=lambda f: f["properties"]["rank"])
    if args.limit:
        targets = targets[: args.limit]
    print(f"{len(fc['features'])} features; {len(targets)} with a single-street label to refine")

    cache = load_cache()
    t0 = time.time()

    # ── Fetch what the cache lacks, in batches ─────────────────────────────────
    pending = []
    for f in targets:
        lon, lat = f["geometry"]["coordinates"]
        if point_key(lat, lon) not in cache:
            pending.append((lat, lon))
    batches = [pending[i:i + args.batch_size] for i in range(0, len(pending), args.batch_size)]
    print(f"{len(pending)} not cached -> {len(batches)} Overpass request(s) of up to {args.batch_size}\n")

    failed_fetch: dict[str, str] = {}
    for bi, batch in enumerate(batches, 1):
        tb = time.time()
        data, err = fetch(overpass_query(batch))
        if data is None:
            msg = f"{type(err).__name__}: {str(err)[:160]}"
            print(f"  batch {bi}/{len(batches)}: fetch failed after {time.time() - tb:.0f}s -- {msg}")
            for lat, lon in batch:
                failed_fetch[point_key(lat, lon)] = msg
            continue
        G = graph_from_elements(data.get("elements", []))
        name_index = {n: collapse_variants(names) for n, names in build_name_index(G).items()}
        for lat, lon in batch:
            cache[point_key(lat, lon)] = relabel_point(lat, lon, G, name_index)
        save_cache(cache)  # after every batch, so an interrupted run resumes
        print(f"  batch {bi}/{len(batches)}: {G.number_of_nodes()} nodes, "
              f"{G.number_of_edges() // 2} way segments in {time.time() - tb:.0f}s")
        if bi < len(batches):
            time.sleep(POLITE_PAUSE_S)
    if batches:
        print()

    # ── Report and apply ──────────────────────────────────────────────────────
    changed, unchanged, mismatched, failed = [], [], [], []
    for i, f in enumerate(targets, 1):
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        key = point_key(lat, lon)
        old = p["intersection_name"]

        if key in failed_fetch:
            rec = {"status": "fetch_failed", "error": failed_fetch[key]}
        else:
            rec = cache.get(key, {"status": "fetch_failed", "error": "not fetched"})

        status = rec.get("status")
        live = rec.get("label") or ""
        if status == "ok" and " & " in live and live != old:
            # The original street must be one of the two named, else the fetch
            # matched a different node and the new label would be a lie.
            if any(same_road(old, part) for part in live.split(" & ")):
                changed.append((p["rank"], old, live, rec["method"]))
                if not args.dry_run:
                    p["intersection_name"] = live
                shown = live
            else:
                mismatched.append((p["rank"], old, live))
                shown = f"SKIPPED (different street): {live}"
        elif status == "ok":
            unchanged.append((p["rank"], old, rec.get("method")))
            shown = f"unchanged ({rec.get('method')})"
        else:
            failed.append((p["rank"], old, status, rec.get("nearest_m") or rec.get("error", "")))
            shown = f"{status}"

        print(f"  [{i:3d}/{len(targets)}] #{p['rank']:<5} {old!r:45s} -> {shown}")

    print(f"\n{len(changed)} relabelled, {len(unchanged)} left as-is, {len(mismatched)} skipped as a "
          f"different street, {len(failed)} could not be matched ({time.time() - t0:.0f}s)")
    if mismatched:
        print("skipped (no street in the live label matches the original):")
        for rank, old, live in mismatched:
            print(f"  #{rank:<5} {old!r} vs {live!r}")
    if failed:
        print("could not match:")
        for rank, old, status, extra in failed:
            print(f"  #{rank:<5} {old!r}: {status} {extra}")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return

    if changed:
        backup = CACHE.parent / "intersections.geojson.before-refine"
        if not backup.exists():  # keep the true original across repeated runs
            shutil.copy2(GEOJSON, backup)
        GEOJSON.write_text(json.dumps(fc), encoding="utf-8")
        print(f"\nwrote {GEOJSON.relative_to(ROOT)}  (backup: {backup.relative_to(ROOT)})")
        print("NOTE: this patches the exported data only. intersection_names.csv and the results/")
        print("CSVs are regenerated by the pipeline, which applies the same rules.")


if __name__ == "__main__":
    main()
