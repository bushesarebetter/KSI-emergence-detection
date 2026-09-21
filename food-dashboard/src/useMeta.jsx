import { createContext, useContext, useEffect, useState } from "react";
import { CANDIDATE_COUNT, CATCH_FALLBACK, liftOverRandom } from "./constants";

/**
 * /data/meta.json describes the export: what the label is, how many places
 * were ranked, when inspections run through, and for each shortlist size how
 * many of the places that went on to have a major violation the top K held.
 * `sample: true` marks an invented export, and the interface says so on every
 * page.
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

/** Catch stats for one shortlist size, or zeros when the export has none. */
export function useCatch(k) {
  const meta = useMeta();
  const entry = meta?.catch?.[String(k)] ?? CATCH_FALLBACK[k] ?? { caught: 0, total: 0 };
  const candidates = meta?.candidates ?? CANDIDATE_COUNT;
  const lift = liftOverRandom(entry.caught, entry.total, k, candidates);
  return { caught: entry.caught, total: entry.total, lift, candidates, scored: Boolean(meta?.catch) };
}

export function useSample() {
  const meta = useMeta();
  return Boolean(meta?.sample);
}
