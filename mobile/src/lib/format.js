export function formatPercentile(p) {
  const fixed = Number.isInteger(p) ? p : parseFloat(Number(p).toFixed(1));
  const str = fixed % 1 === 0 ? String(Math.round(fixed)) : fixed.toFixed(1);
  const n = Math.round(fixed);
  if (n % 100 >= 11 && n % 100 <= 13) return `${str}th`;
  switch (n % 10) {
    case 1: return `${str}st`;
    case 2: return `${str}nd`;
    case 3: return `${str}rd`;
    default: return `${str}th`;
  }
}

// Great-circle distance in miles, for the "nearest to me" sort.
export function haversineMiles(lat1, lon1, lat2, lon2) {
  const R = 3958.8;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}
