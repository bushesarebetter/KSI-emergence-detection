/**
 * Find intersections by name the way people type them.
 *
 * "balboa and genesee", "Genesee & Balboa", "balboa x genesee", "genesee ave"
 * all mean "Balboa Avenue & Genesee Avenue". The query is split into words on
 * the separators people use for a crossing, common street-type abbreviations
 * are expanded, and every word must appear somewhere in the name, in any
 * order. Matches at the start of a word rank first, then earlier matches,
 * then the corner's rank.
 */
const SEPARATORS = /\s*(?:&|\/|@|,|\+|\band\b|\bx\b|\bat\b|\bwith\b)\s*|\s+/i;

const ABBREVIATIONS = {
  st: "street", ave: "avenue", av: "avenue", blvd: "boulevard", bl: "boulevard", rd: "road",
  dr: "drive", ln: "lane", ct: "court", pl: "place", pkwy: "parkway", hwy: "highway",
  ter: "terrace", cir: "circle", trl: "trail", wy: "way",
};

export function tokenize(query) {
  return String(query ?? "")
    .toLowerCase()
    .split(SEPARATORS)
    .map((t) => t.trim().replace(/\.$/, ""))
    .filter(Boolean)
    .map((t) => ABBREVIATIONS[t] ?? t);
}

/** Lower is better; -1 means a token is missing. */
export function scoreName(name, tokens) {
  const n = String(name ?? "").toLowerCase();
  let score = 0;
  for (const t of tokens) {
    const idx = n.indexOf(t);
    if (idx === -1) return -1;
    const atBoundary = idx === 0 || n[idx - 1] === " " || n[idx - 1] === "&";
    score += (atBoundary ? 0 : 500) + idx;
  }
  return score;
}

export function searchIntersections(features, query, max = 8) {
  const tokens = tokenize(query);
  if (!tokens.length || !features) return [];
  return features
    .map((f) => ({ f, s: scoreName(f.properties?.intersection_name, tokens) }))
    .filter((r) => r.s >= 0)
    .sort((a, b) => a.s - b.s || (a.f.properties.rank ?? 0) - (b.f.properties.rank ?? 0))
    .slice(0, max)
    .map((r) => r.f);
}
