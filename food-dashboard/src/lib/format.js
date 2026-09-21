import { inspectionStats, themeCounts, typeLabel } from "./inspections.js";
import { patternOf } from "./advice.js";

export function formatPercentile(p) {
  if (p == null) return "";
  const n = Math.round(p * 10) / 10;
  const suffix = (v) => {
    const i = Math.floor(v);
    if (i % 100 >= 11 && i % 100 <= 13) return "th";
    return ["th", "st", "nd", "rd"][Math.min(i % 10, 4)] ?? "th";
  };
  return `${n}${suffix(n)}`;
}

const cell = (v) => {
  const s = v == null ? "" : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

/**
 * The whole export as a spreadsheet: everything a reporter, a council office
 * or the County's own staff would want to sort by, one row per place.
 */
export function facilitiesToCsv(features) {
  const header = [
    "rank", "facility_id", "name", "address", "facility_type", "risk_category", "council_district", "percentile",
    "last_inspection", "last_type", "last_score", "last_grade", "majors_36mo", "minors_36mo", "closures_5yr",
    "reinspections_5yr", "score_trend", "top_theme", "pattern", "top_signal", "is_known_positive", "lon", "lat",
  ];
  const rows = features.map((f) => {
    const p = f.properties;
    const s = inspectionStats(p);
    const [theme] = themeCounts(p.violations);
    const [lon, lat] = f.geometry.coordinates;
    return [
      p.rank, p.facility_id, p.name, p.address, typeLabel(p.facility_type), p.risk_category ?? "", p.council_district ?? "",
      p.percentile ?? "",
      s?.last?.date ?? "", s?.last?.type ?? "", s?.lastScore ?? "", s?.lastGrade ?? "", s?.majors36 ?? "", s?.minors36 ?? "",
      s?.closures ?? "", s?.reinspections ?? "", s?.trend ?? "", theme?.label ?? "", patternOf(p) ?? "",
      p.shap_features?.[0]?.display_label ?? "", p.is_known_positive ? "true" : "false", lon, lat,
    ].map(cell).join(",");
  });
  return [header.join(","), ...rows].join("\n");
}
