#!/usr/bin/env node
/**
 * Check the export the site is about to ship.
 *
 * Fails the build when the export breaks the contract (docs/FOOD_DATA_CONTRACT.md):
 * ranks not 1..N, a place without a name or an address, signal labels outside
 * the vocabulary the plain-language rewrites know, or a shortlist where most
 * places would get no "If you eat here" item. Prints a summary otherwise.
 */
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const data = join(root, "public", "data");
const lib = (name) => import(pathToFileURL(join(root, "src", "lib", name)).href);

const { adviceFor, patternOf } = await lib("advice.js");
const { chipsFor, typesFor } = await lib("filters.js");
const { knownLabel } = await lib("signals.js");
const { inspectionStats } = await lib("inspections.js");

const readJson = (name) => (existsSync(join(data, name)) ? JSON.parse(readFileSync(join(data, name), "utf8")) : null);
const fc = readJson("facilities.geojson");
if (!fc) {
  console.error("FAIL: public/data/facilities.geojson is missing");
  process.exit(1);
}
const meta = readJson("meta.json");
const TOP = 500;

const ranks = fc.features.map((f) => f.properties.rank).sort((a, b) => a - b);
const contiguous = ranks.every((r, i) => r === i + 1);
const top = fc.features.filter((f) => f.properties.rank <= TOP);
let noAdvice = 0, unknownLabels = 0, labels = 0, missing = 0, noRecord = 0, worsening = 0, closed = 0;
const lead = {};
for (const f of top) {
  const p = f.properties;
  if (!p.name || !p.address || !p.facility_type) missing++;
  const s = inspectionStats(p);
  if (!s) noRecord++;
  else {
    if (s.trend === "worsening") worsening++;
    if (s.closures > 0) closed++;
  }
  for (const sf of p.shap_features ?? []) {
    labels++;
    if (!knownLabel(sf.display_label)) unknownLabels++;
  }
  const items = adviceFor(p);
  if (!items.length) noAdvice++;
  const k = patternOf(p) ?? "(none)";
  lead[k] = (lead[k] || 0) + 1;
}

const caught = meta?.catch?.[String(TOP)];
console.log(`export: ${fc.features.length} places; ${meta?.sample ? "SAMPLE DATA; " : ""}run ${meta?.run ?? "?"}, ${meta?.candidates ?? "?"} candidates, inspections through ${meta?.inspections_through ?? "?"}${caught ? `, ${caught.caught}/${caught.total} caught at ${TOP}` : ", not scored"}`);
console.log(`top ${TOP}: advice for ${top.length - noAdvice}, no record ${noRecord}, worsening ${worsening}, closed before ${closed}`);
console.log(`types: ${typesFor(fc, TOP).map((t) => `${t.label} ${t.count}`).join("; ")}`);
console.log(`lead patterns: ${Object.entries(lead).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} ${v}`).join("; ")}`);
console.log(`chips: ${chipsFor(fc, TOP).map((c) => c.label).join(", ") || "(none)"}`);
const byDistrict = {};
for (const f of top) byDistrict[f.properties.council_district ?? "none"] = (byDistrict[f.properties.council_district ?? "none"] || 0) + 1;
console.log(`top ${TOP} by district: ${Object.entries(byDistrict).sort().map(([d, n]) => `${d}:${n}`).join("  ")}`);

let failed = false;
const fail = (msg) => { console.error(`FAIL: ${msg}`); failed = true; };
if (!contiguous) fail("ranks are not 1..N without gaps");
if (missing) fail(`${missing} of the top ${TOP} lack a name, an address or a facility type`);
if (labels && unknownLabels / labels > 0.1) fail(`${unknownLabels} of ${labels} signal labels are outside the vocabulary the rewrites know`);
if (top.length && noAdvice / top.length > 0.4) fail(`${noAdvice} of ${top.length} places would get no "If you eat here" item`);
if (meta?.catch) {
  const ks = Object.keys(meta.catch).map(Number).sort((a, b) => a - b);
  for (let i = 1; i < ks.length; i++) {
    if (meta.catch[ks[i]].caught < meta.catch[ks[i - 1]].caught) fail(`catch at ${ks[i]} is below catch at ${ks[i - 1]}`);
  }
}
if (!meta?.sample && fc.features.some((f) => /^Sample /.test(f.properties.name ?? ""))) fail("a real export contains a place named 'Sample …'");
if (failed) process.exit(1);
console.log("export check passed");
