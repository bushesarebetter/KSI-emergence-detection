import { useState, useEffect } from "react";
import Constants from "expo-constants";

const BASE =
  Constants.expoConfig?.extra?.dataBaseUrl ??
  "https://ksi-emergence.onrender.com/data";

function parseProp(v) {
  if (typeof v === "string") {
    try {
      return JSON.parse(v);
    } catch {
      return [];
    }
  }
  return v ?? [];
}

/**
 * Loads the same two static files the web dashboard serves. Deliberately not
 * bundled into the binary: pointing at the deployed dashboard means a new model
 * export reaches users on next launch rather than on next app-store release.
 */
export default function useIntersections() {
  const [intersections, setIntersections] = useState(null);
  const [districts, setDistricts] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [geoRes, distRes] = await Promise.all([
        fetch(`${BASE}/intersections.geojson`),
        fetch(`${BASE}/districts.json`),
      ]);
      if (!geoRes.ok) throw new Error(`Intersections: HTTP ${geoRes.status}`);
      if (!distRes.ok) throw new Error(`Districts: HTTP ${distRes.status}`);

      const [geoData, distData] = await Promise.all([geoRes.json(), distRes.json()]);

      setIntersections(
        geoData.features.map((f) => ({
          id: String(f.properties.rank),
          lat: f.geometry.coordinates[1],
          lon: f.geometry.coordinates[0],
          ...f.properties,
          crash_history: parseProp(f.properties.crash_history),
          shap_features: parseProp(f.properties.shap_features),
        }))
      );
      setDistricts(distData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return { intersections, districts, loading, error, reload: load };
}
