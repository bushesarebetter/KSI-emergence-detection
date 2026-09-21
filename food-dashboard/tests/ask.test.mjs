import { test } from "node:test";
import assert from "node:assert/strict";
import { citation, recordText } from "../src/lib/ask.js";

const feature = {
  properties: {
    rank: 12, name: "Sample Grill 077", address: "800 5th Ave, San Diego, CA 92101", facility_type: "restaurant", risk_category: 3, council_district: 3,
    inspections: [{ date: "2026-05-05", type: "routine", score: 81, grade: "B", major: 2, minor: 4, closed: false }],
    violations: [{ date: "2026-05-05", theme: "handwashing", severity: "major" }],
  },
  geometry: { coordinates: [-117.16, 32.71] },
};

test("a citation names the authors, the place, the rank and the URL", () => {
  const c = citation({ feature, candidates: 8200, url: "https://example.org/place/12" });
  assert.match(c, /^Zhang, C\., and Pendharkar, A\. \(\d{4}\)\. San Diego Food Safety Risk: Sample Grill 077, 800 5th Ave, San Diego, CA 92101, rank 12 of 8,200 candidate food facilities\. https:\/\/example\.org\/place\/12\. Retrieved \d{4}-\d{2}-\d{2}\.$/);
});

test("the record text states the County's record and where to check it", () => {
  const t = recordText({ feature, candidates: 8200, url: "https://example.org/place/12" });
  assert.match(t, /Last inspection: 2026-05-05, routine, score 81 \(grade B\)/);
  assert.match(t, /2 major and 4 minor violations across 1 visits/);
  assert.match(t, /Hand washing: 1 finding, 1 major, latest 2026-05-05/);
  assert.match(t, /sandiegocounty\.gov/);
  assert.doesNotMatch(t, /unsafe|dangerous/, "the record text states the record and nothing more");
});
