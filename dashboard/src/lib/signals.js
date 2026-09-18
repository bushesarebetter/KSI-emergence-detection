/**
 * Turn a model feature label into something a non-specialist can act on.
 *
 * The `display_label` strings come from the export
 * (scripts/build_export_panel_verified.py) and are written in feature-space:
 * "EWMA crash rate 3.1", "16 distinct crash days (72 months)". Those are exactly
 * right for a traffic engineer reading SHAP values and meaningless to everyone
 * else, so plain mode rewrites them.
 *
 * Rewrites must stay faithful. "EWMA crash rate 3.1" becomes "steady recent
 * crash rate" — a fair reading of an exponentially-weighted moving average,
 * which by construction weights recent years most. It must not become "this
 * intersection is dangerous", which is a claim about hazard the model does not
 * make.
 *
 * Unmatched labels fall through unchanged rather than being dropped: showing a
 * technical string is better than showing nothing.
 */

const RULES = [
  {
    // Exponentially-weighted moving average of crashes: recent years dominate.
    test: /ewma crash rate\s*([\d.]+)/i,
    render: (m) => `Steady recent crash rate, about ${m[1]} a year`,
  },
  {
    test: /([\d.]+)\s*years? since last crash/i,
    render: (m) => {
      const yrs = parseFloat(m[1]);
      if (yrs < 1) return "A crash happened here within the last year";
      // Round first, then pluralise: 1.6 years is "about 2 years", not "2 year".
      const n = Math.round(yrs);
      return n <= 1 ? "Last crash here was about a year ago" : `Last crash here was about ${n} years ago`;
    },
  },
  {
    test: /(\d+)\s*distinct crash days/i,
    render: (m) => `Crashes on ${m[1]} separate days, not one bad incident`,
  },
  {
    test: /(\d+)\s*crashes in last (\d+) months/i,
    render: (m) => `${m[1]} crashes in the last ${Math.round(Number(m[2]) / 12)} years`,
  },
  { test: /left[_\s-]?turn/i, render: () => "Several crashes involved left turns" },
  { test: /broadside/i, render: () => "Several crashes were side-impact collisions" },
  { test: /\bped(estrian)?\b/i, render: () => "Pedestrians were involved in crashes here" },
  { test: /\bbike|bicycle\b/i, render: () => "Cyclists were involved in crashes here" },
  { test: /\bnight\b/i, render: () => "Several crashes happened after dark" },
  { test: /\bdui\b|alcohol/i, render: () => "Alcohol was involved in crashes here" },
  { test: /changepoint/i, render: () => "Crash rate here recently jumped from a stable baseline" },
  { test: /trend|slope|mann.?kendall/i, render: () => "Crashes here are trending upward" },
  { test: /momentum|velocity|acceleration/i, render: () => "Crashes here are speeding up" },
  { test: /worst severity/i, render: () => "Past crashes here caused injuries" },
  { test: /covid/i, render: () => "Crash pattern shifted during the pandemic years" },
];

export function humanizeSignal(label) {
  if (!label || label === "—") return "—";
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
      ? `Known KSI site · ${plural(n, "KSI crash")} in the history window`
      : `Already had ${plural(n, "serious crash")} here`;
  }
  if (s === "screen") {
    const n = props.screen_count ?? 5;
    return advanced
      ? `City screen · ${n} crashes in one year (≥5 rule)`
      : `On the City's own list · ${n} crashes in one year`;
  }
  return null;
}

/**
 * What to show in place of model signals for a site that has none. A known or
 * screen site was not ranked by the model, and saying so is the honest reading
 * of an empty SHAP list.
 */
export function inclusionReason(props, advanced) {
  const s = sourceOf(props);
  if (s === "known") {
    return advanced
      ? "Included from the known-KSI tier; no model prediction applies."
      : "Included because a serious crash has already happened here — no prediction needed.";
  }
  if (s === "screen") {
    return advanced
      ? "Included from the City-screen tier (≥5 crashes in a year); no model prediction applies."
      : "Included because it meets the City's own screening rule: five or more crashes in a year.";
  }
  return null;
}
