import { useRef, useEffect, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import useMapbox from "./useMapbox";
import MapLegend from "./MapLegend";

const INITIAL_ZOOM = 12;
const FLY_ZOOM = 15;
const FLY_DURATION = 800;

// YlOrRd-derived colorblind-safe ramp: red (most dangerous) → yellow (least)
const STEP_COLOR = [
  "step", ["get", "rank"],
  "#ef4444",       // rank 1–50: red
  51,  "#f97316",  // 51–100: orange
  101, "#fbbf24",  // 101–200: amber
  201, "#fde68a",  // 201–500: pale yellow
];

const STEP_RADIUS = [
  "step", ["get", "rank"],
  8,
  51,  7,
  101, 6,
  201, 5,
];

const EMPTY_FC = { type: "FeatureCollection", features: [] };

export default function MapView({ intersections, filters, selectedIntersection, onSelectIntersection }) {
  const containerRef = useRef(null);
  const popupRef = useRef(null);
  const [mapReady, setMapReady] = useState(false);

  const setupSources = useCallback((map) => {
    ["intersections-halo-layer", "intersections-layer", "emergents-layer"]
      .forEach((id) => { if (map.getLayer(id)) map.removeLayer(id); });
    ["intersections-source", "emergents-source"]
      .forEach((id) => { if (map.getSource(id)) map.removeSource(id); });

    // Main source for ranked intersections
    map.addSource("intersections-source", { type: "geojson", data: EMPTY_FC });

    // Soft shadow halo under each dot (depth separation from basemap)
    map.addLayer({
      id: "intersections-halo-layer",
      type: "circle",
      source: "intersections-source",
      paint: {
        "circle-radius": ["step", ["get", "rank"], 12, 51, 11, 101, 10, 201, 9],
        "circle-color": "rgba(0,0,0,0.45)",
        "circle-blur": 0.5,
        "circle-opacity": 1,
      },
    });

    // Main markers
    map.addLayer({
      id: "intersections-layer",
      type: "circle",
      source: "intersections-source",
      paint: {
        "circle-radius": STEP_RADIUS,
        "circle-color": STEP_COLOR,
        "circle-stroke-width": 1.5,
        "circle-stroke-color": "rgba(255,255,255,0.22)",
        "circle-opacity": 0.92,
      },
    });

    // All 108 emergent sites (>=1 KSI), white ring always visible regardless of threshold
    map.addSource("emergents-source", { type: "geojson", data: EMPTY_FC });
    map.addLayer({
      id: "emergents-layer",
      type: "circle",
      source: "emergents-source",
      paint: {
        "circle-radius": ["step", ["get", "rank"], 11, 51, 10, 101, 9, 201, 8],
        "circle-color": "rgba(0,0,0,0)",
        "circle-stroke-width": 2,
        "circle-stroke-color": "#ffffff",
      },
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.addControl(new maplibregl.ScaleControl(), "bottom-left");

    // Hover popup
    map.on("mouseenter", "intersections-layer", (e) => {
      map.getCanvas().style.cursor = "pointer";
      const feat = e.features[0];
      const coords = feat.geometry.coordinates.slice();
      const { intersection_name, rank, council_district } = feat.properties;

      if (popupRef.current) popupRef.current.remove();
      popupRef.current = new maplibregl.Popup({ closeButton: false, offset: 14, maxWidth: "260px" })
        .setLngLat(coords)
        .setHTML(`
          <div>
            <div style="font-weight:600;color:#e2e8f0;margin-bottom:5px;line-height:1.3">${intersection_name}</div>
            <div style="color:#94a3b8;font-size:11px">
              Rank <strong style="color:#f97316">#${rank}</strong>
              &nbsp;·&nbsp;District ${council_district}
            </div>
          </div>
        `)
        .addTo(map);
    });

    map.on("mouseleave", "intersections-layer", () => {
      map.getCanvas().style.cursor = "";
      if (popupRef.current) { popupRef.current.remove(); popupRef.current = null; }
    });

    map.on("click", "intersections-layer", (e) => {
      const feat = e.features[0];
      onSelectIntersection(feat);
      map.flyTo({ center: feat.geometry.coordinates, zoom: FLY_ZOOM, duration: FLY_DURATION });
    });

    setMapReady(true);
  }, [onSelectIntersection]);

  const { mapRef } = useMapbox(containerRef, setupSources, INITIAL_ZOOM);

  // Update data when filters change
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !intersections) return;

    const districtSet = new Set(filters.districts);
    const shown = intersections.features.filter((f) => {
      const p = f.properties;
      if (p.rank > filters.threshold) return false;
      if (districtSet.size > 0 && !districtSet.has(p.council_district)) return false;
      return true;
    });

    const emergents = shown.filter((f) => Boolean(f.properties.is_known_emergent));

    map.getSource("intersections-source")?.setData({ type: "FeatureCollection", features: shown });
    map.getSource("emergents-source")?.setData({ type: "FeatureCollection", features: emergents });
  }, [intersections, filters, mapReady]);

  // Fly to selected
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedIntersection) return;
    map.flyTo({
      center: selectedIntersection.geometry.coordinates,
      zoom: FLY_ZOOM,
      duration: FLY_DURATION,
    });
  }, [selectedIntersection]);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />

      {/* Risk legend */}
      <MapLegend threshold={filters.threshold} />
    </div>
  );
}
