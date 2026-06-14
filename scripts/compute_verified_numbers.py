"""
Compute canonical figures for two pipeline runs:

  VERIFIED RUN  (2016-2021 features -> 2022-2024 labels)
    Reads data/model/model_scores.parquet directly.
    These numbers never change regardless of config.

  FORWARD RUN  (2016-2023 features -> 2024-2026 labels)
    Reads data/model/frozen_scores.parquet (output of fit_frozen).
    Uses data/model/candidate_panel.parquet for labels.
    Label window partially complete (2024 final; 2025-2026 pending).

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


def severity_mix(proc_dir: Path) -> tuple[float, float]:
    path = proc_dir / "ksi_label_crashes.parquet"
    if not path.exists():
        return 0.243, 0.757
    crashes = pd.read_parquet(path)
    sev_col = next(
        (c for c in ["severity", "COLLISION_SEVERITY", "collision_severity"] if c in crashes.columns),
        None,
    )
    if sev_col is None:
        return 0.243, 0.757
    sev = pd.to_numeric(crashes[sev_col], errors="coerce")
    ksi = sev[sev.isin(KSI_SEVERITY_CODES)]
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
        "fhwa_fatal_cost_2024": FHWA_FATAL_COST,
        "fhwa_serious_cost_2024": FHWA_SERIOUS_COST,
        "source": "FHWA-SA-25-021 October 2025",
    }


def run_verified(fatal_share: float) -> dict:
    """Verified run: model_scores.parquet, labels embedded, 2016-2021 -> 2022-2024."""
    scores = pd.read_parquet(MODEL_DIR / "model_scores.parquet")
    score_col = "xgb_tweedie_score"
    label_col = "KSI_label"

    df = scores[[score_col, label_col]].copy()
    df = df.sort_values(score_col, ascending=False).reset_index(drop=True)
    n = len(df)

    ge2 = recall_table(df, label_col, score_col, threshold=2)
    ge1 = recall_table(df, label_col, score_col, threshold=1)

    return {
        "label": "(verified run: 2016-2021 features, 2022-2024 labels, n=22 emergent)",
        "candidates": n,
        "spearman_rho": {
            "random_split": 0.175,
            "spatial_split": 0.169,
            "note": "source: milestone3a_results.json",
        },
        "persistence_baseline_spearman": {
            "random_split": 0.085,
            "spatial_split": 0.108,
        },
        "threshold_ge2": {
            "description": "Strong emergence: >=2 KSI events in the 3-year label window",
            "sites": ge2["total_positives"],
            "total_ksi_events": ge2["total_ksi_events"],
            "city_approach_recall": 0,
            "city_approach_note": "Definitional zero: emergent sites have no prior KSI history",
            "full_ranking_recall_at_k": {k: v for k, v in ge2.items() if k.isdigit()},
            "harm": harm_estimate(ge2["total_ksi_events"], fatal_share),
        },
        "threshold_ge1": {
            "description": "Any future KSI: >=1 KSI event in the 3-year label window",
            "sites": ge1["total_positives"],
            "total_ksi_events": ge1["total_ksi_events"],
            "city_approach_recall": 0,
            "city_approach_note": "Same zero: all candidate sites had zero prior KSI history",
            "full_ranking_recall_at_k": {k: v for k, v in ge1.items() if k.isdigit()},
            "harm": harm_estimate(ge1["total_ksi_events"], fatal_share),
        },
    }


def run_forward(fatal_share: float) -> dict:
    """Forward run: frozen_scores.parquet + candidate_panel.parquet, 2016-2023 -> 2024-2026."""
    frozen = pd.read_parquet(MODEL_DIR / "frozen_scores.parquet")
    panel = pd.read_parquet(MODEL_DIR / "candidate_panel.parquet")

    # Use crash-only scores (Set A)
    score_col = next(
        (c for c in ["score_A_crash_only", "A_crash_only"] if c in frozen.columns),
        [c for c in frozen.columns if "crash_only" in c.lower()][0]
        if any("crash_only" in c.lower() for c in frozen.columns)
        else frozen.columns[-1],
    )

    # Join scores to panel labels on node_id
    id_col = next((c for c in ["node_id", "osmid"] if c in frozen.columns and c in panel.columns), None)
    if id_col:
        df = frozen[[id_col, score_col]].merge(panel[[id_col, "KSI_label"]], on=id_col, how="inner")
    else:
        df = frozen[[score_col]].copy()
        df["KSI_label"] = panel["KSI_label"].values[: len(df)]

    df = df.sort_values(score_col, ascending=False).reset_index(drop=True)
    n = len(df)

    ge2 = recall_table(df, "KSI_label", score_col, threshold=2)
    ge1 = recall_table(df, "KSI_label", score_col, threshold=1)

    return {
        "label": "(forward run: 2016-2023 features, 2024-2026 labels)",
        "label_completeness_note": (
            "label window partially complete as of June 2026 — "
            "2024 outcomes are final, 2025-2026 are not yet available"
        ),
        "candidates": n,
        "spearman_rho": {
            "random_split": 0.0948,
            "spatial_split": 0.1084,
            "note": "source: forward-run milestone4.md (Set A crash-only)",
        },
        "threshold_ge2": {
            "description": "Strong emergence: >=2 KSI events in label window (partial — 2024 only)",
            "sites": ge2["total_positives"],
            "total_ksi_events": ge2["total_ksi_events"],
            "full_ranking_recall_at_k": {k: v for k, v in ge2.items() if k.isdigit()},
            "harm": harm_estimate(ge2["total_ksi_events"], fatal_share) if ge2["total_ksi_events"] > 0 else None,
        },
        "threshold_ge1": {
            "description": "Any future KSI: >=1 KSI event in label window (2024 data only)",
            "sites": ge1["total_positives"],
            "total_ksi_events": ge1["total_ksi_events"],
            "full_ranking_recall_at_k": {k: v for k, v in ge1.items() if k.isdigit()},
            "harm": harm_estimate(ge1["total_ksi_events"], fatal_share) if ge1["total_ksi_events"] > 0 else None,
        },
    }


def print_run_header(title: str, label: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print(label)
    print("=" * 72)


def print_threshold_block(name: str, data: dict, total_pos: int, ge_data: dict) -> None:
    print()
    print(f"  THRESHOLD {name}:")
    print(f"    Sites:      {data['sites']}")
    print(f"    Events:     {data['total_ksi_events']}")
    harm = data.get("harm")
    if harm:
        print(f"    Harm:       {harm['total_harm_readable']}")
    else:
        print(f"    Harm:       N/A (0 events)")
    print(f"    Recall@K (full population):")
    for k in ("50", "100", "200", "500", "1000"):
        v = data["full_ranking_recall_at_k"][k]
        if v["recall"] is None:
            print(f"      @{k:<5}  {v['hits']}/{total_pos} = N/A  (no positives to recall)")
        else:
            print(f"      @{k:<5}  {v['hits']}/{total_pos} = {v['recall']:.3f}  ({v['lift_over_random']:.1f}x random)")


def main() -> int:
    fatal_share, _ = severity_mix(PROC_DIR)

    verified = run_verified(fatal_share)
    forward = run_forward(fatal_share)

    out = {"verified_run": verified, "forward_run": forward}

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print("Canonical numbers written: " + str(OUT))

    # ---- VERIFIED RUN printout ----
    print_run_header("VERIFIED RUN", verified["label"])
    print(f"  Candidates:   {verified['candidates']}")
    print(f"  Spearman:     {verified['spearman_rho']['random_split']} (random) / {verified['spearman_rho']['spatial_split']} (spatial)")
    ge2_v = verified["threshold_ge2"]
    ge1_v = verified["threshold_ge1"]
    print_threshold_block(">=2 KSI (strong emergence)", ge2_v, ge2_v["sites"], ge2_v["full_ranking_recall_at_k"])
    print_threshold_block(">=1 KSI (any future severe harm)", ge1_v, ge1_v["sites"], ge1_v["full_ranking_recall_at_k"])

    # ---- FORWARD RUN printout ----
    print_run_header("FORWARD RUN", forward["label"])
    print(f"  NOTE: {forward['label_completeness_note']}")
    print(f"  Candidates:   {forward['candidates']}")
    print(f"  Spearman:     {forward['spearman_rho']['random_split']} (random) / {forward['spearman_rho']['spatial_split']} (spatial)")
    ge2_f = forward["threshold_ge2"]
    ge1_f = forward["threshold_ge1"]
    print_threshold_block(">=2 KSI (partial — 2024 only)", ge2_f, ge2_f["sites"], ge2_f["full_ranking_recall_at_k"])
    print_threshold_block(">=1 KSI (2024 data only)", ge1_f, ge1_f["sites"], ge1_f["full_ranking_recall_at_k"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
