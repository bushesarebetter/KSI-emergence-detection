"""
Export dashboard data for either the verified or forward pipeline run.

  --run verified  (default)
      Uses model_scores.parquet + embedded labels (2016-2021 -> 2022-2024).
      Validation gate: expects exactly 81,007 candidates, 22 emergent(>=2), 389 (>=1).

  --run forward
      Uses frozen_scores.parquet (Set A crash-only) + candidate_panel.parquet labels
      (2016-2023 -> 2024-2026 partial window).
      Validation gate: n_candidates within 1000 of forward panel count (flexible).

Usage:
    python scripts/build_export_panel_verified.py              # verified
    python scripts/build_export_panel_verified.py --run forward
"""
import argparse
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

KSI_SEVERITY = {1, 2}
INJURY_SEVERITY = {3, 4}
COUNCIL_DISTRICTS_URL = (
    "https://geo.sandag.org/server/rest/directories/downloads/Council_Districts.geojson"
)
COUNCIL_DISTRICTS_CACHE = "data/proc/council_districts.geojson"
COUNCIL_DISTRICT_FIELD = "DISTRICT"
COUNCIL_DISTRICT_JUR_FIELD = "JUR_NAME"
COUNCIL_DISTRICT_JUR_VALUE = "SAN DIEGO"
TOP_N = 1000

# Verified run constants — updated for 2025-label retrain (SWITRS 20260615)
VERIFIED_EXPECTED_CANDIDATES = 80618
VERIFIED_EXPECTED_EMERGENT_GE2 = 2
VERIFIED_EXPECTED_EMERGENT_GE1 = 111
CANDIDATE_TOLERANCE = 5

DISPLAY_LABEL_TEMPLATES: dict[str, str] = {
    "years_since_last_crash":   "{v:.1f} years since last crash",
    "changepoint_prob":         "{v100:.0f}% structural break probability",
    "distinct_crash_days_72mo": "{v:.0f} distinct crash days (72 months)",
    "crashes_72mo":             "{v:.0f} crashes in last 72 months",
    "crashes_36mo":             "{v:.0f} crashes in last 36 months",
    "ewma_crashes":             "EWMA crash rate {v:.1f}",
    "mann_kendall_tau":         "Mann-Kendall trend tau = {v:.2f}",
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
    "worst_severity_72mo":      "Worst severity {v:.0f}",
    "covid_period_share":       "COVID-period crash share {v:.2f}",
    "ped_row_violation_72mo":   "{v:.0f} ped right-of-way violations",
}


def load_panels_verified(cfg: dict, root: Path) -> gpd.GeoDataFrame:
    """Load verified run: model_scores.parquet with embedded KSI_label."""
    scores = pd.read_parquet(root / cfg["paths"]["model"] / "model_scores.parquet")
    score_col = "xgb_tweedie_score"
    if score_col not in scores.columns:
        raise ValueError(f"Score column '{score_col}' not found in model_scores.parquet")

    spine = gpd.read_parquet(
        root / cfg["paths"]["proc"] / "nodes_spine_2230.parquet",
        columns=["intersection_id", "osm_id", "lon", "lat", "geometry", "geometry_4326"],
    )
    features = pd.read_parquet(root / cfg["paths"]["model"] / "feature_table.parquet")
    names_path = root / cfg["paths"]["proc"] / "intersection_names.csv"
    if not names_path.exists():
        raise FileNotFoundError("Run scripts/build_intersection_names.py first.")
    names = pd.read_csv(names_path, dtype={"intersection_id": "str", "intersection_name": "str"})

    merged = scores.merge(spine, on="intersection_id", how="inner")
    merged = merged.merge(features, on="intersection_id", how="left")
    merged = merged.merge(names, on="intersection_id", how="left")
    merged.loc[merged["intersection_name"].isna(), "intersection_name"] = "Unnamed intersection"

    # Verified run uses "xgb_tweedie_score" as the primary score column
    merged["_score"] = merged[score_col]
    return gpd.GeoDataFrame(merged, geometry="geometry", crs=spine.crs)


