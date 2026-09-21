/**
 * What a rank is worth, in the only terms the export can back.
 *
 * The model produces an ordering, not a probability. meta.json records, for
 * each shortlist size K, how many of the year's serious-crash corners the top
 * K contained. That gives an honest statement for any corner: "the top K, which
 * this corner is in, had a serious crash at about N times the rate of an
 * average candidate", with the raw counts shown so the reader can see how
 * small they are. Per-tier slices (101 to 200 alone) rest on one or two events
 * and are not shown; the cumulative figure at the corner's own K is.
 */
export const MIN_EVENTS_FOR_RATIO = 3;

export function tierLift(rank, meta) {
  const catchTable = meta?.catch;
  const candidates = meta?.candidates;
  if (!catchTable || !candidates || !(rank > 0)) return null;
  const ks = Object.keys(catchTable).map(Number).filter((k) => k >= rank).sort((a, b) => a - b);
  if (!ks.length) return null;
  const k = ks[0];
  const { caught, total } = catchTable[String(k)] ?? {};
  if (!(total > 0)) return null;
  const rateInTop = caught / k;
  const baseRate = total / candidates;
  return { k, caught, total, candidates, lift: baseRate > 0 ? rateInTop / baseRate : null };
}

/** A sentence for the panel, or null when the export cannot support one. */
export function liftSentence(rank, meta, { advanced = false } = {}) {
  const t = tierLift(rank, meta);
  if (!t || t.lift == null) return null;
  const times = t.lift >= 10 ? Math.round(t.lift) : Math.round(t.lift * 10) / 10;
  const shortlistPct = (100 * t.caught / t.k).toFixed(1);
  const basePct = (100 * t.total / t.candidates).toFixed(2);
  const all = t.candidates.toLocaleString();
  // A ratio on one or two events is noise dressed as a number; the counts are
  // shown and the ratio is withheld until there are at least three.
  const fewEvents = t.caught < MIN_EVENTS_FOR_RATIO;
  if (advanced) {
    return fewEvents
      ? `Top ${t.k}: ${t.caught} of ${t.total} 2025 positives (${shortlistPct}% of the shortlist; base rate ${basePct}%; too few events for a ratio).`
      : `Top ${t.k}: ${t.caught} of ${t.total} 2025 positives (${shortlistPct}% of the shortlist, ${times}× the base rate of ${basePct}%).`;
  }
  if (t.caught === 0) {
    return `None of the ${t.k} corners ranked this high or higher had a serious crash in 2025 so far; ${t.total} of all ${all} did.`;
  }
  if (fewEvents) {
    return `${t.caught === 1 ? "One" : "Two"} of the ${t.k} corners ranked this high or higher had a serious crash in 2025 so far, against ${t.total} of all ${all}: too few events to put a ratio on.`;
  }
  return `Corners ranked in the top ${t.k}, which includes this one, had a serious crash in 2025 so far at about ${times} times the rate of an average candidate: ${t.caught} of ${t.k}, against ${t.total} of ${all}.`;
}
