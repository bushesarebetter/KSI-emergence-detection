import { test } from "node:test";
import assert from "node:assert/strict";
import { candidates, adviceFor, patternOf, patternKeys, FILTER_PATTERNS } from "../src/lib/advice.js";

const labels = (...ls) => ls.map((display_label) => ({ display_label }));
const routine = (date, score, major = 0) => ({ date, type: "routine", score, grade: score >= 90 ? "A" : score >= 80 ? "B" : "C", major, minor: 1, closed: false });

test("a major vermin finding outranks everything and quotes the record", () => {
  const p = {
    violations: [
      { date: "2026-03-02", theme: "vermin", severity: "major" },
      { date: "2026-03-02", theme: "temperature", severity: "major" },
      { date: "2025-11-11", theme: "temperature", severity: "minor" },
    ],
    inspections: [routine("2026-03-02", 86, 2)],
  };
  const [first, second] = adviceFor(p);
  assert.equal(first.pattern, "Pests");
  assert.match(first.fact, /1 major violation for pests in the last three years, most recently in March 2026/);
  assert.equal(second.pattern, "Food temperatures");
  assert.match(second.fact, /1 major violation for food temperatures/);
  assert.equal(patternOf(p), "Pests");
});

test("a single minor finding is not enough for an item, two are", () => {
  const one = candidates({ violations: [{ date: "2026-01-01", theme: "sanitizing", severity: "minor" }] });
  assert.equal(one.length, 0);
  const two = candidates({ violations: [{ date: "2026-01-01", theme: "sanitizing", severity: "minor" }, { date: "2025-06-01", theme: "sanitizing", severity: "minor" }] });
  assert.equal(two[0].pattern, "Cleaning");
  assert.match(two[0].fact, /2 findings/);
});

test("model signals add themes and closures the violation list does not carry", () => {
  const p = { shap_features: labels("temperature cited 3 times", "Closed by the County 2025", "Risk category 3") };
  const items = candidates(p);
  assert.deepEqual(items.map((i) => i.key), ["temperature", "closed"]);
  assert.match(items[0].fact, /cited food temperatures 3 times/);
  assert.match(items[1].fact, /closed it in 2025/);
});

test("a recent B or C and repeat reinspections come from the history", () => {
  const p = {
    inspections: [
      routine("2025-01-01", 95),
      { date: "2025-01-08", type: "reinspection", score: 92, major: 0, minor: 0 },
      routine("2025-06-01", 88, 1),
      { date: "2025-06-08", type: "reinspection", score: 91, major: 0, minor: 0 },
      routine("2025-09-01", 84, 1),
    ],
  };
  const keys = patternKeys(p);
  assert.ok(keys.includes("grade"));
  assert.ok(keys.includes("repeat"));
  const grade = candidates(p).find((i) => i.key === "grade");
  assert.match(grade.fact, /scored 84 \(grade B\) at its last inspection in September 2025/);
  // A reinspection that restored an A is the last word: no "Recent B or C".
  const restored = { inspections: [...p.inspections, { date: "2025-09-08", type: "reinspection", score: 93, major: 0, minor: 0 }] };
  assert.ok(!patternKeys(restored).includes("grade"));
});

test("every filter chip key can be produced by some record", () => {
  for (const key of Object.keys(FILTER_PATTERNS)) {
    assert.ok(["vermin", "temperature", "handwashing", "hygiene", "sanitizing", "storage", "closed", "grade", "repeat"].includes(key), key);
  }
  assert.equal(patternOf({}), null);
  assert.deepEqual(adviceFor(null), []);
});
