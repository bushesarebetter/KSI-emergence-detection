import { test } from "node:test";
import assert from "node:assert/strict";
import { tokenize, searchIntersections } from "../src/lib/search.js";

const site = (rank, intersection_name) => ({ properties: { rank, intersection_name } });
const features = [
  site(26, "Balboa Avenue & Mount Everest Boulevard"),
  site(120, "Balboa Avenue & Genesee Avenue"),
  site(8, "Genesee Avenue & Scripps Hospital Drive"),
  site(300, "El Cajon Boulevard & 30th Street"),
  site(310, "Del Cajon Court & Main Street"),
  site(45, "Detroit Place & Duluth Avenue"),
];
const names = (q) => searchIntersections(features, q).map((f) => f.properties.intersection_name);

test("words match in any order, with the separators people type for a crossing", () => {
  assert.deepEqual(tokenize("balboa and genesee"), ["balboa", "genesee"]);
  assert.deepEqual(tokenize("Genesee & Balboa"), ["genesee", "balboa"]);
  assert.deepEqual(tokenize("balboa x genesee"), ["balboa", "genesee"]);
  assert.deepEqual(tokenize("balboa/genesee"), ["balboa", "genesee"]);
  assert.deepEqual(names("genesee and balboa"), ["Balboa Avenue & Genesee Avenue"]);
  assert.deepEqual(names("balboa & genesee"), ["Balboa Avenue & Genesee Avenue"]);
});

test("street-type abbreviations expand", () => {
  assert.deepEqual(tokenize("genesee ave"), ["genesee", "avenue"]);
  assert.deepEqual(tokenize("El Cajon Blvd."), ["el", "cajon", "boulevard"]);
  assert.deepEqual(names("el cajon blvd"), ["El Cajon Boulevard & 30th Street"]);
});

test("a match at the start of a word outranks one inside a word", () => {
  assert.deepEqual(names("cajon"), ["El Cajon Boulevard & 30th Street", "Del Cajon Court & Main Street"]);
  assert.deepEqual(names("el cajon")[0], "El Cajon Boulevard & 30th Street");
});

test("ties break on rank, and missing words exclude a name", () => {
  const both = names("genesee");
  assert.equal(both[0], "Genesee Avenue & Scripps Hospital Drive", "rank 8 before rank 120 when both match at a word start");
  assert.deepEqual(names("genesee duluth"), []);
  assert.deepEqual(searchIntersections(features, "   "), []);
  assert.deepEqual(searchIntersections(null, "balboa"), []);
});
