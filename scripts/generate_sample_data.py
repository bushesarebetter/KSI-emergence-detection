import io
import json
import os
import random
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

STREET_NAMES = [
    "El Cajon Blvd", "University Ave", "Adams Ave", "Garnet Ave",
    "Mission Blvd", "Sports Arena Blvd", "Rosecrans St", "Midway Dr",
    "Imperial Ave", "Market St", "National Ave", "Main St",
    "Broadway", "Island Ave", "Harbor Dr", "Kettner Blvd",
    "India St", "Laurel St", "Washington St", "Park Blvd",
    "30th St", "32nd St", "35th St", "54th St",
    "College Ave", "Euclid Ave", "Division St", "Ocean View Blvd",
    "Highland Ave", "Fairmount Ave", "Wightman St", "Montezuma Rd",
    "Alvarado Rd", "70th St", "Lake Murray Blvd", "Jackson Dr",
]

LAT_MIN = 32.55
LAT_MAX = 32.85
LON_MIN = -117.28
LON_MAX = -117.05

LAT_RANGE = LAT_MAX - LAT_MIN
LON_RANGE = LON_MAX - LON_MIN

SHAP_FEATURE_SPECS = [
    ("years_since_last_crash",   "{v:.1f} years since last crash",         0.1, 8.0),
    ("changepoint_prob",         "{v_pct:.0f}% structural break probability", 0.0, 1.0),
    ("distinct_crash_days_72mo", "{v_int} distinct crash days (72 months)", 0,   45),
    ("crashes_72mo",             "{v_int} crashes in last 72 months",       0,   60),
    ("ewma_crashes",             "EWMA crash rate {v:.1f}",                  0.0, 8.0),
]

YEARS = list(range(2013, 2022))

OUTPUT_DIR = os.path.join("dashboard", "public", "data")


def assign_district(lat: float, lon: float) -> int:
    col = int((lon - LON_MIN) / LON_RANGE * 3)
    row = int((lat - LAT_MIN) / LAT_RANGE * 3)
    col = min(col, 2)
    row = min(row, 2)
    return row * 3 + col + 1


def make_intersection_name(rng: random.Random) -> str:
    a, b = rng.sample(STREET_NAMES, 2)
    return f"{a} & {b}"


def make_crash_history(rank: int, rng: random.Random) -> list:
    history = []
    for year in YEARS:
        weight = 1.0
        if year >= 2019 and rank <= 200:
            weight = 1.0 + (rank <= 100) * 0.8 + (rank <= 50) * 0.7
        ksi = rng.randint(0, max(1, int(2 * weight)))
        ksi = min(ksi, 2)
        injury = rng.randint(0, max(1, int(5 * weight)))
        injury = min(injury, 5)
        pdo = rng.randint(0, max(1, int(8 * weight)))
        pdo = min(pdo, 8)
        history.append({"year": year, "ksi": ksi, "injury": injury, "pdo": pdo})
    return history


def make_shap_features(rank: int, rng: random.Random) -> list:
    base_scale = max(0.05, 1.0 - (rank - 1) / 500.0)
    features = []
    for name, template, lo, hi in SHAP_FEATURE_SPECS:
        raw = rng.uniform(lo, hi) if isinstance(lo, float) else rng.randint(int(lo), int(hi))
        shap_val = rng.uniform(0.05, 0.6) * base_scale

        if name == "changepoint_prob":
            label = template.format(v_pct=raw * 100)
        elif name in ("distinct_crash_days_72mo", "crashes_72mo"):
            label = template.format(v_int=int(raw))
        else:
            label = template.format(v=raw)

        features.append({
            "feature_name": name,
            "display_label": label,
            "shap_value": round(shap_val, 4),
            "raw_value": round(raw, 4) if isinstance(raw, float) else raw,
        })

    features.sort(key=lambda x: x["shap_value"], reverse=True)
    return features


def generate() -> None:
    rng = random.Random(42)

    emergent_ranks = set()
    emergent_districts: dict[int, list[int]] = {}
    candidate_pool = list(range(1, 201))
    rng.shuffle(candidate_pool)
    for rank in candidate_pool:
        if len(emergent_ranks) >= 12:
            break
        lat = rng.uniform(LAT_MIN, LAT_MAX)
        lon = rng.uniform(LON_MIN, LON_MAX)
        d = assign_district(lat, lon)
        emergent_districts.setdefault(d, [])
        if len(emergent_districts) < 4 or len(emergent_districts[d]) < 4:
            emergent_ranks.add(rank)
            emergent_districts[d].append(rank)

    while len(emergent_ranks) < 12:
        rank = rng.choice(candidate_pool)
        emergent_ranks.add(rank)

    district_counts: dict[int, dict[str, int]] = {
        d: {"top_50_count": 0, "top_100_count": 0, "top_200_count": 0, "top_500_count": 0}
        for d in range(1, 10)
    }

    features = []
    for rank in range(1, 501):
        lat = rng.uniform(LAT_MIN, LAT_MAX)
        lon = rng.uniform(LON_MIN, LON_MAX)
        district = assign_district(lat, lon)
        name = make_intersection_name(rng)
        is_emergent = rank in emergent_ranks
        is_active = rank <= 100 or (rank <= 500 and rng.random() < 0.65)

        if rank <= 100:
            crashes = rng.randint(5, 25)
        elif rank <= 300:
            crashes = rng.randint(1, 10)
        else:
            crashes = rng.randint(0, 5)

        percentile = round(100.0 * (500 - rank) / 500, 2)

        crash_history = make_crash_history(rank, rng)
        shap_features = make_shap_features(rank, rng)

        props = {
            "rank": rank,
            "intersection_name": name,
            "council_district": district,
            "percentile": percentile,
            "is_known_emergent": is_emergent,
            "is_crash_active": is_active,
            "crashes_training": crashes,
            "crash_history": crash_history,
            "shap_features": shap_features,
        }

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
            "properties": props,
        })

        if rank <= 50:
            district_counts[district]["top_50_count"] += 1
        if rank <= 100:
            district_counts[district]["top_100_count"] += 1
        if rank <= 200:
            district_counts[district]["top_200_count"] += 1
        district_counts[district]["top_500_count"] += 1

    geojson = {"type": "FeatureCollection", "features": features}

    districts = [
        {"district": d, **counts}
        for d, counts in sorted(district_counts.items())
    ]

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    geojson_path = os.path.join(OUTPUT_DIR, "intersections.geojson")
    districts_path = os.path.join(OUTPUT_DIR, "districts.json")

    with open(geojson_path, "w") as f:
        json.dump(geojson, f)

    with open(districts_path, "w") as f:
        json.dump(districts, f, indent=2)

    print(
        "Sample data written.\n"
        f"Intersections: 500 | Known emergents: {len(emergent_ranks)} | Districts: 9\n"
        f"→ {geojson_path}\n"
        f"→ {districts_path}"
    )


if __name__ == "__main__":
    generate()
