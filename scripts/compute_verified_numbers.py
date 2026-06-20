"""
Compute canonical figures for two pipeline runs:

  VERIFIED RUN  (2016-2021 features -> 2022-2024 labels)
    Source: data/model/verified_run/ (archive written after STEP 2 of the
    June 2026 pipeline run). This is the primary scientific result.
    These numbers never change regardless of config.

  FORWARD RUN  (2016-2024 features -> 2025-2027 labels)
    Source: data/model/forward_run/ (archive written after STEP 4).
    Label window: 2025 complete; 2026-2027 are future predictions.

IMPORTANT: data/model/frozen_scores.parquet and data/model/model_scores.parquet
at the project root are the CURRENT RUN artifacts and will be overwritten by
any retraining. Always read from data/model/verified_run/ and
data/model/forward_run/ archives for stable canonical figures.

Writes: reports/verified_canonical_numbers.json

Run from project root:
    python scripts/compute_verified_numbers.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.utils import project_root

ROOT = project_root()
MODEL_DIR = ROOT / "data" / "model"
PROC_DIR = ROOT / "data" / "proc"
REPORTS_DIR = ROOT / "reports"
OUT = REPORTS_DIR / "verified_canonical_numbers.json"

FHWA_FATAL_COST = 15_988_000.0
FHWA_SERIOUS_COST = 1_705_100.0
KSI_SEVERITY_CODES = {1, 2}
FATAL_CODE = 1

# Genuine out-of-fold figures (scripts/refit_verified_run_oof.py). The recall@K table
# computed below from frozen_scores.parquet is in-sample; cross-check against
# results/oof_verified_run_results.json before citing recall@K externally.
VERIFIED_SPEARMAN = {"random": 0.0869, "spatial": 0.0842}
VERIFIED_BASELINE = {"random": 0.0868, "spatial": 0.0868}


def recall_table(df: pd.DataFrame, label_col: str, score_col: str, threshold: int) -> dict:
    positives = df[label_col] >= threshold
    total_pos = int(positives.sum())
    total_events = int(df.loc[positives, label_col].sum())
    n = len(df)
    result = {"total_positives": total_pos, "total_ksi_events": total_events}
    for k in (50, 100, 200, 500, 1000):
        hits = int((df.head(k)[label_col] >= threshold).sum())
        recall = hits / total_pos if total_pos else None
        base = k / n
        lift = recall / base if (recall is not None and base > 0) else None
        result[str(k)] = {
            "hits": hits,
            "recall": round(recall, 4) if recall is not None else None,
            "random_baseline_recall": round(base, 6),
            "lift_over_random": round(lift, 1) if lift is not None else None,
        }
    return result


def severity_mix(proc_dir: Path, label_start: str, label_end: str) -> tuple[float, float]:
    """Fatal share of KSI crashes in a specific label window, computed directly from raw
    SWITRS rather than data/proc/ksi_label_crashes.parquet.

    That proc file is NOT archived per-run: src/labels/build_panel.py overwrites it in
    place every time it runs, for any window, so it silently reflects whichever run was
    built most recently rather than the window this call actually wants. Filtering raw
    SWITRS by the label window directly avoids that trap.
    """
    raw_dir = ROOT / "data" / "raw" / "switrs"
    frames = []
    if raw_dir.exists():
        for snapshot_dir in sorted(raw_dir.iterdir()):
            f = snapshot_dir / "crashes.csv"
            if f.exists():
                frames.append(pd.read_csv(f, low_memory=False))
    if not frames:
        print("  WARNING: no raw SWITRS crashes.csv found; using fallback 24.3% fatal")
        return 0.243, 0.757
    crashes = pd.concat(frames).drop_duplicates(subset="CASE_ID")
    crashes["COLLISION_DATE"] = pd.to_datetime(crashes["COLLISION_DATE"], errors="coerce")
    in_window = (crashes["COLLISION_DATE"] >= label_start) & (crashes["COLLISION_DATE"] <= label_end)
    surface = crashes["STATE_HWY_IND"].astype(str).str.upper() != "Y"
    ksi = crashes.loc[in_window & surface & crashes["COLLISION_SEVERITY"].isin(KSI_SEVERITY_CODES), "COLLISION_SEVERITY"]
    if len(ksi) == 0:
        return 0.243, 0.757
    fatal = float((ksi == FATAL_CODE).sum() / len(ksi))
    return fatal, 1.0 - fatal


def harm_estimate(total_events: int, fatal_share: float) -> dict:
    blended = fatal_share * FHWA_FATAL_COST + (1.0 - fatal_share) * FHWA_SERIOUS_COST
    total = total_events * blended
    return {
        "total_ksi_events": total_events,
        "fatal_share_measured": round(fatal_share, 4),
        "blended_cost_per_event_usd": round(blended),
        "total_harm_usd": round(total),
        "total_harm_readable": "$%.0fM" % (total / 1e6),
        "fhwa_cost_source": "FHWA-SA-25-021 October 2025 2024 dollars",
    }


def load_verified_artifacts() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Load verified-run scores and panel from the archive directory.

    Returns (scores_df, panel_df, score_column_name).
    Raises FileNotFoundError with a clear message if the archive is missing.
    """
    verified_dir = MODEL_DIR / "verified_run"

    # Try archive first (stable), then legacy path (may be overwritten)
    for scores_path, panel_path, source in [
        (verified_dir / "frozen_scores.parquet",
         verified_dir / "candidate_panel.parquet",
         "data/model/verified_run/ (archive)"),
        (MODEL_DIR / "model_scores.parquet",
         MODEL_DIR / "candidate_panel.parquet",
         "data/model/ (WARNING: may be overwritten by forward run)"),
    ]:
        if scores_path.exists() and panel_path.exists():
            scores = pd.read_parquet(scores_path)
            panel = pd.read_parquet(panel_path)
            # Validate: verified run must have exactly 21 ge2 positives (City of San Diego
            # candidate set, post-D11; the pre-D11 county-wide set had 22)
            if "KSI_label" in panel.columns and (panel["KSI_label"] >= 2).sum() == 21:
                score_col = next(
                    (c for c in scores.columns
                     if ("crash_only" in c.lower() and "xgb_tweedie" in c.lower())
                     or c == "xgb_tweedie_score"),
                    None,
                )
                if score_col:
                    print(f"  Verified run source: {source}")
                    print(f"  Score column: {score_col}")
                    return scores, panel, score_col
            elif "KSI_label" in panel.columns:
                n21 = (panel["KSI_label"] >= 2).sum()
                print(f"  SKIP {source}: found {n21} ge2 positives (expected 21) -- likely forward run artifacts")

    raise FileNotFoundError(
        "Verified-run artifacts not found or invalid. "
        "Expected data/model/verified_run/frozen_scores.parquet with 21 ge2 positives. "
        "Run the verified-run pipeline (feature_end=2021-12-31, label_end=2024-12-31) "
        "and ensure fit_frozen.py archives to data/model/verified_run/."
    )


