/**
 * Every user-facing string, in two registers.
 *
 * The dashboard has two audiences that pull in opposite directions. Traffic
 * engineers, Caltrans staff and SafeTREC researchers speak "KSI", "recall@K" and
 * "out-of-fold" natively, and a tool that avoids those words reads to them as
 * unserious. Everyone else bounces off them entirely.
 *
 * So the vocabulary lives here rather than being scattered through components,
 * and the whole interface switches register together. Plain is the default,
 * because a first-time visitor should never have to decode an acronym to
 * understand what they are looking at; Advanced restores the precise terms.
 *
 * Rules for editing:
 *   - Plain wording must stay *accurate*, not just simple. "Serious crash" is a
 *     fair rendering of KSI; "dangerous intersection" would not be, because the
 *     model predicts outcomes, not hazard.
 *   - Never let the two registers state different facts. Same claim, different
 *     words.
 */

const PLAIN = {
  appName: "San Diego Intersection Risk",
  tagline: "Where serious crashes are likely to happen next",

  // Header
  aboutButton: "How this works",
  aboutTitle: "What am I looking at?",

  // Stats
  statWindow: "Predicting",
  statShown: "Intersections shown",
  statEmergent: "Had a serious crash in 2025",
  statTopDistrict: "Most sites in",

  // Filter
  filterTitle: "How many to show",
  filterOption: (n) => `Top ${n}`,
  catchTitle: "Flagged in advance",
  catchDetail: (caught, total, k) =>
    `Of the ${total} intersections that had a serious crash in 2025, this list of ${k} flagged ${caught} beforehand.`,

  // Legend
  legendTitle: "Predicted risk",
  legendTiers: ["Highest risk", "High risk", "Elevated risk", "Moderate risk"],
  legendRange: (range) => `Ranked ${range} on the list`,
  legendCaught: "Had a serious crash in 2025",
  legendCaughtSub: "this list flagged it in advance",
  legendMissed: "Had a serious crash in 2025",
  legendMissedSub: "this list did not flag it",
  legendSize: "Bigger dot = higher risk",

  // Search
  searchPlaceholder: "Search for an intersection…",
  searchEmpty: "No intersection matches that.",
  searchHint: "Try a street name, e.g. “El Cajon”",

  // Detail panel
  detailOf: (n) => `of ${n} intersections`,
  detailHistory: "Crashes recorded here",
  detailSignals: "Why the model ranked it here",
  detailSignalsNote: "Everything the model knew as of January 2025",
  detailStreetView: "Look at this intersection",
  detailCrashActive: "Has recent crashes",
  detailCrashSilent: "No recent crashes",
  detailEmergent: "Serious crash in 2025",

  // Map
  mapHint: "Tap a dot for details",
};

const ADVANCED = {
  appName: "KSI Emergence",
  tagline: "San Diego · forward run 2025–2027",

  aboutButton: "Methodology",
  aboutTitle: "Methodology",

  statWindow: "Window",
  statShown: "Sites shown",
  statEmergent: "Emergent (≥1 KSI)",
  statTopDistrict: "Top district",

  filterTitle: "Top N sites",
  filterOption: (n) => `Top ${n}`,
  catchTitle: "Recall@K",
  catchDetail: (caught, total, k) =>
    `${caught} of ${total} 2025 KSI positives caught at K=${k} (forward run, ≥1 KSI).`,

  legendTitle: "Predicted risk",
  legendTiers: ["Highest risk", "High risk", "Elevated risk", "Moderate risk"],
  legendRange: (range) => `Rank ${range}`,
  legendCaught: "2025 KSI, caught",
  legendCaughtSub: (k) => `top-${k} hit`,
  legendMissed: "2025 KSI, not yet caught",
  legendMissedSub: (k) => `outside top-${k}`,
  legendSize: "Dot size ∝ rank tier",

  searchPlaceholder: "Search intersection…",
  searchEmpty: "No match.",
  searchHint: "Substring match on intersection_name",

  detailOf: (n) => `of ${n}`,
  detailHistory: "Crash history (2016–2025)",
  detailSignals: "Model signals",
  detailSignalsNote: "All values measured as of Jan 1, 2025 (training cutoff)",
  detailStreetView: "Street View",
  detailCrashActive: "Crash active",
  detailCrashSilent: "Crash silent",
  detailEmergent: "2025 KSI positive",

  mapHint: "Click a dot for details",
};

export function copyFor(advanced) {
  return advanced ? ADVANCED : PLAIN;
}
