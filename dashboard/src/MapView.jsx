import { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { GoogleMapsOverlay } from "@deck.gl/google-maps";
import { ScatterplotLayer } from "@deck.gl/layers";
import useGoogleMap from "./useGoogleMap";
import MapLegend from "./MapLegend";

const INITIAL_ZOOM = 12;
const FLY_ZOOM = 16;

// YlOrRd-derived colorblind-safe ramp: red (most dangerous) → yellow (least).
// deck.gl wants [r, g, b] 0-255, so these are the same hexes as the old MapLibre
// `step` expression, pre-converted.
const RANK_COLORS = [
  [239, 68, 68],   // rank 1–50:   #ef4444 red
  [249, 115, 22],  // rank 51–100: #f97316 orange
  [251, 191, 36],  // rank 101–200:#fbbf24 amber
  [253, 230, 138], // rank 201+:   #fde68a pale yellow
];

function rankTier(rank) {
  if (rank <= 50) return 0;
  if (rank <= 100) return 1;
  if (rank <= 200) return 2;
  return 3;
}

function rankColor(rank) {
  return RANK_COLORS[rankTier(rank)];
}

// Radii are in metres (deck.gl world units) rather than pixels, clamped to a
// pixel range so dots stay legible when zoomed out and don't swamp the map when
// zoomed in.
function rankRadius(rank) {
  return [26, 23, 20, 17][rankTier(rank)];
}

export default function MapView({ intersections, filters, selectedIntersection, onSelectIntersection }) {
  const containerRef = useRef(null);
  const overlayRef = useRef(null);
  const infoWindowRef = useRef(null);
  const [mapReady, setMapReady] = useState(false);

  const handleMapLoad = useCallback((map) => {
    const overlay = new GoogleMapsOverlay({ interleaved: false });
    overlay.setMap(map);
    overlayRef.current = overlay;

    // Safe to reach for the global here: useGoogleMap only calls back once the
    // API has finished loading.
    infoWindowRef.current = new window.google.maps.InfoWindow({ disableAutoPan: true });

    setMapReady(true);
  }, []);

  const { mapRef, error } = useGoogleMap(containerRef, handleMapLoad, INITIAL_ZOOM);

  // Apply the threshold + district filters. Mirrors the previous MapLibre logic
  // exactly: ranked dots are gated by the live top-K threshold, emergent rings
  // are NOT, so sites the shortlist missed stay visible at every tier.
  const { shown, emergents } = useMemo(() => {
    if (!intersections) return { shown: [], emergents: [] };
    const districtSet = new Set(filters.districts);
    const inDistrict = (p) => districtSet.size === 0 || districtSet.has(p.council_district);

    return {
      shown: intersections.features.filter(
        (f) => f.properties.rank <= filters.threshold && inDistrict(f.properties)
      ),
      emergents: intersections.features.filter(
        (f) => f.properties.is_known_emergent && inDistrict(f.properties)
      ),
    };
  }, [intersections, filters]);

  // Rebuild deck.gl layers whenever the filtered data changes.
  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay || !mapReady) return;

    const showTooltip = (info) => {
      const iw = infoWindowRef.current;
      const map = mapRef.current;
      if (!iw || !map) return;
      if (!info.object) {
        iw.close();
        return;
      }
      const { intersection_name, rank, council_district } = info.object.properties;
      const [lng, lat] = info.object.geometry.coordinates;
      iw.setContent(`
        <div style="font-family:inherit;padding:2px 4px">
          <div style="font-weight:600;color:#0f172a;margin-bottom:4px;line-height:1.3">${intersection_name}</div>
          <div style="color:#475569;font-size:11px">
            Rank <strong style="color:#c2410c">#${rank}</strong>
            &nbsp;·&nbsp;District ${council_district}
          </div>
        </div>
      `);
      iw.setPosition({ lat, lng });
      iw.open(map);
    };

    const handleClick = (info) => {
      if (!info.object) return;
      onSelectIntersection(info.object);
    };

    const layers = [
      // Emergent rings: hollow outline under the ranked dots. A bold white ring
      // means the site was caught at the current top-K tier; a thin slate ring
      // means it wasn't caught at this tier. Deliberately not a red/black
      // "failure" colour -- it's just not (yet) confirmed at this threshold.
      // See docs/DECISIONS.md D12.
      new ScatterplotLayer({
        id: "emergents-layer",
        data: emergents,
        pickable: false,
        stroked: true,
        filled: false,
        radiusUnits: "meters",
        radiusMinPixels: 7,
        radiusMaxPixels: 16,
        lineWidthUnits: "pixels",
        getPosition: (f) => f.geometry.coordinates,
        getRadius: (f) => rankRadius(f.properties.rank) + 6,
        getLineColor: (f) => {
          const r = f.properties.oof_rank;
          const caught = r != null && r <= filters.threshold;
          return caught ? [255, 255, 255, 255] : [100, 116, 139, 115];
        },
        getLineWidth: (f) => {
          const r = f.properties.oof_rank;
          return r != null && r <= filters.threshold ? 2 : 1.5;
        },
        updateTriggers: {
          getLineColor: filters.threshold,
          getLineWidth: filters.threshold,
        },
      }),

      // Ranked shortlist dots.
      new ScatterplotLayer({
        id: "intersections-layer",
        data: shown,
        pickable: true,
        stroked: true,
        filled: true,
        radiusUnits: "meters",
        radiusMinPixels: 4,
        radiusMaxPixels: 13,
        lineWidthUnits: "pixels",
        getPosition: (f) => f.geometry.coordinates,
        getRadius: (f) => rankRadius(f.properties.rank),
        getFillColor: (f) => [...rankColor(f.properties.rank), 235],
        getLineColor: [255, 255, 255, 160],
        getLineWidth: 1.5,
        onHover: showTooltip,
        onClick: handleClick,
      }),
    ];

    overlay.setProps({ layers });
  }, [shown, emergents, filters.threshold, mapReady, onSelectIntersection]);

  // Pan to the selected intersection.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedIntersection) return;
    const [lng, lat] = selectedIntersection.geometry.coordinates;
    map.panTo({ lat, lng });
    if (map.getZoom() < FLY_ZOOM) map.setZoom(FLY_ZOOM);
  }, [selectedIntersection]);

  // Tear the overlay down on unmount so the WebGL context is released.
  useEffect(() => {
    return () => {
      overlayRef.current?.finalize();
      overlayRef.current = null;
      infoWindowRef.current?.close();
    };
  }, []);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />

      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-950/90 px-8 text-center">
          <div className="max-w-md text-sm text-red-400">
            <div className="mb-2 font-semibold">Map failed to load</div>
            <div className="text-slate-400 text-xs leading-relaxed">{error}</div>
          </div>
        </div>
      )}

      <MapLegend threshold={filters.threshold} />
    </div>
  );
}
