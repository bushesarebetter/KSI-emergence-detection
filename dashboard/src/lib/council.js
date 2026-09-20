import { CITY } from "../city.js";

/** Where to send a corner: the district office's public page, from the city config. */
export const COUNCIL_INDEX = CITY.districts.councilIndex;

export function councilUrl(district) {
  const d = Number(district);
  return d >= 1 && d <= CITY.districts.count ? CITY.districts.councilUrl(d) : COUNCIL_INDEX;
}
