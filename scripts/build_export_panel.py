import json
import logging
import pickle
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import shap
from scipy.spatial import cKDTree

from src.utils import buffer_feet, load_config, project_root

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

SCORE_COL = "A_crash_only__xgb_tweedie"
KSI_SEVERITY = {1, 2}
INJURY_SEVERITY = {3, 4}
FEATURE_YEARS = list(range(2016, 2022))
COUNCIL_DISTRICTS_URL = (
    "https://geo.sandag.org/server/rest/directories/downloads/Council_Districts.geojson"
)
COUNCIL_DISTRICTS_CACHE = "data/proc/council_districts.geojson"
COUNCIL_DISTRICT_FIELD = "DISTRICT"
COUNCIL_DISTRICT_JUR_FIELD = "JUR_NAME"
COUNCIL_DISTRICT_JUR_VALUE = "SAN DIEGO"
TOP_N_DEFAULT = 1000
DISPLAY_LABEL_TEMPLATES: dict[str, str] = {
    "years_since_last_crash":   "{v:.1f} years since last crash",
    "changepoint_prob":         "{v100:.0f}% structural break probability",
    "distinct_crash_days_72mo": "{v:.0f} distinct crash days (72 months)",
    "crashes_72mo":             "{v:.0f} crashes in last 72 months",
    "crashes_36mo":             "{v:.0f} crashes in last 36 months",
    "ewma_crashes":             "EWMA crash rate {v:.1f}",
    "mann_kendall_tau":         "Mann-Kendall trend τ = {v:.2f}",
    "crash_trend_slope":        "Crash trend slope {v:+.2f}/yr",
    "emergence_velocity":       "Emergence velocity {v:+.1f}",
    "emergence_acceleration":   "Emergence acceleration {v:+.2f}",
    "momentum_ratio":           "Late/early crash ratio {v:.2f}",
    "ped_crashes_72mo":         "{v:.0f} pedestrian crashes (72 months)",
    "bike_crashes_72mo":        "{v:.0f} bicycle crashes (72 months)",
    "broadside_72mo":           "{v:.0f} broadside crashes (72 months)",
    "left_turn_72mo":           "{v:.0f} left-turn crashes (72 months)",
    "dui_72mo":                 "{v:.0f} DUI crashes (72 months)",
    "night_72mo":               "{v:.0f} night crashes (72 months)",
    "worst_severity_72mo":      "Worst severity code {v:.0f}",
    "covid_period_share":       "COVID-period crash share {v:.2f}",
    "ped_row_violation_72mo":   "{v:.0f} ped right-of-way violations (72mo)",
}


def load_panels(cfg: dict, root: Path) -> gpd.GeoDataFrame:
    candidates = gpd.read_parquet(root / cfg["paths"]["model"] / "candidate_panel.parquet")
    scores = pd.read_parquet(root / cfg["paths"]["model"] / "frozen_scores.parquet")
    if SCORE_COL not in scores.columns:
        raise ValueError(f"Score column '{SCORE_COL}' not found in frozen_scores.parquet")
    features = pd.read_parquet(root / cfg["paths"]["model"] / "feature_table.parquet")

    names_path = root / cfg["paths"]["proc"] / "intersection_names.csv"
    if not names_path.exists():
        raise FileNotFoundError("Run scripts/build_intersection_names.py first.")
    names = pd.read_csv(names_path, dtype={"intersection_id": "str", "intersection_name": "str"})

    merged = candidates.merge(scores, on="intersection_id", how="left")
    merged = merged.merge(features, on="intersection_id", how="left")
    merged = merged.merge(names, on="intersection_id", how="left")

    merged[SCORE_COL] = merged[SCORE_COL].fillna(0.0)
    mask = merged["intersection_name"].isna()
    merged.loc[mask, "intersection_name"] = "Intersection " + merged.loc[mask, "intersection_id"].str[:8]

    return merged


