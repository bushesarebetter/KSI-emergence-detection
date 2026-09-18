import { useAdvanced } from "./useAdvanced";

// recall@K, forward run, >=1 KSI (108 positives, 2025 partial label window). Source:
// results/recall_evaluation.json / docs/DECISIONS.md D17. Scored by a model fit once on
// the verified-run's resolved 2016-2021->2022-2024 window and applied via predict-only
// to current forward-candidate features -- it never fit on the 2025-2027 outcome being
// counted here. Deliberately static so this can't silently drift; re-run
// scripts/predict_forward_run.py and update these by hand when new label years land.
export const CATCH_STATS = {
  50: { caught: 2, total: 108 },
  100: { caught: 3, total: 108 },
  200: { caught: 9, total: 108 },
  500: { caught: 24, total: 108 },
};

const RANDOM_LIFT = { 50: 9.6, 100: 7.2, 200: 10.9, 500: 11.6 };

/**
 * The one statement the whole project rests on, set as an editorial pull-figure.
 *
 * A progress bar labelled "catch rate 8%" invites the reader to see 8% as a bad
 * score out of 100. The honest framing is a ratio against a hard baseline: 9 of
 * 108, which is roughly eleven times what picking at random would find. Setting
 * the numerator large and serif, with the sentence running beneath it, puts the
 * comparison rather than the percentage in front of the reader.
 */
export default function CatchFigure({ threshold }) {
  const { advanced } = useAdvanced();
  const { caught, total } = CATCH_STATS[threshold] ?? { caught: 0, total: 0 };
  const lift = RANDOM_LIFT[threshold];

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
              of <span className="tnum font-medium text-ink">{total}</span> 2025 KSI
              positives caught in the top&nbsp;
              <span className="tnum font-medium text-ink">{threshold}</span>.
            </>
          ) : (
            <>
              of the <span className="tnum font-medium text-ink">{total}</span> intersections
              that had a serious crash in 2025 were already on this list of{" "}
              <span className="tnum font-medium text-ink">{threshold}</span>.
            </>
          )}
        </p>
      </div>

      {/* The comparison that gives the figure meaning. */}
      <p className="mt-4 border-t border-rule pt-3 text-[12px] leading-[1.5] text-ink-3">
        {advanced ? (
          <>
            <span className="tnum font-medium text-ink-2">{lift}×</span> lift over random
            at this K.
          </>
        ) : (
          <>
            About{" "}
            <span className="tnum font-medium text-ink-2">
              {Math.round(lift)} times better
            </span>{" "}
            than picking that many intersections at random — and still missing most of
            them.
          </>
        )}
      </p>
    </div>
  );
}
