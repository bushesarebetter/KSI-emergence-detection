/**
 * From a site's model signals to something a person can do at that corner.
 *
 * The export gives each site up to five signal labels in feature space. Two
 * vocabularies are read. The crash-history model names crash types ("3
 * left-turn crashes (72 months)"). The E model names the road and its context
 * ("Transit stop 21 m away", "~5 lanes", "72 km/h speed limit",
 * "Stop-controlled"). This module turns either into {fact, action} pairs: the
 * fact quotes what the label says, the action is standard road practice for
 * that situation, addressed to the person reading.
 *
 * Rules that keep it honest:
 *   - Every fact quotes a value the export contains. No fact is inferred.
 *   - Actions are plain road-safety practice. They never claim the corner is
 *     "dangerous" or that the action would have prevented a specific crash.
 *   - Items about what you will meet (a crash type, a transit stop, a fast
 *     road, a wide crossing, stop signs) rank above tempo items (a rising
 *     rate, a recent crash), because the first says what to change and the
 *     second only how much care.
 */

const YEARS = (months) => Math.max(1, Math.round(months / 12));
const KMH_TO_MPH = 0.621371;
const mph = (kmh) => Math.round((kmh * KMH_TO_MPH) / 5) * 5;

// Each rule reads one label pattern and yields a candidate item, or null.
const RULES = [
  // ── Crash types (crash-history model) ───────────────────────────────────
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

  // ── What you will meet (E model) ────────────────────────────────────────
  {
    key: "ped",
    test: /transit stop (\d+) m away/i,
    make: (m) => ({
      priority: 95,
      pattern: "People on foot",
      fact: `A transit stop is ${m} m away, so people cross here to reach it.`,
      driving: "Before you turn, look for someone crossing to or from the stop, then look again.",
      walking: "Cross at the corner with the signal, even when the stop is closer mid-block.",
    }),
  },
  {
    key: "speed",
    test: /(\d+) km\/h speed limit/i,
    make: (kmh) => (mph(kmh) >= 40 ? {
      priority: 78,
      pattern: "Fast road",
      fact: `The speed limit here is ${mph(kmh)} mph.`,
      driving: "Slow before the corner, not in it. At this speed a late brake is a crash.",
      walking: `Wait for a fresh walk signal; a car at ${mph(kmh)} mph covers the block in seconds.`,
    } : null),
  },
  {
    key: "wide",
    test: /~\s*(\d+) lanes/i,
    make: (n) => (n >= 5 ? {
      priority: 72,
      pattern: "Wide crossing",
      fact: `About ${n} lanes meet here.`,
      driving: "Check the far lane before you turn; a wide corner hides a car in the outer lane.",
      walking: `Start only on a fresh walk signal. It is ${n} lanes to the other side.`,
    } : null),
  },
  {
    key: "stop",
    test: /stop-controlled/i,
    make: () => ({
      priority: 66,
      pattern: "Stop signs, no signal",
      fact: "This corner has stop signs rather than a signal.",
      driving: "Stop fully. The cross traffic may not have to stop, and a rolling stop is how most of these crashes start.",
    }),
  },
  {
    key: "complex",
    test: /^(\d+)-(?:leg|way) intersection$/i,
    make: (n) => (n >= 5 ? {
      priority: 60,
      pattern: "Complex corner",
      fact: `${n} roads meet here.`,
      driving: "Take the corner in two looks: one for cross traffic, one for the road you are turning into.",
    } : null),
  },

  // ── Tempo ───────────────────────────────────────────────────────────────
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
    key: "days",
    test: /recent crash rate ([\d.]+)\/yr/i,
    make: (rate) => (rate >= 1 ? {
      priority: 40 + Math.min(Math.round(rate * 4), 30),
      pattern: "Crashes are routine here",
      fact: `About ${rate} crashes a year here recently.`,
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
    test: /crash trend slope \+([\d.]+)\/yr|rising crash-rate trend|accelerating crash trend/i,
    make: () => ({
      priority: 30,
      pattern: "Crashes rising",
      fact: "Crashes here have been rising year over year.",
      driving: "Something about this corner changed. Drive it like a road you do not know.",
    }),
  },
  {
    key: "cluster",
    test: /(\d+) crashes within (\d+) m/i,
    make: (n, m) => (n >= 5 ? {
      priority: 28,
      pattern: "Crashes along this stretch",
      fact: `${n} crashes within ${m} m of this corner on nearby roads.`,
      driving: "Treat the whole block with care, not only the corner.",
    } : null),
  },
  {
    key: "hotspot",
    test: /(\d+) m to nearest high-crash site/i,
    make: (m) => (m <= 300 ? {
      priority: 26,
      pattern: "Near a corner the City already reviews",
      fact: `A corner the City already reviews is ${m} m away.`,
      driving: "The same traffic that fills that corner passes through this one.",
    } : null),
  },
  {
    key: "recent",
    test: /([\d.]+)\s*years? since last crash|last crash under a year ago/i,
    make: (yrs) => (yrs < 1 ? {
      priority: 20,
      pattern: "Recent crash",
      fact: "The last crash here was within the past year.",
    } : null),
  },
];

const TEMPO = new Set(["days", "jump", "trend", "recent", "cluster", "hotspot"]);

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

const SCHOOL_M = 300;

function candidates(props) {
  const items = [];
  const seen = new Set();
  // A school within reach is a fact about the corner, not a model signal; it
  // comes from scripts/fetch_school_proximity.py and outranks most signals
  // because the people it concerns are children on a timetable.
  const school = props?.near_school;
  if (school && school.meters <= SCHOOL_M) {
    seen.add("school");
    items.push({
      key: "school",
      priority: 98,
      pattern: "Near a school",
      fact: `${school.name} is ${school.meters} m away.`,
      driving: "On school days, expect children crossing anywhere along this block at the start and end of school. Where a school zone is posted and children are present, the California limit is 15 mph.",
      walking: "Cross with the crossing guard or at the signal, and not from between parked cars.",
    });
  }
  for (const f of props?.shap_features ?? []) {
    const label = f?.display_label ?? "";
    for (const rule of RULES) {
      const m = label.match(rule.test);
      if (!m) continue;
      const item = rule.make(Number(m[1] ?? 0), Number(m[2] ?? 0));
      if (item && !seen.has(rule.key)) {
        seen.add(rule.key);
        items.push({ ...item, key: rule.key });
      }
      break;
    }
  }
  return items.sort((a, b) => b.priority - a.priority);
}

/**
 * Up to `max` items for the detail panel: [{key, pattern, fact, driving, walking?, cycling?}].
 * Tempo items all say "more care", so only the strongest one is kept; the
 * others are kept because each asks for a different change.
 */
export function adviceFor(props, { max = 3, control = null } = {}) {
  const items = candidates(props);
  const out = [];
  let tempoUsed = false;
  for (const it of items) {
    const isTempo = TEMPO.has(it.key);
    if (isTempo && tempoUsed) continue;
    if (isTempo) tempoUsed = true;
    const specific = control ? CONTROL_ACTIONS[it.key]?.[control] : null;
    out.push(specific ? { ...it, driving: specific } : it);
    if (out.length >= max) break;
  }
  return out;
}

/** The patterns a reader can filter by, in display order, with the key each rule uses. */
export const FILTER_PATTERNS = [
  { key: "ped", label: "People on foot" },
  { key: "bike", label: "Bikes" },
  { key: "left", label: "Left turns" },
  { key: "night", label: "After dark" },
  { key: "speed", label: "Fast roads" },
  { key: "wide", label: "Wide crossings" },
  { key: "stop", label: "Stop signs" },
  { key: "complex", label: "Complex corners" },
  { key: "school", label: "Near schools" },
];

/** Every pattern present at a site, as rule keys, for filtering. */
export function patternKeys(props) {
  return new Set(candidates(props).map((it) => it.key));
}

/** Short noun phrase for tables and tooltips: "Left turns", "Fast road", or null. */
export function patternOf(props) {
  const [first] = candidates(props);
  return first?.pattern ?? null;
}

/** One sentence for the phone sheet: the strongest fact and its action. */
export function adviceLine(props) {
  const [first] = adviceFor(props, { max: 1 });
  if (!first) return null;
  const action = first.driving ?? first.walking ?? null;
  return action ? `${first.fact} ${action}` : first.fact;
}
