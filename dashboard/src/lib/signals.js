/**
 * Turn a model feature label into a sentence a non-specialist can read.
 *
 * The `display_label` strings come from the export
 * (scripts/build_export_panel_verified.py) and are written in feature space:
 * "EWMA crash rate 3.1", "16 distinct crash days (72 months)". A traffic
 * engineer reading SHAP values wants exactly that; everyone else needs words.
 *
 * Rewrites stay faithful. "EWMA crash rate 3.1" becomes "steady recent crash
 * rate", a fair reading of an exponentially weighted average that counts recent
 * years most. It never becomes "this intersection is dangerous", which is a
 * claim about hazard the model does not make.
 *
 * Unmatched labels fall through unchanged. A technical string beats nothing.
 */

const RULES = [
  {
    test: /ewma crash rate\s*([\d.]+)/i,
    render: (m) => `A steady crash rate, about ${m[1]} a year, weighted toward recent years`,
  },
  {
    test: /([\d.]+)\s*years? since last crash/i,
    render: (m) => {
      const yrs = parseFloat(m[1]);
      if (yrs < 1) return "A crash within the past year";
      const n = Math.round(yrs);
      return n <= 1 ? "The last crash was about a year ago" : `The last crash was about ${n} years ago`;
    },
  },
  {
    test: /(\d+)\s*distinct crash days \((\d+) months\)/i,
    render: (m) => `Crashes on ${m[1]} separate days in ${Math.round(Number(m[2]) / 12)} years`,
  },
  {
    test: /(\d+)\s*crashes in last (\d+) months/i,
    render: (m) => `${m[1]} crashes in the last ${Math.round(Number(m[2]) / 12)} years`,
  },
  {
    test: /(\d+)\s*left-turn crashes? \((\d+) months\)/i,
    render: (m) => `${m[1]} left-turn ${Number(m[1]) === 1 ? "crash" : "crashes"} in ${Math.round(Number(m[2]) / 12)} years`,
  },
  {
    test: /(\d+)\s*night crashes? \((\d+) months\)/i,
    render: (m) => `${m[1]} ${Number(m[1]) === 1 ? "crash" : "crashes"} after dark in ${Math.round(Number(m[2]) / 12)} years`,
  },
  {
    test: /(\d+)\s*bicycle crashes? \((\d+) months\)/i,
    render: (m) => `${m[1]} ${Number(m[1]) === 1 ? "crash" : "crashes"} involving a bike in ${Math.round(Number(m[2]) / 12)} years`,
  },
  {
    test: /(\d+)\s*pedestrian crashes? \((\d+) months\)/i,
    render: (m) => `${m[1]} ${Number(m[1]) === 1 ? "crash" : "crashes"} involving someone on foot in ${Math.round(Number(m[2]) / 12)} years`,
  },
  {
    test: /(\d+)\s*broadside crashes? \((\d+) months\)/i,
    render: (m) => `${m[1]} side-impact ${Number(m[1]) === 1 ? "crash" : "crashes"} in ${Math.round(Number(m[2]) / 12)} years`,
  },
  { test: /\bdui\b|alcohol/i, render: () => "Alcohol was involved in crashes here" },
  {
    test: /(\d+)% structural break probability/i,
    render: (m) => `The crash rate jumped from its earlier level (${m[1]}% likely)`,
  },
  { test: /crash trend slope \+/i, render: () => "Crashes rising year over year" },
  { test: /mann.?kendall trend tau = -/i, render: () => "Crashes falling year over year" },
  { test: /trend|slope|mann.?kendall/i, render: () => "A crash trend over the years" },
  { test: /worst severity\s*([\d.]+)/i, render: () => "Past crashes here caused injuries" },
  { test: /covid/i, render: () => "The crash pattern shifted in the pandemic years" },
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

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

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
