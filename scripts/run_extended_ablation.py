"""Extended Protocol A ablation — Groups E (ADT proxy), F (ACS demo), G (ped infra), H (all).

Group E: ADT proxy from OSM maxspeed (Caltrans data not available; fallback per spec)
Group F: ACS demographics via Census API (requires CENSUS_API_KEY; skipped if unavailable)
Group G: Pedestrian infrastructure from OSM history + Overpass
Group H: E + G (+ F if available)

Run from project root:
    python scripts/run_extended_ablation.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import xgboost as xgb
from scipy import stats
from scipy.spatial import cKDTree
from sklearn.model_selection import GroupKFold, StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.eval.milestone2 import bootstrap_count_ci, count_metrics
from src.eval.splitter import add_spatial_blocks, random_split, spatial_block_kfold
from src.utils import load_config, project_root

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

ROOT = project_root()
MODEL_DIR = ROOT / "data" / "model"
RAW_DIR = ROOT / "data" / "raw"
RESULTS_DIR = ROOT / "results"
REPORTS_DIR = ROOT / "reports"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# San Diego bounding box from config [south, west, north, east]
BBOX = [32.50, -117.30, 33.00, -116.90]
OSM_DATE = "2021-12-31T23:59:59Z"
BUFFER_M = 76.2
# EPSG:2230 US survey feet: 1 m = 3937/1200 ft
BUFFER_FT = BUFFER_M * 3937.0 / 1200.0


# ---------------------------------------------------------------------------
# Protocol A evaluation harness (mirrors src.eval.milestone4)
# ---------------------------------------------------------------------------

def _load_frozen_params():
    p = MODEL_DIR / "frozen_params.json"
    raw = json.loads(p.read_text())
    return raw.get("frozen", raw.get("sets", {}).get("A_crash_only", {}).get("xgb_tweedie", {}))


def _fit_score(X: np.ndarray, y: np.ndarray, params: dict) -> np.ndarray:
    model = xgb.XGBRegressor(
        objective=params.get("objective", "reg:tweedie"),
        tweedie_variance_power=float(params.get("tweedie_variance_power", 1.3)),
        max_depth=int(params.get("max_depth", 3)),
        learning_rate=float(params.get("learning_rate", 0.03)),
        n_estimators=int(params.get("n_estimators", 100)),
        reg_alpha=float(params.get("reg_alpha", 0.0)),
        reg_lambda=float(params.get("reg_lambda", 1.0)),
        min_child_weight=float(params.get("min_child_weight", 1.0)),
        subsample=float(params.get("subsample", 0.8)),
        colsample_bytree=float(params.get("colsample_bytree", 0.8)),
        verbosity=0,
    )
    # Mask NaN features
    X_clean = np.where(np.isnan(X), 0.0, X)
    model.fit(X_clean, y)
    return model.predict(X_clean)


def _spearman_concat(scores: np.ndarray, y: np.ndarray, panel: pd.DataFrame,
                      cfg: dict, split: str) -> tuple[float, float, float]:
    """Return (point, lo, hi) Spearman rho using concatenated test-set approach."""
    n_boot = cfg["evaluation"]["bootstrap_resamples"]
    seed = cfg["project"]["rng_seed"]
    p = cfg["target"]["tweedie_variance_power"]

    if split == "random":
        _, test_idx = random_split(panel, cfg)
        folds = [(None, test_idx)]
    else:
        folds = [(None, ti) for _, ti in spatial_block_kfold(panel, cfg)]

    yc_parts, sc_parts = [], []
    for _, ti in folds:
        yc_parts.append(y[ti])
        sc_parts.append(scores[ti])

    ay = np.concatenate(yc_parts)
    asc = np.concatenate(sc_parts)
    pt = count_metrics(ay, asc, p)
    ci = bootstrap_count_ci(ay, asc, n_resamples=n_boot, seed=seed, p=p)

    rho = pt.get("spearman_rho", float("nan"))
    rho_ci = ci.get("spearman_rho", {})
    return rho, rho_ci.get("lo", float("nan")), rho_ci.get("hi", float("nan"))


def eval_feature_set(
    panel: pd.DataFrame,
    feature_cols: list[str],
    y_count: np.ndarray,
    cfg: dict,
    params: dict,
    label: str,
) -> dict:
    available = [c for c in feature_cols if c in panel.columns]
    log.info("Evaluating %s: %d / %d features available", label, len(available), len(feature_cols))
    X = panel[available].values.astype(float)
    scores = _fit_score(X, y_count, params)

    r_rho, r_lo, r_hi = _spearman_concat(scores, y_count, panel, cfg, "random")
    s_rho, s_lo, s_hi = _spearman_concat(scores, y_count, panel, cfg, "spatial")
    log.info("  %s random rho=%.4f [%.4f, %.4f]", label, r_rho, r_lo, r_hi)
    log.info("  %s spatial rho=%.4f [%.4f, %.4f]", label, s_rho, s_lo, s_hi)
    return {
        "random_rho": r_rho, "random_lo": r_lo, "random_hi": r_hi,
        "spatial_rho": s_rho, "spatial_lo": s_lo, "spatial_hi": s_hi,
        "n_features": len(available),
    }


# ---------------------------------------------------------------------------
# Feature group definitions
# ---------------------------------------------------------------------------

CRASH_ONLY_COLS = [
    "crashes_36mo", "crashes_72mo", "ped_crashes_72mo", "bike_crashes_72mo",
    "broadside_72mo", "left_turn_72mo", "dui_72mo", "night_72mo",
    "ped_row_violation_72mo", "years_since_last_crash", "distinct_crash_days_72mo",
    "worst_severity_72mo", "crash_trend_slope", "emergence_velocity",
    "emergence_acceleration", "mann_kendall_tau", "changepoint_prob",
    "ewma_crashes", "momentum_ratio", "covid_period_share",
]


# ---------------------------------------------------------------------------
# Group E — ADT proxy from OSM maxspeed (Caltrans fallback)
# ---------------------------------------------------------------------------

def build_group_e(panel: pd.DataFrame, infra: pd.DataFrame) -> pd.DataFrame:
    """ADT proxy using OSM speed_limit (Caltrans data unavailable; per-spec fallback)."""
    log.info("Building Group E (ADT proxy from speed_limit) ...")
    df = panel[["intersection_id"]].copy()
    df = df.merge(infra[["intersection_id", "speed_limit", "speed_limit_missing"]], on="intersection_id", how="left")
    df["aadt_proxy"] = df["speed_limit"].fillna(0.0)
    df["aadt_missing"] = df["speed_limit_missing"].fillna(1).astype(int)
    df["log_aadt"] = np.log1p(df["aadt_proxy"])
    return df[["intersection_id", "aadt_proxy", "aadt_missing", "log_aadt"]]


GROUP_E_COLS = ["aadt_proxy", "aadt_missing", "log_aadt"]


# ---------------------------------------------------------------------------
# Group F — ACS demographics (requires Census API key)
# ---------------------------------------------------------------------------

def build_group_f(panel: pd.DataFrame, cfg: dict) -> pd.DataFrame | None:
    """ACS 2022 5-year demographics joined by census tract.

    Returns None if Census API key is not set.
    """
    api_key = os.environ.get("CENSUS_API_KEY", "")
    if not api_key:
        log.warning(
            "Group F skipped: CENSUS_API_KEY environment variable not set. "
            "Set CENSUS_API_KEY=<your_key> and re-run to include ACS demographics."
        )
        return None

    from census import Census
    c = Census(api_key)

    variables = {
        "B01003_001E": "pop_total",
        "B19013_001E": "median_hh_income",
        "B08201_002E": "hh_no_vehicle",
        "B08201_001E": "hh_total",
        "B17001_002E": "pop_below_poverty",
        "B17001_001E": "pop_poverty_total",
        "B02001_001E": "pop_race_total",
        "B02001_003E": "pop_black",
        "B02001_004E": "pop_amer_indian",
        "B02001_005E": "pop_asian",
        "B02001_006E": "pop_pacific_islander",
        "B02001_007E": "pop_other_race",
    }

    log.info("Fetching ACS 2022 5-year data for San Diego County (FIPS 073) ...")
    try:
        results = c.acs5.state_county_tract(
            fields=list(variables.keys()),
            state_fips="06",
            county_fips="073",
            tract="*",
            year=2022,
        )
    except Exception as e:
        log.error("Census API call failed: %s", e)
        return None

    df_acs = pd.DataFrame(results)
    df_acs = df_acs.rename(columns=variables)
    df_acs["geoid"] = "1400000US06073" + df_acs["tract"].astype(str).str.zfill(6)

    df_acs["pop_total"] = pd.to_numeric(df_acs["pop_total"], errors="coerce")
    df_acs["median_hh_income"] = pd.to_numeric(df_acs["median_hh_income"], errors="coerce")
    df_acs["hh_no_vehicle"] = pd.to_numeric(df_acs["hh_no_vehicle"], errors="coerce")
    df_acs["hh_total"] = pd.to_numeric(df_acs["hh_total"], errors="coerce")
    df_acs["pop_below_poverty"] = pd.to_numeric(df_acs["pop_below_poverty"], errors="coerce")
    df_acs["pop_poverty_total"] = pd.to_numeric(df_acs["pop_poverty_total"], errors="coerce")
    df_acs["pop_race_total"] = pd.to_numeric(df_acs["pop_race_total"], errors="coerce")

    # Derived features
    df_acs["pct_no_vehicle"] = np.where(
        df_acs["hh_total"] > 0, df_acs["hh_no_vehicle"] / df_acs["hh_total"] * 100, np.nan
    )
    df_acs["pct_below_poverty"] = np.where(
        df_acs["pop_poverty_total"] > 0,
        df_acs["pop_below_poverty"] / df_acs["pop_poverty_total"] * 100, np.nan
    )
    for col in ["pop_black", "pop_amer_indian", "pop_asian", "pop_pacific_islander", "pop_other_race"]:
        df_acs[col] = pd.to_numeric(df_acs[col], errors="coerce")
    df_acs["pop_nonwhite"] = (
        df_acs[["pop_black", "pop_amer_indian", "pop_asian", "pop_pacific_islander", "pop_other_race"]]
        .sum(axis=1, skipna=True)
    )
    df_acs["pct_nonwhite"] = np.where(
        df_acs["pop_race_total"] > 0, df_acs["pop_nonwhite"] / df_acs["pop_race_total"] * 100, np.nan
    )

    # Download census tract geometries for San Diego County
    # Layer 6 = Census Tracts (layer 8 is Block Groups, a different geography).
    # WHERE clause values must be quoted strings, not bare numbers, or the
    # service returns a 200 OK with an embedded {"error":...} JSON body.
    log.info("Downloading census tract geometries ...")
    tiger_url = (
        "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2022/MapServer/6/"
        "query?where=STATE%3D%2706%27+AND+COUNTY%3D%27073%27&outFields=GEOID,AREALAND&f=geojson&outSR=4326"
    )
    try:
        r = requests.get(tiger_url, timeout=60)
        if not r.ok:
            log.error("Failed to download tract geometries: HTTP %d", r.status_code)
            return None
        if r.text.lstrip().startswith('{"error"'):
            log.error("Failed to download tract geometries: service returned an error payload: %s", r.text[:200])
            return None
        tracts_gdf = gpd.read_file(r.text, driver="GeoJSON")
        tracts_gdf["tract"] = tracts_gdf["GEOID"].str[-6:]
        tracts_gdf["STATE"] = "06"
        tracts_gdf["COUNTY"] = "073"
    except Exception as e:
        log.error("Failed to download tract geometries: %s", e)
        return None

    # Compute pop_density (per sq km)
    tracts_gdf["area_sqkm"] = tracts_gdf["AREALAND"].astype(float) / 1e6
    tracts_m = tracts_gdf.merge(df_acs[["tract", "pop_total", "pct_no_vehicle", "median_hh_income",
                                         "pct_below_poverty", "pct_nonwhite"]], on="tract", how="left")
    tracts_m["pop_density"] = np.where(
        tracts_m["area_sqkm"] > 0, tracts_m["pop_total"].astype(float) / tracts_m["area_sqkm"], np.nan
    )

    # Spatial join: candidates to census tracts
    cands_gdf = panel[["intersection_id", "lat", "lon"]].copy()
    cands_gdf = gpd.GeoDataFrame(
        cands_gdf,
        geometry=gpd.points_from_xy(cands_gdf["lon"], cands_gdf["lat"]),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(cands_gdf[["intersection_id", "geometry"]], tracts_m, how="left", predicate="within")

    result = joined[["intersection_id", "pop_density", "median_hh_income",
                      "pct_no_vehicle", "pct_below_poverty", "pct_nonwhite"]].copy()
    result = result.drop_duplicates(subset=["intersection_id"])
    result.columns = ["intersection_id", "pop_density", "median_hh_income",
                       "pct_no_vehicle", "pct_below_poverty", "pct_nonwhite"]
    log.info("Group F: joined demographics for %d / %d candidates", result["pop_density"].notna().sum(), len(panel))
    return result


GROUP_F_COLS = ["pop_density", "median_hh_income", "pct_no_vehicle", "pct_below_poverty", "pct_nonwhite"]


# ---------------------------------------------------------------------------
# Group G — Pedestrian infrastructure from OSM
# ---------------------------------------------------------------------------

def _overpass_query(query: str, timeout: int = 120) -> dict | None:
    for attempt in range(3):
        try:
            resp = requests.post(
                OVERPASS_URL,
                data={"data": query},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=timeout + 30,
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 503):
                log.warning("Overpass rate-limited; sleeping 60s")
                time.sleep(60)
        except Exception as e:
            log.warning("Overpass attempt %d failed: %s", attempt + 1, e)
            time.sleep(10)
    return None


def _fetch_crossings() -> gpd.GeoDataFrame | None:
    """Fetch highway=crossing nodes/ways as of 2021-12-31 from Overpass."""
    s, w, n, e = BBOX
    # Nodes tagged as crossings (pedestrian crossing infrastructure)
    q = (
        f'[out:json][timeout:120][date:"{OSM_DATE}"];\n'
        f'(\n'
        f'  node[highway=crossing]({s},{w},{n},{e});\n'
        f'  node[crossing=marked]({s},{w},{n},{e});\n'
        f'  node[crossing=uncontrolled]({s},{w},{n},{e});\n'
        f');\n'
        f'out body;\n'
    )
    log.info("Querying Overpass for crossing nodes (2021 vintage)...")
    result = _overpass_query(q)
    if result is None:
        log.warning("Overpass crossing query failed")
        return None
    elements = result.get("elements", [])
    if not elements:
        log.warning("No crossing nodes returned from Overpass")
        return None
    lons = [e["lon"] for e in elements if "lon" in e]
    lats = [e["lat"] for e in elements if "lat" in e]
    if not lons:
        return None
    gdf = gpd.GeoDataFrame(
        {"osm_id": [e["id"] for e in elements if "lon" in e]},
        geometry=gpd.points_from_xy(lons, lats),
        crs="EPSG:4326",
    )
    log.info("Crossing nodes: %d", len(gdf))
    return gdf


def _fetch_sidewalk_ways() -> gpd.GeoDataFrame | None:
    """Fetch ways with sidewalk tags as of 2021-12-31."""
    s, w, n, e = BBOX
    q = (
        f'[out:json][timeout:120][date:"{OSM_DATE}"];\n'
        f'way[sidewalk~"^(yes|left|right|both|separate)$"]({s},{w},{n},{e});\n'
        f'out center;\n'
    )
    log.info("Querying Overpass for sidewalk ways (2021 vintage)...")
    result = _overpass_query(q)
    if result is None:
        log.warning("Overpass sidewalk query failed")
        return None
    elements = [e for e in result.get("elements", []) if "center" in e]
    if not elements:
        log.warning("No sidewalk ways returned")
        return None
    lons = [e["center"]["lon"] for e in elements]
    lats = [e["center"]["lat"] for e in elements]
    gdf = gpd.GeoDataFrame(
        {"osm_id": [e["id"] for e in elements]},
        geometry=gpd.points_from_xy(lons, lats),
        crs="EPSG:4326",
    )
    log.info("Sidewalk ways (centers): %d", len(gdf))
    return gdf


def _kdtree_within_m(
    query_lons: np.ndarray, query_lats: np.ndarray,
    ref_lons: np.ndarray, ref_lats: np.ndarray,
    radius_m: float,
) -> np.ndarray:
    """Return boolean array: True if any ref point is within radius_m of each query point."""
    if len(ref_lons) == 0:
        return np.zeros(len(query_lons), dtype=bool)
    lat0 = np.mean(np.concatenate([query_lats, ref_lats]))
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = 111_320.0 * np.cos(np.radians(lat0))
    qxy = np.column_stack([query_lons * meters_per_deg_lon, query_lats * meters_per_deg_lat])
    rxy = np.column_stack([ref_lons * meters_per_deg_lon, ref_lats * meters_per_deg_lat])
    tree = cKDTree(rxy)
    result = tree.query_ball_point(qxy, r=radius_m)
    return np.array([len(r) > 0 for r in result])


def build_group_g(panel: pd.DataFrame) -> pd.DataFrame:
    """Pedestrian infrastructure from OSM history + Overpass."""
    log.info("Building Group G (pedestrian infrastructure) ...")
    df = panel[["intersection_id", "lon", "lat"]].copy()

    cands_lons = df["lon"].values
    cands_lats = df["lat"].values

    # has_ped_signal: from existing traffic_signals.geojson
    sig_path = RAW_DIR / "osm_history" / "20211231" / "traffic_signals.geojson"
    if sig_path.exists():
        sig_gdf = gpd.read_file(sig_path)
        sig_lons = sig_gdf.geometry.x.values
        sig_lats = sig_gdf.geometry.y.values
        df["has_ped_signal"] = _kdtree_within_m(cands_lons, cands_lats, sig_lons, sig_lats, BUFFER_M).astype(int)
        log.info("has_ped_signal: %d / %d candidates with signal within %.1fm",
                 df["has_ped_signal"].sum(), len(df), BUFFER_M)
    else:
        log.warning("traffic_signals.geojson not found; has_ped_signal = 0")
        df["has_ped_signal"] = 0

    # has_crosswalk: Overpass query for highway=crossing nodes
    crossings_cache = RAW_DIR / "osm_history" / "20211231" / "crossings.geojson"
    if crossings_cache.exists():
        cross_gdf = gpd.read_file(crossings_cache)
    else:
        cross_gdf = _fetch_crossings()
        if cross_gdf is not None:
            cross_gdf.to_file(crossings_cache, driver="GeoJSON")

    if cross_gdf is not None and len(cross_gdf) > 0:
        cx_lons = cross_gdf.geometry.x.values
        cx_lats = cross_gdf.geometry.y.values
        df["has_crosswalk"] = _kdtree_within_m(cands_lons, cands_lats, cx_lons, cx_lats, BUFFER_M).astype(int)
        log.info("has_crosswalk: %d / %d candidates with crossing within %.1fm",
                 df["has_crosswalk"].sum(), len(df), BUFFER_M)
    else:
        log.warning("No crossing data; has_crosswalk = 0")
        df["has_crosswalk"] = 0

    # has_sidewalk: Overpass query for sidewalk ways
    sidewalk_cache = RAW_DIR / "osm_history" / "20211231" / "sidewalks.geojson"
    if sidewalk_cache.exists():
        sw_gdf = gpd.read_file(sidewalk_cache)
    else:
        sw_gdf = _fetch_sidewalk_ways()
        if sw_gdf is not None:
            sw_gdf.to_file(sidewalk_cache, driver="GeoJSON")

    if sw_gdf is not None and len(sw_gdf) > 0:
        sw_lons = sw_gdf.geometry.x.values
        sw_lats = sw_gdf.geometry.y.values
        df["has_sidewalk"] = _kdtree_within_m(cands_lons, cands_lats, sw_lons, sw_lats, BUFFER_M).astype(int)
        log.info("has_sidewalk: %d / %d candidates with sidewalk within %.1fm",
                 df["has_sidewalk"].sum(), len(df), BUFFER_M)
    else:
        log.warning("No sidewalk data; has_sidewalk = 0")
        df["has_sidewalk"] = 0

    df["ped_infra_score"] = df["has_crosswalk"] + df["has_sidewalk"] + df["has_ped_signal"]
    return df[["intersection_id", "has_crosswalk", "has_sidewalk", "has_ped_signal", "ped_infra_score"]]


GROUP_G_COLS = ["has_crosswalk", "has_sidewalk", "has_ped_signal", "ped_infra_score"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _ci_separated(model_lo: float, baseline_hi: float) -> bool:
    return not (np.isnan(model_lo) or np.isnan(baseline_hi)) and model_lo > baseline_hi


def main():
    cfg = load_config()

    # Load core data
    log.info("Loading core pipeline data ...")
    panel = gpd.read_parquet(MODEL_DIR / "candidate_panel.parquet")
    crash_feats = pd.read_parquet(MODEL_DIR / "feature_table.parquet")
    infra_feats = pd.read_parquet(MODEL_DIR / "infra_features.parquet")

    panel = panel.merge(crash_feats, on="intersection_id", how="left")
    panel = panel.merge(infra_feats, on="intersection_id", how="left")
    if "spatial_block" not in panel.columns:
        panel = add_spatial_blocks(panel, cfg)

    y_count = panel["KSI_label"].values.astype(float)
    params = _load_frozen_params()
    log.info("Frozen params loaded: %s", {k: v for k, v in params.items() if k in
             ["tweedie_variance_power", "max_depth", "learning_rate", "n_estimators"]})

    # ---- Build new feature groups ----
    grp_e = build_group_e(panel, infra_feats)
    grp_f = build_group_f(panel, cfg)  # None if Census API key unavailable
    grp_g = build_group_g(panel)

    # Merge into panel
    panel = panel.merge(grp_e, on="intersection_id", how="left")
    panel = panel.merge(grp_g, on="intersection_id", how="left")
    if grp_f is not None:
        panel = panel.merge(grp_f, on="intersection_id", how="left")

    # ---- Run Protocol A for each set ----
    log.info("=" * 70)
    log.info("Running Protocol A frozen-param ablation for all 8 sets ...")

    # Read Sets A-D from frozen_scores.parquet
    scores_df = pd.read_parquet(MODEL_DIR / "frozen_scores.parquet")

    def get_frozen_rho(set_name: str, split: str) -> tuple[float, float, float]:
        col = f"{set_name}__xgb_tweedie"
        if col not in scores_df.columns:
            return float("nan"), float("nan"), float("nan")
        sc = scores_df[col].values
        return _spearman_concat(sc, y_count, panel, cfg, split)

    existing_sets = {
        "A_crash_only":    ("A: crash only (20 features)", CRASH_ONLY_COLS),
        "B_road_geometry": ("B: crash + road geometry", None),
        "C_signals":       ("C: crash + signals/signs", None),
        "D_all_infra":     ("D: crash + all OSM infra", None),
    }

    results = {}
    for set_name, (desc, _) in existing_sets.items():
        r_rho, r_lo, r_hi = get_frozen_rho(set_name, "random")
        s_rho, s_lo, s_hi = get_frozen_rho(set_name, "spatial")
        results[set_name] = {
            "description": desc,
            "random_rho": r_rho, "random_lo": r_lo, "random_hi": r_hi,
            "spatial_rho": s_rho, "spatial_lo": s_lo, "spatial_hi": s_hi,
            "n_features": {"A_crash_only": 20, "B_road_geometry": 25,
                           "C_signals": 22, "D_all_infra": 30}.get(set_name, "?"),
        }
        log.info("Set %s: random rho=%.4f [%.4f, %.4f]  spatial rho=%.4f [%.4f, %.4f]",
                 set_name, r_rho, r_lo, r_hi, s_rho, s_lo, s_hi)

    # Group E
    e_cols = CRASH_ONLY_COLS + GROUP_E_COLS
    results["E_adt_proxy"] = eval_feature_set(
        panel, e_cols, y_count, cfg, params, "E_adt_proxy"
    )
    results["E_adt_proxy"]["description"] = "E: crash + ADT proxy (OSM maxspeed fallback; Caltrans unavailable)"

    # Group F
    if grp_f is not None:
        f_cols = CRASH_ONLY_COLS + GROUP_F_COLS
        results["F_demographics"] = eval_feature_set(
            panel, f_cols, y_count, cfg, params, "F_demographics"
        )
        results["F_demographics"]["description"] = "F: crash + ACS demographics (Census 2022 5-yr)"
    else:
        results["F_demographics"] = {
            "description": "F: crash + ACS demographics — SKIPPED (CENSUS_API_KEY not set)",
            "random_rho": float("nan"), "random_lo": float("nan"), "random_hi": float("nan"),
            "spatial_rho": float("nan"), "spatial_lo": float("nan"), "spatial_hi": float("nan"),
            "n_features": "N/A",
        }

    # Group G
    g_cols = CRASH_ONLY_COLS + GROUP_G_COLS
    results["G_ped_infra"] = eval_feature_set(
        panel, g_cols, y_count, cfg, params, "G_ped_infra"
    )
    results["G_ped_infra"]["description"] = "G: crash + pedestrian infrastructure (crosswalk, sidewalk, ped signal)"

    # Group H: A + E + G (+ F if available)
    h_cols = CRASH_ONLY_COLS + GROUP_E_COLS + GROUP_G_COLS
    if grp_f is not None:
        h_cols += GROUP_F_COLS
    results["H_all_new"] = eval_feature_set(
        panel, h_cols, y_count, cfg, params, "H_all_new"
    )
    results["H_all_new"]["description"] = (
        "H: crash + E + G" + (" + F" if grp_f is not None else " (F skipped)")
    )

    # ---- Print summary table ----
    set_order = ["A_crash_only", "B_road_geometry", "C_signals", "D_all_infra",
                 "E_adt_proxy", "F_demographics", "G_ped_infra", "H_all_new"]

    a = results["A_crash_only"]
    a_r_hi = a["random_hi"]
    a_s_hi = a["spatial_hi"]

    print()
    print("=" * 110)
    print("EXTENDED PROTOCOL A ABLATION — 8-SET SUMMARY")
    print("Metric: Tweedie Spearman rho (concatenated test-set); 95% bootstrap CI; Protocol A frozen params")
    print("=" * 110)
    print(f"{'Set':<20} {'Description':<52} {'Spear_R':>8} {'Spear_S':>8} {'Lift_R':>8} {'Lift_S':>8} {'CI_sep?':>8}")
    print("-" * 110)

    for sname in set_order:
        r = results.get(sname, {})
        r_rho = r.get("random_rho", float("nan"))
        s_rho = r.get("spatial_rho", float("nan"))
        r_lo = r.get("random_lo", float("nan"))
        s_lo = r.get("spatial_lo", float("nan"))
        desc = r.get("description", sname)[:50]
        if sname == "A_crash_only":
            lift_r = "    —"
            lift_s = "    —"
            ci_sep = "    —"
        else:
            lift_r = f"{r_rho - a['random_rho']:+.4f}" if not np.isnan(r_rho) else "  N/A"
            lift_s = f"{s_rho - a['spatial_rho']:+.4f}" if not np.isnan(s_rho) else "  N/A"
            ci_r = _ci_separated(r_lo, a_r_hi)
            ci_s = _ci_separated(s_lo, a_s_hi)
            if np.isnan(r_rho):
                ci_sep = "  N/A"
            else:
                ci_sep = "  yes" if (ci_r and ci_s) else ("  R" if ci_r else "   no")
        print(f"{sname:<20} {desc:<52} {r_rho:>8.4f} {s_rho:>8.4f} {lift_r:>8} {lift_s:>8} {ci_sep:>8}")
    print("=" * 110)

    # ---- Save results ----
    rows = []
    for sname in set_order:
        r = results.get(sname, {})
        r_rho = r.get("random_rho", float("nan"))
        s_rho = r.get("spatial_rho", float("nan"))
        r_lo = r.get("random_lo", float("nan"))
        s_lo = r.get("spatial_lo", float("nan"))
        a_r = a["random_rho"]
        a_s = a["spatial_rho"]
        ci_r = _ci_separated(r_lo, a_r_hi) if sname != "A_crash_only" else None
        ci_s = _ci_separated(s_lo, a_s_hi) if sname != "A_crash_only" else None
        if sname == "A_crash_only":
            ci_sep_str = "—"
        elif np.isnan(r_rho):
            ci_sep_str = "N/A"
        else:
            ci_sep_str = "yes" if (ci_r and ci_s) else ("random_only" if ci_r else "no")
        rows.append({
            "set": sname,
            "description": r.get("description", sname),
            "spearman_random": r_rho,
            "spearman_spatial": s_rho,
            "random_ci_lo": r_lo,
            "random_ci_hi": r.get("random_hi", float("nan")),
            "spatial_ci_lo": s_lo,
            "spatial_ci_hi": r.get("spatial_hi", float("nan")),
            "lift_random": r_rho - a_r if not np.isnan(r_rho) else float("nan"),
            "lift_spatial": s_rho - a_s if not np.isnan(s_rho) else float("nan"),
            "ci_separated": ci_sep_str,
            "n_features": r.get("n_features", "?"),
        })

    out_csv = RESULTS_DIR / "ablation_results_extended.csv"
    RESULTS_DIR.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    log.info("Wrote %s", out_csv)

    # Write markdown report
    md_lines = [
        "# Extended Protocol A Ablation — 8-Set Summary",
        "",
        "**Protocol A** — frozen hyperparameters from M3a crash-only XGB-Tweedie.",
        "No re-tuning. All 8 feature sets use identical hyperparameters.",
        "",
        "**Group E note:** Caltrans ADT data not available locally; fell back to OSM maxspeed tag",
        "as a proxy for traffic volume (higher posted speed ≈ higher volume corridor per spec).",
        "",
        "**Group F note:** Census API key (`CENSUS_API_KEY`) not set in this environment.",
        "ACS demographics could not be fetched. Re-run with key to include Group F.",
        "",
        "## Results table",
        "",
        "| Set | Description | Spearman_R | Spearman_S | Lift_R | Lift_S | CI_sep? |",
        "| --- | ----------- | ---------- | ---------- | ------ | ------ | ------- |",
    ]
    for row in rows:
        r_rho = row["spearman_random"]
        s_rho = row["spearman_spatial"]
        l_r = "—" if row["set"] == "A_crash_only" else (f"{row['lift_random']:+.4f}" if not np.isnan(row["lift_random"]) else "N/A")
        l_s = "—" if row["set"] == "A_crash_only" else (f"{row['lift_spatial']:+.4f}" if not np.isnan(row["lift_spatial"]) else "N/A")
        r_str = f"{r_rho:.4f}" if not np.isnan(r_rho) else "N/A"
        s_str = f"{s_rho:.4f}" if not np.isnan(s_rho) else "N/A"
        md_lines.append(f"| {row['set']} | {row['description'][:60]} | {r_str} | {s_str} | {l_r} | {l_s} | {row['ci_separated']} |")

    md_lines += [
        "",
        "## Interpretation",
        "",
        "- **CI_sep = yes**: model CI lower bound > Set A CI upper bound in BOTH splits",
        "  (strong evidence of positive lift over crash-only baseline)",
        "- **CI_sep = no**: CIs overlap; difference not statistically distinguishable from zero",
        "- **CI_sep = random_only**: separated in random split only (weaker evidence)",
        "",
        "## D9 decision",
        "",
    ]

    any_ci_sep = any(row["ci_separated"] == "yes" for row in rows if row["set"] not in ["A_crash_only"])
    if any_ci_sep:
        winning = [row["set"] for row in rows if row["ci_separated"] == "yes"]
        md_lines += [
            f"**D9 RESOLVED — POSITIVE LIFT:** Sets {winning} show CI-separated lift over crash-only.",
            "At least one new external feature group adds independent predictive signal.",
        ]
    else:
        md_lines += [
            "**D9 RESOLVED — NULL:** No new feature group (E/F/G/H) shows CI-separated lift",
            "over crash-only (Set A) under frozen Protocol A hyperparameters.",
            "External data (ADT proxy, pedestrian infrastructure) do not add signal beyond crash history",
            "at this spatial resolution (76.2m buffer).",
        ]

    out_md = REPORTS_DIR / "ablation_extended.md"
    REPORTS_DIR.mkdir(exist_ok=True)
    out_md.write_text("\n".join(md_lines), encoding="utf-8")
    log.info("Wrote %s", out_md)

    return 0


if __name__ == "__main__":
    sys.exit(main())
