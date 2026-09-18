# Project Documentation

This folder makes the repository self-describing: the design and the reasoning behind every
change live here, so anyone (or any AI session) can pick up the project from the repo alone.

**Current state and results:** `../README.md`, then `HYPOTHESIS.md`.

**Read order:**

1. `../README.md` — the model (E: crash history + infrastructure + spatial-neighbor structure),
   results, and reproduction.
2. `HYPOTHESIS.md` — the claim, its mechanism, the evidence, and where it breaks.
3. `RESEARCH_DESIGN.md` — the study design: task, unit, windows, target, evaluation.
4. `DECISIONS.md` — the decision and deviation log; read before changing anything (D18 defines
   the candidate set).
5. `DATA_SOURCES.md` — every dataset, how to get it, and the coordinate fields
   (`POINT_X`/`POINT_Y`).
6. `FEATURE_CATALOG.md` — feature groups (including Group 9, spatial), status, and the two
   temporal-validity walls.
7. `METHODOLOGY.md` — candidate set, windows, model, and evaluation in prose.

**Ground truth for runtime constants is `../configs/config.yaml`.** If a value here disagrees
with config, config wins and the doc needs fixing.
