import { test } from "node:test";
import assert from "node:assert/strict";
import { crashRate, ratePerMillionEntering, roundVehicles, fmtPerYear } from "../src/lib/rates.js";

const years = (counts) => Object.entries(counts).map(([year, n]) => ({ year: Number(year), pdo: n, injury: 0, ksi: 0 }));

test("rate uses the nine full years and ignores the partial one", () => {
  const h = years({ 2016: 1, 2017: 1, 2018: 1, 2019: 1, 2020: 1, 2021: 1, 2022: 1, 2023: 1, 2024: 1, 2025: 9 });
  const r = crashRate(h);
  assert.equal(r.years, 9);
  assert.equal(r.perYear, 1);
  assert.equal(r.trend, "steady");
});

test("trend needs both a ratio and an absolute change", () => {
  const up = years({ 2016: 0, 2017: 0, 2018: 0, 2019: 1, 2020: 0, 2021: 1, 2022: 2, 2023: 3, 2024: 2 });
  assert.equal(crashRate(up).trend, "rising");
  const noise = years({ 2016: 0, 2017: 0, 2018: 1, 2019: 0, 2020: 0, 2021: 0, 2022: 0, 2023: 1, 2024: 0 });
  assert.equal(crashRate(noise).trend, "steady", "0.17 to 0.33 a year is noise");
  const down = years({ 2016: 3, 2017: 3, 2018: 3, 2019: 3, 2020: 3, 2021: 3, 2022: 0, 2023: 1, 2024: 0 });
  assert.equal(crashRate(down).trend, "falling");
});

test("rate per million entering vehicles", () => {
  assert.equal(ratePerMillionEntering(1, 33012).toFixed(3), (1 / (33012 * 365 / 1e6)).toFixed(3));
  assert.equal(ratePerMillionEntering(1, 0), null);
});

test("vehicle rounding keeps two significant figures", () => {
  assert.equal(roundVehicles(33012), 33000);
  assert.equal(roundVehicles(6466), 6500);
  assert.equal(roundVehicles(92), 92);
  assert.equal(fmtPerYear(1.84), "1.8");
  assert.equal(fmtPerYear(12.4), "12");
});

test("injury-only rate counts injury and KSI crashes over the same nine years", () => {
  const h = years({ 2016: 2, 2017: 2, 2018: 2, 2019: 2, 2020: 2, 2021: 2, 2022: 2, 2023: 2, 2024: 2 });
  h[8].injury = 3;
  h[8].ksi = 1;
  const r = crashRate(h);
  assert.equal(r.injuries, 4);
  assert.equal(r.injuryPerYear.toFixed(3), (4 / 9).toFixed(3));
  assert.equal(r.perYear.toFixed(3), (22 / 9).toFixed(3), "the all-crash rate includes the injury crashes");
});
