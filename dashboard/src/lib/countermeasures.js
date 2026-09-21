import { patternKeys } from "./advice.js";
import { CITY } from "../city.js";

/**
 * What fixing a corner might involve, and what it might cost.
 *
 * Each measure is one of FHWA's Proven Safety Countermeasures or a standard
 * signal change, with the crash reduction FHWA publishes for it and a rough
 * installed-cost range. Costs are order-of-magnitude figures for a typical
 * urban intersection; a City bid can land outside them, and the page says so.
 * Edit this table, not the components, when a figure changes.
 *
 * `applies` names the crash patterns (advice.js keys) a measure addresses;
 * `needs` restricts it to signalised or unsignalised corners where that matters.
 */
export const FHWA_PSC = "https://highways.dot.gov/safety/proven-safety-countermeasures";
export const CMF_CLEARINGHOUSE = "https://www.cmfclearinghouse.org/";

export const MEASURES = [
  {
    key: "lpi",
    life: 10,
    name: "Leading pedestrian interval",
    what: "The walk signal starts a few seconds before the green, so people are in the crosswalk before cars turn.",
    cost: [1000, 5000],
    reduction: "13% fewer pedestrian crashes",
    applies: ["ped", "school"],
    needs: "signals",
    source: FHWA_PSC,
  },
  {
    key: "rrfb",
    life: 10,
    name: "Rapid-flashing beacon at the crossing",
    what: "Bright yellow lights a walker turns on, at a crossing with no signal.",
    cost: [15000, 40000],
    reduction: "47% fewer pedestrian crashes",
    applies: ["ped"],
    needs: "unsignalised",
    source: FHWA_PSC,
  },
  {
    key: "refuge",
    life: 20,
    name: "Pedestrian refuge island",
    what: "A raised island in the middle so a walker crosses one direction of traffic at a time.",
    cost: [10000, 40000],
    reduction: "56% fewer pedestrian crashes",
    applies: ["ped", "wide", "school"],
    source: FHWA_PSC,
  },
  {
    key: "crosswalk",
    life: 8,
    name: "High-visibility crosswalk and lighting",
    what: "Ladder markings, a crossing light and cut-back parking so drivers see the crossing.",
    cost: [5000, 30000],
    reduction: "Up to 40% fewer pedestrian crashes; lighting alone cuts night pedestrian crashes 42%",
    applies: ["ped", "night", "wide", "school"],
    source: FHWA_PSC,
  },
  {
    key: "protectedLeft",
    life: 10,
    name: "Protected left-turn arrow",
    what: "A green arrow, so a left turn never has to find a gap in oncoming traffic.",
    cost: [10000, 60000],
    reduction: "Large cuts in left-turn crashes; values vary by study",
    applies: ["left"],
    needs: "signals",
    source: CMF_CLEARINGHOUSE,
  },
  {
    key: "turnLane",
    life: 20,
    name: "Dedicated left-turn lane",
    what: "A separate lane, so a car waiting to turn is out of the through traffic and can see what is coming.",
    cost: [20000, 150000],
    reduction: "28% to 48% fewer crashes",
    applies: ["left"],
    source: FHWA_PSC,
  },
  {
    key: "backplates",
    life: 10,
    name: "Signal backplates with reflective borders",
    what: "A dark frame with a yellow edge around each signal head, so it stands out by day and at night.",
    cost: [1000, 5000],
    reduction: "15% fewer crashes",
    applies: ["night", "broadside", "days", "jump", "trend"],
    needs: "signals",
    source: FHWA_PSC,
  },
  {
    key: "yellow",
    life: 10,
    name: "Longer yellow light",
    what: "Retiming the yellow to the actual speed of the road.",
    cost: [500, 2000],
    reduction: "36% to 50% fewer red-light-running crashes",
    applies: ["broadside"],
    needs: "signals",
    source: FHWA_PSC,
  },
  {
    key: "lighting",
    life: 15,
    name: "Intersection lighting",
    what: "Lights aimed at the crossings and the corner itself.",
    cost: [5000, 30000],
    reduction: "42% fewer night pedestrian crashes at intersections",
    applies: ["night"],
    source: FHWA_PSC,
  },
  {
    key: "bike",
    life: 8,
    name: "Bike lane carried through the corner",
    what: "Green markings and a waiting box that put the bike where a turning driver looks.",
    cost: [5000, 25000],
    reduction: "Bike lanes cut bike crashes 30% to 49%",
    applies: ["bike"],
    source: FHWA_PSC,
  },
  {
    key: "roadDiet",
    life: 10,
    name: "Road diet on the approach",
    what: "Four lanes restriped to two plus a turn lane and bike lanes; slower, fewer conflicts.",
    cost: [25000, 200000],
    per: "mile",
    reduction: "19% to 47% fewer crashes",
    applies: ["days", "jump", "trend", "speed", "wide", "cluster"],
    source: FHWA_PSC,
  },
  {
    key: "feedback",
    life: 8,
    name: "Speed feedback sign on the approach",
    what: "A sign that shows each driver their speed as they come to the corner.",
    cost: [5000, 15000],
    reduction: "Slows the approach; a speed-management tool rather than an FHWA proven countermeasure",
    applies: ["speed", "school"],
    source: FHWA_PSC,
  },
  {
    key: "allway",
    life: 10,
    name: "All-way stop or signal warrant study",
    what: "An engineer checks whether the corner now meets the standard for an all-way stop or a signal.",
    cost: [2000, 10000],
    reduction: "",
    applies: ["stop", "complex"],
    needs: "unsignalised",
    source: null,
  },
  {
    key: "roundabout",
    life: 25,
    name: "Roundabout",
    what: "Replaces the signal or stop signs; nobody turns across oncoming traffic.",
    cost: [500000, 3000000],
    reduction: "78% fewer fatal and injury crashes at a signalised corner",
    applies: ["left", "broadside"],
    big: true,
    source: FHWA_PSC,
  },
];

