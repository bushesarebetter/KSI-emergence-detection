# Project Documentation

This folder makes the repository self-describing. The full design and the reasoning
behind every change live here, so anyone (or any AI session) can pick up the project
from the repo alone, no outside context needed.

**Resuming the project, or starting a new chat? Read `PROJECT_STATE.md` first.** It's the
current-state and resume point.

**Read order:**

1. `PROJECT_STATE.md` — where the project stands now, what's verified, what's open, next action.
2. `RESEARCH_DESIGN.md` — the locked study design: task, unit, windows, target, evaluation.
3. `DECISIONS.md` — the decision and deviation log: design choices, methodology, and the
   "why" behind every change. Read this before changing anything.
4. `DATA_SOURCES.md` — every dataset, how to get it, and the correct coordinate fields to use
   (`POINT_X`/`POINT_Y`).
5. `FEATURE_CATALOG.md` — feature groups, implementation status, and both temporal-validity walls.
6. `ROADMAP.md` — milestone sequence and current status.

**Ground truth for runtime constants is `../configs/config.yaml`.** If a value here and in
config disagree, config wins and this doc needs fixing.
