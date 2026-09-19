import { metersBetween } from "./geo.js";

/**
 * Which listed corners a route passes through.
 *
 * `path` is an array of [lon, lat] pairs (a Google Directions overview path,
 * converted). A corner counts when it lies within `maxM` of any segment of the
 * path, measured as point-to-segment distance in a local flat projection, which
 * is exact enough over a city block. Corners come back in route order, with the
 * distance along the route so a list can read "at 2.3 km".
 */

function project(lonlat, lat0) {
  const k = Math.cos((lat0 * Math.PI) / 180);
  return [lonlat[0] * 111320 * k, lonlat[1] * 110540];
}

// Distance from p to segment ab, all in projected metres, plus the parameter t
// of the closest point along ab (0 at a, 1 at b).
function pointToSegment(p, a, b) {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  let t = len2 === 0 ? 0 : ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  const cx = a[0] + t * dx;
  const cy = a[1] + t * dy;
  return { d: Math.hypot(p[0] - cx, p[1] - cy), t };
}

export function cornersAlong(path, features, maxM = 35) {
  if (!path || path.length < 2 || !features) return [];
  const lat0 = path[0][1];
  const P = path.map((c) => project(c, lat0));
  // Cumulative distance along the route at each vertex, in metres.
  const cum = [0];
  for (let i = 1; i < P.length; i++) cum.push(cum[i - 1] + Math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1]));

  const out = [];
  for (const f of features) {
    const q = project(f.geometry.coordinates, lat0);
    let best = null;
    for (let i = 1; i < P.length; i++) {
      const { d, t } = pointToSegment(q, P[i - 1], P[i]);
      if (d <= maxM && (best === null || d < best.d)) {
        best = { d, along: cum[i - 1] + t * (cum[i] - cum[i - 1]) };
      }
    }
    if (best) out.push({ feature: f, meters: best.d, alongM: best.along });
  }
  return out.sort((a, b) => a.alongM - b.alongM);
}

/** Listed corners within `maxM` of a point ([lon, lat]), nearest first. */
export function cornersNear(lonlat, features, maxM = 500) {
  if (!lonlat || !features) return [];
  const out = [];
  for (const f of features) {
    const m = metersBetween(lonlat, f.geometry.coordinates);
    if (m <= maxM) out.push({ feature: f, meters: m });
  }
  return out.sort((a, b) => a.meters - b.meters);
}

export function fmtKm(m) {
  return m < 950 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1)} km`;
}
