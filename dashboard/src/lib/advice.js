/**
 * From a site's model signals to something a person can do at that corner.
 *
 * The export gives each site up to five signal labels in feature space:
 * "3 left-turn crashes (72 months)", "2 night crashes (72 months)",
 * "16 distinct crash days (72 months)". Those describe what has happened at the
 * corner. This module turns them into a short list of {fact, action} pairs:
 * the fact is the record, the action is the standard countermeasure for that
 * kind of crash, addressed to the person reading.
 *
 * Rules that keep it honest:
 *   - Every fact quotes a count the export contains. No fact is inferred.
 *   - Actions are plain road-safety practice for that crash type. They never
 *     claim the corner is "dangerous" or that the action would have prevented
 *     a specific crash.
 *   - Crash-type items (left turns, dark, bikes, people on foot, side impacts)
 *     rank above tempo items (many separate days, a recent jump), because a
 *     crash type tells you what to change; a tempo tells you how much care.
 */

const YEARS = (months) => Math.max(1, Math.round(months / 12));

// Each rule reads one label pattern and yields a candidate item.
const RULES = [
  {
    key: "ped",
    test: /(\d+)\s*pedestrian crashes? \((\d+) months\)/i,
    make: (n, months) => ({
      priority: 100 + n,
      pattern: "People on foot",
      fact: `${n} of the crashes here in the last ${YEARS(months)} years involved someone on foot.`,
      driving: "Before you turn, look for someone stepping off the curb, then look again.",
      walking: "Wait for the walk signal, and make eye contact with anyone turning before you cross.",
    }),
  },
  {
    key: "bike",
    test: /(\d+)\s*bicycle crashes? \((\d+) months\)/i,
    make: (n, months) => ({
      priority: 90 + n,
      pattern: "Bikes",
      fact: `${n} of the crashes here in the last ${YEARS(months)} years involved someone on a bike.`,
      driving: "Turning right, check the bike lane and your mirror before you go.",
      cycling: "Hold your lane through the intersection and assume the driver next to you has not seen you.",
    }),
  },
  {
    key: "left",
    test: /(\d+)\s*left-turn crashes? \((\d+) months\)/i,
    make: (n, months) => ({
      priority: 80 + n,
      pattern: "Left turns",
      fact: `${n} of the crashes here in the last ${YEARS(months)} years were left turns.`,
      driving: "Turning left, wait for the green arrow or a gap you are sure of. If the light is about to change, stay put.",
    }),
  },
  {
    key: "night",
    test: /(\d+)\s*night crashes? \((\d+) months\)/i,
    make: (n, months) => ({
      priority: 70 + n,
      pattern: "After dark",
      fact: `${n} of the crashes here in the last ${YEARS(months)} years happened after dark.`,
      driving: "After dark, come through slower than you would by day and check the crosswalk before the light changes.",
      walking: "At night, cross where the light is best and assume drivers cannot see you until you are in front of them.",
    }),
  },
  {
    key: "broadside",
    test: /(\d+)\s*broadside crashes? \((\d+) months\)/i,
    make: (n, months) => ({
      priority: 85 + n,
      pattern: "Side impacts",
      fact: `${n === 1 ? "One crash" : `${n} crashes`} here in the last ${YEARS(months)} years ${n === 1 ? "was" : "were"} a side impact, the kind running a red light causes.`,
      driving: "When your light turns green, look both ways before you go.",
    }),
  },
  {
    key: "days",
    test: /(\d+)\s*distinct crash days \((\d+) months\)/i,
    make: (n, months) => (n >= 6 ? {
      priority: 40 + Math.min(n, 30),
      pattern: "Crashes are routine here",
      fact: `Crashes here happened on ${n} separate days in the last ${YEARS(months)} years.`,
      driving: "Leave a car length more than usual and expect the car ahead to brake.",
    } : null),
  },
  {
    key: "jump",
    test: /(\d+)% structural break probability/i,
    make: (p) => (p >= 50 ? {
      priority: 35,
      pattern: "Crash rate jumped",
      fact: `The crash rate here jumped from its earlier level; the model puts that at ${p}% likely.`,
      driving: "Something about this corner changed. Drive it like a road you do not know.",
    } : null),
  },
  {
    key: "trend",
    test: /crash trend slope \+([\d.]+)\/yr/i,
    make: () => ({
      priority: 30,
      pattern: "Crashes rising",
      fact: "Crashes here have been rising year over year.",
      driving: "Something about this corner changed. Drive it like a road you do not know.",
    }),
  },
  {
    key: "recent",
    test: /([\d.]+)\s*years? since last crash/i,
    make: (yrs) => (yrs < 1 ? {
      priority: 20,
      pattern: "Recent crash",
      fact: "The last crash here was within the past year.",
    } : null),
  },
];

// Where the corner's control is known (control.json, from OpenStreetMap), the
// action for a turn or a side impact can say what the driver will actually meet.
const CONTROL_ACTIONS = {
  left: {
    signals: "Turning left, wait for the green arrow. If the signal has no arrow, wait for a gap you are sure of, and if the light is about to change, stay put.",
    stop: "Turning left, stop fully, then wait for a gap you are sure of. Most left-turn crashes start with a turn taken a second too early.",
  },
  broadside: {
    signals: "When your light turns green, look both ways before you go.",
    stop: "Stop fully, look both ways, then look again before you roll into the intersection.",
  },
};

function candidates(shapFeatures) {
  const items = [];
  for (const f of shapFeatures ?? []) {
    const label = f?.display_label ?? "";
    for (const rule of RULES) {
      const m = label.match(rule.test);
      if (!m) continue;
      const item = rule.make(Number(m[1]), Number(m[2] ?? 0));
      if (item) items.push({ ...item, key: rule.key });
      break;
    }
  }
  return items.sort((a, b) => b.priority - a.priority);
}

/**
 * Up to `max` items for the detail panel: [{key, pattern, fact, driving, walking?, cycling?}].
 * Two tempo items say the same thing ("be more careful"), so only the strongest
 * one is kept; crash-type items are all kept because each asks for a different change.
 */
export function adviceFor(props, { max = 3, control = null } = {}) {
  const items = candidates(props?.shap_features);
  const out = [];
  let tempoUsed = false;
  for (const it of items) {
    const isTempo = ["days", "jump", "trend", "recent"].includes(it.key);
    if (isTempo && tempoUsed) continue;
    if (isTempo) tempoUsed = true;
    const specific = control ? CONTROL_ACTIONS[it.key]?.[control] : null;
    out.push(specific ? { ...it, driving: specific } : it);
    if (out.length >= max) break;
  }
  return out;
}

/** Every crash-type pattern present at a site, as rule keys, for filtering. */
export const FILTER_PATTERNS = [
  { key: "left", label: "Left turns" },
  { key: "night", label: "After dark" },
  { key: "bike", label: "Bikes" },
  { key: "ped", label: "People on foot" },
];

export function patternKeys(props) {
  return new Set(candidates(props?.shap_features).map((it) => it.key));
}

/** Short noun phrase for tables and tooltips: "Left turns", "After dark", or null. */
export function patternOf(props) {
  const [first] = candidates(props?.shap_features);
  return first?.pattern ?? null;
}

/** One sentence for the phone sheet: the strongest fact and its action. */
export function adviceLine(props) {
  const [first] = adviceFor(props, { max: 1 });
  if (!first) return null;
  const action = first.driving ?? first.walking ?? null;
  return action ? `${first.fact} ${action}` : first.fact;
}
