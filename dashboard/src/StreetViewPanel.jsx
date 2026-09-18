import { useRef, useEffect, useState } from "react";
import { loadMaps } from "./useGoogleMap";

const SEARCH_RADIUS_M = 60;

/**
 * Embedded Street View pano for one intersection.
 *
 * Street View is the fastest way for a reviewer to sanity-check a shortlisted
 * site without leaving the dashboard -- you can see the approach geometry, sight
 * lines, crossing markings, and signal hardware directly.
 *
 * Not every intersection has coverage (alleys, private drives, gated areas), so
 * this resolves the nearest pano first and renders a plain fallback when there
 * is none.
 */
export default function StreetViewPanel({ lat, lon }) {
  const containerRef = useRef(null);
  const panoramaRef = useRef(null);
  const [status, setStatus] = useState("loading"); // loading | ok | none | error

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");

    loadMaps()
      .then((maps) => {
        if (cancelled || !containerRef.current) return;

        const svService = new maps.StreetViewService();
        return svService
          .getPanorama({ location: { lat, lng: lon }, radius: SEARCH_RADIUS_M })
          .then(({ data }) => {
            if (cancelled || !containerRef.current) return;

            // Aim the camera from the pano back toward the intersection itself,
            // otherwise the default heading often faces away from it.
            const panoLoc = data.location.latLng;
            const heading = maps.geometry
              ? maps.geometry.spherical.computeHeading(panoLoc, new maps.LatLng(lat, lon))
              : 0;

            panoramaRef.current = new maps.StreetViewPanorama(containerRef.current, {
              pano: data.location.pano,
              pov: { heading, pitch: 0 },
              zoom: 0,
              addressControl: false,
              fullscreenControl: false,
              motionTracking: false,
              motionTrackingControl: false,
              linksControl: false,
              panControl: false,
              zoomControl: false,
              enableCloseButton: false,
            });
            setStatus("ok");
          })
          .catch(() => {
            if (!cancelled) setStatus("none");
          });
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      });

    return () => {
      cancelled = true;
      panoramaRef.current = null;
    };
  }, [lat, lon]);

  return (
    <div className="relative h-36 w-full overflow-hidden rounded-md border border-slate-800 bg-slate-950">
      <div ref={containerRef} className="h-full w-full" />
      {status !== "ok" && (
        <div className="absolute inset-0 flex items-center justify-center text-[11px] text-slate-600">
          {status === "loading" && "Loading Street View…"}
          {status === "none" && "No Street View coverage here"}
          {status === "error" && "Street View unavailable"}
        </div>
      )}
    </div>
  );
}
