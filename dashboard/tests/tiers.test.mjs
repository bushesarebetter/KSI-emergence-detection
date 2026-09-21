import { test } from "node:test";
import assert from "node:assert/strict";
import { tierLift, liftSentence } from "../src/lib/tiers.js";

const meta = {
  candidates: 25034,
  catch: { 50: { caught: 1, total: 62 }, 100: { caught: 2, total: 62 }, 500: { caught: 9, total: 62 }, 800: { caught: 11, total: 62 } },
};

test("the corner's K is the smallest shortlist that contains it", () => {
  assert.equal(tierLift(1, meta).k, 50);
  assert.equal(tierLift(50, meta).k, 50);
  assert.equal(tierLift(51, meta).k, 100);
  assert.equal(tierLift(300, meta).k, 500);
  assert.equal(tierLift(801, meta), null, "beyond the largest K there is nothing to say");
});

test("lift is the top-K rate over the base rate", () => {
  const t = tierLift(300, meta);
  assert.equal(t.caught, 9);
  assert.ok(Math.abs(t.lift - (9 / 500) / (62 / 25034)) < 1e-9);
});

test("sentences show the raw counts and never invent a probability", () => {
  const plain = liftSentence(300, meta);
  assert.match(plain, /top 500/);
  assert.match(plain, /9 of 500, against 62 of 25,034/);
  assert.match(plain, /times the rate of an average candidate/);
  const tech = liftSentence(300, meta, { advanced: true });
  assert.match(tech, /^Top 500: 9 of 62 2025 positives/);
  assert.equal(liftSentence(5, { candidates: 0, catch: {} }), null);
});

test("a shortlist with no catches says so plainly", () => {
  const m = { candidates: 1000, catch: { 10: { caught: 0, total: 5 } } };
  assert.match(liftSentence(3, m), /None of the 10 corners/);
});

test("one or two events get their counts but no ratio", () => {
  const one = liftSentence(12, meta);
  assert.match(one, /^One of the 50 corners/);
  assert.match(one, /too few events to put a ratio on/);
  assert.doesNotMatch(one, /times the rate/);
  const two = liftSentence(60, meta);
  assert.match(two, /^Two of the 100 corners/);
  const tech = liftSentence(12, meta, { advanced: true });
  assert.match(tech, /too few events for a ratio/);
  assert.doesNotMatch(tech, /×/);
});
