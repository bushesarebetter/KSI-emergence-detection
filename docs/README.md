# Project Documentation

This folder makes the repository self-describing. The full design and the reasoning
behind every change live here, so anyone (or any AI session) can pick up the project
from the repo alone, no outside context needed.

**Resuming the project, or starting a new chat? Read `../reports/milestone_final.md` first.**
Research is complete as of 2026-06-20; that file is the current-state and resume point
(it replaced `PROJECT_STATE.md` and `ROADMAP.md`, which tracked in-progress status and are
now removed).

**Read order:**

1. `../reports/milestone_final.md`, where the project stands now: verified-run and
   forward-run results, what's validated vs. pending, recommended next steps, file index.
2. `RESEARCH_DESIGN.md`, the locked study design: task, unit, windows, target, evaluation.
3. `DECISIONS.md`, the decision and deviation log: design choices, methodology, and the
   "why" behind every change. Read this before changing anything.
4. `DATA_SOURCES.md`, every dataset, how to get it, and the correct coordinate fields to use
   (`POINT_X`/`POINT_Y`).
5. `FEATURE_CATALOG.md`, feature groups, implementation status, and both temporal-validity walls.
6. `../reports/`, milestone reports (`milestone1.md` through `milestone5_prewriting.md`)
   are kept as the historical record of how the project arrived at the final result; several
   carry erratum banners since `DECISIONS.md` D11 (candidate-set scope bug) was discovered
   after they were written. Treat their headline numbers as superseded by
   `milestone_final.md`.

**Ground truth for runtime constants is `../configs/config.yaml`.** If a value here and in
config disagree, config wins and this doc needs fixing.
