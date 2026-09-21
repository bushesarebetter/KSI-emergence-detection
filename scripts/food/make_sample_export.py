"""Write an invented export for the food-safety site, in the shape the real one
must take (docs/FOOD_DATA_CONTRACT.md), so the site can be built and reviewed
before the model exists.

Every place is fictional. Names carry the word "Sample", meta.json carries
``"sample": true``, and the site shows a notice on every page while that flag
is set. Nothing here is drawn from any real inspection.

The generator is deterministic (seeded), and internally consistent: a place's
rank follows a latent risk that also drives its scores, its violations and its
signals, so the interface can be judged on records that hang together.

Usage
  python scripts/food/make_sample_export.py            # 1,000 places
  python scripts/food/make_sample_export.py --n 300 --out /tmp/out
"""
from __future__ import annotations

import argparse
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "food-dashboard" / "public" / "data"

# Commercial areas of the City of San Diego: name, lat, lon, council district,
# a street for invented addresses, a zip, and a weight (busier corridors get
# more places).
ANCHORS = [
    ("Convoy", 32.827, -117.155, 6, "Convoy St", "92111", 3),
    ("Hillcrest", 32.748, -117.163, 3, "University Ave", "92103", 2),
    ("North Park", 32.748, -117.129, 3, "30th St", "92104", 2),
    ("Gaslamp", 32.712, -117.160, 3, "5th Ave", "92101", 3),
    ("Little Italy", 32.723, -117.168, 3, "India St", "92101", 2),
    ("Pacific Beach", 32.797, -117.254, 2, "Garnet Ave", "92109", 2),
    ("Ocean Beach", 32.748, -117.249, 2, "Newport Ave", "92107", 1),
    ("Point Loma", 32.735, -117.230, 2, "Rosecrans St", "92106", 1),
    ("Clairemont", 32.818, -117.192, 2, "Balboa Ave", "92117", 1),
    ("Bay Park", 32.785, -117.205, 2, "Morena Blvd", "92110", 1),
    ("La Jolla", 32.847, -117.273, 1, "Girard Ave", "92037", 2),
    ("University City", 32.871, -117.212, 1, "Genesee Ave", "92122", 1),
    ("Carmel Valley", 32.939, -117.230, 1, "El Camino Real", "92130", 1),
    ("Mira Mesa", 32.916, -117.145, 6, "Mira Mesa Blvd", "92126", 2),
    ("Kearny Mesa", 32.833, -117.140, 6, "Clairemont Mesa Blvd", "92123", 1),
    ("Rancho Bernardo", 33.020, -117.078, 5, "Bernardo Center Dr", "92128", 1),
    ("Scripps Ranch", 32.906, -117.099, 5, "Scripps Poway Pkwy", "92131", 1),
    ("Rancho Penasquitos", 32.960, -117.120, 5, "Carmel Mountain Rd", "92129", 1),
    ("Mission Valley", 32.768, -117.155, 7, "Camino del Rio N", "92108", 2),
    ("Linda Vista", 32.787, -117.185, 7, "Linda Vista Rd", "92111", 1),
    ("Tierrasanta", 32.822, -117.096, 7, "Santo Rd", "92124", 1),
    ("College Area", 32.774, -117.070, 9, "El Cajon Blvd", "92115", 2),
    ("City Heights", 32.750, -117.100, 9, "University Ave", "92105", 2),
    ("Normal Heights", 32.762, -117.118, 9, "Adams Ave", "92116", 1),
    ("Barrio Logan", 32.697, -117.140, 8, "Logan Ave", "92113", 1),
    ("San Ysidro", 32.552, -117.040, 8, "San Ysidro Blvd", "92173", 2),
    ("Otay Mesa", 32.573, -117.010, 8, "Otay Mesa Rd", "92154", 1),
    ("Encanto", 32.712, -117.060, 4, "Imperial Ave", "92114", 1),
    ("Paradise Hills", 32.685, -117.055, 4, "Paradise Valley Rd", "92139", 1),
    ("Skyline", 32.700, -117.040, 4, "Meadowbrook Dr", "92114", 1),
    ("Mission Hills", 32.750, -117.180, 3, "Washington St", "92103", 1),
]

