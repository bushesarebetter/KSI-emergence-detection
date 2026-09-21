import { patternKeys, FILTER_PATTERNS } from "./advice.js";
import { TYPE_LABELS } from "./inspections.js";

/**
 * One place to decide whether a facility is shown. The map, the table and
 * the search all call this so they never disagree.
 *
 * filters: { threshold, districts: number[], types: string[], pattern: string|null }
 */
export function passesFilters(p, filters) {
  if (!p) return false;
  if (p.rank > filters.threshold) return false;
  if (filters.districts?.length && !filters.districts.includes(p.council_district)) return false;
  if (filters.types?.length && !filters.types.includes(p.facility_type ?? "other")) return false;
  if (filters.pattern && !patternKeys(p).includes(filters.pattern)) return false;
  return true;
}

/** The pattern chips worth showing: only patterns some listed place has. */
export function chipsFor(fc, threshold = Infinity) {
  if (!fc?.features) return [];
  const present = new Set();
  for (const f of fc.features) {
    if (f.properties.rank > threshold) continue;
    for (const k of patternKeys(f.properties)) present.add(k);
  }
  return Object.entries(FILTER_PATTERNS)
    .filter(([key]) => present.has(key))
    .map(([key, label]) => ({ key, label }));
}

/** The facility types present in the export, most common first. */
export function typesFor(fc, threshold = Infinity) {
  if (!fc?.features) return [];
  const counts = {};
  for (const f of fc.features) {
    if (f.properties.rank > threshold) continue;
    const t = f.properties.facility_type ?? "other";
    counts[t] = (counts[t] || 0) + 1;
  }
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([key, count]) => ({ key, label: TYPE_LABELS[key] ?? TYPE_LABELS.other, count }));
}
