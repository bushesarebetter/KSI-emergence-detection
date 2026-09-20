import { patternKeys, FILTER_PATTERNS } from "./advice.js";
import { crashRate } from "./rates.js";

/**
 * One definition of "shown", shared by the map, the table and the district
 * counts, so the three never disagree about which corners are on screen.
 * filters: { threshold, districts: [], pattern: null | <pattern key> | "rising" }
 */
export function passesFilters(p, filters) {
  if (p.rank > filters.threshold) return false;
  if (filters.districts?.length && !filters.districts.includes(p.council_district)) return false;
  if (filters.pattern === "rising") return crashRate(p.crash_history)?.trend === "rising";
  if (filters.pattern && !patternKeys(p).has(filters.pattern)) return false;
  return true;
}

/**
 * The chips to offer for an export: the patterns that actually occur in it,
 * plus "Rising", which comes from the crash history rather than the signals.
 * A chip that would select nothing is not offered.
 */
export function chipsFor(intersections) {
  const features = intersections?.features ?? [];
  const counts = {};
  let rising = 0;
  for (const f of features) {
    for (const k of patternKeys(f.properties)) counts[k] = (counts[k] || 0) + 1;
    if (crashRate(f.properties.crash_history)?.trend === "rising") rising += 1;
  }
  const chips = FILTER_PATTERNS.filter(({ key }) => counts[key] > 0);
  if (rising > 0) chips.push({ key: "rising", label: "Rising" });
  return chips;
}
