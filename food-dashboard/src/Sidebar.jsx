import { useAdvanced } from "./useAdvanced";
import { useMeta } from "./useMeta";
import FilterBar from "./FilterBar";
import NearPanel from "./NearPanel";
import DistrictSummary from "./DistrictSummary";
import CatchFigure from "./CatchFigure";
import { fmtDate } from "./lib/dates";
import { SITE } from "./site";

/**
 * The editorial column, read top to bottom: what this shows and how fresh it
 * is, how much of it to show and of what kind, whether any of it is near
 * you, how well it has worked, and where it concentrates.
 */
export default function Sidebar({ facilities, filters, onFiltersChange, onPoint, onSelect }) {
  const { advanced } = useAdvanced();
  const meta = useMeta();

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-paper">
      <div className="px-6 pb-6 pt-6">
        <p className="label mb-3">{advanced ? "Forward run" : "What this shows"}</p>

        <h2 className="font-serif text-[27px] font-medium leading-[1.12] tracking-[-0.015em] text-ink">
          {advanced ? (
            <>Predicted major violation at the next routine inspection</>
          ) : (
            <>
              The places most likely
              <br />
              to fail their next inspection
            </>
          )}
        </h2>

        <p className="mt-3.5 max-w-measure text-[13.5px] leading-[1.55] text-ink-2">
          {advanced ? (
            <>
              {SITE.name} retail food facilities ranked by predicted probability of at least one
              major violation at the next routine inspection, from the County&rsquo;s published
              inspection history.
            </>
          ) : (
            <>
              Every {SITE.name} restaurant, market and food truck, ranked by how likely the
              County&rsquo;s next routine inspection is to find a major violation. It uses only the
              inspection results the County already publishes.
            </>
          )}
        </p>

        <p className="mt-3 text-[11px] leading-[1.5] text-ink-3">
          {meta?.inspections_through && <>Inspections through {fmtDate(meta.inspections_through)}.</>}
          {meta?.generated && <> Model export {fmtDate(meta.generated)}.</>}
        </p>
      </div>

      <hr className="rule" />
      <FilterBar filters={filters} onFiltersChange={onFiltersChange} facilities={facilities} />

      <hr className="rule" />
      <NearPanel facilities={facilities} filters={filters} onPoint={onPoint} onSelect={onSelect} />

      <hr className="rule-strong" />
      <CatchFigure threshold={filters.threshold} />

      <hr className="rule-strong" />
      <DistrictSummary facilities={facilities} filters={filters} onFiltersChange={onFiltersChange} />
    </div>
  );
}
