import { useAdvanced } from "./useAdvanced";
import FilterBar from "./FilterBar";
import DistrictSummary from "./DistrictSummary";
import CatchFigure from "./CatchFigure";

/**
 * The editorial column.
 *
 * Read top to bottom it is a short article: what this shows, how much of it to
 * show, how well it has worked, and where it concentrates. That ordering is the
 * design — a first-time visitor gets the claim and the caveat before they get
 * any controls, which is the opposite of a dashboard, where controls come first
 * and meaning is left to the reader.
 */
export default function Sidebar({ intersections, districts, filters, onFiltersChange }) {
  const { advanced } = useAdvanced();

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-paper">
      {/* Standfirst */}
      <div className="px-6 pb-6 pt-6">
        <p className="label mb-3">{advanced ? "Forward run" : "What this shows"}</p>

        <h2 className="font-serif text-[27px] font-medium leading-[1.12] tracking-[-0.015em] text-ink">
          {advanced ? (
            <>Predicted KSI emergence, 2025–2027</>
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
              26,045 City-of-San-Diego intersections with no KSI history through 2024,
              ranked by predicted KSI count over the label window.
            </>
          ) : (
            <>
              Every San Diego intersection that has never had a serious crash, ranked by
              how likely it is to have one — using only crash records the city already
              keeps.
            </>
          )}
        </p>
      </div>

      <hr className="rule" />
      <FilterBar filters={filters} onFiltersChange={onFiltersChange} />

      <hr className="rule-strong" />
      <CatchFigure threshold={filters.threshold} />

      <hr className="rule-strong" />
      <DistrictSummary
        districts={districts}
        filters={filters}
        onFiltersChange={onFiltersChange}
        intersections={intersections}
      />
    </div>
  );
}
