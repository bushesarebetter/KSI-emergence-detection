/**
 * Every user-facing string, in two registers.
 *
 * Two audiences pull in opposite directions. Traffic engineers, Caltrans staff
 * and SafeTREC researchers say "KSI", "recall@K" and "out-of-fold" natively, and
 * a tool that avoids those words reads to them as unserious. Everyone else
 * bounces off them.
 *
 * So the vocabulary lives here rather than scattered through components, and
 * the whole interface switches register together. Plain is the default: a
 * first-time visitor should never have to decode an acronym. Technical restores
 * the precise terms.
 *
 * Rules for editing:
 *   - Plain wording must stay accurate as well as simple. "Serious crash" is a
 *     fair rendering of KSI. "Dangerous intersection" is not, because the model
 *     predicts outcomes, not hazard.
 *   - The two registers state the same facts in different words.
 *   - No em dashes, no "not X, Y" contrasts, no lists of three for rhythm.
 */

import { CITY } from "../city.js";

const PLAIN = {
  appName: CITY.siteTitle,
  tagline: "Where serious crashes are likely to happen next",

  // Header
  aboutButton: "How this works",
  aboutTitle: "What am I looking at?",

  // Filter
  filterTitle: "Shortlist size",
  filterUnit: "intersections shown",
  catchTitle: "How well it has worked",

  // Search
  searchPlaceholder: "Search for an intersection",
  searchEmpty: "No intersection matches that.",
  searchHint: "Try one street name, like El Cajon.",

  // Detail panel
  detailOf: (n) => `of ${n} intersections`,
  detailHistory: "Crashes recorded here",
  detailExposure: "How busy it is, and how often crashes happen",
  detailExposureNote: "City traffic counts, and the crash record for 2016 to 2024",
  detailNearby: "Other corners on this list nearby",
  detailCase: "The case for fixing it",
  detailCaseNote: "How close it is to the City's own review, and what a fix would cost",
  detailAdvice: "If you use this corner",
  detailAdviceNote: "What the record shows, and what to do about it",
  detailSignals: "Why the model ranked it here",
  detailSignalsNote: "Everything the model knew as of January 2025",
  detailStreetView: "Look at this intersection",
  detailCrashActive: "Has recent crashes",
  detailCrashSilent: "No recent crashes",
  detailEmergent: "Serious crash in 2025",
  detailNoAdvice: "Nothing in this corner's top signals names a crash type or a hazard you can act on; the model listed it for the road it sits on and what is around it. Slow down and leave more room than you would elsewhere.",

  // Map
  mapHint: "Tap a dot for details",
};

const ADVANCED = {
  appName: "KSI Emergence",
  tagline: `${CITY.name}, forward run 2025 to 2027`,

  aboutButton: "Methodology",
  aboutTitle: "Methodology",

  filterTitle: "Top N",
  filterUnit: "K",
  catchTitle: "Recall @ K",

  searchPlaceholder: "Search intersection",
  searchEmpty: "No match.",
  searchHint: "Substring match on intersection_name",

  detailOf: (n) => `of ${n}`,
  detailHistory: "Crash history (2016 to 2025)",
  detailExposure: "Exposure and crash rate",
  detailExposureNote: "City ADT counts; rate = crashes/yr ÷ (entering ADT × 365 / 10⁶)",
  detailNearby: "Nearby listed sites",
  detailCase: "Countermeasures and cost",
  detailCaseNote: "Distance to the City screen (5 injury crashes/yr); FHWA PSC measures with rough installed cost",
  detailAdvice: "Countermeasure prompts",
  detailAdviceNote: "Crash-type features present in the record, with the standard road-user countermeasure",
  detailSignals: "Model signals",
  detailSignalsNote: "All values as of Jan 1, 2025 (training cutoff)",
  detailStreetView: "Street View",
  detailCrashActive: "Crash active",
  detailCrashSilent: "Crash silent",
  detailEmergent: "2025 KSI positive",
  detailNoAdvice: "No actionable feature in the top signals; structural and recency features only.",

  mapHint: "Click a dot for details",
};

export function copyFor(advanced) {
  return advanced ? ADVANCED : PLAIN;
}
