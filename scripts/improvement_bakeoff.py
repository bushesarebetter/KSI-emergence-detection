"""Evaluate candidate model improvements under one shared, honest protocol.

Companion to docs/MODEL_IMPROVEMENTS.md. Every arm below is scored with genuine
out-of-fold predictions -- fit on k-1 folds, predict the held-out fold -- so no arm
is ever scored by a model that saw its label. Arms are then compared to BOTH the
current frozen model and the persistence baseline with a *paired* bootstrap, which
is the part the existing evaluation is missing.

Why paired: scripts/refit_verified_run_oof.py reports a CI per model by resampling
positive positions against one fixed ranking. Those CIs are wide (n=21) and they
overlap for everything, which makes every comparison look like a tie. The question
that actually matters is "does arm A beat arm B on the SAME resample", and the
difference has far less variance than either arm's level. That is what
`paired_bootstrap_delta` computes.

Repeated CV: each arm is refit over N_REPEATS different fold seeds. Single-split
CV at 21 positives is dominated by which fold the positives landed in; averaging
over seeds removes most of that and reports the seed-to-seed spread so you can see
how much of any apparent gain is noise.

Usage
-----
    python scripts/improvement_bakeoff.py                   # all available arms
    python scripts/improvement_bakeoff.py --arms current,corridor,ensemble
    python scripts/improvement_bakeoff.py --repeats 20 --threshold 1

Requires the verified-run panel that refit_verified_run_oof.py consumes:
    data/model/verified_run/candidate_panel.parquet
    data/model/verified_run/feature_table.parquet
    data/model/frozen_params.json
Those are produced by the pipeline in README.md -> "Reproducing the results".
If they are absent this script exits with instructions rather than inventing data.

Outputs
-------
    results/improvement_bakeoff.json   full per-arm metrics + paired deltas
    stdout                             ranked comparison table
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

# Heavier imports (xgboost, scipy, sklearn) and every `src.*` import are deferred
# into the functions that need them. The `src` package pulls in geopandas at import
# time, so importing it up here would make a fresh clone fail with an opaque
# ModuleNotFoundError instead of the actionable "you have no data yet" guard below.

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "data" / "model"
RESULTS_DIR = ROOT / "results"

# Set by --panel-dir. Defaults to the real verified-run output; point it at a
# synthetic panel (scripts/make_synthetic_panel.py) to exercise the harness
# without TIMS data.
VERIFIED_DIR = MODEL_DIR / "verified_run"
IS_SYNTHETIC = False


def set_panel_dir(rel: str) -> None:
    global VERIFIED_DIR, IS_SYNTHETIC
    VERIFIED_DIR = (ROOT / rel).resolve()
    IS_SYNTHETIC = (VERIFIED_DIR / "SYNTHETIC.json").exists()

N_FOLDS = 5
N_REPEATS = 10
KS = [100, 200, 500, 1000]
REPORT_K = 500
BOOTSTRAP_RESAMPLES = 2000
SEED = 42

# Features whose direction is known a priori. Used only by the `monotone` arm.
# +1 = score must be non-decreasing in this feature, -1 = non-increasing.
MONOTONE_PRIORS = {
    "crashes_36mo": 1,
    "crashes_72mo": 1,
    "ewma_crashes": 1,
    "distinct_crash_days_72mo": 1,
    "ped_crashes_72mo": 1,
    "bike_crashes_72mo": 1,
    "worst_severity_72mo": 1,
    "years_since_last_crash": -1,
}

# Corridor kernel: neighbour crash pressure decays with distance. 150 m is roughly
# one short city block -- far enough to capture the adjacent intersections on the
# same arterial, tight enough not to smear across a whole neighbourhood.
CORRIDOR_BANDWIDTH_M = 150.0
CORRIDOR_RADIUS_M = 500.0


# ────────────────────────────────────────────────────────────────────────────────
# Data loading
# ────────────────────────────────────────────────────────────────────────────────

def require_inputs() -> None:
    missing = [
        p for p in (
            VERIFIED_DIR / "candidate_panel.parquet",
            VERIFIED_DIR / "feature_table.parquet",
            frozen_params_path(),
        ) if not p.exists()
    ]
    if missing:
        print("Cannot run: required pipeline artefacts are missing.\n")
        for p in missing:
            print(f"  missing  {p.relative_to(ROOT)}")
        print(
            "\nSWITRS data cannot be redistributed, so a fresh clone has none of these.\n"
            "Download the TIMS export into data/raw/switrs/<YYYYMMDD>/ (see\n"
            "docs/DATA_SOURCES.md), then run the pipeline from README.md:\n\n"
            "  python -m src.ingest.run\n"
            "  python -m src.gis.build_spine\n"
            "  python -m src.labels.build_panel\n"
            "  python -m src.features.build_crash_emergence\n"
            "  python -m src.model.fit_frozen\n"
            "  python scripts/restrict_candidates_to_city_limits.py\n"
        )
        sys.exit(1)


def frozen_params_path() -> Path:
    """Prefer a frozen_params.json sitting beside the panel (synthetic runs carry
    their own), falling back to the canonical one under data/model/."""
    local = VERIFIED_DIR / "frozen_params.json"
    return local if local.exists() else MODEL_DIR / "frozen_params.json"


def load_frozen_params() -> tuple[dict, list[str]]:
    raw = json.loads(frozen_params_path().read_text())
    f = raw["frozen"]
    params = {
        "objective": f["objective"],
        "tweedie_variance_power": float(f["tweedie_variance_power"]),
        "max_depth": int(f["max_depth"]),
        "learning_rate": float(f["learning_rate"]),
        "n_estimators": int(f["n_estimators"]),
        "reg_alpha": float(f["reg_alpha"]),
        "reg_lambda": float(f["reg_lambda"]),
        "min_child_weight": int(f["min_child_weight"]),
        "subsample": float(f["subsample"]),
        "colsample_bytree": float(f["colsample_bytree"]),
        "random_state": int(f["random_state"]),
        "verbosity": 0,
    }
    return params, raw["sets"]["A_crash_only"]["feature_list"]


def load_panel() -> tuple[pd.DataFrame, list[str]]:
    import geopandas as gpd
    from src.eval.splitter import add_spatial_blocks
    from src.utils import load_config

    cfg = load_config()
    panel = gpd.read_parquet(VERIFIED_DIR / "candidate_panel.parquet")
    feat = pd.read_parquet(VERIFIED_DIR / "feature_table.parquet")
    panel = panel.merge(feat, on="intersection_id", how="left")
    panel = add_spatial_blocks(panel, cfg)
    _, feature_list = load_frozen_params()
    return panel, feature_list


# ────────────────────────────────────────────────────────────────────────────────
# Feature construction — improvement #5, corridor / neighbourhood
# ────────────────────────────────────────────────────────────────────────────────

def add_corridor_features(panel: pd.DataFrame, feature_list: list[str]) -> list[str]:
    """Distance-decayed crash pressure from NEIGHBOURING candidate nodes.

    Leakage note: this is built only from `crashes_72mo` and `ewma_crashes`, which
    are already feature-window-only quantities enforced by the crash wall. No label
    information from any neighbour enters here -- deliberately, since neighbour
    *labels* would leak across spatial CV folds.

    Adds three columns and returns the extended feature list:
      corridor_crash_pressure  Gaussian-decayed sum of neighbour crashes_72mo
      corridor_trend_pressure  same kernel applied to neighbour ewma_crashes
      corridor_n_neighbors     raw neighbour count inside the radius (density proxy)
    """
    from scipy.spatial import cKDTree
    from src.utils import load_config

    # Project to the analysis CRS so distances are in feet, then convert to metres.
    cfg = load_config()
    proj = panel.to_crs(cfg["crs"]["analysis"])
    xy = np.c_[proj.geometry.x.values, proj.geometry.y.values]
    # EPSG:2230 is in US SURVEY feet, not international feet. src/eval/splitter.py
    # uses the same 3937/1200 ratio; the two definitions differ by 2 ppm, which is
    # immaterial here but worth keeping consistent across the codebase.
    US_FT_PER_M = 3937.0 / 1200.0
    xy_m = xy / US_FT_PER_M

    tree = cKDTree(xy_m)
    pairs = tree.query_ball_point(xy_m, r=CORRIDOR_RADIUS_M)

    crashes = panel["crashes_72mo"].fillna(0.0).to_numpy(dtype=float)
    ewma = panel["ewma_crashes"].fillna(0.0).to_numpy(dtype=float)

    pressure = np.zeros(len(panel))
    trend = np.zeros(len(panel))
    counts = np.zeros(len(panel))

    for i, neigh in enumerate(pairs):
        neigh = [j for j in neigh if j != i]  # exclude self: own history is already a feature
        if not neigh:
            continue
        d = np.linalg.norm(xy_m[neigh] - xy_m[i], axis=1)
        w = np.exp(-0.5 * (d / CORRIDOR_BANDWIDTH_M) ** 2)
        pressure[i] = float(np.dot(w, crashes[neigh]))
        trend[i] = float(np.dot(w, ewma[neigh]))
        counts[i] = len(neigh)

    panel["corridor_crash_pressure"] = pressure
    panel["corridor_trend_pressure"] = trend
    panel["corridor_n_neighbors"] = counts

    return feature_list + [
        "corridor_crash_pressure",
        "corridor_trend_pressure",
        "corridor_n_neighbors",
    ]


# ────────────────────────────────────────────────────────────────────────────────
# OOF scoring — improvement #1, repeated CV
# ────────────────────────────────────────────────────────────────────────────────

def make_splits(y: np.ndarray, groups: np.ndarray, mode: str, seed: int):
    from sklearn.model_selection import (
        GroupKFold, StratifiedGroupKFold, StratifiedKFold,
    )

    """Fold generator.

    `groups` carries spatial blocks for the spatial mode. It ALSO guards the
    window-stacking arm (#3): when the panel contains the same intersection under
    several feature/label windows, groups must be intersection_id so that no
    intersection appears in both train and test. StratifiedGroupKFold keeps
    positives spread across folds while honouring that constraint.
    """
    y_strat = (y >= 2).astype(int)
    if mode == "random":
        if groups is None:
            return StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=seed).split(
                np.zeros(len(y)), y_strat
            )
        return StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=seed).split(
            np.zeros(len(y)), y_strat, groups=groups
        )
    if mode == "spatial":
        # GroupKFold is deterministic, so vary the fold assignment across repeats by
        # permuting the group labels -- otherwise every repeat is an identical fit.
        rng = np.random.RandomState(seed)
        uniq = np.unique(groups)
        remap = dict(zip(uniq, rng.permutation(len(uniq))))
        shuffled = np.array([remap[g] for g in groups])
        return GroupKFold(n_splits=N_FOLDS).split(np.zeros(len(y)), y, groups=shuffled)
    raise ValueError(mode)


def oof_predict(X, y, groups, params, mode, seed, sample_weight=None):
    import xgboost as xgb
    oof = np.full(len(y), np.nan)
    for train_idx, test_idx in make_splits(y, groups, mode, seed):
        model = xgb.XGBRegressor(**params)
        kw = {}
        if sample_weight is not None:
            kw["sample_weight"] = sample_weight[train_idx]
        model.fit(X[train_idx], y[train_idx], **kw)
        oof[test_idx] = model.predict(X[test_idx])
    if np.isnan(oof).any():
        # GroupKFold can leave rows unassigned when group counts are very uneven.
        oof[np.isnan(oof)] = np.nanmin(oof)
    return oof


def oof_rank_predict(X, y, groups, params, mode, seed):
    """XGBRanker variant for the rank-objective arm (#11).

    XGBRanker needs query groups; there is only one ranking here (all candidates
    compete against each other), so each fit gets a single group spanning the
    whole training fold.
    """
    import xgboost as xgb
    oof = np.full(len(y), np.nan)
    rank_params = {k: v for k, v in params.items()
                   if k not in ("objective", "tweedie_variance_power")}
    rank_params["objective"] = "rank:pairwise"
    for train_idx, test_idx in make_splits(y, groups, mode, seed):
        model = xgb.XGBRanker(**rank_params)
        model.fit(X[train_idx], y[train_idx], group=[len(train_idx)])
        oof[test_idx] = model.predict(X[test_idx])
    if np.isnan(oof).any():
        oof[np.isnan(oof)] = np.nanmin(oof)
    return oof


# ────────────────────────────────────────────────────────────────────────────────
# Metrics
# ────────────────────────────────────────────────────────────────────────────────

def recall_at_k(scores: np.ndarray, y: np.ndarray, k: int, threshold: int) -> float:
    n_pos = int((y >= threshold).sum())
    if n_pos == 0:
        return float("nan")
    top = np.argsort(-scores)[:k]
    return float((y[top] >= threshold).sum()) / n_pos


def paired_bootstrap_delta(
    scores_a: np.ndarray, scores_b: np.ndarray, y: np.ndarray,
    k: int, threshold: int, resamples: int = BOOTSTRAP_RESAMPLES, seed: int = SEED,
) -> dict:
    """Bootstrap the DIFFERENCE in recall@K between two rankings.

    Both arms are evaluated on the same resampled set of positives every draw, so
    the shared "which positives did we happen to sample" noise cancels. The result
    is a CI on the delta that is far tighter than the difference of two marginal
    CIs, and it answers the comparison question directly.
    """
    rng = np.random.RandomState(seed)
    pos = np.where(y >= threshold)[0]
    if len(pos) == 0:
        return {"delta": float("nan"), "ci95": [float("nan")] * 2, "p_better": float("nan")}

    rank_a = np.empty(len(y), dtype=int)
    rank_a[np.argsort(-scores_a)] = np.arange(len(y))
    rank_b = np.empty(len(y), dtype=int)
    rank_b[np.argsort(-scores_b)] = np.arange(len(y))

    deltas = np.empty(resamples)
    for i in range(resamples):
        draw = rng.choice(pos, size=len(pos), replace=True)
        deltas[i] = ((rank_a[draw] < k).mean() - (rank_b[draw] < k).mean())

    return {
        "delta": float(np.mean(deltas)),
        "ci95": [float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))],
        "p_better": float((deltas > 0).mean()),
    }


# ────────────────────────────────────────────────────────────────────────────────
# Arms
# ────────────────────────────────────────────────────────────────────────────────

def build_arms(panel, feature_list, params, args):
    """Each arm returns a callable (mode, seed) -> OOF score vector."""
    import xgboost as xgb
    from src.model.fit import persistence_baseline_scores

    y = panel["KSI_label"].to_numpy(dtype=float)
    blocks = panel["spatial_block"].to_numpy()

    # Window-stacked panels repeat intersections, so grouping must switch from
    # spatial block to intersection_id to keep OOF honest (see #3 in the doc).
    stacked = panel["intersection_id"].duplicated().any()
    if stacked:
        print("  ! panel contains repeated intersection_id -> grouping OOF folds by "
              "intersection to prevent cross-window leakage")
    random_groups = panel["intersection_id"].to_numpy() if stacked else None

    X_base = panel[feature_list].fillna(0.0).to_numpy(dtype=float)

    def groups_for(mode):
        return blocks if mode == "spatial" else random_groups

    arms = {}

    arms["baseline"] = lambda mode, seed: persistence_baseline_scores(panel)

    arms["current"] = lambda mode, seed: oof_predict(
        X_base, y, groups_for(mode), params, mode, seed
    )

    # #10 monotonic constraints
    mono = tuple(MONOTONE_PRIORS.get(f, 0) for f in feature_list)
    if any(mono):
        mono_params = {**params, "monotone_constraints": mono}
        arms["monotone"] = lambda mode, seed: oof_predict(
            X_base, y, groups_for(mode), mono_params, mode, seed
        )

    # #11 rank objective
    arms["rank_objective"] = lambda mode, seed: oof_rank_predict(
        X_base, y, groups_for(mode), params, mode, seed
    )

    # #5 corridor features
    if args.corridor:
        ext_list = add_corridor_features(panel, feature_list)
        X_corr = panel[ext_list].fillna(0.0).to_numpy(dtype=float)
        arms["corridor"] = lambda mode, seed: oof_predict(
            X_corr, y, groups_for(mode), params, mode, seed
        )

    # #7 harm-weighted target. Needs the fatal/severe split; KSI_label alone is a
    # count, and scaling a count by a constant cost does not change the ranking.
    if {"fatal_label", "severe_label"}.issubset(panel.columns):
        FATAL_COST, SEVERE_COST = 15_988_000.0, 1_705_100.0
        harm = (panel["fatal_label"].fillna(0).to_numpy() * FATAL_COST
                + panel["severe_label"].fillna(0).to_numpy() * SEVERE_COST) / SEVERE_COST

        def harm_arm(mode, seed, _h=harm):
            oof = np.full(len(y), np.nan)
            for tr, te in make_splits(y, groups_for(mode), mode, seed):
                m = xgb.XGBRegressor(**params)
                m.fit(X_base[tr], _h[tr])
                oof[te] = m.predict(X_base[te])
            if np.isnan(oof).any():
                oof[np.isnan(oof)] = np.nanmin(oof)
            return oof

        arms["harm_weighted"] = harm_arm
    else:
        print("  - skipping harm_weighted arm: panel has no fatal_label/severe_label "
              "columns (rebuild the label panel with the severity split to enable it)")

    # #6 two-stage frequency x conditional severity
    if "total_crashes_label" in panel.columns:
        total = panel["total_crashes_label"].fillna(0).to_numpy(dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            cond = np.where(total > 0, y / np.maximum(total, 1e-9), 0.0)

        def two_stage(mode, seed):
            freq = np.full(len(y), np.nan)
            sev = np.full(len(y), np.nan)
            for tr, te in make_splits(y, groups_for(mode), mode, seed):
                mf = xgb.XGBRegressor(**params)
                mf.fit(X_base[tr], total[tr])
                freq[te] = mf.predict(X_base[te])

                sev_params = {**params, "objective": "reg:logistic"}
                sev_params.pop("tweedie_variance_power", None)
                ms = xgb.XGBRegressor(**sev_params)
                ms.fit(X_base[tr], np.clip(cond[tr], 0, 1))
                sev[te] = ms.predict(X_base[te])
            out = freq * sev
            if np.isnan(out).any():
                out[np.isnan(out)] = np.nanmin(out)
            return out

        arms["two_stage"] = two_stage
    else:
        print("  - skipping two_stage arm: panel has no total_crashes_label column")

    return arms, y


def rank_average(*score_vectors):
    """#8 ensemble: average the normalised ranks, not the raw scores.

    Raw scores from a Tweedie model and a hand-built persistence score are on
    incomparable scales, so averaging them would silently let whichever has the
    larger variance dominate. Ranks put both on [0, 1].
    """
    n = len(score_vectors[0])
    acc = np.zeros(n)
    for s in score_vectors:
        r = np.empty(n)
        r[np.argsort(-s)] = np.arange(n)
        acc += r / n
    return -acc / len(score_vectors)


# ────────────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--panel-dir", default="data/model/verified_run",
                    help="directory holding candidate_panel.parquet + "
                         "feature_table.parquet (default: data/model/verified_run)")
    ap.add_argument("--arms", default="all", help="comma-separated arm names, or 'all'")
    ap.add_argument("--repeats", type=int, default=N_REPEATS,
                    help=f"CV seeds per arm (default {N_REPEATS})")
    ap.add_argument("--threshold", type=int, default=1, choices=[1, 2],
                    help="KSI count defining a positive (default 1: more positives, "
                         "measurable effects)")
    ap.add_argument("--no-corridor", dest="corridor", action="store_false",
                    help="skip the corridor-feature arm (it is the slow one)")
    ap.set_defaults(corridor=True)
    args = ap.parse_args()

    set_panel_dir(args.panel_dir)
    require_inputs()

    if IS_SYNTHETIC:
        banner = "!" * 76
        print(
            f"\n{banner}\n"
            f"SYNTHETIC PANEL ({args.panel_dir}). Every number below describes the\n"
            f"generator in scripts/make_synthetic_panel.py, NOT San Diego. Valid only\n"
            f"for checking that the harness runs and that CV does not leak.\n"
            f"{banner}\n"
        )

    from scipy import stats

    print("Loading verified-run panel...")
    panel, feature_list = load_panel()
    params, _ = load_frozen_params()

    n_pos = int((panel["KSI_label"] >= args.threshold).sum())
    print(f"  {len(panel):,} candidates | {n_pos} positives at >={args.threshold} KSI")
    print(f"  {len(feature_list)} base features | {args.repeats} CV seeds x {N_FOLDS} folds\n")

    arms, y = build_arms(panel, feature_list, params, args)
    if args.arms != "all":
        wanted = {a.strip() for a in args.arms.split(",")}
        unknown = wanted - set(arms)
        if unknown:
            print(f"Unknown arm(s): {sorted(unknown)}\nAvailable: {sorted(arms)}")
            sys.exit(1)
        arms = {k: v for k, v in arms.items() if k in wanted}

    results: dict = {
        "synthetic": IS_SYNTHETIC,
        "panel_dir": args.panel_dir,
        "config": {
            "n_candidates": len(panel),
            "n_positives": n_pos,
            "threshold": args.threshold,
            "n_folds": N_FOLDS,
            "n_repeats": args.repeats,
            "report_k": REPORT_K,
        },
        "note": (
            "Arms scored with genuine out-of-fold predictions, repeated over "
            f"{args.repeats} fold seeds. Deltas are PAIRED bootstraps of the recall@K "
            "difference on identical resamples, so they are much tighter than the "
            "difference of two marginal CIs. An arm is adopted only if its delta CI "
            "excludes zero on BOTH splits and it does not degrade the forward run."
        ),
        "arms": {},
    }

    # Collect one representative OOF vector per arm per mode (first seed) for the
    # paired comparisons, plus the across-seed spread for the level estimates.
    representative: dict = {}

    for mode in ("random", "spatial"):
        print(f"=== {mode.upper()} split ===")
        representative[mode] = {}
        for name, fn in arms.items():
            recalls, spearmans = [], []
            for rep in range(args.repeats):
                seed = SEED + rep
                s = fn(mode, seed)
                recalls.append(recall_at_k(s, y, REPORT_K, args.threshold))
                spearmans.append(stats.spearmanr(s, y).correlation)
                if rep == 0:
                    representative[mode][name] = s
                if name == "baseline":
                    break  # deterministic, no point repeating

            entry = results["arms"].setdefault(name, {})
            entry[mode] = {
                "recall_at_%d" % REPORT_K: round(float(np.mean(recalls)), 4),
                "recall_sd_across_seeds": round(float(np.std(recalls)), 4),
                "spearman": round(float(np.mean(spearmans)), 4),
            }
            print(f"  {name:16s} recall@{REPORT_K}={np.mean(recalls):.4f} "
                  f"(sd {np.std(recalls):.4f})  rho={np.mean(spearmans):.4f}")

        # #8 ensemble, built from the arms just scored
        if {"current", "baseline"} <= set(representative[mode]):
            ens = rank_average(representative[mode]["current"],
                               representative[mode]["baseline"])
            representative[mode]["ensemble"] = ens
            entry = results["arms"].setdefault("ensemble", {})
            entry[mode] = {
                "recall_at_%d" % REPORT_K: round(recall_at_k(ens, y, REPORT_K, args.threshold), 4),
                "recall_sd_across_seeds": None,
                "spearman": round(float(stats.spearmanr(ens, y).correlation), 4),
            }
            print(f"  {'ensemble':16s} recall@{REPORT_K}="
                  f"{recall_at_k(ens, y, REPORT_K, args.threshold):.4f}  (rank-average)")
        print()

    # Paired deltas against both reference arms.
    print("=== PAIRED deltas vs. reference arms (recall@%d, >=%d KSI) ===" % (REPORT_K, args.threshold))
    for ref in ("current", "baseline"):
        for mode in ("random", "spatial"):
            for name, s in representative[mode].items():
                if name == ref:
                    continue
                d = paired_bootstrap_delta(
                    s, representative[mode][ref], y, REPORT_K, args.threshold
                )
                results["arms"].setdefault(name, {}).setdefault("deltas", {}) \
                    .setdefault(f"vs_{ref}", {})[mode] = {
                        "delta": round(d["delta"], 4),
                        "ci95": [round(c, 4) for c in d["ci95"]],
                        "p_better": round(d["p_better"], 3),
                    }

    for name in sorted(results["arms"]):
        deltas = results["arms"][name].get("deltas", {})
        if not deltas:
            continue
        print(f"\n  {name}")
        for ref, per_mode in deltas.items():
            for mode, d in per_mode.items():
                excl = "*" if (d["ci95"][0] > 0 or d["ci95"][1] < 0) else " "
                print(f"    {ref:12s} {mode:8s} delta={d['delta']:+.4f} "
                      f"CI[{d['ci95'][0]:+.4f},{d['ci95'][1]:+.4f}] "
                      f"P(better)={d['p_better']:.2f} {excl}")

    print("\n  * = 95% paired CI excludes zero. Adopt only when BOTH splits are starred")
    print("    and the forward run does not degrade (see docs/MODEL_IMPROVEMENTS.md).")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / ("improvement_bakeoff_synthetic.json" if IS_SYNTHETIC
                         else "improvement_bakeoff.json")
    out.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