TYPES = [("restaurant", 55), ("market", 14), ("mobile", 10), ("bar", 7), ("bakery", 5), ("school", 4), ("caterer", 2), ("other", 3)]
KINDS = {
    "restaurant": ["Kitchen", "Taqueria", "Grill", "Noodle House", "Cafe", "Diner", "Pho House", "Sushi Bar", "Pizzeria", "Cantina"],
    "market": ["Market", "Grocery", "Mini Mart", "Produce"],
    "mobile": ["Taco Truck", "Food Cart", "Lunch Truck"],
    "bar": ["Tavern", "Pub", "Lounge"],
    "bakery": ["Bakery", "Panaderia", "Donuts"],
    "school": ["School Kitchen"],
    "caterer": ["Catering"],
    "other": ["Commissary", "Snack Bar"],
}

# Inspection report items by theme (the numbered items of the California retail
# food inspection report), with an invented but typical description each.
ITEMS = {
    "temperature": [("7", "Improper hot and cold holding temperatures"), ("9", "Cooking time and temperature not met"), ("11", "Improper cooling of cooked food")],
    "handwashing": [("5", "Hands not clean or not properly washed"), ("6", "Handwashing facility blocked or without soap and towels")],
    "vermin": [("23", "Evidence of rodents, insects or other vermin")],
    "sanitizing": [("14", "Food-contact surfaces not clean and sanitized"), ("33", "Nonfood-contact surfaces not clean"), ("39", "Wiping cloths not stored in sanitizer")],
    "storage": [("27", "Food not separated and protected from contamination"), ("30", "Food stored on the floor or uncovered"), ("26", "Unapproved thawing method")],
    "hygiene": [("25", "Personal cleanliness or hair restraint not maintained"), ("4", "Eating, drinking or tobacco use in food preparation area")],
    "equipment": [("36", "Equipment or utensils not in good repair"), ("38", "Thermometers missing or inaccurate")],
    "plumbing": [("21", "Hot and cold water not available at required temperature"), ("40", "Plumbing not properly installed or maintained")],
    "labeling": [("32", "Food not properly labeled"), ("47", "Food handler cards not available")],
    "other": [("44", "Floors, walls or ceilings not clean or in good repair"), ("41", "Garbage and refuse not properly disposed")],
}
THEME_WEIGHTS = [("temperature", 28), ("handwashing", 16), ("sanitizing", 14), ("storage", 12), ("hygiene", 8), ("vermin", 6), ("equipment", 7), ("plumbing", 4), ("labeling", 3), ("other", 2)]
MAJOR_THEMES = {"temperature", "handwashing", "vermin", "storage", "hygiene"}

THROUGH = date(2026, 8, 31)
PER_YEAR = {1: 1, 2: 2, 3: 3}


def grade(score: int) -> str:
    return "A" if score >= 90 else "B" if score >= 80 else "C"


def weighted(rng: random.Random, pairs):
    total = sum(w for _, w in pairs)
    x = rng.uniform(0, total)
    for item, w in pairs:
        x -= w
        if x <= 0:
            return item
    return pairs[-1][0]


def poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    l, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= l:
            return k
        k += 1