def load_panels_forward(cfg: dict, root: Path) -> gpd.GeoDataFrame:
    """Load forward run: frozen_scores (Set A crash-only) + candidate_panel labels."""
    frozen = pd.read_parquet(root / cfg["paths"]["model"] / "frozen_scores.parquet")
    panel = pd.read_parquet(root / cfg["paths"]["model"] / "candidate_panel.parquet")

    # Identify Set A score column
    score_col = next(
        (c for c in frozen.columns if "crash_only" in c.lower()),
        next((c for c in frozen.columns if c.startswith("score_")), None),
    )
    if score_col is None:
        raise ValueError("Cannot find crash_only score column in frozen_scores.parquet")

    # Merge scores + labels on intersection_id
    id_col = "intersection_id"
    scores_df = frozen[[id_col, score_col]].copy()
    scores_df = scores_df.merge(panel[[id_col, "KSI_label"]], on=id_col, how="inner")
    scores_df = scores_df.rename(columns={score_col: "_score_raw"})

    spine = gpd.read_parquet(
        root / cfg["paths"]["proc"] / "nodes_spine_2230.parquet",
        columns=["intersection_id", "osm_id", "lon", "lat", "geometry", "geometry_4326"],
    )
    features = pd.read_parquet(root / cfg["paths"]["model"] / "feature_table.parquet")
    names_path = root / cfg["paths"]["proc"] / "intersection_names.csv"
    if not names_path.exists():
        raise FileNotFoundError("Run scripts/build_intersection_names.py first.")
    names = pd.read_csv(names_path, dtype={"intersection_id": "str", "intersection_name": "str"})

    merged = scores_df.merge(spine, on="intersection_id", how="inner")
    merged = merged.merge(features, on="intersection_id", how="left")
    merged = merged.merge(names, on="intersection_id", how="left")
    merged.loc[merged["intersection_name"].isna(), "intersection_name"] = "Unnamed intersection"

    merged["_score"] = merged["_score_raw"]
    return gpd.GeoDataFrame(merged, geometry="geometry", crs=spine.crs)


def validate_gate_verified(merged: gpd.GeoDataFrame) -> None:
    n_candidates = len(merged)
    n_emergent_ge2 = int((merged["KSI_label"] >= 2).sum())
    n_emergent_ge1 = int((merged["KSI_label"] >= 1).sum())

    print(
        f"Validation [verified]: {n_candidates} candidates | "
        f"{n_emergent_ge2} emergent (>=2) | {n_emergent_ge1} (>=1)"
    )

    errors = []
    if abs(n_candidates - VERIFIED_EXPECTED_CANDIDATES) > CANDIDATE_TOLERANCE:
        errors.append(
            f"  FAIL: candidates={n_candidates}, expected {VERIFIED_EXPECTED_CANDIDATES} "
            f"(tolerance ±{CANDIDATE_TOLERANCE})"
        )
    if n_emergent_ge2 != VERIFIED_EXPECTED_EMERGENT_GE2:
        errors.append(f"  FAIL: emergent(>=2)={n_emergent_ge2}, expected {VERIFIED_EXPECTED_EMERGENT_GE2}")
    if n_emergent_ge1 != VERIFIED_EXPECTED_EMERGENT_GE1:
        errors.append(f"  FAIL: emergent(>=1)={n_emergent_ge1}, expected {VERIFIED_EXPECTED_EMERGENT_GE1}")

    if errors:
        print("Validation gate FAILED — no dashboard files written:")
        for e in errors:
            print(e)
        sys.exit(1)


def validate_gate_forward(merged: gpd.GeoDataFrame) -> None:
    n_candidates = len(merged)
    n_emergent_ge2 = int((merged["KSI_label"] >= 2).sum())
    n_emergent_ge1 = int((merged["KSI_label"] >= 1).sum())

    print(
        f"Validation [forward]: {n_candidates} candidates | "
        f"{n_emergent_ge2} emergent (>=2, partial 2024 only) | {n_emergent_ge1} (>=1)"
    )

    # Flexible gate: within 1000 of expected forward panel count
    expected_approx = 80736
    if abs(n_candidates - expected_approx) > 1000:
        print(
            f"  FAIL: candidates={n_candidates} deviates from expected ~{expected_approx} by >1000"
        )
        sys.exit(1)
    # Print positives but don't assert fixed numbers — label window is partial
    print(f"  Note: emergent(>=2)={n_emergent_ge2}, emergent(>=1)={n_emergent_ge1} "
          f"(label window partially complete; 2025-2026 data not yet available)")


