import { useRef, useEffect } from "react";
import maplibregl from "maplibre-gl";

export default function useMapbox(containerRef, onLoad, zoom = 12) {
  const mapRef = useRef(null);
  const onLoadRef = useRef(onLoad);
  onLoadRef.current = onLoad;

  useEffect(() => {
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: "https://tiles.stadiamaps.com/styles/alidade_smooth_dark.json",
      center: [-117.1611, 32.7157],
      zoom,
    });

    mapRef.current = map;
    map.on("style.load", () => onLoadRef.current(map));

    return () => {
      map.remove();
    };
  }, []);

  return { mapRef };
}
