/**
 * Shared constants, in their own module so that components never import from
 * App.jsx and App.jsx never depends on a component for a number.
 */

// The shortlist the interface opens on and the sizes it offers.
export const DEFAULT_THRESHOLD = 500;
export const THRESHOLDS = [100, 200, 500, 1000];

// Used only when /data/meta.json is absent. Zero, so the interface never
// states a figure that no export backs.
export const CANDIDATE_COUNT = 0;
export const CATCH_FALLBACK = {};

export const REPO_URL = "https://github.com/bushesarebetter/KSI-emergence-detection";

/** recall@K divided by what a random shortlist of K would score. */
export function liftOverRandom(caught, total, k, candidates = CANDIDATE_COUNT) {
  if (!total || !k || !candidates) return null;
  return caught / total / (k / candidates);
}
