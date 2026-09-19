/**
 * Where to send a corner. Each council district has an office with a public
 * contact page; the member changes, the district page does not.
 */
export const COUNCIL_INDEX = "https://www.sandiego.gov/citycouncil";

export function councilUrl(district) {
  const d = Number(district);
  return d >= 1 && d <= 9 ? `${COUNCIL_INDEX}/cd${d}` : COUNCIL_INDEX;
}
