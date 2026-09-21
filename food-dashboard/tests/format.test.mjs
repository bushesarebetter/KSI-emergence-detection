import { test } from "node:test";
import assert from "node:assert/strict";
import { facilitiesToCsv, formatPercentile } from "../src/lib/format.js";

const feature = {
  properties: {
    rank: 4, facility_id: "PR001", name: "Sample Taqueria, North", address: "1234 30th St, San Diego, CA 92104", facility_type: "restaurant",
    risk_category: 3, council_district: 3, percentile: 99.9, is_known_positive: true,
    inspections: [
      { date: "2025-02-01", type: "routine", score: 95, grade: "A", major: 0, minor: 1, closed: false },
      { date: "2026-02-01", type: "routine", score: 84, grade: "B", major: 2, minor: 3, closed: false },
    ],
    violations: [{ date: "2026-02-01", theme: "temperature", severity: "major" }, { date: "2026-02-01", theme: "temperature", severity: "major" }],
    shap_features: [{ display_label: "temperature cited 2 times" }],
  },
  geometry: { coordinates: [-117.13, 32.75] },
};

test("the CSV carries the record a reporter or an inspector would sort by", () => {
  const [header, row] = facilitiesToCsv([feature]).split("\n");
  const cols = header.split(",");
  const vals = row.match(/("([^"]|"")*"|[^,]*)(,|$)/g).map((s) => s.replace(/,$/, "").replace(/^"|"$/g, "").replace(/""/g, '"'));
  const get = (name) => vals[cols.indexOf(name)];
  assert.equal(get("rank"), "4");
  assert.equal(get("name"), "Sample Taqueria, North", "a comma in the name is quoted");
  assert.equal(get("facility_type"), "Restaurant");
  assert.equal(get("last_score"), "84");
  assert.equal(get("last_grade"), "B");
  assert.equal(get("majors_36mo"), "2");
  assert.equal(get("top_theme"), "Food temperatures");
  assert.equal(get("pattern"), "Food temperatures");
  assert.equal(get("is_known_positive"), "true");
  assert.equal(get("lat"), "32.75");
});

test("a place with no record still produces a row of the same width", () => {
  const bare = { properties: { rank: 9, name: "Sample", address: "x", inspections: [], violations: [] }, geometry: { coordinates: [0, 0] } };
  const [header, row] = facilitiesToCsv([bare]).split("\n");
  assert.equal(header.split(",").length, row.split(",").length);
});

test("percentile ordinals", () => {
  assert.equal(formatPercentile(99.9), "99.9th");
  assert.equal(formatPercentile(1), "1st");
  assert.equal(formatPercentile(12), "12th");
});
