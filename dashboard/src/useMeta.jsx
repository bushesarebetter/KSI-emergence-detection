import { createContext, useContext, useEffect, useState } from "react";
import { CANDIDATE_COUNT, CATCH_FALLBACK, liftOverRandom } from "./constants";

/**
 * /data/meta.json describes the exported list: recall@K of the model's ranking
 * at each shortlist size, and how many rows each tier contributed when the
 * export is the combined list. It is written by the pipeline alongside the
 * geojson so the interface never states a number it cannot trace to an export.
 *
 * Older exports have no meta.json; every consumer falls back to the
 * hardcoded table in constants.js, which matches the last classic export.
 */
const MetaContext = createContext(null);

export function useMetaFetch() {
  const [meta, setMeta] = useState(null);
  useEffect(() => {
    let cancelled = false;
    fetch("/data/meta.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((m) => { if (!cancelled) setMeta(m); })
      .catch(() => { if (!cancelled) setMeta(null); });
    return () => { cancelled = true; };
  }, []);
  return meta;
}

export function MetaProvider({ meta, children }) {
  return <MetaContext.Provider value={meta}>{children}</MetaContext.Provider>;
}

export function useMeta() {
  return useContext(MetaContext);
}

/** Catch stats for one shortlist size, from meta.json or the fallback table. */
export function useCatch(k) {
  const meta = useMeta();
  const entry = meta?.catch?.[String(k)] ?? CATCH_FALLBACK[k] ?? { caught: 0, total: 0 };
  const candidates = meta?.candidates ?? CANDIDATE_COUNT;
  const lift = liftOverRandom(entry.caught, entry.total, k, candidates);
  return { caught: entry.caught, total: entry.total, lift, candidates };
}

/** Tier composition of the exported list; all "predicted" for a classic export. */
export function useComposition() {
  const meta = useMeta();
  const c = meta?.composition ?? {};
  return {
    known: c.known ?? 0,
    screen: c.screen ?? 0,
    predicted: c.predicted ?? 0,
    isCombined: (c.known ?? 0) + (c.screen ?? 0) > 0,
    topN: meta?.top_n ?? null,
  };
}