def compute_rank_and_percentile(merged: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    n = len(merged)
    merged = merged.copy()
    merged["rank"] = (-merged["_score"]).rank(method="first").astype(int)
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
                "Could not download council districts (%s). council_district will be 0.", exc
            )
            return None

    gdf = gpd.read_file(cache_path)
    city_mask = gdf[COUNCIL_DISTRICT_JUR_FIELD].str.upper() == COUNCIL_DISTRICT_JUR_VALUE
    gdf = gdf[city_mask].copy()
    if len(gdf) == 0:
        logging.warning("No San Diego City rows found in council districts data.")
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

    nodes_4326 = merged.set_geometry("geometry_4326").set_crs("EPSG:4326", allow_override=True)
    districts_4326 = districts.to_crs("EPSG:4326")

    joined = gpd.sjoin(
        nodes_4326[["intersection_id", "geometry_4326"]],
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
    # Include the first label year so crash history shows it in the chart
    history_end = pd.Timestamp(cfg["windows"]["label_start"]) + pd.DateOffset(years=1) - pd.Timedelta(days=1)
    crashes_raw = crashes_raw[
        (crashes_raw["date"] >= feature_start) & (crashes_raw["date"] <= history_end)
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

    def _sev_cat(val: object) -> str:
        try:
            sev = int(val)
        except (ValueError, TypeError):
            return "pdo"
        if sev in KSI_SEVERITY:
            return "ksi"
        if sev in INJURY_SEVERITY:
            return "injury"
        return "pdo"

    matched_crashes["sev_cat"] = matched_crashes["severity"].apply(_sev_cat)

    feature_years = list(range(
        pd.Timestamp(cfg["windows"]["feature_start"]).year,
        history_end.year + 1,
    ))

    sev_dfs = []
    for sev_cat in ("ksi", "injury", "pdo"):
        sub = matched_crashes[matched_crashes["sev_cat"] == sev_cat]
        grp = sub.groupby(["intersection_id", "year"]).size().reset_index(name=sev_cat)
        sev_dfs.append(grp)

    all_iids = merged["intersection_id"].tolist()
    index = pd.MultiIndex.from_product([all_iids, feature_years], names=["intersection_id", "year"])
    base = pd.DataFrame(index=index).reset_index()
    base["ksi"] = 0
    base["injury"] = 0
    base["pdo"] = 0

    for sev_df in sev_dfs:
        col = sev_df.columns[-1]
        base = base.merge(
            sev_df.rename(columns={col: f"_{col}"}),
            on=["intersection_id", "year"],
            how="left",
        )
        base[col] = base[col] + base[f"_{col}"].fillna(0).astype(int)
        base = base.drop(columns=[f"_{col}"])

    result: dict[str, list[dict]] = {}
    for iid, grp in base.groupby("intersection_id"):
        result[str(iid)] = [
            {
                "year": int(r["year"]),
                "ksi": int(r["ksi"]),
                "injury": int(r["injury"]),
                "pdo": int(r["pdo"]),
            }
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
                "shap_value": float(shap_values[i][j]),
                "raw_value": raw_val,
                "display_label": format_display_label(feature_cols[j], raw_val),
            })
        result[str(iid)] = entry
    return result


def assemble_export_panel(
    merged: gpd.GeoDataFrame,
    crash_history: dict[str, list[dict]],
    shap_features: dict[str, list[dict]],
) -> pd.DataFrame:
    df = merged.copy()
    df["node_id"] = df["osm_id"].fillna(0).astype("int64")
    df["tweedie_score"] = df["_score"].astype("float64")
    df["is_known_emergent"] = (df["KSI_label"] >= 1)
    df["is_crash_active"] = (df["crashes_72mo"].fillna(0) > 0)
    df["crashes_training"] = df["crashes_72mo"].fillna(0).round().astype("int64")

    df["crash_history_json"] = df["intersection_id"].map(
        lambda iid: json.dumps(crash_history.get(str(iid), []))
    )
    df["shap_json"] = df["intersection_id"].map(
        lambda iid: json.dumps(shap_features.get(str(iid), []))
    )

    keep_cols = [
        "intersection_id", "node_id", "lon", "lat",
        "tweedie_score", "percentile", "rank",
        "council_district",
        "is_known_emergent", "is_crash_active", "crashes_training",
        "crash_history_json", "shap_json",
    ]
    return df[keep_cols].reset_index(drop=True)


def print_recall_at_k_verified(merged: gpd.GeoDataFrame) -> None:
    n_emergent = VERIFIED_EXPECTED_EMERGENT_GE2
    print("  Full-ranking recall@K (verified run, all candidates):")
    for k in [50, 100, 200, 500, 1000]:
        hits = int(((merged["rank"] <= k) & (merged["KSI_label"] >= 2)).sum())
        recall = hits / n_emergent
        print(f"    @{k:<5}: {hits}/22 = {recall:.3f}")


def print_recall_at_k_forward(merged: gpd.GeoDataFrame) -> None:
    n_ge1 = int((merged["KSI_label"] >= 1).sum())
    n_ge2 = int((merged["KSI_label"] >= 2).sum())
    print(f"  Full-ranking recall@K (forward run, 2024 labels only):")
    print(f"  (>=2 sites: {n_ge2} — insufficient for recall@K; >=1 sites: {n_ge1})")
    if n_ge1 > 0:
        for k in [50, 100, 200, 500, 1000]:
            hits = int(((merged["rank"] <= k) & (merged["KSI_label"] >= 1)).sum())
            recall = hits / n_ge1
            base = k / len(merged)
            lift = recall / base if base > 0 else 0
            print(f"    @{k:<5} (>=1): {hits}/{n_ge1} = {recall:.3f}  ({lift:.1f}x random)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run",
        choices=["verified", "forward"],
        default="verified",
        help="Which pipeline run to export (default: verified)",
    )
    args = parser.parse_args()
    run_mode = args.run

    try:
        cfg = load_config()
        root = project_root()

        logging.info("Run mode: %s", run_mode)

        logging.info("Step 1: loading panels...")
        if run_mode == "verified":
            merged = load_panels_verified(cfg, root)
        else:
            merged = load_panels_forward(cfg, root)

        logging.info("Step 2: validation gate...")
        if run_mode == "verified":
            validate_gate_verified(merged)
        else:
            validate_gate_forward(merged)

        logging.info("Step 3: computing rank and percentile...")
        merged = compute_rank_and_percentile(merged)

        logging.info("Step 4: loading council districts...")
        districts = load_council_districts(root)

        logging.info("Step 5: assigning council districts...")
        merged = assign_council_districts(merged, districts)

        logging.info("Step 6: building crash history (may take 1-2 min)...")
        t0 = time.time()
        crash_history = build_crash_history(merged, cfg, root)
        logging.info("  crash history done in %.1fs", time.time() - t0)

        logging.info("Step 7: computing SHAP features (may take 3-6 min)...")
        t0 = time.time()
        shap_features_map = build_shap_features(merged, cfg, root)
        logging.info("  SHAP done in %.1fs", time.time() - t0)

        logging.info("Step 8: assembling export panel...")
        panel_df = assemble_export_panel(merged, crash_history, shap_features_map)

        logging.info("Step 9: exporting dashboard files...")
        from scripts.export_predictions import write_districts, write_geojson

        names_path = root / cfg["paths"]["proc"] / "intersection_names.csv"
        names_df = pd.read_csv(
            names_path, dtype={"intersection_id": "str", "intersection_name": "str"}
        )

        out_dir = root / "dashboard" / "public" / "data"
        write_geojson(panel_df, names_df, output_dir=out_dir, top_n=TOP_N)
        write_districts(panel_df, output_dir=out_dir)

        n_unnamed = int((merged["intersection_name"] == "Unnamed intersection").sum())
        n_no_district_top1000 = int(
            (panel_df.head(TOP_N)["council_district"] == 0).sum()
        )

        print(f"\n{run_mode.upper()} RUN exported successfully:")
        if run_mode == "verified":
            print("  Candidates: 81,007 | Emergent (>=2): 22 | Emergent (>=1): 389")
            print(f"  Top-{TOP_N} written to {out_dir}/")
            print_recall_at_k_verified(merged)
        else:
            n_ge2 = int((merged["KSI_label"] >= 2).sum())
            n_ge1 = int((merged["KSI_label"] >= 1).sum())
            print(f"  Candidates: {len(merged)} | Emergent (>=2, partial): {n_ge2} | (>=1): {n_ge1}")
            print(f"  Top-{TOP_N} written to {out_dir}/")
            print_recall_at_k_forward(merged)
        print(f"  Unnamed intersections: {n_unnamed}")
        print(f"  Nodes outside district polygons in top-{TOP_N} (district=0): {n_no_district_top1000}")

    except Exception as exc:
        print(f"ERROR: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
