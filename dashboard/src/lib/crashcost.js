/**
 * The dollar figures the funding case rests on, each with its source.
 *
 * Crash costs are the ones the pipeline uses (scripts/compute_verified_numbers.py):
 * FHWA comprehensive crash costs, FHWA-SA-25-021 (October 2025), in 2024 dollars.
 * The program figures are this project's own estimate for treating the top-500
 * shortlist, as stated in the README with its two assumptions: the City's cost
 * per corner after the federal share, and a 30% treatment effectiveness.
 */
export const CRASH_COST = {
  fatal: 15_988_000,
  serious: 1_705_100,
};

export const CRASH_COST_SOURCE = {
  label: "FHWA, Crash Costs for Highway Safety Analysis, FHWA-SA-25-021 (October 2025), 2024 dollars",
  short: "FHWA-SA-25-021, 2024 dollars",
  url: "https://highways.dot.gov/safety/data-analysis-tools",
};

export const PROGRAM = {
  label: "the README's top-500 estimate",
  sites: 500,
  cityCost: 3_200_000,
  federalShare: 0.9,
  effectiveness: 0.3,
  preventedHarm: 62_000_000,
  bcr: 19,
};
