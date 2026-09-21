/**
 * What to look for, from what inspectors found.
 *
 * Each item quotes the record (a count the export carries, never a guess)
 * and gives the standard thing a customer can check for that kind of
 * finding. The checks are general food-safety practice; none of them is a
 * verdict on the place, and the panel says so. Items come from three places:
 * the model's top signals, the violations cited in the last three years, and
 * the last inspection's grade.
 */
import { THEMES, inspectionStats, themeCounts } from "./inspections.js";

const THEME_ADVICE = {
  vermin: {
    priority: 98,
    pattern: "Pests",
    look: "Droppings along the walls, flies over food, gnawed packaging, or a sticky trap in view.",
    act: "Any of those is a reason to leave, and to tell the County.",
  },
  temperature: {
    priority: 95,
    pattern: "Food temperatures",
    look: "Hot food that arrives lukewarm, cold food that is not cold, rice or chicken sitting out under no heat.",
    act: "Send back anything lukewarm. Rice, chicken, seafood and cut fruit are the ones that make people ill.",
  },
  handwashing: {
    priority: 92,
    pattern: "Hand washing",
    look: "A sink behind the counter with soap and towels, and staff using it between handling money and food.",
    act: "If the sink is blocked or used for something else, order food that is cooked to order and served hot.",
  },
  hygiene: {
    priority: 85,
    pattern: "Employee hygiene",
    look: "Bare hands on ready-to-eat food, hair uncovered, staff eating or drinking at the prep line.",
    act: "Choose dishes that are cooked after you order them rather than assembled from prepared trays.",
  },
  sanitizing: {
    priority: 80,
    pattern: "Cleaning",
    look: "Sticky tables, cloudy glasses, a bathroom without soap. A kitchen is rarely cleaner than the bathroom.",
    act: "Ask for a fresh glass or plate if one is not clean; a place that minds that usually minds the kitchen.",
  },
  storage: {
    priority: 75,
    pattern: "Food storage",
    look: "Raw meat above ready-to-eat food in a visible cooler, or boxes on the floor.",
    act: "Avoid raw or undercooked items here; cross-contamination is what this finding is about.",
  },
  equipment: {
    priority: 60,
    pattern: "Equipment",
    look: "Coolers that are not cold to the touch, or a hot-holding unit that is off.",
    act: "Nothing to do at the table; it is a reason the County checks more often.",
  },
  plumbing: {
    priority: 60,
    pattern: "Plumbing and water",
    look: "No hot water at the hand sink, or standing water on the floor.",
    act: "Nothing to do at the table; it is a reason the County checks more often.",
  },
  labeling: { priority: 40, pattern: "Labels and records" },
  other: { priority: 30, pattern: "Other findings" },
};

export const FILTER_PATTERNS = {
  vermin: "Pests",
  temperature: "Food temperatures",
  handwashing: "Hand washing",
  hygiene: "Employee hygiene",
  sanitizing: "Cleaning",
  storage: "Food storage",
  closed: "Closed before",
  grade: "Recent B or C",
  repeat: "Repeat findings",
};

const fmtDate = (iso) => {
  const m = /^(\d{4})-(\d{2})/.exec(iso || "");
  if (!m) return iso || "";
  const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  return `${months[Number(m[2]) - 1]} ${m[1]}`;
};

function themeItem(theme, fact) {
  const a = THEME_ADVICE[theme] ?? THEME_ADVICE.other;
  return { key: theme, pattern: a.pattern, priority: a.priority, fact, look: a.look, act: a.act };
}

/** Every item the record supports, strongest first. */
export function candidates(props) {
  const p = props ?? {};
  const items = new Map();
  const add = (it) => {
    if (!it) return;
    const cur = items.get(it.key);
    if (!cur || it.priority > cur.priority) items.set(it.key, it);
  };

  // Violations cited in the last three years, by theme.
  for (const t of themeCounts(p.violations)) {
    if (t.major === 0 && t.count < 2) continue;
    const what = t.major > 0
      ? `${t.major} major ${t.major === 1 ? "violation" : "violations"}`
      : `${t.count} findings`;
    add({ ...themeItem(t.theme, `Inspectors recorded ${what} for ${THEMES[t.theme].toLowerCase()} in the last three years, most recently in ${fmtDate(t.last)}.`),
      priority: (THEME_ADVICE[t.theme] ?? THEME_ADVICE.other).priority + Math.min(t.major, 3) });
  }

  // The model's own signals can name a theme the violation list does not.
  for (const f of p.shap_features ?? []) {
    const m = /^(temperature|handwashing|vermin|sanitizing|storage|hygiene|equipment|plumbing|labeling) cited (\d+) times?/i.exec(f.display_label ?? "");
    if (m) {
      const theme = m[1].toLowerCase();
      const n = Number(m[2]);
      add(themeItem(theme, `Inspectors cited ${THEMES[theme].toLowerCase()} ${n === 1 ? "once" : `${n} times`}.`));
    }
    if (/^closed by the county (\d{4})/i.test(f.display_label ?? "")) {
      const yr = /(\d{4})/.exec(f.display_label)[1];
      add({ key: "closed", pattern: "Closed before", priority: 90,
        fact: `The County closed it in ${yr} for an imminent health hazard, and let it reopen after a reinspection.`,
        look: "The grade card in the window, which shows what the most recent inspection found.",
        act: "A place that has been closed once is inspected more often; a current A means the last visit found it in order." });
    }
  }

  const s = inspectionStats(p);
  if (s) {
    if (s.closures > 0 && !items.has("closed")) {
      add({ key: "closed", pattern: "Closed before", priority: 90,
        fact: `The County closed it ${s.closures === 1 ? "once" : `${s.closures} times`} in the last five years for an imminent health hazard.`,
        look: "The grade card in the window, which shows what the most recent inspection found.",
        act: "A place that has been closed once is inspected more often; a current A means the last visit found it in order." });
    }
    if (s.lastGrade && s.lastGrade !== "A") {
      add({ key: "grade", pattern: "Recent B or C", priority: 70,
        fact: `It scored ${s.lastScore} (grade ${s.lastGrade}) at its last inspection in ${fmtDate(s.last.date)}.`,
        look: "The posted grade card. San Diego County requires it to be displayed where customers can see it.",
        act: "A B or C means the last inspection found at least one major violation; a reinspection usually follows within weeks." });
    }
    if (s.reinspections >= 2) {
      add({ key: "repeat", pattern: "Repeat findings", priority: 65,
        fact: `Inspectors had to come back ${s.reinspections} times to check that problems were fixed.`,
        look: "Whether the same problem is visible now: the finding that brought them back is the one to watch.",
        act: "Repeat findings are the strongest sign in this record; treat the other items here as the things to check." });
    }
  }

  return [...items.values()].sort((a, b) => b.priority - a.priority);
}

export function adviceFor(props, { max = 3 } = {}) {
  return candidates(props).slice(0, max);
}

export function patternKeys(props) {
  return candidates(props).map((it) => it.key);
}

export function patternOf(props) {
  const [top] = candidates(props);
  return top?.pattern ?? null;
}
