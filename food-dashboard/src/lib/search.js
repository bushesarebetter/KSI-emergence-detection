/**
 * Find places by name or street the way people type them.
 *
 * "taco convoy", "Sample Kitchen", "garnet ave": the query is split into
 * words, street-type abbreviations are expanded, and every word must appear
 * somewhere in the name or the address, in any order. Matches at the start
 * of a word rank first, then earlier matches, then the place's rank.
 */
const SEPARATORS = /\s*(?:&|\/|@|,|\+|\band\b|\bat\b|\bon\b)\s*|\s+/i;

const ABBREVIATIONS = {
  st: "street", ave: "avenue", av: "avenue", blvd: "boulevard", rd: "road", dr: "drive", ln: "lane",
  ct: "court", pl: "place", pkwy: "parkway", hwy: "highway", ter: "terrace", cir: "circle",
};

export function tokenize(query) {
  return String(query ?? "")
    .toLowerCase()
    .split(SEPARATORS)
    .map((t) => t.trim().replace(/\.$/, ""))
    .filter(Boolean)
    .map((t) => ABBREVIATIONS[t] ?? t);
}

// Addresses in the export use the County's abbreviations; expand them once so
// "garnet ave" and "garnet avenue" both match "Garnet Ave".
const expand = (s) => String(s ?? "").toLowerCase().replace(/\b(st|ave|av|blvd|rd|dr|ln|ct|pl|pkwy|hwy|ter|cir)\b\.?/g, (m) => ABBREVIATIONS[m.replace(".", "")] ?? m);

/** Lower is better; -1 means a token is missing. */
export function scoreText(text, tokens) {
  const n = expand(text);
  let score = 0;
  for (const t of tokens) {
    const idx = n.indexOf(t);
    if (idx === -1) return -1;
    const atBoundary = idx === 0 || /[\s,&]/.test(n[idx - 1]);
    score += (atBoundary ? 0 : 500) + idx;
  }
  return score;
}

export function searchPlaces(features, query, max = 8) {
  const tokens = tokenize(query);
  if (!tokens.length || !features) return [];
  return features
    .map((f) => ({ f, s: scoreText(`${f.properties?.name ?? ""} ${f.properties?.address ?? ""}`, tokens) }))
    .filter((r) => r.s >= 0)
    .sort((a, b) => a.s - b.s || (a.f.properties.rank ?? 0) - (b.f.properties.rank ?? 0))
    .slice(0, max)
    .map((r) => r.f);
}
