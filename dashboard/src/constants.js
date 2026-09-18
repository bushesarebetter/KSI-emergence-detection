/**
 * Shared constants. Lives in its own module so that Landing.jsx and App.jsx
 * do not import from each other -- App renders Landing, so Landing importing
 * back from App is a circular dependency, harmless at runtime here but a trap
 * for the next person who adds a top-level read.
 */

// Top-500 is the K the README leads with and the one the outreach emails quote
// (24 of 108 caught, 22%). Defaulting to it is the only catch-rate lever that
// does not touch the model: same predictions, same data, the headline shortlist.
export const DEFAULT_THRESHOLD = 500;

// Forward-run candidate set: City of San Diego intersections with no KSI history
// through 2024 (results/recall_evaluation.json -> prospective_2025.candidates).
export const CANDIDATE_COUNT = 26045;

export const REPO_URL = "https://github.com/bushesarebetter/KSI-emergence-detection";
