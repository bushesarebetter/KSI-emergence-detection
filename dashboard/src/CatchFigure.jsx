import { useAdvanced } from "./useAdvanced";
import { useCatch } from "./useMeta";

/**
 * The one statement the whole project rests on, set as a pull-figure.
 *
 * A progress bar labelled "catch rate 8%" invites the reader to see 8% as a bad
 * score out of 100. The fair framing is a comparison: 34 of 108, against the 3
 * that picking 800 corners at random would find. The numerator is set large and
 * serif with the sentence running beneath it, so the comparison rather than the
 * percentage is what the reader takes away.
 *
 * Numbers come from /data/meta.json, written by the export, so this can never
 * drift from the data on the map.
 */
export default function CatchFigure({ threshold }) {
  const { advanced } = useAdvanced();
  const { caught, total, lift } = useCatch(threshold);
  const randomCatch = lift ? Math.max(1, Math.round(caught / lift)) : null;

  return (
    <div className="bg-paper-sunk px-6 py-6">
      <p className="label mb-4">{advanced ? `Recall @ K=${threshold}` : "How well it has worked"}</p>

      <div className="flex items-start gap-4">
        <span className="tnum shrink-0 font-serif text-[52px] font-normal leading-[0.82] text-ink">
          {caught}
        </span>
        <p className="pt-1 text-[13px] leading-[1.5] text-ink-2">
          {advanced ? (
            <>
              of <span className="tnum font-medium text-ink">{total}</span> 2025 KSI positives
              caught in the model&rsquo;s top&nbsp;
              <span className="tnum font-medium text-ink">{threshold}</span>.
            </>
          ) : (
            <>
              of the <span className="tnum font-medium text-ink">{total}</span> intersections
              that had a serious crash in 2025 so far were already on this list of{" "}
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
            <span className="tnum font-medium text-ink-2">{lift.toFixed(1)}×</span> lift over random
            at this K.
          </>
        ) : (
          <>
            Picking {threshold} at random would have caught about{" "}
            <span className="tnum font-medium text-ink-2">{randomCatch}</span>. The list still
            misses most of them.
          </>
        )}
      </p>
    </div>
  );
}
