/**
 * Turn a model feature label into a sentence a non-specialist can read.
 *
 * The `display_label` strings come from the export and are written in feature
 * space. Two vocabularies are handled: the crash-history model's ("EWMA crash
 * rate 3.1", "3 left-turn crashes (72 months)") and the E model's, which adds
 * road layout and context ("Secondary arterial", "~5 lanes", "Transit stop
 * 21 m away", "72 km/h speed limit"). A traffic engineer reading SHAP values
 * wants the original; everyone else needs words.
 *
 * Rewrites stay faithful. "EWMA crash rate 3.1" becomes "a steady crash rate",
 * a fair reading of an exponentially weighted average. It never becomes "this
 * intersection is dangerous", which is a claim about hazard the model does not
 * make. Unmatched labels fall through unchanged.
 */

const KMH_TO_MPH = 0.621371;
const yrs = (months) => Math.round(Number(months) / 12);
const plural = (n, word) => `${n} ${word}${Number(n) === 1 ? "" : "s"}`;

const RULES = [
  // ── Crash-history model ──────────────────────────────────────────────────
  { test: /ewma crash rate\s*([\d.]+)/i, render: (m) => `A steady crash rate, about ${m[1]} a year, weighted toward recent years` },
  {
    test: /([\d.]+)\s*years? since last crash/i,
    render: (m) => {
      const y = parseFloat(m[1]);
      if (y < 1) return "A crash within the past year";
      const n = Math.round(y);
      return n <= 1 ? "The last crash was about a year ago" : `The last crash was about ${n} years ago`;
    },
  },
  { test: /(\d+)\s*distinct crash days \((\d+) months\)/i, render: (m) => `Crashes on ${m[1]} separate days in ${yrs(m[2])} years` },
  { test: /(\d+)\s*crashes in last (\d+) months/i, render: (m) => `${m[1]} crashes in the last ${yrs(m[2])} years` },
  { test: /(\d+)\s*left-turn crashes? \((\d+) months\)/i, render: (m) => `${plural(m[1], "left-turn crash")} in ${yrs(m[2])} years` },
  { test: /(\d+)\s*night crashes? \((\d+) months\)/i, render: (m) => `${plural(m[1], "crash")} after dark in ${yrs(m[2])} years` },
  { test: /(\d+)\s*bicycle crashes? \((\d+) months\)/i, render: (m) => `${plural(m[1], "crash")} involving a bike in ${yrs(m[2])} years` },
  { test: /(\d+)\s*pedestrian crashes? \((\d+) months\)/i, render: (m) => `${plural(m[1], "crash")} involving someone on foot in ${yrs(m[2])} years` },
  { test: /(\d+)\s*broadside crashes? \((\d+) months\)/i, render: (m) => `${plural(m[1], "side-impact crash")} in ${yrs(m[2])} years` },
  { test: /\bdui\b|alcohol/i, render: () => "Alcohol was involved in crashes here" },
  { test: /(\d+)% structural break probability/i, render: (m) => `The crash rate jumped from its earlier level (${m[1]}% likely)` },
  { test: /crash trend slope \+/i, render: () => "Crashes rising year over year" },
  { test: /mann.?kendall trend tau = -/i, render: () => "Crashes falling year over year" },
  { test: /worst severity\s*([\d.]+)/i, render: () => "Past crashes here caused injuries" },
  { test: /covid/i, render: () => "The crash pattern shifted in the pandemic years" },

  // ── E model: road layout and context ────────────────────────────────────
  { test: /last crash under a year ago/i, render: () => "A crash within the past year" },
  {
    test: /last crash ~?\s*([\d.]+)\s*years? ago/i,
    render: (m) => {
      const n = Math.round(parseFloat(m[1]));
      return n <= 1 ? "The last crash was about a year ago" : `The last crash was about ${n} years ago`;
    },
  },
  { test: /recent crash rate ([\d.]+)\/yr/i, render: (m) => `About ${m[1]} crashes a year recently` },
  { test: /rising crash-rate trend/i, render: () => "Crash rate rising" },
  { test: /accelerating crash trend/i, render: () => "Crashes speeding up" },
  { test: /^(\d+)-(?:leg|way) intersection$/i, render: (m) => `${m[1]} roads meet here` },
  { test: /^major arterial$/i, render: () => "On a major arterial, a main through road" },
  { test: /^secondary arterial$/i, render: () => "On a secondary arterial, a busy through road" },
  { test: /^arterial$/i, render: () => "On an arterial, a through road" },
  { test: /~\s*(\d+) lanes/i, render: (m) => `About ${m[1]} lanes across` },
  { test: /transit stop (\d+) m away/i, render: (m) => `A transit stop ${m[1]} m away, so people cross here to reach it` },
  { test: /stop-controlled/i, render: () => "Stop signs, no signal" },
  { test: /(\d+) km\/h speed limit/i, render: (m) => `${Math.round(Number(m[1]) * KMH_TO_MPH / 5) * 5} mph speed limit` },
  { test: /(\d+) intersections within (\d+) m/i, render: (m) => `${m[1]} intersections within ${m[2]} m, a dense grid` },
  { test: /(\d+) crashes within (\d+) m/i, render: (m) => `${m[1]} crashes within ${m[2]} m on nearby roads` },
  { test: /(\d+) m to nearest high-crash site/i, render: (m) => `${m[1]} m from a corner the City already reviews` },
  { test: /([\d.]+)% grade/i, render: (m) => `A ${m[1]}% slope` },
  { test: /trend|slope|mann.?kendall/i, render: () => "A crash trend over the years" },
];

export function humanizeSignal(label) {
  if (!label || label === "—") return "";
  for (const { test, render } of RULES) {
    const m = label.match(test);
    if (m) return render(m);
  }
  return label;
}

// ── Combined-list sources ───────────────────────────────────────────────────────
// A combined export tags each site with the tier that admitted it. On a classic
// export the field is absent and everything is a model prediction.

export function sourceOf(props) {
  return props?.source ?? "predicted";
}

/** One short line naming why a non-predicted site is on the list, or null. */
export function sourceLine(props, advanced) {
  const s = sourceOf(props);
  if (s === "known") {
    const n = props.ksi_history ?? 1;
    return advanced
      ? `Known KSI site, ${plural(n, "KSI crash")} in the history window`
      : `Already had ${plural(n, "serious crash")} here`;
  }
  if (s === "screen") {
    const n = props.screen_count ?? 5;
    return advanced
      ? `City screen, ${n} crashes in one year (5-or-more rule)`
      : `On the City's own list, ${n} crashes in one year`;
  }
  return null;
}

/**
 * What to show in place of model signals for a site that has none. A known or
 * screen site was never ranked by the model, and the panel says so.
 */
export function inclusionReason(props, advanced) {
  const s = sourceOf(props);
  if (s === "known") {
    return advanced
      ? "Included from the known-KSI tier. No model prediction applies."
      : "A serious crash has already happened here, so it is on the list by record. The model did not rank it.";
  }
  if (s === "screen") {
    return advanced
      ? "Included from the City-screen tier (5 or more crashes in a year). No model prediction applies."
      : "It meets the City's own screening rule, five or more crashes in a year, so it is on the list by record. The model did not rank it.";
  }
  return null;
}
