import { test } from "node:test";
import assert from "node:assert/strict";
import { intersectionsToCsv, formatPercentile } from "../src/lib/format.js";

const feature = {
  properties: {
    rank: 4, council_district: 4, intersection_name: "Paradise Valley Road & South Woodman Street", percentile: 99.9,
    crashes_training: 13, is_crash_active: true, is_known_emergent: false,
    shap_features: [{ display_label: "Transit stop 12 m away" }],
    crash_history: [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023].map((year) => ({ year, pdo: 1, injury: 0, ksi: 0 }))
      .concat([{ year: 2024, pdo: 0, injury: 3, ksi: 1 }]),
    near_school: { name: "Kimball Elementary", meters: 140, kind: "school" },
  },
  geometry: { coordinates: [-117.05, 32.7] },
};
const key = "32.700000,-117.050000";

test("the CSV carries the grant-handoff columns", () => {
  const csv = intersectionsToCsv([feature], {
    traffic: { sites: { [key]: { entering: 18000, complete: false } } },
    recent: { sites: { [key]: { count: 3, injured: 3, killed: 0 } } },
    control: { sites: { [key]: { control: "signals" } } },
  });
  const [header, row] = csv.split("\n");
  const cols = header.split(",");
  const vals = row.split(",");
  const get = (name) => vals[cols.indexOf(name)];
  assert.equal(get("rank"), "4");
  assert.equal(get("intersection_name"), "Paradise Valley Road & South Woodman Street");
  assert.equal(get("vehicles_per_day"), "18000");
  assert.equal(get("traffic_complete"), "false");
  assert.equal(get("control"), "signals");
  assert.equal(get("near_school"), "Kimball Elementary");
  assert.equal(get("near_school_m"), "140");
  assert.equal(get("police_since_cutoff"), "3");
  assert.equal(get("police_people_hurt"), "3");
  assert.equal(get("injury_crashes_2024"), "4");
  assert.equal(get("injury_gap_to_city_screen_2024"), "1");
  assert.equal(get("pattern"), "Near a school", "a school within 300 m outranks the transit stop");
});

test("the older call shape and missing context still produce a row", () => {
  const csv = intersectionsToCsv([feature], { sites: {} });
  const [header, row] = csv.split("\n");
  assert.equal(header.split(",").length, row.split(",").length);
  assert.match(row, /,,/, "empty cells for absent context");
});

test("names with commas are quoted", () => {
  const f = { ...feature, properties: { ...feature.properties, intersection_name: "A Street, North & B Avenue" } };
  const row = intersectionsToCsv([f]).split("\n")[1];
  assert.match(row, /"A Street, North & B Avenue"/);
});

test("percentile ordinals", () => {
  assert.equal(formatPercentile(99.9), "99.9th");
  assert.equal(formatPercentile(1), "1st");
  assert.equal(formatPercentile(12), "12th");
});

test("the CSV carries the severity history a grant worksheet asks for", () => {
  const csv = intersectionsToCsv([feature]);
  const [header, row] = csv.split("\n");
  const cols = header.split(",");
  const vals = row.split(",");
  const get = (name) => vals[cols.indexOf(name)];
  assert.equal(get("pdo_2020_2024"), "4", "2020 to 2023 one each, 2024 none");
  assert.equal(get("injury_2020_2024"), "3");
  assert.equal(get("ksi_2020_2024"), "1");
  assert.equal(get("injury_crashes_per_year_2016_2024"), (4 / 9).toFixed(2));
});
