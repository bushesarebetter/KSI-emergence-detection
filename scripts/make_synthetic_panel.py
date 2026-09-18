"""Generate a synthetic verified-run panel with the real one's schema and regime.

WHY THIS EXISTS
---------------
SWITRS cannot be redistributed, so a fresh clone has no data and none of the
modelling scripts can run at all. That makes it impossible to tell whether a change
to the pipeline is correct until you happen to be sitting at a machine with a TIMS
export on it -- which is a bad place to discover that your cross-validation leaks.

This script writes a panel with the exact schema `scripts/improvement_bakeoff.py`
and `scripts/refit_verified_run_oof.py` consume, populated by a generative process
chosen to reproduce the *statistical regime* that makes this problem hard:

  - ~26,000 candidates across a San Diego-shaped bounding box, in EPSG:2230
  - spatially autocorrelated exposure, so spatial-block CV is a real constraint
    and corridor features have genuine structure to find
  - all 20 crash-history features derived from ONE latent crash series, which is
    what makes them mutually redundant in the real data and why a two-term
    persistence baseline is so hard to beat
  - KSI labels calibrated to the real counts: ~378 positives at >=1, ~21 at >=2

WHAT IT IS NOT
--------------
**A synthetic panel cannot tell you whether a modelling idea works.** Any recall,
Spearman, or delta computed on this data is a property of the generator, not of San
Diego. Its only legitimate uses are:

  1. proving the harness runs end to end and the fold logic is honest
  2. catching leaks -- a change that scores implausibly well here is usually
     leaking, because the generator's true signal ceiling is known and modest
  3. letting someone without TIMS access develop against the pipeline

Every artefact it writes is stamped with `"synthetic": true` so that a synthetic
run can never be mistaken for a real one downstream.

Usage
-----
    python scripts/make_synthetic_panel.py
    python scripts/improvement_bakeoff.py --panel-dir data/model/synthetic_run
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

# Real panel dimensions, from README.md / reports/verified_canonical_numbers.json.
N_CANDIDATES = 26_423
TARGET_POS_GE1 = 378
TARGET_POS_GE2 = 21

# Feature window 2016-2021 -> label window 2022-2024, matching the verified run.
FEATURE_YEARS = list(range(2016, 2022))

# Signal strength. KSI risk is split between `exposure` (which the crash-history
# features can see) and `severity_prone` (which they cannot). That split sets how
# predictable the labels are, and it is calibrated against the one quantity we know
# for the real panel: the persistence baseline gets recall@500 = 16.1% at the >=1
# threshold. These weights reproduce that. Do not tune them to make a model look
# good -- the point of matching the real difficulty is that an arm scoring far
# above it is almost certainly leaking, which is what this panel exists to catch.
W_EXPOSURE = 1.00
W_SEVERITY = 0.33
SEVERITY_NOISE = 0.68
REAL_BASELINE_RECALL_500_GE1 = 0.161

# EPSG:2230 is NAD83 / California State Plane Zone VI in US survey feet. These are
# the approximate State Plane bounds of the City of San Diego; generating directly
# in the analysis CRS means add_spatial_blocks() works without a reprojection.
X_MIN, X_MAX = 6_240_000.0, 6_330_000.0
Y_MIN, Y_MAX = 1_820_000.0, 1_920_000.0

# The 20 crash-history features, in the order docs/FEATURE_CATALOG.md lists them.
GROUP1 = [
    "crashes_36mo", "crashes_72mo", "ped_crashes_72mo", "bike_crashes_72mo",
    "broadside_72mo", "left_turn_72mo", "dui_72mo", "night_72mo",
    "ped_row_violation_72mo", "years_since_last_crash",
    "distinct_crash_days_72mo", "worst_severity_72mo",
]
GROUP2 = [
    "crash_trend_slope", "emergence_velocity", "emergence_acceleration",
    "mann_kendall_tau", "changepoint_prob", "ewma_crashes", "momentum_ratio",
    "covid_period_share",
]
FEATURE_LIST = GROUP1 + GROUP2


def smooth_field(xy: np.ndarray, rng: np.random.Generator, n_centers: int, scale_ft: float) -> np.ndarray:
    """A spatially autocorrelated field built from random Gaussian bumps.

    Real exposure is not iid across intersections -- arterials run in corridors and
    busy areas cluster. Without that structure, spatial-block CV would be identical
    to random CV and the corridor features would be pure noise, so the synthetic
    panel would not exercise either.
    """
    centers = np.c_[
        rng.uniform(X_MIN, X_MAX, n_centers),
        rng.uniform(Y_MIN, Y_MAX, n_centers),
    ]
    weights = rng.gamma(2.0, 1.0, n_centers)
    field = np.zeros(len(xy))
    for c, w in zip(centers, weights):
        d2 = ((xy - c) ** 2).sum(axis=1)
        field += w * np.exp(-d2 / (2 * scale_ft ** 2))
    return field / (field.std() + 1e-9)


def build(n: int, seed: int) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(seed)

    # ── geometry ──────────────────────────────────────────────────────────────
    # Clustered rather than uniform: intersection density itself is higher
    # downtown, which matters because spatial blocks are equal-area, not
    # equal-count.
    n_clusters = 140
    cl_x = rng.uniform(X_MIN, X_MAX, n_clusters)
    cl_y = rng.uniform(Y_MIN, Y_MAX, n_clusters)
    pick = rng.integers(0, n_clusters, n)
    x = np.clip(cl_x[pick] + rng.normal(0, 9_000, n), X_MIN, X_MAX)
    y = np.clip(cl_y[pick] + rng.normal(0, 9_000, n), Y_MIN, Y_MAX)
    xy = np.c_[x, y]

    # ── latent exposure and risk ──────────────────────────────────────────────
    # `exposure` drives how many crashes of any kind a node sees. `severity_prone`
    # is a SEPARATE spatial field driving how likely a crash is to be severe.
    # Keeping them separate is the whole point: it is what makes crash count an
    # imperfect proxy for KSI risk, and therefore what leaves any room at all for
    # a model to beat a crash-count baseline.
    exposure = np.exp(0.9 * smooth_field(xy, rng, 60, 12_000) + rng.normal(0, 0.45, n))
    severity_prone = smooth_field(xy, rng, 45, 15_000) + rng.normal(0, SEVERITY_NOISE, n)

    # ── yearly crash series over the feature window ───────────────────────────
    # A mild per-node trend plus a COVID dip in 2020-21, mirroring the real data.
    trend = rng.normal(0.0, 0.16, n)
    yearly = np.zeros((n, len(FEATURE_YEARS)))
    for i, yr in enumerate(FEATURE_YEARS):
        covid = 0.72 if yr in (2020, 2021) else 1.0
        lam = 0.55 * exposure * np.exp(trend * (i - 2.5)) * covid
        yearly[:, i] = rng.poisson(lam)

    c72 = yearly.sum(axis=1)
    c36 = yearly[:, -3:].sum(axis=1)

    df = pd.DataFrame({"intersection_id": np.arange(n, dtype=np.int64)})

    # ── Group 1: crash history ────────────────────────────────────────────────
    # Every one of these is a transform of `yearly`. That redundancy is deliberate
    # and is the single most important property to reproduce -- it is why the
    # tuned model ties the persistence baseline on the real data.
    df["crashes_36mo"] = c36
    df["crashes_72mo"] = c72
    df["ped_crashes_72mo"] = rng.binomial(c72.astype(int), 0.09)
    df["bike_crashes_72mo"] = rng.binomial(c72.astype(int), 0.06)
    df["broadside_72mo"] = rng.binomial(c72.astype(int), 0.27)
    df["left_turn_72mo"] = rng.binomial(c72.astype(int), 0.21)
    df["dui_72mo"] = rng.binomial(c72.astype(int), 0.05)
    df["night_72mo"] = rng.binomial(c72.astype(int), 0.28)
    df["ped_row_violation_72mo"] = rng.binomial(c72.astype(int), 0.04)

    # Years since last crash: from the last year with a nonzero count.
    last_idx = np.where(yearly > 0, np.arange(len(FEATURE_YEARS)), -1).max(axis=1)
    df["years_since_last_crash"] = np.where(
        last_idx >= 0, (len(FEATURE_YEARS) - 1 - last_idx) + rng.uniform(0, 1, n), 9.0
    )

    # Distinct crash days saturates below the crash count (repeat days happen).
    df["distinct_crash_days_72mo"] = np.minimum(
        c72, rng.binomial(c72.astype(int), 0.93)
    )
    # Worst severity 1-4; candidates are KSI-free by construction, so cap at 3.
    df["worst_severity_72mo"] = np.where(
        c72 == 0, 0, np.minimum(3, 1 + rng.poisson(0.55 + 0.05 * severity_prone.clip(0), n))
    )

    # ── Group 2: emergence / trend ────────────────────────────────────────────
    first3 = yearly[:, :3].sum(axis=1)
    last3 = yearly[:, 3:].sum(axis=1)

    yr_idx = np.arange(len(FEATURE_YEARS))
    yr_centered = yr_idx - yr_idx.mean()
    denom = (yr_centered ** 2).sum()
    df["crash_trend_slope"] = (yearly * yr_centered).sum(axis=1) / denom

    df["emergence_velocity"] = (last3 - first3) / 3.0
    df["emergence_acceleration"] = (
        (yearly[:, 4:].sum(axis=1) - yearly[:, 2:4].sum(axis=1)) / 2.0
    )
    # Mann-Kendall tau on 6 points, computed exactly.
    sign_sum = np.zeros(n)
    for a in range(len(FEATURE_YEARS)):
        for b in range(a + 1, len(FEATURE_YEARS)):
            sign_sum += np.sign(yearly[:, b] - yearly[:, a])
    n_pairs = len(FEATURE_YEARS) * (len(FEATURE_YEARS) - 1) / 2
    df["mann_kendall_tau"] = sign_sum / n_pairs

    df["changepoint_prob"] = 1.0 / (1.0 + np.exp(-(last3 - first3) / 2.0))

    # EWMA over the series, most recent year weighted highest.
    alpha = 0.4
    w = alpha * (1 - alpha) ** np.arange(len(FEATURE_YEARS))[::-1]
    df["ewma_crashes"] = (yearly * w).sum(axis=1) / w.sum()

    df["momentum_ratio"] = (last3 + 1.0) / (first3 + 1.0)
    covid_crashes = yearly[:, 4:].sum(axis=1)
    df["covid_period_share"] = np.where(c72 > 0, covid_crashes / np.maximum(c72, 1), 0.0)

    # ── labels ────────────────────────────────────────────────────────────────
    # KSI intensity depends on exposure AND the independent severity field. The
    # coefficients below are then rescaled to hit the real positive counts.
    base = W_EXPOSURE * np.log1p(exposure) + W_SEVERITY * severity_prone
    ksi_lambda = np.exp(base - base.mean())

    # Real KSI counts are overdispersed relative to Poisson: the panel has 378
    # sites with >=1 KSI but 21 with >=2, a tail far heavier than a Poisson with
    # the same >=1 rate produces (which gives ~7). Multiplying the rate by a
    # mean-1 Gamma frailty adds exactly that kind of heterogeneity, and `shape`
    # controls how much -- smaller shape, heavier tail.
    shape = _calibrate_dispersion(ksi_lambda, TARGET_POS_GE1, TARGET_POS_GE2)
    frailty = rng.gamma(shape, 1.0 / shape, n)
    scale = _calibrate_scale(ksi_lambda * frailty, rng, TARGET_POS_GE1, n)
    ksi = rng.poisson(ksi_lambda * frailty * scale)

    df["KSI_label"] = ksi.astype(float)

    # Severity split and total-crash label, so the harm_weighted and two_stage arms
    # in improvement_bakeoff.py are exercised rather than silently skipped.
    df["fatal_label"] = rng.binomial(ksi.astype(int), 0.243)
    df["severe_label"] = df["KSI_label"] - df["fatal_label"]
    df["total_crashes_label"] = rng.poisson(1.6 * exposure) + ksi

    # Self-check: report what the persistence baseline achieves on this draw, so a
    # change to the generator that silently makes the problem easier or harder is
    # visible immediately rather than months later.
    order = np.argsort(-(df["crashes_72mo"].to_numpy()
                         + df["crash_trend_slope"].to_numpy() / 100.0))
    n_pos1 = max(1, int((ksi >= 1).sum()))
    baseline_recall_500 = float((ksi[order][:500] >= 1).sum()) / n_pos1

    meta = {
        "synthetic": True,
        "baseline_recall_at_500_ge1": round(baseline_recall_500, 4),
        "real_baseline_recall_at_500_ge1": REAL_BASELINE_RECALL_500_GE1,
        "generator": "scripts/make_synthetic_panel.py",
        "seed": seed,
        "n_candidates": int(n),
        "n_pos_ge1": int((ksi >= 1).sum()),
        "n_pos_ge2": int((ksi >= 2).sum()),
        "target_pos_ge1": TARGET_POS_GE1,
        "target_pos_ge2": TARGET_POS_GE2,
        "WARNING": (
            "SYNTHETIC DATA. Any metric computed on this panel describes the "
            "generator, not San Diego. Use only to verify that pipeline code runs "
            "and that cross-validation does not leak. Never publish or cite a "
            "number derived from it."
        ),
    }

    return df, meta, xy


def _calibrate_dispersion(lam: np.ndarray, target_ge1: int, target_ge2: int) -> float:
    """Pick the Gamma frailty shape that reproduces the real >=2 / >=1 ratio.

    Under a Gamma(k, 1/k) mixture the marginal count is negative binomial, so both
    P(Y>=1) and P(Y>=2) are available in closed form. For each candidate shape we
    re-solve the rate scale to hold the >=1 count at its target, then read off how
    many >=2 sites that implies. The >=2 count falls monotonically in k (less
    dispersion, thinner tail), so bisection is safe.

    Working analytically rather than by resampling keeps this deterministic and
    fast -- it is solving expectations, not searching over random draws.
    """
    def ge2_at(k: float) -> float:
        lo, hi = 1e-10, 1e4
        for _ in range(200):
            s = (lo + hi) / 2
            m = s * lam
            # NB survival: P(Y>=1) = 1 - (k/(k+m))^k
            p0 = (k / (k + m)) ** k
            if float((1.0 - p0).sum()) < target_ge1:
                lo = s
            else:
                hi = s
        m = ((lo + hi) / 2) * lam
        p0 = (k / (k + m)) ** k
        p1 = p0 * (m / (k + m)) * k          # P(Y=1) for NB
        return float((1.0 - p0 - p1).sum())

    lo_k, hi_k = 0.02, 50.0
    for _ in range(60):
        mid = np.sqrt(lo_k * hi_k)           # geometric bisection: k spans decades
        if ge2_at(mid) > target_ge2:
            lo_k = mid                       # too heavy a tail -> raise k
        else:
            hi_k = mid
    return float(np.sqrt(lo_k * hi_k))


def _calibrate_scale(lam: np.ndarray, rng: np.random.Generator, target_ge1: int, n: int) -> float:
    """Find the multiplier on the Poisson rate that yields ~target_ge1 positives.

    Solved by bisection on the expected count, E[#{y>=1}] = sum(1 - exp(-s*lam)),
    which is monotone in s -- so this is exact in expectation rather than a
    trial-and-error loop over sampled draws.
    """
    lo, hi = 1e-8, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        expected = float((1.0 - np.exp(-mid * lam)).sum())
        if expected < target_ge1:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--n", type=int, default=N_CANDIDATES)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/model/synthetic_run",
                    help="output directory. Deliberately NOT data/model/verified_run: "
                         "that path holds real pipeline output and must never be "
                         "clobbered by generated data. Point the bakeoff here with "
                         "--panel-dir data/model/synthetic_run.")
    args = ap.parse_args()

    import geopandas as gpd
    from shapely.geometry import Point

    print(f"Generating synthetic panel: n={args.n:,} seed={args.seed}")
    df, meta, xy = build(args.n, args.seed)

    print(f"  positives >=1 KSI: {meta['n_pos_ge1']:4d}  (real panel: {TARGET_POS_GE1})")
    print(f"  positives >=2 KSI: {meta['n_pos_ge2']:4d}  (real panel: {TARGET_POS_GE2})")
    print(f"  persistence baseline recall@500 (>=1): "
          f"{meta['baseline_recall_at_500_ge1']:.3f}  "
          f"(real panel: {REAL_BASELINE_RECALL_500_GE1:.3f})")

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    # candidate_panel: geometry + labels, read with gpd.read_parquet downstream.
    panel_cols = ["intersection_id", "KSI_label", "fatal_label", "severe_label",
                  "total_crashes_label"]
    panel = gpd.GeoDataFrame(
        df[panel_cols].copy(),
        geometry=[Point(a, b) for a, b in xy],
        crs="EPSG:2230",
    )
    # NOTE: crashes_72mo / crash_trend_slope deliberately live ONLY in the feature
    # table, not here. persistence_baseline_scores() reads them off the panel, but
    # every consumer merges the feature table onto the panel first -- carrying them
    # in both places makes that merge emit crashes_72mo_x / _y and breaks the
    # feature lookup.
    panel.to_parquet(out_dir / "candidate_panel.parquet", index=False)

    # feature_table: intersection_id + the 20 features.
    df[["intersection_id"] + FEATURE_LIST].to_parquet(
        out_dir / "feature_table.parquet", index=False
    )

    (out_dir / "SYNTHETIC.json").write_text(json.dumps(meta, indent=2))

    # frozen_params.json, matching the real file's structure. Values are the
    # Protocol-A defaults from configs/config.yaml; a synthetic run has no
    # business re-tuning them.
    params_path = out_dir / "frozen_params.json"
    if params_path.exists():
        print(f"  keeping existing {params_path.relative_to(ROOT)}")
    else:
        params_path.parent.mkdir(parents=True, exist_ok=True)
        params_path.write_text(json.dumps({
            "synthetic": True,
            "frozen": {
                "objective": "reg:tweedie",
                "tweedie_variance_power": 1.3,
                "max_depth": 4,
                "learning_rate": 0.05,
                "n_estimators": 400,
                "reg_alpha": 0.5,
                "reg_lambda": 2.0,
                "min_child_weight": 5,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "random_state": 42,
            },
            "sets": {"A_crash_only": {"feature_list": FEATURE_LIST}},
        }, indent=2))
        print(f"  wrote {params_path.relative_to(ROOT)} (synthetic placeholder)")

    print(f"\nWrote to {out_dir.relative_to(ROOT)}:")
    print("  candidate_panel.parquet")
    print("  feature_table.parquet")
    print("  SYNTHETIC.json   <- marks this panel as generated, not real")
    print("\n" + "!" * 76)
    print("SYNTHETIC DATA. Metrics from this panel describe the generator, not San")
    print("Diego. Use only to check that code runs and that CV does not leak.")
    print("!" * 76)


if __name__ == "__main__":
    main()
