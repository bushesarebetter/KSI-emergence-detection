/**
 * Turn a model feature label into something a non-specialist can act on.
 *
 * The `display_label` strings come from the export
 * (scripts/build_export_panel_verified.py) and are written in feature-space:
 * "EWMA crash rate 3.1", "16 distinct crash days (72 months)". Those are exactly
 * right for a traffic engineer reading SHAP values and meaningless to everyone
 * else, so plain mode rewrites them.
 *
 * Rewrites must stay faithful. "EWMA crash rate 3.1" becomes "crashes here are
 * frequent and recent" — a fair reading of an exponentially-weighted moving
 * average, which by construction weights recent years most. It must not become
 * "this intersection is dangerous", which is a claim about hazard the model does
 * not make.
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
      if (yrs < 2) return `Last crash here was about ${Math.round(yrs)} year ago`;
      return `Last crash here was about ${Math.round(yrs)} years ago`;
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
