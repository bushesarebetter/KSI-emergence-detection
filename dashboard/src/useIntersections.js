import { useState, useEffect } from "react";

export default function useIntersections() {
  const [intersections, setIntersections] = useState(null);
  const [districts, setDistricts] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const [geoRes, distRes] = await Promise.all([
          fetch("/data/intersections.geojson"),
          fetch("/data/districts.json"),
        ]);

        if (!geoRes.ok) throw new Error(`Failed to load intersections: ${geoRes.status}`);
        if (!distRes.ok) throw new Error(`Failed to load districts: ${distRes.status}`);

        const [geoData, distData] = await Promise.all([geoRes.json(), distRes.json()]);

        const parsed = {
          ...geoData,
          features: geoData.features.map((f) => ({
            ...f,
            properties: {
              ...f.properties,
              crash_history: typeof f.properties.crash_history === "string"
                ? JSON.parse(f.properties.crash_history)
                : f.properties.crash_history,
              shap_features: typeof f.properties.shap_features === "string"
                ? JSON.parse(f.properties.shap_features)
                : f.properties.shap_features,
            },
          })),
        };

        setIntersections(parsed);
        setDistricts(distData);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return { intersections, districts, loading, error };
}
