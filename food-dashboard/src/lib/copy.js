/**
 * Every user-facing string, in two registers: plain for diners and reporters,
 * technical for environmental-health staff and researchers. The two say the
 * same facts in different words. Plain is the default.
 *
 * Rules: plain wording stays accurate ("major violation" is the County's own
 * term and is kept); no em dashes; no "not X, Y" contrasts.
 */
import { SITE } from "../site.js";

const PLAIN = {
  appName: SITE.siteTitle,
  tagline: "The places most likely to fail their next inspection",

  aboutButton: "How this works",

  filterTitle: "Shortlist size",
  filterUnit: "places shown",
  typeTitle: "Kind of place",
  patternTitle: "What inspectors found",
  patternUnit: "in the record",
  catchTitle: "How well it has worked",

  searchPlaceholder: "Search for a restaurant or market",
  searchEmpty: "No place matches that.",
  searchHint: SITE.searchHint,

  detailOf: (n) => `of ${n} places`,
  detailHistory: "Inspection scores",
  detailHistoryNote: "Routine inspections and reinspections, oldest to newest",
  detailFindings: "What inspectors found",
  detailFindingsNote: "Violations cited in the last three years, by theme",
  detailAdvice: "If you eat here",
  detailAdviceNote: "What the record shows, and what to look for yourself",
  detailNoAdvice: "Nothing in this place's record names a finding you can check for at the table; the model listed it for the kind of place it is and the pattern of its scores. Look for the posted grade card.",
  detailSignals: "Why the model ranked it here",
  detailSignalsNote: "Everything the model knew at the export date",
  detailNearby: "Other places on this list nearby",
  detailStreetView: "Look at this place",
  detailRecord: "The County's record",

  mapHint: "Tap a dot for details",
};

const ADVANCED = {
  appName: "Inspection Risk",
  tagline: `${SITE.name}, forward run`,

  aboutButton: "Methodology",

  filterTitle: "Top N",
  filterUnit: "K",
  typeTitle: "Facility type",
  patternTitle: "Violation theme",
  patternUnit: "present in record or signals",
  catchTitle: "Recall @ K",

  searchPlaceholder: "Search facility",
  searchEmpty: "No match.",
  searchHint: "Word match on name and address",

  detailOf: (n) => `of ${n}`,
  detailHistory: "Inspection history",
  detailHistoryNote: "Score by visit; reinspections and complaint visits marked",
  detailFindings: "Violations by theme",
  detailFindingsNote: "CalCode citations, last 36 months, grouped",
  detailAdvice: "Customer checks",
  detailAdviceNote: "Themes present in the record, with the standard customer-side check",
  detailNoAdvice: "No actionable theme in the record; structural and score-pattern features only.",
  detailSignals: "Model signals",
  detailSignalsNote: "Top SHAP features at the export date",
  detailNearby: "Nearby listed facilities",
  detailStreetView: "Street View",
  detailRecord: "DEHQ record",

  mapHint: "Click a dot for details",
};

export function copyFor(advanced) {
  return advanced ? ADVANCED : PLAIN;
}
