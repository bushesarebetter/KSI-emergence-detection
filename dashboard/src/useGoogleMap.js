import { useRef, useEffect, useState } from "react";
import { Loader } from "@googlemaps/js-api-loader";
import { CITY } from "./city";

export const SAN_DIEGO_CENTER = CITY.center;

// One loader per page. The Google Maps JS API is a singleton -- calling
// importLibrary twice with different options throws, so the options are fixed here.
let loaderPromise = null;

export function loadMaps() {
  if (!loaderPromise) {
    const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
    if (!apiKey) {
      return Promise.reject(
        new Error(
          "VITE_GOOGLE_MAPS_API_KEY is not set. Copy dashboard/.env.example to " +
            "dashboard/.env and add a Google Maps JavaScript API key."
        )
      );
    }
    const loader = new Loader({ apiKey, version: "weekly" });
    // `streetView` powers StreetViewPanel and `geometry` gives us computeHeading,
    // used to aim the pano camera back at the intersection.
    loaderPromise = Promise.all([
      loader.importLibrary("core"),
      loader.importLibrary("maps"),
      loader.importLibrary("geometry"),
      loader.importLibrary("streetView"),
      // Resolve to the merged google.maps namespace so callers get every loaded
      // library off one object instead of juggling per-library handles.
    ]).then(() => window.google.maps);
  }
  return loaderPromise;
}

/**
 * Creates a Google Maps vector map in `containerRef` and calls `onLoad(map)` once
 * it is ready. Mirrors the old useMapbox signature so MapView's structure is unchanged.
 *
 * A Map ID is required: deck.gl's WebGL overlay only interleaves correctly on a
 * vector map, and the dark styling lives in the Cloud console style attached to
 * that Map ID (google.maps.Map `styles` is ignored when mapId is present).
 */
export default function useGoogleMap(containerRef, onLoad, zoom = 12) {
  const mapRef = useRef(null);
  const onLoadRef = useRef(onLoad);
  onLoadRef.current = onLoad;

  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    loadMaps()
      .then((maps) => {
        if (cancelled || !containerRef.current) return;

        const map = new maps.Map(containerRef.current, {
          center: SAN_DIEGO_CENTER,
          zoom,
          mapId: import.meta.env.VITE_GOOGLE_MAPS_MAP_ID || "DEMO_MAP_ID",
          disableDefaultUI: true,
          zoomControl: true,
          scaleControl: true,
          mapTypeControl: true,
          mapTypeControlOptions: {
            style: maps.MapTypeControlStyle.DROPDOWN_MENU,
            position: maps.ControlPosition.TOP_RIGHT,
            mapTypeIds: ["roadmap", "satellite"],
          },
          streetViewControl: true,
          clickableIcons: false,
          gestureHandling: "greedy",
        });

        mapRef.current = map;
        onLoadRef.current(map);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });

    return () => {
      cancelled = true;
      mapRef.current = null;
    };
  }, []);

  return { mapRef, error };
}
