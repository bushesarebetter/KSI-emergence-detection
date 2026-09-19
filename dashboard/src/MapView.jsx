import { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { GoogleMapsOverlay } from "@deck.gl/google-maps";
import { ScatterplotLayer, PathLayer } from "@deck.gl/layers";
import useGoogleMap from "./useGoogleMap";
import MapLegend from "./MapLegend";
import { patternOf } from "./lib/advice";
import { passesFilters } from "./lib/filters";

const INITIAL_ZOOM = 13;
const FLY_ZOOM = 16;

// Sequential ramp, dark to light, matching MapLegend's RISK_TIERS. Lightness
// carries the order as well as hue so the tiers survive greyscale printing and
// colourblind viewing. deck.gl wants [r, g, b] 0-255.
const RANK_COLORS = [
  [127, 29, 29],   // rank 1 to 50     #7F1D1D oxblood
  [194, 65, 12],   // rank 51 to 100   #C2410C burnt orange
  [217, 119, 6],   // rank 101 to 200  #D97706 amber
  [232, 181, 99],  // rank 201 and up  #E8B563 pale amber
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

// Radii are in metres (deck.gl world units), clamped to a pixel range so dots
// stay legible zoomed out and do not swamp the map zoomed in.
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
  // Where the live-traffic toggle sits; the phone shell moves it under its bar.
  trafficControlClass = "top-4 left-4",
  trafficControlStyle,
  // {path: [[lon, lat], ...]} for a checked route, or {point: [lon, lat]} for
  // an address, from the route panel. Drawn in ink under the dots.
  routeOverlay = null,
}) {
  const containerRef = useRef(null);
  const overlayRef = useRef(null);
  const infoWindowRef = useRef(null);
  const trafficLayerRef = useRef(null);
  const [mapReady, setMapReady] = useState(false);
  const [trafficOn, setTrafficOn] = useState(false);

  const handleMapLoad = useCallback((map) => {
    const overlay = new GoogleMapsOverlay({ interleaved: false });
    overlay.setMap(map);
    overlayRef.current = overlay;

    // Safe to reach for the global here: useGoogleMap only calls back once the
    // API has finished loading.
    infoWindowRef.current = new window.google.maps.InfoWindow({ disableAutoPan: true });
    trafficLayerRef.current = new window.google.maps.TrafficLayer();

    setMapReady(true);
  }, []);

  const { mapRef, error } = useGoogleMap(containerRef, handleMapLoad, INITIAL_ZOOM);

  // Google's live traffic: green moving, red stopped, drawn on the roads under
  // the dots. Off by default because its reds compete with the risk ramp; the
  // legend explains the colours whenever it is on.
  useEffect(() => {
    const layer = trafficLayerRef.current;
    const map = mapRef.current;
    if (!layer || !map || !mapReady) return;
    layer.setMap(trafficOn ? map : null);
  }, [trafficOn, mapReady]);

  // Ranked dots obey every filter; emergent rings obey only the district
  // filter, so sites the shortlist missed stay visible at every tier.
  const { shown, emergents } = useMemo(() => {
    if (!intersections) return { shown: [], emergents: [] };
    const districtSet = new Set(filters.districts);
    const inDistrict = (p) => districtSet.size === 0 || districtSet.has(p.council_district);
    return {
      shown: intersections.features.filter((f) => passesFilters(f.properties, filters)),
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
      const pattern = patternOf(info.object.properties);
      const [lng, lat] = info.object.geometry.coordinates;
      iw.setContent(`
        <div style="font-family:'Public Sans',Helvetica,Arial,sans-serif;padding:9px 12px;min-width:150px">
          <div style="font-size:13px;font-weight:600;color:#17150F;line-height:1.3;margin-bottom:5px">
            ${intersection_name}
          </div>
          <div style="font-size:11px;color:#8A8272;letter-spacing:.02em">
            <span style="font-variant-numeric:tabular-nums;color:#17150F;font-weight:600">#${rank}</span>,
            District ${council_district}${pattern ? `, ${pattern.toLowerCase()}` : ""}
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

    // Without this the dots give no affordance at all: the cursor stays a
    // plain arrow and most people never discover they are interactive.
    const handleCursor = ({ isHovering }) => {
      const el = mapRef.current?.getDiv();
      if (el) el.style.cursor = isHovering ? "pointer" : "";
    };

    const layers = [
      ...(routeOverlay?.path
        ? [new PathLayer({
            id: "route-layer",
            data: [{ path: routeOverlay.path }],
            getPath: (d) => d.path,
            getColor: [23, 21, 15, 190],
            widthUnits: "pixels",
            getWidth: 5,
            capRounded: true,
            jointRounded: true,
          })]
        : []),
      ...(routeOverlay?.point
        ? [new ScatterplotLayer({
            id: "address-layer",
            data: [{ position: routeOverlay.point }],
            getPosition: (d) => d.position,
            radiusUnits: "pixels",
            getRadius: 9,
            filled: false,
            stroked: true,
            lineWidthUnits: "pixels",
            getLineWidth: 2.5,
            getLineColor: [23, 21, 15, 255],
          })]
        : []),
      // Emergent rings: hollow outline under the ranked dots. Ink means the site
      // was caught at the current top-K tier; a thin slate ring means it was
      // not. See docs/DECISIONS.md D12.
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
  }, [shown, emergents, filters.threshold, mapReady, onSelectIntersection, routeOverlay]);

  // Frame a checked route, or centre on the address.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !routeOverlay) return;
    if (routeOverlay.path?.length) {
      const b = new window.google.maps.LatLngBounds();
      for (const [lng, lat] of routeOverlay.path) b.extend({ lat, lng });
      map.fitBounds(b, 60);
    } else if (routeOverlay.point) {
      const [lng, lat] = routeOverlay.point;
      map.panTo({ lat, lng });
      map.setZoom(15);
    }
  }, [routeOverlay]);

  // Pan to the selected intersection.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedIntersection) return;
    const [lng, lat] = selectedIntersection.geometry.coordinates;
    map.panTo({ lat, lng });
    if (map.getZoom() < FLY_ZOOM) map.setZoom(FLY_ZOOM);
    // panBy(0, +y) moves the map's centre down in the world, so the point that
    // was just centred ends up higher on screen, above the sheet.
    if (selectionOffsetY) map.panBy(0, selectionOffsetY);
  }, [selectedIntersection, selectionOffsetY]);

  // Tear the overlay down on unmount so the WebGL context is released.
  useEffect(() => {
    return () => {
      overlayRef.current?.finalize();
      overlayRef.current = null;
      infoWindowRef.current?.close();
      trafficLayerRef.current?.setMap(null);
    };
  }, []);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />

      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-paper px-8">
          <div className="max-w-md bg-paper-sunk px-6 py-5">
            <p className="label mb-2 text-risk-1">Map failed to load</p>
            <p className="font-serif text-[15px] leading-[1.55] text-ink-2">{error}</p>
          </div>
        </div>
      )}

      {mapReady && (
        <button
          onClick={() => setTrafficOn((v) => !v)}
          aria-pressed={trafficOn}
          title="Google's live traffic speeds on the roads"
          className={`absolute z-10 border px-3 py-2 text-[12px] font-medium shadow-paper ${trafficControlClass} ${
            trafficOn ? "border-ink bg-ink text-paper" : "border-rule-strong bg-paper text-ink-2 hover:text-ink"
          }`}
          style={trafficControlStyle}
        >
          {trafficOn ? "Traffic now: on" : "Traffic now"}
        </button>
      )}

      {showLegend && <MapLegend threshold={filters.threshold} trafficOn={trafficOn} />}
    </div>
  );
}
