import { useAdvanced } from "./useAdvanced";
import Term from "./Term";

const THRESHOLD_OPTIONS = [50, 100, 200, 500];

// recall@K, forward run, >=1 KSI (108 positives, 2025 partial label window). Source:
// results/recall_evaluation.json / docs/DECISIONS.md D17. Scored by a model fit once on
// the verified-run's resolved 2016-2021->2022-2024 window and applied via predict-only
// to current forward-candidate features -- it never fit on the 2025-2027 outcome being
// counted here. Deliberately static so this can't silently drift; re-run
// scripts/predict_forward_run.py and update these by hand when new label years land.
const CATCH_STATS = {
  50: { caught: 2, total: 108 },
  100: { caught: 3, total: 108 },
  200: { caught: 9, total: 108 },
  500: { caught: 24, total: 108 },
};

export default function FilterBar({ filters, onFiltersChange }) {
  const { advanced, copy } = useAdvanced();

  function handleThreshold(t) {
    onFiltersChange({ ...filters, threshold: t });
  }

  const { caught, total } = CATCH_STATS[filters.threshold] ?? { caught: 0, total: 0 };
  const pct = total > 0 ? Math.round((caught / total) * 100) : 0;

  return (
    <div className="border-b border-slate-800">
      <div className="px-4 pb-2.5 pt-4 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
        {copy.filterTitle}
      </div>
      <div className="grid grid-cols-2 gap-1.5 px-4 pb-3">
        {THRESHOLD_OPTIONS.map((value) => (
          <button
            key={value}
            onClick={() => handleThreshold(value)}
            aria-pressed={filters.threshold === value}
            className={`rounded-md py-2 text-sm font-medium transition-all ${
              filters.threshold === value
                ? "bg-orange-500 text-white shadow-sm shadow-orange-500/25 ring-1 ring-orange-400/30"
                : "border border-slate-700 bg-slate-800 text-slate-400 hover:bg-slate-700/80 hover:text-slate-200"
            }`}
          >
            {copy.filterOption(value)}
          </button>
        ))}
      </div>

      {total > 0 && (
        <div className="px-4 pb-4">
          <div className="rounded-lg border border-slate-700/40 bg-slate-800/60 px-3 py-2.5">
            <div className="mb-1.5 flex items-baseline justify-between gap-2">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                <Term id="catchRate">{copy.catchTitle}</Term>
              </span>
              <span className="text-xs font-bold tabular-nums text-orange-400">{pct}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-700">
              <div
                className="h-full rounded-full bg-orange-500 transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="mt-2 text-[11px] leading-relaxed text-slate-500">
              {advanced ? (
                <>
                  <span className="font-semibold text-orange-400">{caught}</span>
                  {" of "}
                  <span className="text-slate-400">{total}</span>
                  {" 2025 KSI positives, top "}
                  <span className="text-slate-400">{filters.threshold}</span>
                </>
              ) : (
                copy.catchDetail(caught, total, filters.threshold)
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
