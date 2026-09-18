/**
 * Deep links: `/?site=<rank>` opens that intersection on load.
 *
 * Rank is stable, unique, and already the identifier people see, so it doubles
 * as the URL key. The address bar becomes the share link -- text someone
 * `…/?site=43` and they land on intersection #43 -- which is what "a web app
 * for everyone" needs without adding a share button to the interface.
 *
 * `replaceState` rather than `pushState`: selecting dots should not fill the
 * back button with forty history entries.
 */
const PARAM = "site";

export function readSiteFromUrl() {
  if (typeof window === "undefined") return null;
  const raw = new URLSearchParams(window.location.search).get(PARAM);
  const rank = raw == null ? NaN : parseInt(raw, 10);
  return Number.isFinite(rank) && rank > 0 ? rank : null;
}

export function writeSiteToUrl(rank) {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (rank) url.searchParams.set(PARAM, String(rank));
  else url.searchParams.delete(PARAM);
  window.history.replaceState(null, "", url);
}
