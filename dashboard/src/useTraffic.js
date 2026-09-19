import { useEffect, useState } from "react";

/**
 * /data/traffic.json: City of San Diego daily traffic counts joined to each
 * exported site by scripts/join_traffic_counts.py, keyed by the site's
 * coordinates. Optional: an export without it simply shows no traffic figures.
 */
export default function useTraffic() {
  const [traffic, setTraffic] = useState(null);
  useEffect(() => {
    let cancelled = false;
    fetch("/data/traffic.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((t) => { if (!cancelled) setTraffic(t); })
      .catch(() => { if (!cancelled) setTraffic(null); });
    return () => { cancelled = true; };
  }, []);
  return traffic;
}

export function pointKey(feature) {
  const [lon, lat] = feature.geometry.coordinates;
  return `${lat.toFixed(6)},${lon.toFixed(6)}`;
}

/** {legs: [{street, adt, year, method}], entering, complete} or null. */
export function trafficFor(traffic, feature) {
  if (!traffic?.sites || !feature) return null;
  return traffic.sites[pointKey(feature)] ?? null;
}
