/**
 * Sanity-check the data files the dashboard ships, after every export.
 *
 *   npm run check
 *
 * Reads public/data and reports what the interface will be able to say: how
 * many corners get advice, which chips will be offered, how many carry
 * traffic, police, control and school context, and whether any signal label
 * falls through the plain-language rewrite unchanged (a new model vocabulary;
 * see DECISIONS.md D24). Exits non-zero on the failures that would ship a
 * silently empty interface.
 */
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const data = join(root, "public", "data");
const lib = (name) => import(pathToFileURL(join(root, "src", "lib", name)).href);

const { adviceFor, patternOf } = await lib("advice.js");
const { chipsFor } = await lib("filters.js");
const { humanizeSignal } = await lib("signals.js");
const { crashRate } = await lib("rates.js");
const { screenGap } = await lib("countermeasures.js");
const { metersBetween, SAME_NODE_M } = await lib("geo.js");

const readJson = (name) => (existsSync(join(data, name)) ? JSON.parse(readFileSync(join(data, name), "utf8")) : null);
const key = (f) => {
  const [lon, lat] = f.geometry.coordinates;
  return `${lat.toFixed(6)},${lon.toFixed(6)}`;
};

const fc = readJson("intersections.geojson");
if (!fc) {
  console.error("FAIL: public/data/intersections.geojson is missing");
  process.exit(1);
}
const meta = readJson("meta.json");
const traffic = readJson("traffic.json");
const recent = readJson("recent.json");
const control = readJson("control.json");

const top = fc.features.filter((f) => f.properties.rank <= 800);
let noAdvice = 0, single = 0, withTraffic = 0, withPolice = 0, withControl = 0, withSchool = 0, rising = 0, nearScreen = 0;
const unmatched = {};
const lead = {};
for (const f of top) {
  const p = f.properties;
  if (!adviceFor(p).length) noAdvice++;
  const pat = patternOf(p) ?? "(none)";
  lead[pat] = (lead[pat] || 0) + 1;
  if (!/&/.test(p.intersection_name ?? "")) single++;
  for (const s of p.shap_features ?? []) {
    const label = s.display_label ?? "";
    if (label && humanizeSignal(label) === label) {
      const k = label.replace(/[\d.]+/g, "N");
      unmatched[k] = (unmatched[k] || 0) + 1;
    }
  }
  if (traffic?.sites?.[key(f)]) withTraffic++;
  if (recent?.sites?.[key(f)]) withPolice++;
  if (control?.sites?.[key(f)]) withControl++;
  if (p.near_school) withSchool++;
  if (crashRate(p.crash_history)?.trend === "rising") rising++;
  const g = screenGap(p.crash_history);
  if (g && g.gap <= 1) nearScreen++;
}

const caught = meta?.catch?.["800"];
console.log(`export: ${fc.features.length} sites; meta run ${meta?.run ?? "?"}, ${meta?.candidates ?? "?"} candidates, ${caught?.caught ?? "?"}/${caught?.total ?? "?"} caught at 800`);
console.log(`top 800: advice for ${top.length - noAdvice}, single-street names ${single}, rising ${rising}, within one crash of the City screen ${nearScreen}`);
console.log(`context: traffic ${withTraffic}${traffic ? "" : " (no file)"}, police ${withPolice}${recent ? "" : " (no file)"}, control ${withControl}${control ? "" : " (no file)"}, schools ${withSchool}`);
console.log(`lead patterns: ${Object.entries(lead).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} ${v}`).join("; ")}`);
console.log(`chips: ${chipsFor(fc).map((c) => c.label).join(", ") || "(none)"}`);
const byDistrict = {};
for (const f of top) byDistrict[f.properties.council_district] = (byDistrict[f.properties.council_district] || 0) + 1;
let twins = 0;
for (let i = 0; i < top.length; i++) {
  for (let j = i + 1; j < top.length; j++) {
    if (metersBetween(top[i].geometry.coordinates, top[j].geometry.coordinates) <= SAME_NODE_M) twins++;
  }
}
console.log(`top 800 pairs within ${SAME_NODE_M} m (one intersection listed twice): ${twins}`);
console.log(`top 800 by district: ${Object.entries(byDistrict).sort((a, b) => a[0] - b[0]).map(([d, n]) => `${d}:${n}`).join("  ")}`);

let failed = false;
if (Object.keys(unmatched).length) {
  failed = true;
  console.error("FAIL: signal labels with no plain-language rewrite (new vocabulary?):");
  for (const [k, v] of Object.entries(unmatched)) console.error(`  ${v}  ${k}`);
}
if (noAdvice > top.length * 0.25) {
  failed = true;
  console.error(`FAIL: ${noAdvice} of the top 800 get no advice (over 25%)`);
}
if (!chipsFor(fc).length) {
  failed = true;
  console.error("FAIL: no chips would be offered");
}
for (const [name, present] of [["traffic.json", traffic], ["recent.json", recent], ["control.json", control]]) {
  if (!present) console.warn(`warn: ${name} absent; the interface omits that line`);
}
process.exit(failed ? 1 : 0);
