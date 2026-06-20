import json
import os
import sys
from pathlib import Path

import click
import pandas as pd

OUTPUT_DIR = os.path.join("dashboard", "public", "data")

REQUIRED_PANEL_COLUMNS = [
    "node_id", "lon", "lat", "tweedie_score", "percentile",
    "council_district", "is_known_emergent", "is_crash_active",
    "crashes_training", "crash_history_json", "shap_json",
]

VALID_DISTRICTS = set(range(0, 10))


def validate_panel(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_PANEL_COLUMNS if c not in df.columns]
    if missing:
        click.echo(f"ERROR: Missing columns: {', '.join(missing)}", err=True)
        sys.exit(1)

    invalid_districts = set(df["council_district"].unique()) - VALID_DISTRICTS
    if invalid_districts:
        click.echo(f"ERROR: council_district out of range 0–9: {invalid_districts}", err=True)
        sys.exit(1)

    for col in ("crash_history_json", "shap_json"):
        for i, val in enumerate(df[col]):
            try:
                json.loads(val)
            except Exception:
                click.echo(f"ERROR: Row {i} has invalid JSON in column '{col}'", err=True)
                sys.exit(1)

    if df["node_id"].duplicated().any():
        click.echo("ERROR: Duplicate node_id values found", err=True)
        sys.exit(1)


def write_geojson(
    panel: pd.DataFrame,
    names: pd.DataFrame,
    output_dir: str | Path = OUTPUT_DIR,
    top_n: int = 1000,
) -> None:
    output_dir = Path(output_dir)
    df = panel.copy()
    df = df.merge(names[["intersection_id", "intersection_name"]], on="intersection_id", how="left")
    df = df.sort_values("tweedie_score", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    # Include top_n ranked sites + ALL emergent sites (so missed positives are visible on the map)
    in_top_n = df["rank"] <= top_n
    is_emergent = df["is_known_emergent"].astype(bool)
    df = df[in_top_n | is_emergent].reset_index(drop=True)

    features = []
    for _, row in df.iterrows():
        rank = int(row["rank"])
        district = int(row["council_district"])
        crash_history = json.loads(row["crash_history_json"])
        shap_features = json.loads(row["shap_json"])

        props = {
            "rank": rank,
            "intersection_name": str(row.get("intersection_name", f"Node {row['node_id']}")),
            "council_district": district,
            "percentile": round(float(row["percentile"]), 4),
            "is_known_emergent": bool(row["is_known_emergent"]),
            "is_crash_active": bool(row["is_crash_active"]),
            "crashes_training": int(row["crashes_training"]),
            "crash_history": crash_history,
            "shap_features": shap_features,
        }

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [round(float(row["lon"]), 6), round(float(row["lat"]), 6)],
            },
            "properties": props,
        })

    geojson = {"type": "FeatureCollection", "features": features}
    output_dir.mkdir(parents=True, exist_ok=True)
    geojson_path = output_dir / "intersections.geojson"
    with open(geojson_path, "w") as f:
        json.dump(geojson, f)


def write_districts(
    panel: pd.DataFrame,
    output_dir: str | Path = OUTPUT_DIR,
) -> None:
    output_dir = Path(output_dir)
    df = panel.copy()
    df = df.sort_values("tweedie_score", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1

    district_counts: dict[int, dict[str, int]] = {
        d: {"top_50_count": 0, "top_100_count": 0, "top_200_count": 0, "top_500_count": 0}
        for d in range(1, 10)
    }

    for _, row in df.iterrows():
        rank = int(row["rank"])
        district = int(row["council_district"])
        if district not in district_counts:
            continue
        if rank <= 50:
            district_counts[district]["top_50_count"] += 1
        if rank <= 100:
            district_counts[district]["top_100_count"] += 1
        if rank <= 200:
            district_counts[district]["top_200_count"] += 1
        if rank <= 500:
            district_counts[district]["top_500_count"] += 1

    districts = [
        {"district": d, **counts}
        for d, counts in sorted(district_counts.items())
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    districts_path = output_dir / "districts.json"
    with open(districts_path, "w") as f:
        json.dump(districts, f, indent=2)


@click.command()
@click.option("--panel", required=True, type=click.Path(exists=True),
              help="Path to scored panel parquet")
@click.option("--names", required=True, type=click.Path(exists=True),
              help="Path to intersection names CSV")
@click.option("--top-n", default=1000, show_default=True, type=int,
              help="Number of intersections to export")
def export(panel: str, names: str, top_n: int) -> None:
    df = pd.read_parquet(panel)
    validate_panel(df)

    names_df = pd.read_csv(names, dtype={"intersection_id": "str", "intersection_name": "str"})

    out_dir = Path(OUTPUT_DIR)
    write_geojson(df, names_df, output_dir=out_dir, top_n=top_n)
    write_districts(df, output_dir=out_dir)

    geojson_path = out_dir / "intersections.geojson"
    districts_path = out_dir / "districts.json"

    with open(geojson_path) as f:
        geojson = json.load(f)
    features = geojson["features"]
    n_emergent = sum(1 for feat in features if feat["properties"]["is_known_emergent"])
    n_districts = len({feat["properties"]["council_district"] for feat in features})

    click.echo(
        f"Exported {len(features)} intersections | {n_districts} districts | "
        f"{n_emergent} known emergents\n"
        f"-> {geojson_path}\n"
        f"-> {districts_path}"
    )


if __name__ == "__main__":
    export()
