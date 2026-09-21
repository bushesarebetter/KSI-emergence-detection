import { useAdvanced } from "./useAdvanced";
import { useCatch, useSample } from "./useMeta";

/**
 * The one statement the project rests on, as a pull-figure with the fair
 * comparison beneath it: how many of the places that went on to have a major
 * violation were already on the list, against what picking at random would
 * have found. Every number comes from meta.json.
 */
export default function CatchFigure({ threshold }) {
  const { advanced } = useAdvanced();
  const { caught, total, lift, scored } = useCatch(threshold);
  const sample = useSample();
  const randomCatch = lift ? Math.max(1, Math.round(caught / lift)) : null;

  if (!scored) {
    return (
      <div className="bg-paper-sunk px-6 py-6">
        <p className="label mb-3">{advanced ? `Recall @ K=${threshold}` : "How well it has worked"}</p>
        <p className="text-[13px] leading-[1.5] text-ink-2">
          Not yet scored. The list is checked against the inspections that come after it; the
          first figure appears once a season of them is in.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-paper-sunk px-6 py-6">
      <p className="label mb-4">{advanced ? `Recall @ K=${threshold}` : "How well it has worked"}</p>

      <div className="flex items-start gap-4">
        <span className="tnum shrink-0 font-serif text-[52px] font-normal leading-[0.82] text-ink">{caught}</span>
        <p className="pt-1 text-[13px] leading-[1.5] text-ink-2">
          {advanced ? (
            <>
              of <span className="tnum font-medium text-ink">{total}</span> positives caught in the
              model&rsquo;s top <span className="tnum font-medium text-ink">{threshold}</span>.
            </>
          ) : (
            <>
              of the <span className="tnum font-medium text-ink">{total}</span> places that had a
              major violation at their next inspection were already on this list of{" "}
              <span className="tnum font-medium text-ink">{threshold}</span>.
            </>
          )}
        </p>
      </div>

      <p className="mt-4 border-t border-rule pt-3 text-[12px] leading-[1.5] text-ink-3">
        {lift == null ? (
          "No validation figure is available for this shortlist size."
        ) : advanced ? (
          <>
            <span className="tnum font-medium text-ink-2">{lift.toFixed(1)}×</span> lift over random at this K.
          </>
        ) : (
          <>
            Picking {threshold} at random would have caught about{" "}
            <span className="tnum font-medium text-ink-2">{randomCatch}</span>. The list still misses most of them.
          </>
        )}
        {sample && <> These are sample numbers.</>}
      </p>
    </div>
  );
}
