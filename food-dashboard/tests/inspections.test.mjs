import { test } from "node:test";
import assert from "node:assert/strict";
import { gradeFor, inspectionStats, themeCounts, lastInspection } from "../src/lib/inspections.js";

const visit = (date, score, extra = {}) => ({ date, type: "routine", score, grade: gradeFor(score), major: 0, minor: 0, closed: false, ...extra });

const record = {
  inspections: [
    visit("2022-03-01", 96),
    visit("2022-10-12", 94),
    visit("2023-05-20", 95, { major: 1, minor: 2 }),
    { date: "2023-05-27", type: "reinspection", score: 98, grade: "A", major: 0, minor: 0, closed: false },
    visit("2024-02-14", 93),
    visit("2025-01-09", 84, { major: 2, minor: 5, closed: true }),
    { date: "2025-01-16", type: "reinspection", score: 91, grade: "A", major: 0, minor: 1, closed: false },
    visit("2025-09-03", 82, { major: 2, minor: 4 }),
  ],
  violations: [
    { date: "2025-09-03", code: "7", theme: "temperature", severity: "major" },
    { date: "2025-09-03", code: "23", theme: "vermin", severity: "major" },
    { date: "2025-01-09", code: "6", theme: "handwashing", severity: "major" },
    { date: "2025-01-09", code: "14", theme: "sanitizing", severity: "minor" },
    { date: "2024-02-14", code: "14", theme: "sanitizing", severity: "minor" },
    { date: "2023-05-20", code: "44", theme: "notatheme", severity: "minor" },
  ],
};

test("grades follow the County's bands", () => {
  assert.equal(gradeFor(90), "A");
  assert.equal(gradeFor(89), "B");
  assert.equal(gradeFor(80), "B");
  assert.equal(gradeFor(79), "C");
  assert.equal(gradeFor(null), null);
});

test("stats count the 36 months before the last visit, not before today", () => {
  const s = inspectionStats(record);
  assert.equal(s.count, 8);
  assert.equal(s.routineCount, 6);
  assert.equal(s.last.date, "2025-09-03");
  assert.equal(s.lastScore, 82);
  assert.equal(s.lastGrade, "B");
  // 2022-10-12 is 35 months before 2025-09-03 and counts; 2022-03-01 does not.
  assert.equal(s.majors36, 1 + 2 + 2);
  assert.equal(s.minors36, 2 + 5 + 1 + 4);
  assert.equal(s.closures, 1);
  assert.equal(s.reinspections, 2);
  assert.equal(s.trend, "worsening", "82 against a mean of the earlier routine scores near 92");
});

test("a place with two routine scores has no trend, and no visits gives null", () => {
  assert.equal(inspectionStats({ inspections: [visit("2025-01-01", 90), visit("2025-06-01", 70)] }).trend, "steady");
  assert.equal(inspectionStats({ inspections: [] }), null);
  assert.equal(lastInspection({ last_inspection: { date: "2026-01-01" }, inspections: [] }).date, "2026-01-01");
});

test("themes sort majors first, then count, then recency, and unknown themes fall to other", () => {
  const t = themeCounts(record.violations);
  assert.deepEqual(t.map((x) => x.theme), ["temperature", "vermin", "handwashing", "sanitizing", "other"]);
  assert.equal(t[3].count, 2);
  assert.equal(t[3].last, "2025-01-09");
  assert.equal(t[4].label, "Other");
});
