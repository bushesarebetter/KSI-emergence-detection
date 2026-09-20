import { useMemo } from "react";
import { useAdvanced } from "./useAdvanced";
import { THRESHOLDS } from "./constants";
import { chipsFor } from "./lib/filters";

/**
 * Two controls, and only two: how many corners to show, and which situation
 * to show them for.
 *
 * The size control is a row of segments sharing one hairline frame; the choice
 * is one variable with a few settings. The situation chips filter the map, the
 * table and the district counts to corners whose signals include that
 * situation, so someone who cycles, or walks to a bus, can see the corners
 * that concern them and nothing else. Only situations present in the export
 * are offered.
 */
export default function FilterBar({ filters, onFiltersChange, intersections }) {
  const { advanced } = useAdvanced();
  const pattern = filters.pattern ?? null;
  const chips = useMemo(() => chipsFor(intersections), [intersections]);

  return (
    <div className="px-6 py-5">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <p className="label">{advanced ? "Top N" : "Shortlist size"}</p>
        <p className="text-[11px] text-ink-3">{advanced ? "K" : "intersections shown"}</p>
      </div>

      <div role="group" aria-label="Shortlist size" className="flex border border-ink/20">
        {THRESHOLDS.map((value, i) => {
          const active = filters.threshold === value;
          return (
            <button
              key={value}
              onClick={() => onFiltersChange({ ...filters, threshold: value })}
              aria-pressed={active}
              className={`tnum flex-1 py-2 text-[13px] font-medium ${
                i > 0 ? "border-l border-ink/20" : ""
              } ${active ? "bg-ink text-paper" : "text-ink-2 hover:bg-paper-edge"}`}
            >
              {value}
            </button>
          );
        })}
      </div>

      {chips.length > 0 && (
        <>
          <div className="mb-2.5 mt-5 flex items-baseline justify-between gap-3">
            <p className="label">{advanced ? "Signal filter" : "What you will meet"}</p>
            <p className="text-[11px] text-ink-3">{advanced ? "present in top signals" : "in the record"}</p>
          </div>

          <div role="group" aria-label="Kind of crash" className="flex flex-wrap gap-1.5">
            {[{ key: null, label: "Any" }, ...chips].map(({ key, label }) => {
              const active = pattern === key;
              return (
                <button
                  key={label}
                  onClick={() => onFiltersChange({ ...filters, pattern: key })}
                  aria-pressed={active}
                  className={`border px-2.5 py-1 text-[12px] font-medium ${
                    active ? "border-ink bg-ink text-paper" : "border-ink/20 text-ink-2 hover:bg-paper-edge"
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