def make_place(rng: random.Random, i: int):
    anchor = weighted(rng, [(a, a[6]) for a in ANCHORS])
    name, lat, lon, district, street, zipcode, _ = anchor
    ftype = weighted(rng, TYPES)
    risk_cat = {"restaurant": weighted(rng, [(3, 6), (2, 3), (1, 1)]), "market": weighted(rng, [(1, 5), (2, 4), (3, 1)]),
                "mobile": weighted(rng, [(2, 5), (3, 4), (1, 1)]), "bar": weighted(rng, [(1, 5), (2, 4), (3, 1)]),
                "school": 2, "bakery": weighted(rng, [(2, 6), (1, 3), (3, 1)]), "caterer": 2, "other": 1}[ftype]
    latent = min(0.98, max(0.02, rng.betavariate(2, 5) + {"restaurant": 0.05, "mobile": 0.06}.get(ftype, 0.0)))

    # Inspections over four years, by risk category, with a few skipped.
    inspections = []
    d = THROUGH - timedelta(days=4 * 365)
    while d < THROUGH:
        gap = 365 / PER_YEAR[risk_cat] * rng.uniform(0.7, 1.4)
        d = d + timedelta(days=int(gap))
        if d >= THROUGH:
            break
        score = int(min(100, max(55, round(rng.gauss(96 - 24 * latent, 5)))))
        major = poisson(rng, max(0.0, 2.4 * latent - 0.25))
        minor = poisson(rng, 1 + 4 * latent)
        if major >= 2:
            score = min(score, 89 - 3 * (major - 2))
        closed = major >= 3 and rng.random() < 0.6
        inspections.append({"date": d.isoformat(), "type": "routine", "score": score, "grade": grade(score), "major": major, "minor": minor, "closed": closed})
        if major >= 1 and (closed or rng.random() < 0.5):
            r = d + timedelta(days=rng.randint(3, 14))
            if r < THROUGH:
                rs = min(100, score + rng.randint(5, 15))
                inspections.append({"date": r.isoformat(), "type": "reinspection", "score": rs, "grade": grade(rs), "major": 0 if rng.random() < 0.85 else 1, "minor": poisson(rng, 1), "closed": False})
                d = r
        if rng.random() < 0.35 * latent:
            c = d + timedelta(days=rng.randint(20, 90))
            if c < THROUGH:
                inspections.append({"date": c.isoformat(), "type": "complaint", "score": None, "grade": None, "major": poisson(rng, 0.6 * latent), "minor": poisson(rng, 0.8), "closed": False})
    if not inspections:
        score = int(min(100, max(60, round(rng.gauss(95 - 20 * latent, 5)))))
        inspections.append({"date": (THROUGH - timedelta(days=rng.randint(30, 300))).isoformat(), "type": "routine", "score": score, "grade": grade(score), "major": 0, "minor": poisson(rng, 2), "closed": False})
    inspections.sort(key=lambda x: x["date"])

    # Violations cited in the 36 months before the last visit, one row per
    # citation: the same window the site's record statistics use, so the theme
    # list and the major count agree. Descriptions are optional in the contract
    # and left out of the sample to keep the file small.
    violations = []
    last_date = date.fromisoformat(inspections[-1]["date"])
    cutoff = (last_date - timedelta(days=int(36 * 30.44))).isoformat()
    for insp in inspections:
        if insp["date"] < cutoff:
            continue
        for sev, n in (("major", insp["major"]), ("minor", insp["minor"])):
            for _ in range(n):
                theme = weighted(rng, [(t, w * (2 if (sev == "major" and t in MAJOR_THEMES) else 1)) for t, w in THEME_WEIGHTS])
                code, _desc = rng.choice(ITEMS[theme])
                violations.append({"date": insp["date"], "code": code, "theme": theme, "severity": sev})
    violations = violations[-60:]

    last = inspections[-1]
    routine = [x for x in inspections if x["type"] == "routine"]
    last_routine = routine[-1] if routine else last
    majors_last3 = sum(x["major"] for x in inspections[-3:])
    theme_counts = {}
    for v in violations:
        theme_counts[v["theme"]] = theme_counts.get(v["theme"], 0) + 1
    top_theme = max(theme_counts.items(), key=lambda kv: kv[1])[0] if theme_counts else None
    closed_years = sorted({x["date"][:4] for x in inspections if x["closed"]})
    reinsp = sum(1 for x in inspections if x["type"] == "reinspection")
    months_since = max(1, int((THROUGH - date.fromisoformat(last["date"])).days / 30.44))
    complaints = sum(1 for x in inspections if x["type"] == "complaint" and x["date"] >= (THROUGH - timedelta(days=730)).isoformat())
    scores = [x["score"] for x in routine if x["score"] is not None]
    falling = len(scores) >= 3 and scores[-1] <= sum(scores[:-1]) / len(scores[:-1]) - 5

    pool = [
        (f"Last routine score {last_routine['score']}", "last_routine_score", last_routine["score"], 0.9 - last_routine["score"] / 200),
        (f"{majors_last3} major violations in the last 3 inspections", "majors_last3", majors_last3, 0.25 * majors_last3),
        (f"Risk category {risk_cat}", "risk_category", risk_cat, 0.08 * risk_cat),
        (f"Facility type: {ftype}", "facility_type", ftype, 0.12 if ftype in ("restaurant", "mobile") else 0.02),
        (f"{months_since} months since last inspection", "months_since_last", months_since, 0.01 * months_since),
    ]
    if top_theme:
        pool.append((f"{top_theme} cited {theme_counts[top_theme]} times", f"theme_{top_theme}", theme_counts[top_theme], 0.12 * theme_counts[top_theme]))
    if closed_years:
        pool.append((f"Closed by the County {closed_years[-1]}", "closed_recent", int(closed_years[-1]), 0.7))
    if reinsp:
        pool.append((f"Reinspection required {reinsp} times", "reinspections", reinsp, 0.15 * reinsp))
    if falling:
        pool.append((f"Score falling: {scores[-2]} to {scores[-1]}", "score_delta", scores[-1] - scores[-2], 0.35))
    if complaints:
        pool.append((f"{complaints} complaints in 2 years", "complaints_2y", complaints, 0.2 * complaints))
    if rng.random() < 0.1:
        yr = rng.choice(["2024", "2025", "2026"])
        pool.append((f"Change of ownership {yr}", "ownership_change", int(yr), 0.3))
    if rng.random() < 0.5:
        nb = int(round(rng.gauss(90 - 8 * latent, 3)))
        pool.append((f"Neighbours' average score {nb}", "neighbour_mean_score", nb, 0.01 * (95 - nb)))
    pool.sort(key=lambda t: -t[3])
    shap = [{"feature_name": fn, "display_label": lbl, "raw_value": rv, "shap_value": round(sv + rng.uniform(0, 0.05), 3)} for lbl, fn, rv, sv in pool[:5]]

    kind = rng.choice(KINDS[ftype])
    return {
        "latent": latent,
        "feature": {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon + rng.gauss(0, 0.007), 6), round(lat + rng.gauss(0, 0.006), 6)]},
            "properties": {
                "facility_id": f"SAMPLE-{i:05d}",
                "name": f"Sample {kind} {i:03d}",
                "address": f"{rng.randint(100, 9899)} {street}, San Diego, CA {zipcode}",
                "facility_type": ftype,
                "risk_category": risk_cat,
                "council_district": district,
                "area": name,
                "last_inspection": last,
                "inspections": inspections,
                "violations": violations,
                "shap_features": shap,
            },
        },
    }


