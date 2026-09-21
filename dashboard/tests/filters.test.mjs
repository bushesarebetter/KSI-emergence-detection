import { test } from "node:test";
import assert from "node:assert/strict";
import { passesFilters, chipsFor } from "../src/lib/filters.js";

const hist = (recent, earlier) => [
  ...[2016, 2017, 2018, 2019, 2020, 2021].map((year) => ({ year, pdo: earlier, injury: 0, ksi: 0 })),
  ...[2022, 2023, 2024].map((year) => ({ year, pdo: recent, injury: 0, ksi: 0 })),
];
const site = (rank, district, labels, history) => ({
  properties: { rank, council_district: district, shap_features: labels.map((display_label) => ({ display_label })), crash_history: history },
});

test("threshold, district and pattern filters compose", () => {
  const p = site(120, 3, ["Transit stop 30 m away"], hist(1, 1)).properties;
  assert.equal(passesFilters(p, { threshold: 100, districts: [], pattern: null }), false);
  assert.equal(passesFilters(p, { threshold: 200, districts: [4], pattern: null }), false);
  assert.equal(passesFilters(p, { threshold: 200, districts: [3], pattern: "ped" }), true);
  assert.equal(passesFilters(p, { threshold: 200, districts: [3], pattern: "left" }), false);
});

test("rising comes from the crash history, not the signals", () => {
  const rising = site(5, 1, [], hist(3, 1)).properties;
  const flat = site(6, 1, [], hist(1, 1)).properties;
  assert.equal(passesFilters(rising, { threshold: 800, districts: [], pattern: "rising" }), true);
  assert.equal(passesFilters(flat, { threshold: 800, districts: [], pattern: "rising" }), false);
});

test("chips are offered only for situations present in the export", () => {
  const fc = { features: [site(1, 1, ["Transit stop 30 m away"], hist(1, 1)), site(2, 2, ["72 km/h speed limit"], hist(3, 1))] };
  assert.deepEqual(chipsFor(fc).map((c) => c.key), ["ped", "speed", "rising"]);
  assert.deepEqual(chipsFor({ features: [] }), []);
});
