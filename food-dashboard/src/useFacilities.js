import { useState, useEffect, useMemo } from "react";

const parse = (v) => (typeof v === "string" ? JSON.parse(v) : v);

/**
 * The export, fetched once. Array-valued properties may arrive as JSON
 * strings when the export was written through a GIS library, so they are
 * parsed here and nowhere else.
 */
export default function useFacilities() {
  const [facilities, setFacilities] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/data/facilities.geojson");
        if (!res.ok) throw new Error(`The list did not load (${res.status}).`);
        const fc = await res.json();
        const parsed = {
          ...fc,
          features: fc.features.map((f) => ({
            ...f,
            properties: {
              ...f.properties,
              inspections: parse(f.properties.inspections) ?? [],
              violations: parse(f.properties.violations) ?? [],
              shap_features: parse(f.properties.shap_features) ?? [],
            },
          })),
        };
        if (!cancelled) setFacilities(parsed);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Counts by council district, for the sidebar and the district filter.
  const districts = useMemo(() => {
    if (!facilities) return null;
    const counts = {};
    for (const f of facilities.features) {
      const d = f.properties.council_district;
      if (d) counts[d] = (counts[d] || 0) + 1;
    }
    return counts;
  }, [facilities]);

  return { facilities, districts, loading, error };
}