def load_forward_artifacts() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Load forward-run scores and panel from archive or current files."""
    forward_dir = MODEL_DIR / "forward_run"

    for scores_path, panel_path, source in [
        (forward_dir / "frozen_scores.parquet",
         forward_dir / "candidate_panel.parquet",
         "data/model/forward_run/ (archive)"),
        (MODEL_DIR / "frozen_scores.parquet",
         MODEL_DIR / "candidate_panel.parquet",
         "data/model/ (current)"),
    ]:
        if scores_path.exists() and panel_path.exists():
            scores = pd.read_parquet(scores_path)
            panel = pd.read_parquet(panel_path)
            score_col = next(
                (c for c in scores.columns
                 if ("crash_only" in c.lower() and "xgb_tweedie" in c.lower())
                 or c == "xgb_tweedie_score"
                 or c == "A_crash_only__xgb_tweedie"),
                scores.columns[-1],
            )
            print(f"  Forward run source: {source}")
            return scores, panel, score_col

    raise FileNotFoundError(
        "Forward-run artifacts not found. "
        "Run the forward-run pipeline (feature_end=2024-12-31, label_end=2027-12-31)."
    )


def build_ranked_df(scores: pd.DataFrame, panel: pd.DataFrame, score_col: str) -> pd.DataFrame:
    """Merge scores with panel labels and sort descending by score."""
    id_cols_scores = [c for c in ["intersection_id", "node_id", "osmid"] if c in scores.columns]
    id_cols_panel = [c for c in ["intersection_id", "node_id", "osmid"] if c in panel.columns]
    if id_cols_scores and id_cols_panel:
        id_s, id_p = id_cols_scores[0], id_cols_panel[0]
        df = scores[[id_s, score_col]].merge(
            panel[[id_p, "KSI_label"]], left_on=id_s, right_on=id_p, how="inner"
        )
    else:
        df = scores[[score_col]].copy()
        df["KSI_label"] = panel["KSI_label"].values[: len(df)]
    return df.sort_values(score_col, ascending=False).reset_index(drop=True)


def run_verified(fatal_share: float) -> dict:
    """Compute verified-run canonical figures from the archived artifacts."""
    scores, panel, score_col = load_verified_artifacts()
    df = build_ranked_df(scores, panel, score_col)
    n = len(df)
    ge2 = recall_table(df, "KSI_label", score_col, threshold=2)
    ge1 = recall_table(df, "KSI_label", score_col, threshold=1)
    return {
        "run": "verified (2016-2021 features -> 2022-2024 labels)",
        "candidates": n,
        "spearman_rho": {
            "random_split": VERIFIED_SPEARMAN["random"],
            "spatial_split": VERIFIED_SPEARMAN["spatial"],
            "note": "Genuine out-of-fold scoring, Protocol A Set A crash-only, SWITRS 20260608.",
        },
        "persistence_baseline_spearman": VERIFIED_BASELINE,
        "threshold_ge2": {
            "description": "Strong emergence: >=2 KSI in 3-year label window",
            "sites": ge2["total_positives"],
            "total_ksi_events": ge2["total_ksi_events"],
            "city_approach_recall": 0,
            "full_ranking_recall_at_k": {k: v for k, v in ge2.items() if k.isdigit()},
            "harm": harm_estimate(ge2["total_ksi_events"], fatal_share),
        },
        "threshold_ge1": {
            "description": "Any future KSI: >=1 KSI in 3-year label window",
            "sites": ge1["total_positives"],
            "total_ksi_events": ge1["total_ksi_events"],
            "city_approach_recall": 0,
            "full_ranking_recall_at_k": {k: v for k, v in ge1.items() if k.isdigit()},
            "harm": harm_estimate(ge1["total_ksi_events"], fatal_share),
        },
        "prospective_validation_2025": {
            "note": (
                "See results/recall_evaluation.json for the prospective evaluation: "
                "the verified-run model applied to 2016-2023 features, validated "
                "against 2025 KSI outcomes it never saw during training. "
                "recall@500 (>=1 KSI, 115 positives): 0.235 (37.9x random). "
                "recall@500 (>=2 KSI): not reported (only 2 sites in single-year window)."
            )
        },
    }


def run_forward(fatal_share: float) -> dict:
    """Compute forward-run figures from the archived artifacts."""
    scores, panel, score_col = load_forward_artifacts()
    df = build_ranked_df(scores, panel, score_col)
    n = len(df)
    ge2 = recall_table(df, "KSI_label", score_col, threshold=2)
    ge1 = recall_table(df, "KSI_label", score_col, threshold=1)
    return {
        "run": "forward (2016-2024 features -> 2025-2027 labels)",
        "candidates": n,
        "label_completeness": "2025 complete (SWITRS 20260615); 2026-2027 are future predictions",
        "spearman_note": "Not directly comparable to verified run -- single-year partial label window",
        "threshold_ge2": {
            "description": "Strong emergence: >=2 KSI in label window (2025 only)",
            "sites": ge2["total_positives"],
            "total_ksi_events": ge2["total_ksi_events"],
            "full_ranking_recall_at_k": {k: v for k, v in ge2.items() if k.isdigit()},
        },
        "threshold_ge1": {
            "description": "Any future KSI: >=1 KSI in label window (2025 data)",
            "sites": ge1["total_positives"],
            "total_ksi_events": ge1["total_ksi_events"],
            "full_ranking_recall_at_k": {k: v for k, v in ge1.items() if k.isdigit()},
        },
    }


def main() -> int:
    print("Reading SWITRS severity mix (verified-run window: 2022-2024)...")
    fatal_share_verified, _ = severity_mix(PROC_DIR, "2022-01-01", "2024-12-31")
    print(f"  Fatal share: {fatal_share_verified:.3f}")
    print("Reading SWITRS severity mix (forward-run window: 2025-2027)...")
    fatal_share_forward, _ = severity_mix(PROC_DIR, "2025-01-01", "2027-12-31")
    print(f"  Fatal share: {fatal_share_forward:.3f}")

    print()
    print("Loading verified run...")
    verified = run_verified(fatal_share_verified)
    print()
    print("Loading forward run...")
    try:
        forward = run_forward(fatal_share_forward)
    except FileNotFoundError as e:
        print(f"  Forward run skipped: {e}")
        forward = {"run": "not available", "note": str(e)}

    out = {"verified_run": verified, "forward_run": forward}
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print()
    print("Canonical numbers written: " + str(OUT))

    # ── Verified run console printout ──────────────────────────────────────────
    print()
    print("VERIFIED RUN (" + verified["run"] + ")")
    print("  Candidates:   " + str(verified["candidates"]))
    sp = verified["spearman_rho"]
    print(f"  Spearman:     {sp['random_split']} (random) / {sp['spatial_split']} (spatial)")
    for key, label in [("threshold_ge2", ">=2 KSI (strong emergence)"),
                        ("threshold_ge1", ">=1 KSI (any future severe harm)")]:
        t = verified[key]
        harm = t.get("harm", {})
        print(f"  {label}:")
        print(f"    Sites:  {t['sites']}   Events: {t['total_ksi_events']}"
              + (f"   Harm: {harm.get('total_harm_readable', 'N/A')}" if harm else ""))
        print("    Recall@K:")
        for k in ("50", "100", "200", "500", "1000"):
            v = t["full_ranking_recall_at_k"][k]
            r = v["recall"]
            lift = v["lift_over_random"]
            if r is None:
                print(f"      @{k:<5} {v['hits']}/{t['sites']} = N/A")
            else:
                print(f"      @{k:<5} {v['hits']}/{t['sites']} = {r:.3f}  ({lift:.1f}x random)")

    # ── Forward run console printout ───────────────────────────────────────────
    if "threshold_ge1" in forward:
        print()
        print("FORWARD RUN (" + forward.get("run", "forward") + ")")
        print("  NOTE: " + forward.get("label_completeness", ""))
        for key, label in [("threshold_ge2", ">=2 KSI"),
                            ("threshold_ge1", ">=1 KSI")]:
            if key not in forward:
                continue
            t = forward[key]
            print(f"  {label}:  {t['sites']} sites  |  {t['total_ksi_events']} events")

    return 0


if __name__ == "__main__":
    sys.exit(main())
