import { crashRate, fmtPerYear, roundVehicles } from "./rates.js";
import { adviceFor } from "./advice.js";
import { measuresFor, fmtRange, screenGap, CITY_SCREEN } from "./countermeasures.js";
import { CANDIDATE_COUNT } from "../constants.js";
import { CITY } from "../city.js";

/**
 * A message a resident can send to their council office about one corner.
 * Plain text, addressed from "I", with the record first and the ask last. It
 * quotes only what the map shows for that corner; the sender fills in a name.
 */
export function councilMessage({ feature, traffic = null, police = null, control = null, candidates = CANDIDATE_COUNT, url }) {
  const p = feature.properties;
  const rate = crashRate(p.crash_history);
  const gap = screenGap(p.crash_history);
  const measures = measuresFor(p, control);
  const advice = adviceFor(p, { control });

  const lines = [];
  lines.push(`Subject: ${p.intersection_name}, District ${p.council_district}`);
  lines.push("");
  lines.push("Hello,");
  lines.push("");
  lines.push(
    `I use the intersection at ${p.intersection_name}. It is number ${p.rank} of ${candidates.toLocaleString()} ` +
    `${CITY.name} intersections on an independent ranking of the corners most likely to see a serious crash next: ${url}`
  );
  lines.push("");
  lines.push("What the record shows:");
  if (rate) {
    lines.push(`- ${fmtPerYear(rate.perYear)} crashes a year from 2016 to 2024, ${rate.trend}${rate.injuries ? `; ${rate.injuries} of ${rate.total} hurt someone` : ""}.`);
  }
  for (const it of advice.slice(0, 2)) lines.push(`- ${it.fact}`);
  if (traffic) {
    lines.push(`- About ${roundVehicles(traffic.entering).toLocaleString()} vehicles a day${traffic.complete ? "" : " on the counted street alone"} (City traffic counts).`);
  }
  if (police) {
    lines.push(`- Police have logged ${police.count} ${police.count === 1 ? "crash" : "crashes"} here since January 2025, ${police.injured + police.killed} people hurt.`);
  }
  if (gap) {
    lines.push(
      gap.gap === 0
        ? `- In ${gap.year} it met the City's own review threshold of ${CITY_SCREEN} injury crashes in a year.`
        : `- In ${gap.year} it was ${gap.gap} injury ${gap.gap === 1 ? "crash" : "crashes"} short of the ${CITY_SCREEN} that trigger the City's own review.`
    );
  }
  lines.push("");
  lines.push("What could be done (FHWA proven countermeasures, rough cost):");
  for (const m of measures) {
    lines.push(`- ${m.name}: ${fmtRange(m.cost, m.per)}${m.reduction ? `. ${m.reduction}.` : "."}`);
  }
  lines.push("");
  lines.push(
    `I am asking your office to request an engineering review of this corner from ${CITY.transportationDept} ` +
    "before it reaches the review threshold, and to put it forward for the next Highway Safety Improvement Program " +
    "or Safe Streets and Roads for All application."
  );
  lines.push("");
  lines.push("Thank you,");
  lines.push("[Your name]");
  lines.push("[Your street or neighborhood]");
  return lines.join("\n");
}

/** How to cite one corner, for a memo, a grant application or a news story. */
export function citation({ feature, candidates = CANDIDATE_COUNT, url }) {
  const p = feature.properties;
  const today = new Date();
  const date = today.toISOString().slice(0, 10);
  return `${CITY.citationAuthors} (${today.getFullYear()}). ${CITY.siteTitle}: ${p.intersection_name}, ` +
    `rank ${p.rank} of ${candidates.toLocaleString()} candidate intersections. ${url}. Retrieved ${date}.`;
}

/** A district-level version for the printable report. */
export function districtMessage({ district, listed, top100, gapCount, costLo, costHi, url }) {
  return [
    `Subject: ${listed} corners in District ${district} the City's review cannot see yet`,
    "",
    "Hello,",
    "",
    `An independent ranking of ${CITY.name} intersections lists ${listed} corners in ${CITY.districts.short} ${district} among the 800 ` +
    `most likely to see a serious crash next, ${top100} of them in the top 100. ${gapCount} of them are within one injury ` +
    `crash of the five-crash threshold that triggers the City's own review. The list, with each corner's crash record, ` +
    `traffic and suggested fix, is at ${url}`,
    "",
    `Low-cost fixes for the district's top ten (FHWA proven countermeasures) add up to roughly ${costLo} to ${costHi}, ` +
    "less than the societal cost of one serious-injury crash.",
    "",
    `I am asking your office to request an engineering review of the top ten from ${CITY.transportationDept}, and ` +
    "to include them in the City's next Highway Safety Improvement Program or Safe Streets and Roads for All application.",
    "",
    "Thank you,",
    "[Your name]",
    "[Your street or neighborhood]",
  ].join("\n");
}
