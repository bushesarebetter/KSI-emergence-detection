import { crashRate } from "./rates.js";
import { patternOf } from "./advice.js";
import { pointKey } from "./geo.js";
import { screenGap } from "./countermeasures.js";

export function formatPercentile(p) {
  const fixed = Number.isInteger(p) ? p : parseFloat(p.toFixed(1));
  const str = fixed % 1 === 0 ? String(Math.round(fixed)) : fixed.toFixed(1);
  const n = Math.round(fixed);
  if (n % 100 >= 11 && n % 100 <= 13) return `${str}th`;
  switch (n % 10) {
    case 1: return `${str}st`;
    case 2: return `${str}nd`;
    case 3: return `${str}rd`;
    default: return `${str}th`;
  }
}

export function formatDistrict(d) {
  return `District ${d}`;
}

export function formatScore(s) {
  return parseFloat(s).toFixed(2);
}

const cell = (v) => {
  const s = v == null ? "" : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

/**
 * The full export as CSV, with the derived columns a spreadsheet user would
 * otherwise have to recompute: crashes a year and trend from the history,
 * vehicles a day from the City counts, and the lead crash pattern.
 */
export function intersectionsToCsv(features, ctx = {}) {
  // Accept the older call shape, intersectionsToCsv(features, traffic).
  const { traffic = null, recent = null, control = null } = ctx && ctx.sites ? { traffic: ctx } : ctx;
  const header = [
    "rank", "intersection_name", "council_district", "percentile", "crashes_training",
    "crashes_per_year_2016_2024", "trend", "vehicles_per_day", "traffic_complete", "pattern",
    "control", "near_school", "near_school_m", "police_since_cutoff", "police_people_hurt",
    "injury_crashes_2024", "injury_gap_to_city_screen_2024",
    "injury_crashes_per_year_2016_2024", "pdo_2020_2024", "injury_2020_2024", "ksi_2020_2024",
    "top_signal", "is_crash_active", "is_known_emergent", "lon", "lat",
  ].join(",");
  const rows = features.map((f) => {
    const p = f.properties;
    const rate = crashRate(p.crash_history);
    const k = pointKey(f);
    const t = traffic?.sites?.[k] ?? null;
    const police = recent?.sites?.[k] ?? null;
    const ctrl = control?.sites?.[k]?.control ?? "";
    const gap = screenGap(p.crash_history);
    const recent5 = (p.crash_history ?? []).filter((h) => h.year >= 2020 && h.year <= 2024);
    const sum = (k) => recent5.reduce((a, h) => a + (h[k] || 0), 0);
    const [lon, lat] = f.geometry.coordinates;
    return [
      p.rank, p.intersection_name, p.council_district, p.percentile, p.crashes_training,
      rate ? rate.perYear.toFixed(2) : "", rate?.trend ?? "", t?.entering ?? "", t ? t.complete : "",
      patternOf(p) ?? "", ctrl, p.near_school?.name ?? "", p.near_school?.meters ?? "",
      police?.count ?? "", police ? police.injured + police.killed : "",
      gap?.injuryCrashes ?? "", gap?.gap ?? "",
      rate ? rate.injuryPerYear.toFixed(2) : "", sum("pdo"), sum("injury"), sum("ksi"),
      p.shap_features?.[0]?.display_label ?? "", p.is_crash_active,
      p.is_known_emergent, lon, lat,
    ].map(cell).join(",");
  });
  return [header, ...rows].join("\n");
}
