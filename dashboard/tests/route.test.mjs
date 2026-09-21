import { test } from "node:test";
import assert from "node:assert/strict";
import { SAME_NODE_M, nearbySites } from "../src/lib/geo.js";
import { cornersAlong, cornersNear, fmtKm } from "../src/lib/route.js";

const f = (rank, lon, lat) => ({ properties: { rank }, geometry: { coordinates: [lon, lat] } });
// A straight east-west path along latitude 32.75 from -117.11 to -117.10 (about 940 m).
const path = [[-117.11, 32.75], [-117.10, 32.75]];

test("corners within 35 m of the path come back in route order", () => {
  const on = f(1, -117.108, 32.75);         // on the line, about 190 m along
  const near = f(2, -117.103, 32.7502);     // about 22 m north of the line, 660 m along
  const off = f(3, -117.105, 32.751);       // about 110 m north: excluded
  const result = cornersAlong(path, [off, near, on], 35);
  assert.deepEqual(result.map((r) => r.feature.properties.rank), [1, 2]);
  assert.ok(result[0].alongM < result[1].alongM);
  assert.ok(result[1].meters > 15 && result[1].meters < 30);
});

test("corners near a point sort by distance and respect the radius", () => {
  const here = [-117.10, 32.75];
  const a = f(1, -117.101, 32.75);   // about 94 m
  const b = f(2, -117.1003, 32.75);  // about 28 m
  const c = f(3, -117.11, 32.75);    // about 940 m
  assert.deepEqual(cornersNear(here, [a, b, c], 500).map((r) => r.feature.properties.rank), [2, 1]);
});

test("distances format for a list", () => {
  assert.equal(fmtKm(180), "180 m");
  assert.equal(fmtKm(2340), "2.3 km");
});

test("a listed node a few metres from another counts as the same intersection", () => {
  assert.ok(SAME_NODE_M >= 20 && SAME_NODE_M <= 40, `SAME_NODE_M = ${SAME_NODE_M}`);
  const here = f(6, -117.1, 32.7);
  const twin = f(491, -117.1 + 0.0001, 32.7); // about 9 m east
  const near = nearbySites(here, { features: [here, twin] });
  assert.equal(near.length, 1);
  assert.ok(near[0].meters < SAME_NODE_M);
});
