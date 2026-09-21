/**
 * Deep links: `/map?place=<rank>` opens that place; `/map?district=3` opens
 * the map filtered to one council district. Rank is stable and already the
 * number people see, so it doubles as the URL key. replaceState, so selecting
 * dots does not fill the back button.
 */
const PLACE = "place";
const DISTRICT = "district";

const readInt = (key) => {
  if (typeof window === "undefined") return null;
  const raw = new URLSearchParams(window.location.search).get(key);
  const n = raw == null ? NaN : parseInt(raw, 10);
  return Number.isFinite(n) && n > 0 ? n : null;
};

const writeParam = (key, value) => {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (value) url.searchParams.set(key, String(value));
  else url.searchParams.delete(key);
  window.history.replaceState(null, "", url);
};

export const readPlaceFromUrl = () => readInt(PLACE);
export const writePlaceToUrl = (rank) => writeParam(PLACE, rank);
export const readDistrictFromUrl = () => readInt(DISTRICT);
export const writeDistrictToUrl = (d) => writeParam(DISTRICT, d);
