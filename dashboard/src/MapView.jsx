import { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { GoogleMapsOverlay } from "@deck.gl/google-maps";
import { ScatterplotLayer } from "@deck.gl/layers";
import useGoogleMap from "./useGoogleMap";
import MapLegend from "./MapLegend";

const INITIAL_ZOOM = 13;
const FLY_ZOOM = 16;

// Sequential ramp, dark → light, matching MapLegend's RISK_TIERS. Ordering is
// carried by lightness as well as hue so the tiers survive greyscale printing
// and colourblind viewing. deck.gl wants [r, g, b] 0-255.
const RANK_COLORS = [
  [127, 29, 29],   // rank 1–50    #7F1D1D oxblood
  [194, 65, 12],   // rank 51–100  #C2410C burnt orange
  [217, 119, 6],   // rank 101–200 #D97706 amber
  [232, 181, 99],  // rank 201+    #E8B563 pale amber
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

export default function MapView({
  intersections,
  filters,
  selectedIntersection,
  onSelectIntersection,
  showLegend = true,
  // Pixels to push the map after centring a selection. The phone sheet covers
  // the lower half of the screen; without this the tapped dot sits under it.
  selectionOffsetY = 0,
}) {
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
        <div style="font-family:'Public Sans',Helvetica,Arial,sans-serif;padding:9px 12px;min-width:150px">
          <div style="font-size:13px;font-weight:600;color:#17150F;line-height:1.3;margin-bottom:5px">
            ${intersection_name}
          </div>
          <div style="font-size:11px;color:#8A8272;letter-spacing:.02em">
            <span style="font-variant-numeric:tabular-nums;color:#17150F;font-weight:600">#${rank}</span>
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

    // Without this the dots give no affordance at all -- the cursor stays a
    // plain arrow and most people never discover they are interactive.
    const handleCursor = ({ isHovering }) => {
      const el = mapRef.current?.getDiv();
      if (el) el.style.cursor = isHovering ? "pointer" : "";
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
          // Ink, not white: the basemap is light, and a white ring on light
          // tiles disappears entirely.
          return caught ? [23, 21, 15, 255] : [138, 130, 114, 150];
        },
        getLineWidth: (f) => {
          const r = f.properties.oof_rank;
          return r != null && r <= filters.threshold ? 2 : 1.2;
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
        getFillColor: (f) => [...rankColor(f.properties.rank), 240],
        // On a combined export, sites admitted because a serious crash has
        // already happened there get a heavy ink outline: they are records,
        // not predictions, and the map must not let the two blur together.
        getLineColor: (f) =>
          f.properties.source === "known" ? [23, 21, 15, 255] : [251, 249, 245, 230],
        getLineWidth: (f) => (f.properties.source === "known" ? 2.4 : 1.2),
        onHover: (info) => {
          showTooltip(info);
          handleCursor({ isHovering: Boolean(info.object) });
        },
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
    // panBy(0, +y) moves the map's centre down in the world, so the point that
    // was just centred ends up higher on screen -- above the sheet.
    if (selectionOffsetY) map.panBy(0, selectionOffsetY);
  }, [selectedIntersection, selectionOffsetY]);

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
        <div className="absolute inset-0 flex items-center justify-center bg-paper px-8">
          <div className="max-w-md border-l-2 border-risk-1 pl-5">
            <p className="label mb-2 text-risk-1">Map failed to load</p>
            <p className="font-serif text-[15px] leading-[1.55] text-ink-2">{error}</p>
          </div>
        </div>
      )}

      {showLegend && <MapLegend threshold={filters.threshold} />}
    </div>
  );
}
