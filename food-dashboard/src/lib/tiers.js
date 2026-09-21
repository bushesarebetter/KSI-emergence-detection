/**
 * What a rank is worth, in the only terms the export can back.
 *
 * The model produces an ordering, not a probability. meta.json records, for
 * each shortlist size K, how many of the places that went on to have a major
 * violation at their next inspection the top K contained. That gives an
 * honest sentence for any place, with the raw counts shown. A ratio on one or
 * two events is noise with a number on it, so it is withheld below three.
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

export function liftSentence(rank, meta, { advanced = false } = {}) {
  const t = tierLift(rank, meta);
  if (!t || t.lift == null) return null;
  const times = t.lift >= 10 ? Math.round(t.lift) : Math.round(t.lift * 10) / 10;
  const shortlistPct = (100 * t.caught / t.k).toFixed(1);
  const basePct = (100 * t.total / t.candidates).toFixed(2);
  const all = t.candidates.toLocaleString();
  const fewEvents = t.caught < MIN_EVENTS_FOR_RATIO;
  if (advanced) {
    return fewEvents
      ? `Top ${t.k}: ${t.caught} of ${t.total} positives (${shortlistPct}% of the shortlist; base rate ${basePct}%; too few events for a ratio).`
      : `Top ${t.k}: ${t.caught} of ${t.total} positives (${shortlistPct}% of the shortlist, ${times}× the base rate of ${basePct}%).`;
  }
  if (t.caught === 0) {
    return `None of the ${t.k} places ranked this high or higher had a major violation at their next inspection; ${t.total} of all ${all} did.`;
  }
  if (fewEvents) {
    return `${t.caught === 1 ? "One" : "Two"} of the ${t.k} places ranked this high or higher had a major violation at their next inspection, against ${t.total} of all ${all}: too few events to put a ratio on.`;
  }
  return `Places ranked in the top ${t.k}, which includes this one, had a major violation at their next inspection at about ${times} times the rate of an average place: ${t.caught} of ${t.k}, against ${t.total} of ${all}.`;
}
