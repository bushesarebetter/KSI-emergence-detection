/**
 * What a facility's inspection record says, computed once from the export.
 *
 * The export carries each place's routine inspections, reinspections and
 * complaint visits for the last five years (`inspections`, oldest first) and
 * the violations cited in the last three (`violations`). Everything the
 * interface states about a record is derived here so a number on the panel,
 * in the table and in the CSV is the same number.
 */
export const THEMES = {
  temperature: "Food temperatures",
  handwashing: "Hand washing",
  vermin: "Pests",
  sanitizing: "Cleaning and sanitizing",
  storage: "Food storage",
  hygiene: "Employee hygiene",
  equipment: "Equipment",
  plumbing: "Plumbing and water",
  labeling: "Labels and records",
  other: "Other",
};

export const TYPE_LABELS = {
  restaurant: "Restaurant",
  market: "Market",
  mobile: "Food truck or cart",
  bar: "Bar",
  school: "School kitchen",
  bakery: "Bakery",
  caterer: "Caterer",
  other: "Food facility",
};

export function gradeFor(score) {
  if (score == null) return null;
  return score >= 90 ? "A" : score >= 80 ? "B" : "C";
}

const MS_MONTH = 30.44 * 24 * 3600 * 1000;
const monthsBetween = (a, b) => (new Date(b) - new Date(a)) / MS_MONTH;
const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);

export function lastInspection(p) {
  if (p?.last_inspection) return p.last_inspection;
  const list = p?.inspections ?? [];
  return list.length ? list[list.length - 1] : null;
}

/**
 * The record in numbers. `months` windows count back from the last
 * inspection on record, not from today, so a stale export does not make every
 * place look clean.
 */
export function inspectionStats(p) {
  const list = (p?.inspections ?? []).filter((i) => i?.date);
  const last = lastInspection(p);
  if (!last) return null;
  const routine = list.filter((i) => (i.type ?? "routine") === "routine");
  const recent36 = list.filter((i) => monthsBetween(i.date, last.date) <= 36);
  const majors36 = recent36.reduce((a, i) => a + (i.major || 0), 0);
  const minors36 = recent36.reduce((a, i) => a + (i.minor || 0), 0);
  const closures = list.filter((i) => i.closed).length;
  const reinspections = list.filter((i) => i.type === "reinspection").length;
  const routineScores = routine.map((i) => i.score).filter((s) => typeof s === "number");
  const lastRoutine = routine.length ? routine[routine.length - 1] : null;
  const earlier = routineScores.slice(0, -1);
  let trend = "steady";
  if (lastRoutine && earlier.length >= 2 && typeof lastRoutine.score === "number") {
    const base = mean(earlier);
    if (lastRoutine.score <= base - 5) trend = "worsening";
    else if (lastRoutine.score >= base + 5) trend = "improving";
  }
  return {
    count: list.length,
    routineCount: routine.length,
    last,
    lastScore: typeof last.score === "number" ? last.score : null,
    lastGrade: last.grade ?? gradeFor(last.score),
    majors36,
    minors36,
    closures,
    reinspections,
    meanScore: mean(routineScores),
    trend,
  };
}

/** Violations grouped by theme, worst first: majors, then count, then recency. */
export function themeCounts(violations = []) {
  const by = new Map();
  for (const v of violations) {
    const key = THEMES[v.theme] ? v.theme : "other";
    const t = by.get(key) ?? { theme: key, label: THEMES[key], count: 0, major: 0, last: null };
    t.count += 1;
    if (v.severity === "major") t.major += 1;
    if (!t.last || v.date > t.last) t.last = v.date;
    by.set(key, t);
  }
  return [...by.values()].sort((a, b) => b.major - a.major || b.count - a.count || (b.last ?? "").localeCompare(a.last ?? ""));
}

export function fmtScore(score) {
  return score == null ? "" : String(Math.round(score));
}

export const typeLabel = (type) => TYPE_LABELS[type] ?? TYPE_LABELS.other;
