const THRESHOLD_OPTIONS = [
  { value: 50, label: "Top 50" },
  { value: 100, label: "Top 100" },
  { value: 200, label: "Top 200" },
  { value: 500, label: "Top 500" },
];

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
  function handleThreshold(t) {
    onFiltersChange({ ...filters, threshold: t });
  }

  const { caught, total } = CATCH_STATS[filters.threshold] ?? { caught: 0, total: 0 };
  const pct = total > 0 ? Math.round((caught / total) * 100) : 0;

  return (
    <div className="border-b border-slate-800">
      <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest px-4 pt-4 pb-2.5">
        Top N Sites
      </div>
      <div className="px-4 pb-3 grid grid-cols-2 gap-1.5">
        {THRESHOLD_OPTIONS.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => handleThreshold(value)}
            className={`py-2 text-sm font-medium rounded-md transition-all ${
              filters.threshold === value
                ? "bg-orange-500 text-white shadow-sm shadow-orange-500/25 ring-1 ring-orange-400/30"
                : "bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700/80 hover:text-slate-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {total > 0 && (
        <div className="px-4 pb-4">
          <div className="bg-slate-800/60 rounded-lg px-3 py-2.5 border border-slate-700/40">
            <div className="flex items-baseline justify-between mb-1.5">
              <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">
                Catch rate
              </span>
              <span className="text-xs font-bold text-orange-400 tabular-nums">
                {pct}%
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-orange-500 rounded-full transition-all duration-500"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
            <div className="mt-1.5 text-[10px] text-slate-500">
              <span className="text-orange-400 font-semibold">{caught}</span>
              {" of "}
              <span className="text-slate-400">{total}</span>
              {" 2025 KSI positives, top "}
              <span className="text-slate-400">{filters.threshold}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
