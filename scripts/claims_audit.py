"""
*** DEPRECATED as of D15 (docs/DECISIONS.md) -- DO NOT TRUST THIS SCRIPT'S OUTPUT. ***

Every STATED constant and source file below (milestone3a_results.json, milestone4.md,
milestone5_prewriting.md, model_scores.parquet) is from before the D6/D10/D11/D15 fixes --
pre-county-restriction candidate counts (81,007/22), pre-fatal-share-fix harm figures, and
file paths that may no longer exist. Running this will produce false "NO"/"REVIEW" flags
against numbers that are now CORRECT, and would silently pass numbers that are now WRONG
(it never reads reports/verified_canonical_numbers.json or any results/oof_*.json file --
the actual current sources of truth).

For an up-to-date claims check, cross-reference README.md / reports/milestone_final.md /
the Notion outreach pages directly against reports/verified_canonical_numbers.json and
results/oof_verified_run_results.json, results/recall_evaluation.json (the forward run and
prospective evaluation are the same artifact as of D17). This script is kept for reference
only and should be rewritten against those files (or deleted) before being run again.

Original docstring follows:

Claims audit: recompute every headline figure directly from source files and
compare against the values currently asserted in the pitch deck, one-pager,
cost analysis, and Notion.

This script does not refit, retrain, or modify any model or data. It reads the
canonical source artifacts, recomputes each claimed statistic from scratch where
possible, and writes a single reconciliation table:

    reports/claims_audit.csv

Each row: claim_id, claim_text, stated_value, recomputed_value, source_file,
match (YES / NO / REVIEW), note.

Run from the project root:
    python scripts/claims_audit.py

Note: this script recomputes spearman/recall directly from model_scores.parquet and
frozen_scores.parquet, which hold in-sample scores. STATED below reflects the genuine
out-of-fold figures (see scripts/refit_verified_run_oof.py), so a mismatch against those
files is expected and correctly flags that they shouldn't be cited as performance claims.
Use results/oof_verified_run_results.json for the validated numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.utils import load_config, project_root

ROOT = project_root()
MODEL_DIR = ROOT / "data" / "model"
PROC_DIR = ROOT / "data" / "proc"
REPORTS_DIR = ROOT / "reports"
OUT_PATH = REPORTS_DIR / "claims_audit.csv"

FHWA_FATAL_COST = 15_988_000.0
FHWA_SERIOUS_COST = 1_705_100.0

KSI_SEVERITY_CODES = {1, 2}
FATAL_SEVERITY_CODE = 1
SERIOUS_SEVERITY_CODE = 2

STATED = {
    "verified_candidates": "81007",
    "verified_emergent_ge2": "22",
    "verified_spearman_random": "0.087",
    "verified_spearman_spatial": "0.084",
    "persistence_spearman_random": "0.087",
    "recall_at_200": "0.273",
    "recall_at_500": "0.455",
    "random_mult_at_200": "110x",
    "ksi_events_per_site": "2.0",
    "fatal_share": "0.243",
    "serious_share": "0.757",
    "total_societal_harm": "227723044",
    "shap_top_feature": "years_since_last_crash",
    "shap_narrative": "recency/timing beats volume",
    "predictive_candidates": "80618",
    "predictive_emergent_ge2": "2",
}

rows = []


def add(claim_id, claim_text, stated, recomputed, source_file, match, note=""):
    rows.append({
        "claim_id": claim_id,
        "claim_text": claim_text,
        "stated_value": stated,
        "recomputed_value": recomputed,
        "source_file": source_file,
        "match": match,
        "note": note,
    })


def near(a, b, tol=0.01):
    return abs(a - b) <= tol


def load_parquet_safe(path):
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def find_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def audit_candidate_counts(cfg):
    panel = load_parquet_safe(MODEL_DIR / "candidate_panel.parquet")
    if panel is None:
        add("candidates", "Number of surface-street candidate intersections",
            STATED["verified_candidates"], "MISSING",
            "data/model/candidate_panel.parquet", "REVIEW",
            "candidate_panel.parquet not found")
        return

    n = len(panel)
    stated_verified = int(STATED["verified_candidates"])
    stated_predictive = int(STATED["predictive_candidates"])
    if n == stated_verified:
        match, note = "YES", "panel matches the VERIFIED run count"
    elif n == stated_predictive:
        match, note = ("REVIEW",
            "panel on disk is the PREDICTIVE run (80,870), not the verified "
            "81,007. Any claim citing 81,007 must use a preserved verified "
            "artifact, not this live panel.")
    else:
        match, note = "NO", "panel count " + str(n) + " matches neither stated run"
    add("candidates", "Number of surface-street candidate intersections",
        str(stated_verified) + " (verified) / " + str(stated_predictive) + " (predictive)",
        str(n), "data/model/candidate_panel.parquet", match, note)

    label_col = find_col(panel, ["KSI_label", "ksi_label", "y_label", "label_ksi"])
    if label_col is not None:
        ge1 = int((panel[label_col] >= 1).sum())
        ge2 = int((panel[label_col] >= 2).sum())
        run = "verified" if n == stated_verified else "predictive"
        stated_ge2 = (STATED["verified_emergent_ge2"] if run == "verified"
                      else STATED["predictive_emergent_ge2"])
        add("emergent_ge2",
            "Emergent sites with >=2 KSI (" + run + " run, recomputed from panel)",
            stated_ge2, str(ge2), "data/model/candidate_panel.parquet",
            "YES" if str(ge2) == stated_ge2 else "NO",
            "This panel is the " + run.upper() + " run. >=1 KSI sites: " + str(ge1) +
            ". NOTE: deck/one-pager cite 22 (verified); live panel may be 10 "
            "(predictive). Confirm every '22' refers to the verified run.")
    else:
        add("emergent_ge2", "Emergent sites with >=2 KSI",
            STATED["verified_emergent_ge2"], "UNKNOWN",
            "data/model/candidate_panel.parquet", "REVIEW",
            "No label column found; columns: " + str(list(panel.columns)[:12]))


def audit_spearman():
    m3a = MODEL_DIR / "milestone3a_results.json"
    if m3a.exists():
        data = json.loads(m3a.read_text())
        tw = data.get("xgb_tweedie", {})
        r_rand = tw.get("random_thr1", {}).get("point", {}).get("spearman_rho")
        r_spat = tw.get("spatial_thr1", {}).get("point", {}).get("spearman_rho")
        base = data.get("baseline", {})
        b_rand = base.get("random_thr1", {}).get("point", {}).get("spearman_rho")

        if r_rand is not None:
            add("spearman_random_verified",
                "Crash-only Tweedie Spearman rho, random split (verified run)",
                STATED["verified_spearman_random"], "%.4f" % r_rand,
                "data/model/milestone3a_results.json",
                "YES" if near(r_rand, float(STATED["verified_spearman_random"]), 0.005) else "NO",
                "milestone3a = original verified run.")
        if r_spat is not None:
            add("spearman_spatial_verified",
                "Crash-only Tweedie Spearman rho, spatial split (verified run)",
                STATED["verified_spearman_spatial"], "%.4f" % r_spat,
                "data/model/milestone3a_results.json",
                "YES" if near(r_spat, float(STATED["verified_spearman_spatial"]), 0.005) else "NO",
                "NOTE: deck cites 0.193 spatial; this JSON is source of truth "
                "for the verified run.")
        if b_rand is not None:
            add("persistence_random_verified",
                "Persistence baseline Spearman rho, random split (verified run)",
                STATED["persistence_spearman_random"], "%.4f" % b_rand,
                "data/model/milestone3a_results.json",
                "YES" if near(b_rand, float(STATED["persistence_spearman_random"]), 0.005) else "NO",
                "")
    else:
        add("spearman_verified", "Verified-run Spearman values",
            STATED["verified_spearman_random"] + "/" + STATED["verified_spearman_spatial"],
            "MISSING", "data/model/milestone3a_results.json", "REVIEW",
            "milestone3a_results.json not found")

    m4 = REPORTS_DIR / "milestone4.md"
    if m4.exists():
        text = m4.read_text()
        a_random = None
        for line in text.splitlines():
            if line.strip().startswith("| A_crash_only"):
                parts = [p.strip() for p in line.split("|")]
                try:
                    a_random = float(parts[2].split("[")[0].strip())
                except (ValueError, IndexError):
                    pass
                break
        if a_random is not None:
            add("spearman_random_predictive",
                "Crash-only Spearman rho, random split (PREDICTIVE/retrained run)",
                STATED["verified_spearman_random"], "%.4f" % a_random,
                "reports/milestone4.md", "REVIEW",
                "CRITICAL: retrained run shows ~0.155, deck cites 0.175 from "
                "the verified run. Two different runs. Pick one framing per "
                "document and label which run it is.")


def audit_recall():
    m4 = REPORTS_DIR / "milestone4.md"
    if not m4.exists():
        add("recall", "recall@K figures",
            STATED["recall_at_200"] + "/" + STATED["recall_at_500"], "MISSING",
            "reports/milestone4.md", "REVIEW", "milestone4.md not found")
        return

    text = m4.read_text()
    rand_block = text.split("(random 80/20 split)")[-1].split("(spatial")[0]
    r200 = r500 = None
    for line in rand_block.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) > 3 and cells[1] == "200":
            try:
                r200 = float(cells[2])
            except ValueError:
                pass
        if len(cells) > 3 and cells[1] == "500":
            try:
                r500 = float(cells[2])
            except ValueError:
                pass

    add("recall_at_200", "recall@200 (current M4 report, random split)",
        STATED["recall_at_200"], "N/A" if r200 is None else "%.3f" % r200,
        "reports/milestone4.md", "REVIEW",
        "CRITICAL: current M4 random-split recall is computed on only 2 "
        "test-set positives (10 emergent sites, 20% in test). recall=1.000 "
        "with CI [0.500,1.000] is 2 sites, not a robust 22. Deck's 0.80/1.00 "
        "came from the earlier 22-site run. State n explicitly everywhere.")
    add("recall_at_500", "recall@500 (current M4 report, random split)",
        STATED["recall_at_500"], "N/A" if r500 is None else "%.3f" % r500,
        "reports/milestone4.md", "REVIEW",
        "Same caveat as recall@200. A single small test-split fold gives an "
        "unstable recall estimate. Use the genuine out-of-fold figures in "
        "results/oof_verified_run_results.json for operational/Council claims.")


def audit_full_ranking_recall():
    scores = load_parquet_safe(MODEL_DIR / "model_scores.parquet")
    panel = load_parquet_safe(MODEL_DIR / "candidate_panel.parquet")
    if scores is None or panel is None:
        add("full_ranking_recall", "Full-ranking recall@K (operational view)",
            STATED["recall_at_200"] + "/" + STATED["recall_at_500"], "MISSING",
            "data/model/model_scores.parquet", "REVIEW",
            "model_scores.parquet or candidate_panel.parquet not found.")
        return

    score_col = find_col(scores, ["xgb_tweedie_score", "A_crash_only__xgb_tweedie",
                                  "xgb_tweedie", "score", "tweedie_score", "pred"])
    id_col_scores = find_col(scores, ["intersection_id", "node_id", "id"])
    id_col_panel = find_col(panel, ["intersection_id", "node_id", "id"])
    label_col = find_col(panel, ["KSI_label", "ksi_label", "y_label"])

    if not all([score_col, id_col_scores, id_col_panel, label_col]):
        add("full_ranking_recall", "Full-ranking recall@K (operational view)",
            STATED["recall_at_200"] + "/" + STATED["recall_at_500"], "REVIEW",
            "data/model/model_scores.parquet", "REVIEW",
            "Could not resolve columns. scores: " + str(list(scores.columns)[:8]) +
            "; panel: " + str(list(panel.columns)[:8]))
        return

    merged = scores[[id_col_scores, score_col]].merge(
        panel[[id_col_panel, label_col]],
        left_on=id_col_scores, right_on=id_col_panel, how="inner")
    merged = merged.sort_values(score_col, ascending=False).reset_index(drop=True)
    total_pos = int((merged[label_col] >= 2).sum())

    for k in (50, 100, 200, 500, 1000):
        topk = merged.head(k)
        hits = int((topk[label_col] >= 2).sum())
        recall = hits / total_pos if total_pos else float("nan")
        base = (k / len(merged)) if len(merged) else float("nan")
        mult = (recall / base) if base and not np.isnan(recall) and base > 0 else float("nan")
        stated = (STATED["recall_at_200"] if k == 200
                  else STATED["recall_at_500"] if k == 500 else "-")
        note = ("FULL-RANKING recall@" + str(k) + ": " + str(hits) + "/" +
                str(total_pos) + " true emergent sites in top " + str(k) + " of " +
                str(len(merged)) + " candidates. Random expectation %.4f" % base +
                " => %.1fx lift. THIS is the operational shortlist number for " % mult +
                "Council/one-pager.")
        add("full_ranking_recall_" + str(k),
            "Full-ranking recall@" + str(k) + " (all candidates, >=2 KSI)",
            stated, "%.3f (" % recall + str(hits) + "/" + str(total_pos) + ")",
            "data/model/model_scores.parquet + candidate_panel.parquet",
            "REVIEW", note)


def audit_cost_assumptions():
    crashes = load_parquet_safe(PROC_DIR / "ksi_label_crashes.parquet")
    panel = load_parquet_safe(MODEL_DIR / "candidate_panel.parquet")

    label_col = None
    if panel is not None:
        label_col = find_col(panel, ["KSI_label", "ksi_label", "y_label"])
        if label_col is not None:
            emergent = panel[panel[label_col] >= 2]
            if len(emergent):
                mean_events = float(emergent[label_col].mean())
                add("ksi_events_per_site",
                    "Mean KSI events per emergent site (measured from labels)",
                    STATED["ksi_events_per_site"], "%.2f" % mean_events,
                    "data/model/candidate_panel.parquet",
                    "YES" if near(mean_events, float(STATED["ksi_events_per_site"]), 0.25) else "NO",
                    "Deck assumed 2.5. This is measured. If it differs, the "
                    "$208M total must be recomputed.")

    if crashes is not None:
        sev_col = find_col(crashes, ["severity", "COLLISION_SEVERITY",
                                     "collision_severity", "sev"])
        if sev_col is not None:
            sev = pd.to_numeric(crashes[sev_col], errors="coerce")
            ksi = sev[sev.isin(KSI_SEVERITY_CODES)]
            n_ksi = len(ksi)
            if n_ksi:
                fatal_share = float((ksi == FATAL_SEVERITY_CODE).sum() / n_ksi)
                serious_share = float((ksi == SERIOUS_SEVERITY_CODE).sum() / n_ksi)
                add("fatal_share",
                    "Fatal share of label-window KSI crashes (measured)",
                    STATED["fatal_share"], "%.3f" % fatal_share,
                    "data/proc/ksi_label_crashes.parquet",
                    "YES" if near(fatal_share, float(STATED["fatal_share"]), 0.03) else "NO",
                    "Deck assumed 15% fatal. This is measured. Drives the $ total.")

                if panel is not None and label_col is not None:
                    emergent = panel[panel[label_col] >= 2]
                    total_events = float(emergent[label_col].sum()) if len(emergent) else 0.0
                    fatal_events = total_events * fatal_share
                    serious_events = total_events * serious_share
                    recomputed_total = (fatal_events * FHWA_FATAL_COST
                                        + serious_events * FHWA_SERIOUS_COST)
                    stated_total = float(STATED["total_societal_harm"])
                    add("total_societal_harm",
                        "Total societal harm, emergent sites (rebuilt from measured mix)",
                        "$%.0fM" % (stated_total / 1e6), "$%.0fM" % (recomputed_total / 1e6),
                        "panel labels + ksi_label_crashes severity + FHWA costs",
                        "YES" if abs(recomputed_total - stated_total) / stated_total < 0.15 else "NO",
                        "Rebuilt from %.0f total KSI events across " % total_events +
                        "emergent sites, measured fatal share %.2f. " % fatal_share +
                        "If NO, the deck's $208M used assumed inputs.")
    else:
        add("cost_severity_mix", "Fatal/serious split for cost calc",
            STATED["fatal_share"] + "/" + STATED["serious_share"], "MISSING",
            "data/proc/ksi_label_crashes.parquet", "REVIEW",
            "Label-window KSI crash file not found; cannot verify the 15/85 "
            "split. The $208M may rest on an unverified assumption.")


def audit_shap_narrative():
    m5 = REPORTS_DIR / "milestone5_prewriting.md"
    if not m5.exists():
        add("shap_narrative", "SHAP narrative (recency vs volume)",
            STATED["shap_narrative"], "MISSING",
            "reports/milestone5_prewriting.md", "REVIEW",
            "milestone5_prewriting.md not found")
        return

    text = m5.read_text()
    recency_wins = "RECENCY > VOLUME" in text
    volume_wins = "VOLUME > RECENCY" in text

    if volume_wins:
        add("shap_narrative", "SHAP narrative: does recency/timing beat volume?",
            STATED["shap_narrative"], "VOLUME > RECENCY (volume wins)",
            "reports/milestone5_prewriting.md", "NO",
            "CRITICAL: M5 found VOLUME > RECENCY. Deck slide 5 frames the signal "
            "as 'recency/timing, not counts' -- the OPPOSITE. changepoint_prob "
            "(#2) supports a 'structural break' story, but 'recency beats volume' "
            "is false. Fix slide 5.")
    elif recency_wins:
        add("shap_narrative", "SHAP narrative: does recency/timing beat volume?",
            STATED["shap_narrative"], "RECENCY > VOLUME",
            "reports/milestone5_prewriting.md", "YES", "")

    top_ok = "years_since_last_crash" in text.split("Top-15")[-1][:200]
    add("shap_top_feature", "Top SHAP feature", STATED["shap_top_feature"],
        "years_since_last_crash" if top_ok else "REVIEW",
        "reports/milestone5_prewriting.md",
        "YES" if top_ok else "REVIEW", "")


def main():
    cfg = load_config()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    audit_candidate_counts(cfg)
    audit_spearman()
    audit_recall()
    audit_full_ranking_recall()
    audit_cost_assumptions()
    audit_shap_narrative()

    df = pd.DataFrame(rows, columns=[
        "claim_id", "claim_text", "stated_value", "recomputed_value",
        "source_file", "match", "note",
    ])
    df.to_csv(OUT_PATH, index=False)

    n_no = int((df["match"] == "NO").sum())
    n_review = int((df["match"] == "REVIEW").sum())
    n_yes = int((df["match"] == "YES").sum())

    print("Claims audit written: " + str(OUT_PATH))
    print("  YES (match):   " + str(n_yes))
    print("  NO (mismatch): " + str(n_no))
    print("  REVIEW:        " + str(n_review))
    print()
    if n_no or n_review:
        print("Rows needing attention:")
        flagged = df[df["match"].isin(["NO", "REVIEW"])]
        for _, r in flagged.iterrows():
            print("  [" + r["match"] + "] " + r["claim_id"] + ": " + r["claim_text"])
            print("        stated=" + str(r["stated_value"]) +
                  "  recomputed=" + str(r["recomputed_value"]))
            if r["note"]:
                print("        " + r["note"])
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
