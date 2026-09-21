import { test } from "node:test";
import assert from "node:assert/strict";
import { councilMessage, districtMessage, citation } from "../src/lib/ask.js";

const feature = {
  properties: {
    rank: 12, council_district: 3, intersection_name: "30th Street & El Cajon Boulevard",
    shap_features: [{ display_label: "2 left-turn crashes (72 months)" }, { display_label: "Transit stop 20 m away" }],
    crash_history: [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024].map((year) => ({ year, pdo: 1, injury: 1, ksi: 0 })),
  },
  geometry: { coordinates: [-117.13, 32.755] },
};

test("the council message quotes only what the panel shows and ends with the ask", () => {
  const text = councilMessage({
    feature, traffic: { entering: 33012, complete: true }, police: { count: 2, injured: 1, killed: 0 },
    control: "signals", candidates: 25034, url: "https://example.org/map?site=12",
  });
  assert.match(text, /^Subject: 30th Street & El Cajon Boulevard, District 3/);
  assert.match(text, /number 12 of 25,034/);
  assert.match(text, /2 of the crashes here in the last 6 years were left turns/);
  assert.match(text, /About 33,000 vehicles a day/);
  assert.match(text, /Police have logged 2 crashes/);
  assert.match(text, /injury crashes short of the 5/);
  assert.match(text, /Leading pedestrian interval/);
  assert.match(text, /engineering review[\s\S]*Highway Safety Improvement Program/);
  assert.doesNotMatch(text, /undefined|NaN/);
});

test("the district message and the citation carry their numbers", () => {
  const d = districtMessage({ district: 3, listed: 135, top100: 11, gapCount: 4, costLo: "$253,000", costHi: "$1.4 million", url: "https://example.org/district/3" });
  assert.match(d, /135 corners in District 3/);
  assert.match(d, /\$253,000 to \$1\.4 million/);
  const c = citation({ feature, candidates: 25034, url: "https://example.org/map?site=12" });
  assert.match(c, /^Zhang, C\., and Pendharkar, A\. \(\d{4}\)\. San Diego Intersection Risk: 30th Street & El Cajon Boulevard, rank 12 of 25,034/);
  assert.match(c, /Retrieved \d{4}-\d{2}-\d{2}\.$/);
});