def compute_rank_and_percentile(merged: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    n = len(merged)
    merged = merged.copy()
    merged["rank"] = (-merged[SCORE_COL]).rank(method="first").astype(int)
    merged["percentile"] = ((1 - (merged["rank"] - 1) / n) * 100).clip(0, 100)
    return merged


def load_council_districts(root: Path) -> gpd.GeoDataFrame | None:
    cache_path = root / COUNCIL_DISTRICTS_CACHE
    if not cache_path.exists():
        try:
            resp = requests.get(COUNCIL_DISTRICTS_URL, timeout=60)
            resp.raise_for_status()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(resp.content)
        except Exception as exc:
            logging.warning(
                "Could not download council districts (%s). "
                "council_district will be set to 0. "
                "Manually download %s to %s to enable district assignment.",
                exc, COUNCIL_DISTRICTS_URL, COUNCIL_DISTRICTS_CACHE,
            )
            return None

    gdf = gpd.read_file(cache_path)

    city_mask = gdf[COUNCIL_DISTRICT_JUR_FIELD].str.upper() == COUNCIL_DISTRICT_JUR_VALUE
    gdf = gdf[city_mask].copy()

    if len(gdf) == 0:
        logging.warning(
            "No San Diego City rows found after filtering on %s == '%s'. "
            "Check the JUR_NAME values in the downloaded file.",
            COUNCIL_DISTRICT_JUR_FIELD, COUNCIL_DISTRICT_JUR_VALUE,
        )
        return None

    gdf = gdf[[COUNCIL_DISTRICT_FIELD, "geometry"]].rename(
        columns={COUNCIL_DISTRICT_FIELD: "district"}
    )
    gdf["district"] = gdf["district"].astype(int)
    return gdf


def assign_council_districts(
    merged: gpd.GeoDataFrame,
    districts: gpd.GeoDataFrame | None,
) -> gpd.GeoDataFrame:
    merged = merged.copy()
    if districts is None:
        merged["council_district"] = 0
        return merged

    if "geometry_4326" in merged.columns:
        nodes_4326 = merged.set_geometry("geometry_4326")
        nodes_4326 = nodes_4326.set_crs("EPSG:4326", allow_override=True)
    else:
        nodes_4326 = merged.to_crs("EPSG:4326")

    districts_4326 = districts.to_crs("EPSG:4326")
    joined = gpd.sjoin(
        nodes_4326[["intersection_id", "geometry_4326" if "geometry_4326" in merged.columns else "geometry"]],
        districts_4326[["district", "geometry"]],
        how="left",
        predicate="within",
    )
    joined = joined[["intersection_id", "district"]].drop_duplicates("intersection_id")

    merged = merged.merge(joined, on="intersection_id", how="left")
    merged["district"] = merged["district"].fillna(0).astype(int)
    merged = merged.rename(columns={"district": "council_district"})
    return merged


def build_crash_history(
    merged: gpd.GeoDataFrame,
    cfg: dict,
    root: Path,
) -> dict[str, list[dict]]:
    crashes_raw = gpd.read_parquet(root / cfg["paths"]["proc"] / "crashes_4326.parquet")
    feature_start = pd.Timestamp(cfg["windows"]["feature_start"])
    feature_end = pd.Timestamp(cfg["windows"]["feature_end"])
    crashes_raw = crashes_raw[
        (crashes_raw["date"] >= feature_start) & (crashes_raw["date"] <= feature_end)
    ].copy()

    crashes_2230 = crashes_raw.to_crs("EPSG:2230")

    node_xy = np.stack([merged.geometry.x.values, merged.geometry.y.values], axis=1)
    crash_xy = np.stack([crashes_2230.geometry.x.values, crashes_2230.geometry.y.values], axis=1)

    buf = buffer_feet(cfg)
    tree = cKDTree(node_xy)
    dists, idxs = tree.query(crash_xy, k=1)

    keep_mask = dists <= buf
    matched_node_idx = idxs[keep_mask]
    matched_crashes = crashes_2230.iloc[keep_mask].copy()
    matched_crashes["node_idx"] = matched_node_idx
    matched_crashes["intersection_id"] = merged["intersection_id"].iloc[matched_node_idx].values
    matched_crashes["year"] = matched_crashes["date"].dt.year

    def parse_severity(val) -> str:
        try:
            sev = int(val)
        except (ValueError, TypeError):
            return "pdo"
        if sev in KSI_SEVERITY:
            return "ksi"
        if sev in INJURY_SEVERITY:
            return "injury"
        return "pdo"

    matched_crashes["sev_cat"] = matched_crashes["severity"].apply(parse_severity)

    rows = []
    for sev_cat in ("ksi", "injury", "pdo"):
        sub = matched_crashes[matched_crashes["sev_cat"] == sev_cat]
        grp = sub.groupby(["intersection_id", "year"]).size().reset_index(name=sev_cat)
        rows.append(grp)

    all_iids = merged["intersection_id"].tolist()
    index = pd.MultiIndex.from_product([all_iids, FEATURE_YEARS], names=["intersection_id", "year"])
    base = pd.DataFrame(index=index).reset_index()
    base["ksi"] = 0
    base["injury"] = 0
    base["pdo"] = 0

    for sev_df in rows:
        col = sev_df.columns[-1]
        base = base.merge(sev_df.rename(columns={col: f"_{col}"}), on=["intersection_id", "year"], how="left")
        base[col] = base[col] + base[f"_{col}"].fillna(0).astype(int)
        base = base.drop(columns=[f"_{col}"])

    result: dict[str, list[dict]] = {}
    for iid, grp in base.groupby("intersection_id"):
        result[iid] = [
            {"year": int(r["year"]), "ksi": int(r["ksi"]), "injury": int(r["injury"]), "pdo": int(r["pdo"])}
            for _, r in grp.sort_values("year").iterrows()
        ]
    return result


def format_display_label(feature_name: str, raw_value: float) -> str:
    tmpl = DISPLAY_LABEL_TEMPLATES.get(feature_name)
    if tmpl is None:
        return f"{feature_name}: {raw_value:.2f}"
    return tmpl.format_map({"v": raw_value, "v100": raw_value * 100})


def build_shap_features(
    merged: gpd.GeoDataFrame,
    cfg: dict,
    root: Path,
) -> dict[str, list[dict]]:
    model_path = root / cfg["paths"]["model"] / "xgb_tweedie.pkl"
    with open(model_path, "rb") as f:
        model = pickle.load(f)

    feature_cols: list[str] = cfg["feature_groups"]["crash_only"]
    X = merged[feature_cols].fillna(0.0).values.astype(float)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    result: dict[str, list[dict]] = {}
    for i, iid in enumerate(merged["intersection_id"]):
        abs_shap = np.abs(shap_values[i])
        top5_idx = np.argsort(abs_shap)[::-1][:5]
        entry = []
        for j in top5_idx:
            raw_val = float(X[i, j])
            entry.append({
                "feature_name": feature_cols[j],
                "shap_value": float(abs_shap[j]),
                "raw_value": raw_val,
                "display_label": format_display_label(feature_cols[j], raw_val),
            })
        result[iid] = entry
    return result


def assemble_export_panel(
    merged: gpd.GeoDataFrame,
    crash_history: dict[str, list[dict]],
    shap_features: dict[str, list[dict]],
    cfg: dict,
    root: Path,
) -> pd.DataFrame:
    spine = pd.read_parquet(
        root / cfg["paths"]["proc"] / "nodes_spine_2230.parquet",
        columns=["intersection_id", "osm_id"],
    )
    df = merged.merge(spine[["intersection_id", "osm_id"]], on="intersection_id", how="left")

    df["node_id"] = df["osm_id"].fillna(0).astype("int64")
    df["tweedie_score"] = df[SCORE_COL].astype("float64")
    df["is_known_emergent"] = df["y_ge2"].fillna(0).astype(bool)
    df["is_crash_active"] = (df["crashes_72mo"].fillna(0) > 0)
    df["crashes_training"] = df["crashes_72mo"].fillna(0).round().astype("int64")

    df["crash_history_json"] = df["intersection_id"].map(
        lambda iid: json.dumps(crash_history.get(iid, []))
    )
    df["shap_json"] = df["intersection_id"].map(
        lambda iid: json.dumps(shap_features.get(iid, []))
    )

    keep_cols = [
        "intersection_id", "node_id", "lon", "lat",
        "tweedie_score", "percentile", "rank",
        "council_district",
        "is_known_emergent", "is_crash_active", "crashes_training",
        "crash_history_json", "shap_json",
    ]
    return df[keep_cols].reset_index(drop=True)


def main() -> None:
    try:
        cfg = load_config()
        root = project_root()

        logging.info("Step 1: loading panels...")
        merged = load_panels(cfg, root)

        logging.info("Step 2: computing rank and percentile...")
        merged = compute_rank_and_percentile(merged)

        logging.info("Step 3: loading council districts...")
        districts = load_council_districts(root)

        logging.info("Step 4: assigning council districts...")
        merged = assign_council_districts(merged, districts)

        logging.info("Step 5: building crash history (may take 1-2 min)...")
        t0 = time.time()
        crash_history = build_crash_history(merged, cfg, root)
        logging.info("  crash history done in %.1fs", time.time() - t0)

        logging.info("Step 6: computing SHAP features (may take 3-6 min)...")
        t0 = time.time()
        shap_features = build_shap_features(merged, cfg, root)
        logging.info("  SHAP done in %.1fs", time.time() - t0)

        logging.info("Step 7: assembling export panel...")
        panel_df = assemble_export_panel(merged, crash_history, shap_features, cfg, root)

        logging.info("Step 8: exporting to dashboard files...")
        from scripts.export_predictions import write_districts, write_geojson

        names_path = root / cfg["paths"]["proc"] / "intersection_names.csv"
        names_df = pd.read_csv(names_path, dtype={"intersection_id": "str", "intersection_name": "str"})

        out_dir = root / "dashboard" / "public" / "data"
        write_geojson(panel_df, names_df, output_dir=out_dir, top_n=TOP_N_DEFAULT)
        write_districts(panel_df, output_dir=out_dir)

        n_districts = panel_df[panel_df["rank"] <= TOP_N_DEFAULT]["council_district"].nunique()
        n_emergent = int(panel_df[panel_df["rank"] <= TOP_N_DEFAULT]["is_known_emergent"].sum())

        print(
            f"Export panel built: {min(len(panel_df), TOP_N_DEFAULT)} intersections | "
            f"{n_districts} districts | {n_emergent} known emergents"
        )
        print(f"-> {out_dir / 'intersections.geojson'}")
        print(f"-> {out_dir / 'districts.json'}")
        sys.exit(0)

    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