def build(n: int, seed: int = 7, candidates: int = 8200):
    rng = random.Random(seed)
    places = [make_place(rng, i + 1) for i in range(n)]
    for p in places:
        p["model"] = p["latent"] + rng.gauss(0, 0.08)
        p["positive"] = p["latent"] + rng.gauss(0, 0.12) > 0.66
    places.sort(key=lambda p: -p["model"])
    features = []
    for rank, p in enumerate(places, start=1):
        f = p["feature"]
        f["properties"]["rank"] = rank
        f["properties"]["percentile"] = round(100 * (1 - (rank - 1) / candidates), 2)
        f["properties"]["is_known_positive"] = bool(p["positive"])
        f["properties"]["oof_rank"] = rank
        features.append(f)
    base_rate = 0.085
    total = int(round(base_rate * candidates))
    catch = {}
    for k in (50, 100, 200, 500, 800, 1000):
        if k > n:
            continue
        catch[str(k)] = {"caught": sum(1 for f in features[:k] if f["properties"]["is_known_positive"]), "total": total}
    meta = {
        "sample": True,
        "model": "sample export, no model yet",
        "run": "sample",
        "generated": date.today().isoformat(),
        "candidates": candidates,
        "label": "at least one major violation at the next routine inspection",
        "label_window": "2026-09-01 to 2027-08-31",
        "inspections_through": THROUGH.isoformat(),
        "catch": catch,
        "source": {"name": "invented sample; no real facility or inspection", "url": None},
    }
    return {"type": "FeatureCollection", "features": features}, meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    fc, meta = build(args.n, args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "facilities.geojson").write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
    (args.out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    size = (args.out / "facilities.geojson").stat().st_size
    print(f"wrote {len(fc['features'])} sample places to {args.out} ({size / 1e6:.1f} MB); catch {meta['catch']}")


if __name__ == "__main__":
    main()
