/**
 * Shared constants. Lives in its own module so that Landing.jsx and App.jsx
 * do not import from each other -- App renders Landing, so Landing importing
 * back from App is a circular dependency, harmless at runtime here but a trap
 * for the next person who adds a top-level read.
 */

// The shortlist the interface opens on and the sizes it offers. 800 is the
// size the combined "most unsafe" list is cut at; the other three give a
// reviewer tighter views of the same ranking.
export const DEFAULT_THRESHOLD = 800;
export const THRESHOLDS = [100, 200, 500, 800];

// Forward-run candidate set: City of San Diego intersections with no KSI history
// through 2024 (results/recall_evaluation.json -> prospective_2025.candidates).
export const CANDIDATE_COUNT = 26045;

export const REPO_URL = "https://github.com/bushesarebetter/KSI-emergence-detection";

// Used only when /data/meta.json is absent (an export older than the meta file).
// Forward run, >=1 KSI, 108 positives, computed from the exported top-1000.
export const CATCH_FALLBACK = {
  50: { caught: 2, total: 108 },
  100: { caught: 3, total: 108 },
  200: { caught: 9, total: 108 },
  500: { caught: 24, total: 108 },
  800: { caught: 34, total: 108 },
  1000: { caught: 38, total: 108 },
};

/** recall@K divided by what a random shortlist of K would score. */
export function liftOverRandom(caught, total, k, candidates = CANDIDATE_COUNT) {
  if (!total || !k || !candidates) return null;
  return caught / total / (k / candidates);
}
