import { test } from "node:test";
import assert from "node:assert/strict";
import { passesFilters, chipsFor, typesFor } from "../src/lib/filters.js";

const site = (rank, district, facility_type, violations = []) => ({
  properties: { rank, council_district: district, facility_type, violations, inspections: [], shap_features: [] },
});
const vermin = [{ date: "2026-01-01", theme: "vermin", severity: "major" }];
const fc = { features: [site(1, 3, "restaurant", vermin), site(2, 3, "market"), site(300, 7, "mobile", vermin), site(900, null, "bar")] };
const base = { threshold: 500, districts: [], types: [], pattern: null };

test("threshold, district, type and pattern each narrow the list", () => {
  const shown = (filters) => fc.features.filter((f) => passesFilters(f.properties, filters)).map((f) => f.properties.rank);
  assert.deepEqual(shown(base), [1, 2, 300]);
  assert.deepEqual(shown({ ...base, districts: [7] }), [300]);
  assert.deepEqual(shown({ ...base, types: ["market", "mobile"] }), [2, 300]);
  assert.deepEqual(shown({ ...base, pattern: "vermin" }), [1, 300]);
  assert.deepEqual(shown({ ...base, threshold: 1000, districts: [] }), [1, 2, 300, 900]);
  assert.equal(passesFilters(null, base), false);
});

test("chips and types only list what the shortlist contains", () => {
  assert.deepEqual(chipsFor(fc, 500).map((c) => c.key), ["vermin"]);
  assert.deepEqual(chipsFor({ features: [site(1, 1, "bar")] }).map((c) => c.key), []);
  assert.deepEqual(typesFor(fc, 500).map((t) => [t.key, t.count]), [["restaurant", 1], ["market", 1], ["mobile", 1]]);
  assert.equal(typesFor(fc, 1000)[3].label, "Bar");
});
