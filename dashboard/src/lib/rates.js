/**
 * Crash rate and trend for one site, from its year-by-year crash history, and
 * the traffic-normalised rate where a City traffic count exists.
 *
 * The export's crash_history runs 2016 through 2025, with 2025 a partial year
 * that the model never saw, so rates use the nine full years 2016 to 2024.
 * "Recent" is the last three of those (2022 to 2024) against the six before.
 * A rate per million entering vehicles is the standard way to compare a busy
 * arterial with a quiet street; the raw count alone rewards the quiet one.
 */

const FIRST_YEAR = 2016;
const LAST_FULL_YEAR = 2024;
const RECENT_FROM = 2022;

const total = (h) => (h.pdo || 0) + (h.injury || 0) + (h.ksi || 0);
const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);

export function crashRate(history) {
  const full = (history ?? []).filter((h) => h.year >= FIRST_YEAR && h.year <= LAST_FULL_YEAR);
  if (!full.length) return null;

  const counts = full.map(total);
  const recent = full.filter((h) => h.year >= RECENT_FROM).map(total);
  const earlier = full.filter((h) => h.year < RECENT_FROM).map(total);
  const recentPerYear = mean(recent);
  const earlierPerYear = mean(earlier);

  // A trend needs both a ratio and an absolute change: 0.3 to 0.7 a year is
  // noise at this scale, 2 to 4 is not.
  let trend = "steady";
  if (recentPerYear >= earlierPerYear * 1.5 && recentPerYear - earlierPerYear >= 1) trend = "rising";
  else if (recentPerYear <= earlierPerYear * 0.5 && earlierPerYear - recentPerYear >= 1) trend = "falling";

  return {
    years: full.length,
    total: counts.reduce((a, b) => a + b, 0),
    injuries: full.reduce((a, h) => a + (h.injury || 0) + (h.ksi || 0), 0),
    perYear: mean(counts),
    recentPerYear,
    earlierPerYear,
    trend,
  };
}

/** Crashes per million vehicles entering, or null without a traffic figure. */
export function ratePerMillionEntering(perYear, enteringDaily) {
  if (!enteringDaily || !(perYear >= 0)) return null;
  return perYear / ((enteringDaily * 365) / 1e6);
}

/** "37,000" style rounding for a daily vehicle count: two significant figures. */
export function roundVehicles(n) {
  if (!n) return 0;
  const digits = Math.floor(Math.log10(n));
  const unit = Math.pow(10, Math.max(0, digits - 1));
  return Math.round(n / unit) * unit;
}

export function fmtPerYear(x) {
  if (x == null) return "";
  return x >= 10 ? Math.round(x).toString() : x.toFixed(1);
}

export const TREND_WORD = { rising: "rising", steady: "steady", falling: "falling" };
