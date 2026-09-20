import { useMemo } from "react";
import { useAdvanced } from "./useAdvanced";
import FilterBar from "./FilterBar";
import RoutePanel from "./RoutePanel";
import DistrictSummary from "./DistrictSummary";
import CatchFigure from "./CatchFigure";
import { CITY } from "./city";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

/** "2026-09-17" -> "September 17, 2026", without a Date object's timezone shift. */
export function fmtDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
  if (!m) return iso || "";
  return `${MONTHS[Number(m[2]) - 1]} ${Number(m[3])}, ${m[1]}`;
}

/**
 * The editorial column, read top to bottom: what this shows and how fresh it
 * is, how much of it to show and for which kind of crash, whether any of it is
 * on your way, how well it has worked, and where it concentrates.
 */
export default function Sidebar({
  intersections, districts, filters, onFiltersChange,
  traffic, recent, onNavigate, onRoute, onSelectIntersection,
}) {
  const { advanced } = useAdvanced();

  // The years the traffic counts span, from the counts themselves.
  const trafficYears = useMemo(() => {
    if (!traffic?.sites) return null;
    let lo = Infinity, hi = -Infinity;
    for (const s of Object.values(traffic.sites)) {
      for (const l of s.legs) if (l.year) { lo = Math.min(lo, l.year); hi = Math.max(hi, l.year); }
    }
    return lo <= hi ? (lo === hi ? `${lo}` : `${lo} to ${hi}`) : null;
  }, [traffic]);

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-paper">
      <div className="px-6 pb-6 pt-6">
        <p className="label mb-3">{advanced ? "Forward run" : "What this shows"}</p>

        <h2 className="font-serif text-[27px] font-medium leading-[1.12] tracking-[-0.015em] text-ink">
          {advanced ? (
            <>Predicted KSI emergence, 2025 to 2027</>
          ) : (
            <>
              Where serious crashes
              <br />
              are likely to happen next
            </>
          )}
        </h2>

        <p className="mt-3.5 max-w-measure text-[13.5px] leading-[1.55] text-ink-2">
          {advanced ? (
            <>
              {CITY.fullName} intersections with no KSI history through 2024,
              ranked by predicted KSI count over the label window.
            </>
          ) : (
            <>
              Every {CITY.name} intersection that has never had a serious crash, ranked by
              how likely it is to have one. It uses only the crash records the city already
              keeps.
            </>
          )}
        </p>

        <p className="mt-3 text-[11px] leading-[1.5] text-ink-3">
          Crash records through {CITY.crashDataThrough}.
          {trafficYears && <> Traffic counts {trafficYears}.</>}
          {recent?.source?.through && <> Police reports through {fmtDate(recent.source.through)}.</>}
        </p>
      </div>

      <hr className="rule" />
      <FilterBar filters={filters} onFiltersChange={onFiltersChange} intersections={intersections} />

      <hr className="rule" />
      <RoutePanel
        intersections={intersections}
        filters={filters}
        onRoute={onRoute}
        onSelect={onSelectIntersection}
      />

      <hr className="rule-strong" />
      <CatchFigure threshold={filters.threshold} />

      <hr className="rule-strong" />
      <DistrictSummary
        districts={districts}
        filters={filters}
        onFiltersChange={onFiltersChange}
        intersections={intersections}
        onNavigate={onNavigate}
      />
    </div>
  );
}
