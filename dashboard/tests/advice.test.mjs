import { test } from "node:test";
import assert from "node:assert/strict";
import { adviceFor, patternKeys, patternOf, FILTER_PATTERNS } from "../src/lib/advice.js";
import { techLabel, humanizeSignal } from "../src/lib/signals.js";

const labels = (...ls) => ({ shap_features: ls.map((display_label) => ({ display_label })) });

test("crash-history vocabulary: left turns lead, tempo items collapse to one", () => {
  const p = labels("3 left-turn crashes (72 months)", "16 distinct crash days (72 months)", "0.4 years since last crash", "EWMA crash rate 3.1");
  const items = adviceFor(p);
  assert.equal(items[0].key, "left");
  assert.match(items[0].fact, /3 of the crashes here in the last 6 years were left turns/);
  assert.equal(items.filter((i) => ["days", "recent"].includes(i.key)).length, 1, "only the strongest tempo item survives");
});

test("E-model vocabulary: transit stop reads as people on foot, speed converts to mph", () => {
  const p = labels("Transit stop 21 m away", "72 km/h speed limit", "~5 lanes", "Stop-controlled", "Rising crash-rate trend");
  const keys = patternKeys(p);
  for (const k of ["ped", "speed", "wide", "stop", "trend"]) assert.ok(keys.has(k), `missing ${k}`);
  const speed = adviceFor(p, { max: 5 }).find((i) => i.key === "speed");
  assert.equal(speed.fact, "The speed limit here is 45 mph.");
  assert.equal(patternOf(p), "People on foot");
});

test("thresholds: a slow road and a narrow corner produce no item", () => {
  const p = labels("40 km/h speed limit", "~3 lanes", "3-leg intersection", "Arterial");
  assert.deepEqual(adviceFor(p), []);
  assert.equal(patternOf(p), null);
});

test("control changes the left-turn action", () => {
  const p = labels("2 left-turn crashes (72 months)");
  assert.match(adviceFor(p, { control: "signals" })[0].driving, /green arrow/);
  assert.match(adviceFor(p, { control: "stop" })[0].driving, /stop fully/i);
  assert.match(adviceFor(p)[0].driving, /green arrow or a gap/);
});

test("a school within 300 m leads the advice; beyond it does not appear", () => {
  const near = { ...labels("2 left-turn crashes (72 months)"), near_school: { name: "Kimball Elementary", meters: 140 } };
  assert.equal(adviceFor(near)[0].key, "school");
  assert.match(adviceFor(near)[0].fact, /Kimball Elementary is 140 m away/);
  const far = { ...labels("2 left-turn crashes (72 months)"), near_school: { name: "X", meters: 900 } };
  assert.equal(adviceFor(far)[0].key, "left");
});

test("every filter pattern has a rule that can produce it", () => {
  const produced = new Set([
    ...patternKeys(labels("1 pedestrian crashes (72 months)", "1 bicycle crashes (72 months)", "1 left-turn crashes (72 months)", "1 night crashes (72 months)")),
    ...patternKeys(labels("72 km/h speed limit", "~6 lanes", "Stop-controlled", "5-leg intersection")),
    ...patternKeys({ near_school: { name: "S", meters: 10 } }),
  ]);
  for (const { key } of FILTER_PATTERNS) assert.ok(produced.has(key), `no rule produces ${key}`);
});

test("a transit stop beyond a short walk gives no crossing advice", () => {
  const far = adviceFor(labels("Transit stop 544 m away"));
  assert.ok(!far.some((it) => it.key === "ped"), "544 m is not a reason to expect people in this crosswalk");
  const near = adviceFor(labels("Transit stop 250 m away"));
  assert.ok(near.some((it) => it.key === "ped"));
});

test("the technical label keeps the export's wording except for one plural", () => {
  assert.equal(techLabel("Last crash ~1 years ago"), "Last crash ~1 year ago");
  assert.equal(techLabel("Last crash ~2 years ago"), "Last crash ~2 years ago");
  assert.equal(techLabel("Transit stop 544 m away"), "Transit stop 544 m away");
  assert.match(humanizeSignal("Transit stop 544 m away"), /^A transit stop 544 m away$/);
  assert.match(humanizeSignal("Transit stop 21 m away"), /so people cross here/);
});
