/** Distance in metres between two [lon, lat] pairs; exact enough within a city. */
export function metersBetween(a, b) {
  const k = Math.cos((a[1] * Math.PI) / 180);
  const dx = (b[0] - a[0]) * 111320 * k;
  const dy = (b[1] - a[1]) * 110540;
  return Math.hypot(dx, dy);
}

/**
 * Other exported sites within `maxM` of a feature, nearest first. A person who
 * drives one flagged corner usually drives the next one along the same road.
 */
export function nearbySites(feature, fc, maxM = 800, n = 3) {
  if (!feature || !fc?.features) return [];
  const here = feature.geometry.coordinates;
  const out = [];
  for (const f of fc.features) {
    if (f === feature || f.properties.rank === feature.properties.rank) continue;
    const meters = metersBetween(here, f.geometry.coordinates);
    if (meters <= maxM) out.push({ feature: f, meters });
  }
  return out.sort((a, b) => a.meters - b.meters).slice(0, n);
}
