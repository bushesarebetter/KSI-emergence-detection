import { test } from "node:test";
import assert from "node:assert/strict";
import { humanizeSignal, knownLabel, techLabel } from "../src/lib/signals.js";

test("every label in the contract's vocabulary is rewritten", () => {
  const cases = [
    ["Last routine score 84", "Scored 84 at the last routine inspection"],
    ["Grade B at last inspection", "Grade B after the last inspection"],
    ["2 major violations in the last 3 inspections", "2 major violations across the last 3 inspections"],
    ["1 major violation in the last 3 inspections", "1 major violation across the last 3 inspections"],
    ["temperature cited 3 times", "Cited 3 times for food temperatures"],
    ["vermin cited 1 time", "Cited once for pests"],
    ["Closed by the County 2025", "Closed by the County in 2025 for an imminent health hazard"],
    ["Reinspection required 2 times", "Needed a reinspection 2 times"],
    ["Risk category 3", "Risk category 3, inspected three times a year"],
    ["Facility type: mobile", "A food truck or cart"],
    ["Score falling: 96 to 84", "Score falling from 96 to 84 over recent inspections"],
    ["7 months since last inspection", "7 months since the last inspection"],
    ["2 complaints in 2 years", "2 complaints to the County in 2 years"],
    ["Neighbours' average score 88", "Nearby places average a score of 88"],
    ["Change of ownership 2025", "Changed hands in 2025"],
    ["120 seats", "About 120 seats"],
  ];
  for (const [label, expected] of cases) {
    assert.equal(humanizeSignal(label), expected, label);
    assert.ok(knownLabel(label), `known: ${label}`);
  }
});

test("an unknown label passes through unchanged and is flagged as unknown", () => {
  assert.equal(humanizeSignal("Something new 42"), "Something new 42");
  assert.equal(knownLabel("Something new 42"), false);
  assert.equal(humanizeSignal(""), "");
  assert.equal(techLabel(null), "");
});
