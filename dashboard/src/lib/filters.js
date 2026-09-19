import { patternKeys, FILTER_PATTERNS } from "./advice";
import { crashRate } from "./rates";

/** The chips in the sidebar: the crash types, plus corners whose rate is rising. */
export const FILTER_CHIPS = [...FILTER_PATTERNS, { key: "rising", label: "Rising" }];

/**
 * One definition of "shown", shared by the map, the table and the district
 * counts, so the three never disagree about which corners are on screen.
 * filters: { threshold, districts: [], pattern: null | "left" | "night" | "bike" | "ped" }
 */
export function passesFilters(p, filters) {
  if (p.rank > filters.threshold) return false;
  if (filters.districts?.length && !filters.districts.includes(p.council_district)) return false;
  if (filters.pattern === "rising") return crashRate(p.crash_history)?.trend === "rising";
  if (filters.pattern && !patternKeys(p).has(filters.pattern)) return false;
  return true;
}
