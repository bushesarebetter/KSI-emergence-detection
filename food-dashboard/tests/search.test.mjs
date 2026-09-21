import { test } from "node:test";
import assert from "node:assert/strict";
import { tokenize, searchPlaces } from "../src/lib/search.js";

const site = (rank, name, address) => ({ properties: { rank, name, address } });
const features = [
  site(120, "Sample Taqueria 004", "1200 Garnet Ave, San Diego, CA 92109"),
  site(8, "Sample Kitchen 011", "4400 Convoy St, San Diego, CA 92111"),
  site(300, "Sample Noodle House 020", "4600 Convoy St, San Diego, CA 92111"),
  site(45, "Sample Market 031", "3100 Garnet Ave, San Diego, CA 92109"),
];
const names = (q) => searchPlaces(features, q).map((f) => f.properties.name);

test("words match the name or the street, in any order, with abbreviations expanded", () => {
  assert.deepEqual(tokenize("garnet ave."), ["garnet", "avenue"]);
  assert.deepEqual(names("garnet avenue"), ["Sample Market 031", "Sample Taqueria 004"], "both on Garnet, by rank");
  assert.deepEqual(names("convoy noodle"), ["Sample Noodle House 020"]);
  assert.deepEqual(names("kitchen on convoy"), ["Sample Kitchen 011"]);
});

test("ties break on rank and missing words exclude", () => {
  assert.deepEqual(names("convoy"), ["Sample Kitchen 011", "Sample Noodle House 020"]);
  assert.deepEqual(names("convoy garnet"), []);
  assert.deepEqual(searchPlaces(features, "  "), []);
  assert.deepEqual(searchPlaces(null, "x"), []);
});
