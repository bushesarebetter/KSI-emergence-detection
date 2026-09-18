import { useAdvanced } from "./useAdvanced";
import { THRESHOLDS } from "./constants";

/**
 * Shortlist size.
 *
 * A row of segments sharing one hairline frame, rather than separate filled
 * buttons: the choice is one variable with a few settings, and a grid of pill
 * buttons read as unrelated actions. The sizes come from constants.js so the
 * export, the district counts and this control agree on what K can be.
 */
export default function FilterBar({ filters, onFiltersChange }) {
  const { advanced } = useAdvanced();

  return (
    <div className="px-6 py-5">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <p className="label">{advanced ? "Top N" : "Shortlist size"}</p>
        <p className="text-[11px] text-ink-3">
          {advanced ? "K" : "intersections shown"}
        </p>
      </div>

      <div role="group" aria-label="Shortlist size" className="flex border border-ink/20">
        {THRESHOLDS.map((value, i) => {
          const active = filters.threshold === value;
          return (
            <button
              key={value}
              onClick={() => onFiltersChange({ ...filters, threshold: value })}
              aria-pressed={active}
              className={`tnum flex-1 py-2 text-[13px] font-medium transition-colors ${
                i > 0 ? "border-l border-ink/20" : ""
              } ${active ? "bg-ink text-paper" : "text-ink-2 hover:bg-paper-edge"}`}
            >
              {value}
            </button>
          );
        })}
      </div>
    </div>
  );
}
