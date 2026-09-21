import { inspectionStats, themeCounts, typeLabel } from "./inspections.js";
import { SITE } from "../site.js";

const today = () => new Date().toISOString().slice(0, 10);

/** A citation for one place, for a story, a letter or a paper. */
export function citation({ feature, candidates, url }) {
  const p = feature.properties;
  const year = new Date().getFullYear();
  return `${SITE.citationAuthors} (${year}). ${SITE.siteTitle}: ${p.name}, ${p.address}, rank ${p.rank} of ${Number(candidates).toLocaleString()} candidate food facilities. ${url}. Retrieved ${today()}.`;
}

/**
 * The record as plain text, to paste into an email or a note. It states what
 * the County recorded and where the reader can check it, and nothing more.
 */
export function recordText({ feature, candidates, url }) {
  const p = feature.properties;
  const s = inspectionStats(p);
  const themes = themeCounts(p.violations).slice(0, 4);
  const lines = [
    `${p.name}`,
    `${p.address}`,
    `${typeLabel(p.facility_type)}${p.risk_category ? `, risk category ${p.risk_category}` : ""}${p.council_district ? `, council district ${p.council_district}` : ""}`,
    "",
    `Ranked ${p.rank} of ${Number(candidates).toLocaleString()} ${SITE.name} food facilities by how likely ${SITE.regulator.short}'s next routine inspection is to find a major violation (${SITE.siteTitle}, independent student research).`,
    "",
  ];
  if (s) {
    lines.push(`Last inspection: ${s.last.date}, ${s.last.type ?? "routine"}, score ${s.lastScore ?? "n/a"}${s.lastGrade ? ` (grade ${s.lastGrade})` : ""}.`);
    lines.push(`Last three years: ${s.majors36} major and ${s.minors36} minor violations across ${s.count} visits; ${s.reinspections} reinspections; closed ${s.closures} ${s.closures === 1 ? "time" : "times"}.`);
  }
  if (themes.length) {
    lines.push("Findings by theme:");
    for (const t of themes) lines.push(`  ${t.label}: ${t.count} ${t.count === 1 ? "finding" : "findings"}${t.major ? `, ${t.major} major` : ""}, latest ${t.last}`);
  }
  lines.push("");
  lines.push(`The County's own record: ${SITE.regulator.resultsUrl}`);
  lines.push(`This page: ${url}`);
  return lines.join("\n");
}
