import { useState } from "react";
import { loadMaps } from "./useGoogleMap";
import { cornersAlong, cornersNear, fmtKm } from "./lib/route";
import { patternOf } from "./lib/advice";
import { passesFilters } from "./lib/filters";

// Bias address lookups to the city; "Broadway" alone should mean the one here.
const SAN_DIEGO_BOUNDS = { south: 32.53, west: -117.29, north: 33.12, east: -116.9 };
const NEAR_M = 500;
const ALONG_M = 35;

function explain(err) {
  const msg = typeof err === "string" ? err : err?.message || err?.code || String(err);
  if (/VITE_GOOGLE_MAPS_API_KEY/.test(msg)) return "The map is not available here, so addresses cannot be looked up.";
  if (/REQUEST_DENIED|not authorized|ApiNotActivated/i.test(msg)) {
    return "Address lookup is not switched on for this site's Google key (it needs the Geocoding and Directions APIs).";
  }
  if (/ZERO_RESULTS|NOT_FOUND/i.test(msg)) return "No match for that. Try a street address or a landmark in San Diego.";
  if (/OVER_QUERY_LIMIT/i.test(msg)) return "Too many lookups right now. Try again in a minute.";
  return msg;
}

/**
 * "Where do you drive?" One address gives the listed corners within 500 m of
 * it. Two give the corners a driving route passes through, in order, with the
 * distance along the way. Both answer the question the map alone does not:
 * does any of this apply to me?
 *
 * Only the corners currently shown (shortlist size, district, crash type) are
 * considered, so the answer matches what is on the map.
 */
export default function RoutePanel({ intersections, filters, onRoute, onSelect, compact = false }) {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  async function run(e) {
    e.preventDefault();
    if (!from.trim() || !intersections) return;
    setBusy(true);
    setError(null);
    try {
      const maps = await loadMaps();
      const shown = intersections.features.filter((f) => passesFilters(f.properties, filters));

      if (!to.trim()) {
        const { results } = await new maps.Geocoder().geocode({
          address: from, bounds: SAN_DIEGO_BOUNDS, region: "us",
        });
        if (!results?.length) throw new Error("ZERO_RESULTS");
        const loc = results[0].geometry.location;
        const point = [loc.lng(), loc.lat()];
        const corners = cornersNear(point, shown, NEAR_M);
        setResult({ mode: "near", label: results[0].formatted_address, corners });
        onRoute?.({ path: null, point });
      } else {
        const res = await new maps.DirectionsService().route({
          origin: from, destination: to, travelMode: maps.TravelMode.DRIVING, region: "us",
        });
        const route = res.routes?.[0];
        if (!route) throw new Error("ZERO_RESULTS");
        const path = route.overview_path.map((p) => [p.lng(), p.lat()]);
        const meters = route.legs.reduce((a, l) => a + (l.distance?.value ?? 0), 0);
        const corners = cornersAlong(path, shown, ALONG_M);
        setResult({
          mode: "route",
          label: `${route.legs[0].start_address} to ${route.legs[route.legs.length - 1].end_address}`,
          corners,
          meters,
        });
        onRoute?.({ path, point });
      }
    } catch (err) {
      setError(explain(err));
      setResult(null);
      onRoute?.(null);
    } finally {
      setBusy(false);
    }
  }

  function clear() {
    setFrom("");
    setTo("");
    setResult(null);
    setError(null);
    onRoute?.(null);
  }

  const field = "w-full border border-rule-strong bg-paper-sunk px-3 py-2 text-[16px] text-ink placeholder:text-ink-3 focus:border-ink focus:bg-paper focus:outline-none md:text-[13px]";

  return (
    <div className={compact ? "" : "px-6 py-5"}>
      {!compact && (
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <p className="label">Where do you drive?</p>
          <p className="text-[11px] text-ink-3">address, or two for a route</p>
        </div>
      )}

      <form onSubmit={run} className="space-y-2">
        <input
          type="text"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
          placeholder="Your address, or a place"
          aria-label="Start address"
          autoComplete="street-address"
          className={field}
        />
        <input
          type="text"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          placeholder="Where you are going (optional)"
          aria-label="Destination address"
          className={field}
        />
        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={busy || !from.trim()}
            className="bg-ink px-4 py-2 text-[13px] font-semibold text-paper hover:bg-ink-2 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? "Looking up" : to.trim() ? "Check the route" : "Check near here"}
          </button>
          {(result || error) && (
            <button type="button" onClick={clear} className="border-b border-ink/25 text-[12px] text-ink-3 hover:border-ink hover:text-ink">
              Clear
            </button>
          )}
        </div>
      </form>

      {error && <p className="mt-3 text-[12.5px] leading-[1.5] text-risk-1">{error}</p>}

      {result && (
        <div className="mt-4">
          <p className="text-[12.5px] leading-[1.5] text-ink-2">
            {result.mode === "route" ? (
              result.corners.length
                ? <>Your route ({fmtKm(result.meters)}) passes {result.corners.length} listed {result.corners.length === 1 ? "corner" : "corners"}.</>
                : <>None of the listed corners are on this route ({fmtKm(result.meters)}).</>
            ) : result.corners.length ? (
              <>{result.corners.length} listed {result.corners.length === 1 ? "corner" : "corners"} within {NEAR_M} m of {result.label}.</>
            ) : (
              <>No listed corners within {NEAR_M} m of {result.label}.</>
            )}
          </p>

          {result.corners.length > 0 && (
            <ol className="mt-2">
              {result.corners.map(({ feature, meters, alongM }) => {
                const p = feature.properties;
                const pattern = patternOf(p);
                return (
                  <li key={p.rank} className="border-b border-rule last:border-b-0">
                    <button
                      onClick={() => onSelect(feature)}
                      className="flex w-full items-baseline gap-3 py-2 text-left hover:bg-paper-sunk"
                    >
                      <span className="tnum w-14 shrink-0 text-[11px] text-ink-3">
                        {result.mode === "route" ? fmtKm(alongM) : `${Math.round(meters / 10) * 10} m`}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[13px] leading-snug text-ink">{p.intersection_name}</span>
                        <span className="block text-[11px] text-ink-3">
                          #{p.rank}{pattern ? `, ${pattern.toLowerCase()}` : ""}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