export const REVIEW = {
  key: "review",
  name: "Engineering review",
  what: "A City traffic engineer walks the corner with the crash reports and picks from the measures above.",
  cost: [2000, 8000],
  reduction: "",
  applies: [],
  source: null,
};

// Crash types first, in the order a resident can act on them; tempo patterns
// only bring the general measures.
const PATTERN_ORDER = ["ped", "school", "bike", "left", "night", "broadside", "speed", "wide", "stop", "complex", "days", "jump", "trend", "cluster", "hotspot"];

/**
 * Up to `max` measures for a corner, given its crash patterns and control
 * ("signals" | "stop" | "yield" | "none" | null). Always ends with the
 * engineering review, because that is the ask a council office can act on.
 */
export function measuresFor(props, control = null, { max = 3 } = {}) {
  const keys = patternKeys(props);
  const signalised = control === "signals";
  const unsignalised = control === "stop" || control === "yield" || control === "none";
  const out = [];
  for (const pat of PATTERN_ORDER) {
    if (!keys.has(pat)) continue;
    for (const m of MEASURES) {
      if (out.includes(m) || !m.applies.includes(pat)) continue;
      if (m.needs === "signals" && unsignalised) continue;
      if (m.needs === "unsignalised" && signalised) continue;
      if (m.big) continue; // a roundabout is a plan, not an ask
      out.push(m);
      if (out.length >= max) break;
    }
    if (out.length >= max) break;
  }
  return [...out, REVIEW];
}

/** Sum of the cost ranges of the non-review measures: [low, high]. */
export function costRange(measures) {
  let lo = 0, hi = 0;
  for (const m of measures) {
    if (m.key === "review") continue;
    lo += m.cost[0];
    hi += m.cost[1];
  }
  return [lo, hi];
}

export function fmtMoney(n) {
  if (n >= 1e6) return `$${(n / 1e6).toFixed(n >= 1e7 ? 0 : 1)} million`;
  if (n >= 1000) return `$${Math.round(n / 1000).toLocaleString()},000`;
  return `$${Math.round(n).toLocaleString()}`;
}

export function fmtRange([lo, hi], per) {
  return `${fmtMoney(lo)} to ${fmtMoney(hi)}${per ? ` a ${per}` : ""}`;
}

/**
 * How close a corner is to the City's own review threshold: five injury or
 * fatal crashes in a year (docs/DECISIONS.md D18). Uses the last full year of
 * the record. gap 0 means it has already met the rule in that year.
 */
export const CITY_SCREEN = CITY.screen.threshold;

export function screenGap(history, year = 2024) {
  const h = (history ?? []).find((x) => x.year === year);
  if (!h) return null;
  const injuryCrashes = (h.injury || 0) + (h.ksi || 0);
  return { year, injuryCrashes, gap: Math.max(0, CITY_SCREEN - injuryCrashes) };
}
