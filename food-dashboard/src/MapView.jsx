import { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { GoogleMapsOverlay } from "@deck.gl/google-maps";
import { ScatterplotLayer } from "@deck.gl/layers";
import useGoogleMap from "./useGoogleMap";
import MapLegend from "./MapLegend";
import { patternOf } from "./lib/advice";
import { passesFilters } from "./lib/filters";
import { lastInspection, typeLabel } from "./lib/inspections";

const INITIAL_ZOOM = 12;
const FLY_ZOOM = 16;

// The tooltip is built as HTML. Names and addresses are data and are escaped.
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const RANK_COLORS = [
  [127, 29, 29],
  [194, 65, 12],
  [217, 119, 6],
  [232, 181, 99],
];

function rankTier(rank) {
  if (rank <= 50) return 0;
  if (rank <= 100) return 1;
  if (rank <= 200) return 2;
  return 3;
}
const rankColor = (rank) => RANK_COLORS[rankTier(rank)];
const rankRadius = (rank) => [26, 23, 20, 17][rankTier(rank)];

export default function MapView({
  facilities,
  filters,
  selected,
  onSelect,
  showLegend = true,
  selectionOffsetY = 0,
  // {point: [lon, lat]} from the address check, drawn as an ink ring.
  pointOverlay = null,
}) {
  const containerRef = useRef(null);
  const overlayRef = useRef(null);
  const infoWindowRef = useRef(null);
  const [mapReady, setMapReady] = useState(false);

  const handleMapLoad = useCallback((map) => {
    const overlay = new GoogleMapsOverlay({ interleaved: false });
    overlay.setMap(map);
    overlayRef.current = overlay;
    infoWindowRef.current = new window.google.maps.InfoWindow({ disableAutoPan: true });
    setMapReady(true);
  }, []);

  const { mapRef, error } = useGoogleMap(containerRef, handleMapLoad, INITIAL_ZOOM);

  // Ranked dots obey every filter; positive rings obey only the district
  // filter, so places the shortlist missed stay visible at every tier.
  const { shown, positives } = useMemo(() => {
    if (!facilities) return { shown: [], positives: [] };
    const districtSet = new Set(filters.districts);
    const inDistrict = (p) => districtSet.size === 0 || districtSet.has(p.council_district);
    return {
      shown: facilities.features.filter((f) => passesFilters(f.properties, filters)),
      positives: facilities.features.filter((f) => f.properties.is_known_positive && inDistrict(f.properties)),
    };
  }, [facilities, filters]);

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
      const p = info.object.properties;
      const last = lastInspection(p);
      const pattern = patternOf(p);
      const [lng, lat] = info.object.geometry.coordinates;
      iw.setContent(`
        <div style="font-family:'Public Sans',Helvetica,Arial,sans-serif;padding:9px 12px;min-width:170px;max-width:260px">
          <div style="font-size:13px;font-weight:600;color:#17150F;line-height:1.3;margin-bottom:3px">${esc(p.name)}</div>
          <div style="font-size:11px;color:#55503F;line-height:1.35;margin-bottom:5px">${esc(p.address)}</div>
          <div style="font-size:11px;color:#8A8272;letter-spacing:.02em">
            <span style="font-variant-numeric:tabular-nums;color:#17150F;font-weight:600">#${esc(p.rank)}</span>,
            ${esc(typeLabel(p.facility_type).toLowerCase())}${last?.grade ? `, grade ${esc(last.grade)} last time` : ""}${pattern ? `, ${esc(pattern.toLowerCase())}` : ""}
          </div>
        </div>
      `);
      iw.setPosition({ lat, lng });
      iw.open(map);
    };

    const handleCursor = ({ isHovering }) => {
      const el = mapRef.current?.getDiv();
      if (el) el.style.cursor = isHovering ? "pointer" : "";
    };

    const layers = [
      ...(pointOverlay?.point
        ? [new ScatterplotLayer({
            id: "address-layer",
            data: [{ position: pointOverlay.point }],
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
      new ScatterplotLayer({
        id: "positives-layer",
        data: positives,
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
          const r = f.properties.oof_rank ?? f.properties.rank;
          return r != null && r <= filters.threshold ? [23, 21, 15, 255] : [138, 130, 114, 150];
        },
        getLineWidth: (f) => {
          const r = f.properties.oof_rank ?? f.properties.rank;
          return r != null && r <= filters.threshold ? 2 : 1.2;
        },
        updateTriggers: { getLineColor: filters.threshold, getLineWidth: filters.threshold },
      }),
      new ScatterplotLayer({
        id: "places-layer",
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
        getLineColor: [251, 249, 245, 230],
        getLineWidth: 1.2,
        onHover: (info) => {
          showTooltip(info);
          handleCursor({ isHovering: Boolean(info.object) });
        },
        onClick: (info) => info.object && onSelect(info.object),
      }),
    ];

    overlay.setProps({ layers });
  }, [shown, positives, filters.threshold, mapReady, onSelect, pointOverlay]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !pointOverlay?.point) return;
    const [lng, lat] = pointOverlay.point;
    map.panTo({ lat, lng });
    map.setZoom(15);
  }, [pointOverlay]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selected) return;
    const [lng, lat] = selected.geometry.coordinates;
    map.panTo({ lat, lng });
    if (map.getZoom() < FLY_ZOOM) map.setZoom(FLY_ZOOM);
    if (selectionOffsetY) map.panBy(0, selectionOffsetY);
  }, [selected, selectionOffsetY]);

  useEffect(() => {
    return () => {
      overlayRef.current?.finalize();
      overlayRef.current = null;
      infoWindowRef.current?.close();
    };
  }, []);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />

      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-paper px-8">
          <div className="max-w-md bg-paper-sunk px-6 py-5">
            <p className="label mb-2 text-risk-1">Map failed to load</p>
            <p className="font-serif text-[15px] leading-[1.55] text-ink-2">{error}</p>
          </div>
        </div>
      )}

      {showLegend && <MapLegend threshold={filters.threshold} />}
    </div>
  );
}
