import { useEffect, useState } from "react";
import { pointKey } from "./useTraffic";

/**
 * The optional per-site files the pipeline scripts write next to the export,
 * each keyed by a site's coordinates:
 *   /data/recent.json   police-reported crashes since the model's cutoff
 *   /data/control.json  signals, stop signs or neither, from OpenStreetMap
 * A missing file is not an error; the interface simply omits that line.
 */
export function useOptionalJson(url) {
  const [data, setData] = useState(null);
  useEffect(() => {
    let cancelled = false;
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setData(null); });
    return () => { cancelled = true; };
  }, [url]);
  return data;
}

export function recordFor(data, feature) {
  if (!data?.sites || !feature) return null;
  return data.sites[pointKey(feature)] ?? null;
}

/** "signals" | "stop" | "yield" | "none" | null (no file or not fetched). */
export function controlFor(control, feature) {
  return recordFor(control, feature)?.control ?? null;
}

export const CONTROL_LABEL = {
  signals: "Traffic signals",
  stop: "Stop signs",
  yield: "Yield signs",
  none: "No signal or stop sign mapped",
};
