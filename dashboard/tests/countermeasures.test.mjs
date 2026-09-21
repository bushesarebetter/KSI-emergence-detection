import { test } from "node:test";
import assert from "node:assert/strict";
import { measuresFor, costRange, screenGap, fmtMoney, fmtRange, MEASURES, CITY_SCREEN } from "../src/lib/countermeasures.js";

const labels = (...ls) => ({ shap_features: ls.map((display_label) => ({ display_label })) });

test("measures follow the corner's control: no beacon at a signal, no LPI at a stop sign", () => {
  const ped = labels("2 pedestrian crashes (72 months)");
  const atSignal = measuresFor(ped, "signals").map((m) => m.key);
  const atStop = measuresFor(ped, "stop").map((m) => m.key);
  assert.ok(atSignal.includes("lpi") && !atSignal.includes("rrfb"));
  assert.ok(atStop.includes("rrfb") && !atStop.includes("lpi"));
  assert.equal(atSignal.at(-1), "review", "the review is always the last ask");
});

test("a roundabout is never suggested as an ask", () => {
  const left = labels("4 left-turn crashes (72 months)", "1 broadside crashes (72 months)");
  assert.ok(!measuresFor(left, null).some((m) => m.key === "roundabout"));
});

test("cost range sums the non-review measures", () => {
  const ms = measuresFor(labels("2 pedestrian crashes (72 months)"), "signals");
  const [lo, hi] = costRange(ms);
  const expected = ms.filter((m) => m.key !== "review").reduce((a, m) => [a[0] + m.cost[0], a[1] + m.cost[1]], [0, 0]);
  assert.deepEqual([lo, hi], expected);
});

test("screen gap counts injury crashes in the last full year", () => {
  const history = [{ year: 2024, pdo: 4, injury: 2, ksi: 1 }];
  assert.deepEqual(screenGap(history), { year: 2024, injuryCrashes: 3, gap: CITY_SCREEN - 3 });
  assert.equal(screenGap([{ year: 2024, pdo: 0, injury: 6, ksi: 0 }]).gap, 0);
  assert.equal(screenGap([]), null);
});

test("money formats read like prose", () => {
  assert.equal(fmtMoney(1200), "$1,000");
  assert.equal(fmtMoney(15_988_000), "$16 million");
  assert.equal(fmtMoney(1_705_100), "$1.7 million");
  assert.equal(fmtRange([25000, 200000], "mile"), "$25,000 to $200,000 a mile");
});

test("every measure names a cost range and the patterns it addresses", () => {
  for (const m of MEASURES) {
    assert.ok(m.cost[0] > 0 && m.cost[1] >= m.cost[0], m.key);
    assert.ok(m.applies.length > 0, m.key);
  }
});

test("every measure carries a service life in whole years", () => {
  for (const m of MEASURES) {
    assert.ok(Number.isInteger(m.life) && m.life >= 5 && m.life <= 30, `${m.key}: ${m.life}`);
  }
});
