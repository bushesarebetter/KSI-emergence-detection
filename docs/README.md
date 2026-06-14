# Project Documentation

This folder makes the repository self-describing: the full design and the reasoning
behind every change live here, so any Claude Code session (or collaborator) can work
from the repo alone without external context.

**Resuming the project / new chat? Read `PROJECT_STATE.md` FIRST.** It is the canonical
current-state and resume point.

**Full read order:**

1. `PROJECT_STATE.md` — where the project stands now, what's verified, what's open, next action.
2. `RESEARCH_DESIGN.md` — the locked study design (task, unit, windows, target, evaluation).
3. `DECISIONS.md` — chronological decision + deviation log (the "why"), incl. the re-scope, the
   coordinate-bug correction, and the M3b ablation confound. **Read before changing anything.**
4. `DATA_SOURCES.md` — every dataset, how to get it, and the `POINT_X`/`POINT_Y` coordinate gotcha.
5. `FEATURE_CATALOG.md` — feature groups, implementation status, and both temporal-validity walls.
6. `ROADMAP.md` — milestone sequence and current status.

**Ground truth for runtime constants is `../configs/config.yaml`.** If a value here and in
config disagree, config wins and this doc should be corrected.

**Integrity:** `../reports/DEVIATIONS.md` is the formal deviations record for the paper;
`DECISIONS.md` here is the fuller narrative. Keep them consistent.
