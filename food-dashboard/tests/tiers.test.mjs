import { test } from "node:test";
import assert from "node:assert/strict";
import { tierLift, liftSentence } from "../src/lib/tiers.js";

const meta = { candidates: 8200, catch: { 50: { caught: 1, total: 697 }, 100: { caught: 2, total: 697 }, 500: { caught: 64, total: 697 } } };

test("the place's K is the smallest shortlist that contains it", () => {
  assert.equal(tierLift(1, meta).k, 50);
  assert.equal(tierLift(51, meta).k, 100);
  assert.equal(tierLift(300, meta).k, 500);
  assert.equal(tierLift(501, meta), null);
  assert.equal(tierLift(3, { candidates: 0, catch: {} }), null);
});

test("sentences show the counts, withhold a ratio below three events, and speak of inspections", () => {
  // 64/500 = 12.8% against a base rate of 697/8,200 = 8.5%: about 1.5 times.
  assert.match(liftSentence(300, meta), /had a major violation at their next inspection at about 1\.5 times the rate of an average place: 64 of 500, against 697 of 8,200/);
  assert.match(liftSentence(12, meta), /^One of the 50 places .* too few events to put a ratio on/);
  assert.match(liftSentence(60, meta, { advanced: true }), /too few events for a ratio/);
  assert.match(liftSentence(300, meta, { advanced: true }), /^Top 500: 64 of 697 positives/);
});
