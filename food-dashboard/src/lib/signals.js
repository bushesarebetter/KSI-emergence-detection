/**
 * Turn a model feature label into a sentence a diner can read.
 *
 * The export writes each place's top signals as `display_label` strings in a
 * fixed vocabulary (docs/DATA_CONTRACT.md). Technical mode shows them as
 * written; plain mode rewrites them here. Rewrites stay faithful: "Cited 3
 * times for food temperatures" is what the record says. "This kitchen is
 * unsafe" is not, and never appears. Unmatched labels fall through unchanged.
 */
import { THEMES, TYPE_LABELS } from "./inspections.js";

const PER_YEAR = { 1: "once a year", 2: "twice a year", 3: "three times a year" };

const RULES = [
  { test: /^last routine score (\d+)/i, render: (m) => `Scored ${m[1]} at the last routine inspection` },
  { test: /^grade ([abc]) at last inspection/i, render: (m) => `Grade ${m[1].toUpperCase()} after the last inspection` },
  {
    test: /^(\d+) major violations? in the last (\d+) inspections?/i,
    render: (m) => `${m[1]} major ${m[1] === "1" ? "violation" : "violations"} across the last ${m[2]} inspections`,
  },
  {
    test: /^(temperature|handwashing|vermin|sanitizing|storage|hygiene|equipment|plumbing|labeling|other) cited (\d+) times?/i,
    render: (m) => `Cited ${m[2] === "1" ? "once" : `${m[2]} times`} for ${THEMES[m[1].toLowerCase()].toLowerCase()}`,
  },
  { test: /^closed by the county (\d{4})/i, render: (m) => `Closed by the County in ${m[1]} for an imminent health hazard` },
  { test: /^reinspection required (\d+) times?/i, render: (m) => `Needed a reinspection ${m[1] === "1" ? "once" : `${m[1]} times`}` },
  { test: /^risk category (\d)/i, render: (m) => `Risk category ${m[1]}, inspected ${PER_YEAR[m[1]] ?? "on the County's schedule"}` },
  { test: /^facility type: (\w+)/i, render: (m) => `A ${(TYPE_LABELS[m[1].toLowerCase()] ?? "food facility").toLowerCase()}` },
  { test: /^score (falling|rising): (\d+) to (\d+)/i, render: (m) => `Score ${m[1]} from ${m[2]} to ${m[3]} over recent inspections` },
  { test: /^(\d+) months? since last inspection/i, render: (m) => `${m[1]} ${m[1] === "1" ? "month" : "months"} since the last inspection` },
  { test: /^(\d+) complaints? in (\d+) years?/i, render: (m) => `${m[1]} ${m[1] === "1" ? "complaint" : "complaints"} to the County in ${m[2]} ${m[2] === "1" ? "year" : "years"}` },
  { test: /^neighbou?rs' average score (\d+)/i, render: (m) => `Nearby places average a score of ${m[1]}` },
  { test: /^change of ownership (\d{4})/i, render: (m) => `Changed hands in ${m[1]}` },
  { test: /^(\d+) seats/i, render: (m) => `About ${m[1]} seats` },
];

export function humanizeSignal(label) {
  if (!label) return "";
  for (const r of RULES) {
    const m = r.test.exec(label);
    if (m) return r.render(m);
  }
  return label;
}

/** The label as the export wrote it. */
export const techLabel = (label) => String(label ?? "");

/** Whether a label is one the rewrites know. The export check counts these. */
export function knownLabel(label) {
  return RULES.some((r) => r.test.test(label ?? ""));
}
