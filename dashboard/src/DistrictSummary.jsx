import { useState, useMemo } from "react";

function countKey(threshold) {
  if (threshold <= 50) return "top_50_count";
  if (threshold <= 100) return "top_100_count";
  if (threshold <= 200) return "top_200_count";
  return "top_500_count";
}

function useEmergentsByDistrict(intersections, threshold) {
  return useMemo(() => {
    if (!intersections) return {};
    const counts = {};
    for (const f of intersections.features) {
      const p = f.properties;
      if (p.is_known_emergent && p.rank <= threshold) {
        counts[p.council_district] = (counts[p.council_district] || 0) + 1;
      }
    }
    return counts;
  }, [intersections, threshold]);
}

export default function DistrictSummary({ districts, filters, onFiltersChange, intersections }) {
  const [sortBy, setSortBy] = useState("count");

  if (!districts) return null;

  const key = countKey(filters.threshold);
  const maxCount = Math.max(...districts.map((d) => d[key]), 1);
  const emergentsByDistrict = useEmergentsByDistrict(intersections, filters.threshold);

  const sorted = [...districts].sort((a, b) =>
    sortBy === "count" ? b[key] - a[key] : a.district - b.district
  );

  function toggleDistrict(d) {
    const current = filters.districts;
    const next = current.includes(d) ? current.filter((x) => x !== d) : [...current, d];
    onFiltersChange({ ...filters, districts: next });
  }

  const anySelected = filters.districts.length > 0;

  return (
    <div className="flex flex-col pb-2">
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">
          By District
        </span>
        <button
          onClick={() => setSortBy((s) => (s === "count" ? "district" : "count"))}
          className="text-[10px] text-slate-600 hover:text-orange-400 transition-colors"
        >
          {sortBy === "count" ? "# Sites ↓" : "D# ↑"}
        </button>
      </div>

      {anySelected && (
        <button
          onClick={() => onFiltersChange({ ...filters, districts: [] })}
          className="mx-4 mb-2 text-[10px] text-slate-500 hover:text-orange-400 text-left transition-colors"
        >
          ✕ Clear selection
        </button>
      )}

      <div className="flex flex-col">
        {sorted.map((d) => {
          const count = d[key];
          const emergentCount = emergentsByDistrict[d.district] || 0;
          const selected = filters.districts.includes(d.district);
          const pct = (count / maxCount) * 100;

          return (
            <button
              key={d.district}
              onClick={() => toggleDistrict(d.district)}
              className={`w-full text-left px-4 py-2.5 transition-colors group border-l-2 ${
                selected
                  ? "bg-orange-500/10 border-orange-500"
                  : "border-transparent hover:bg-slate-800/60"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span
                  className={`text-xs font-semibold ${
                    selected ? "text-orange-400" : "text-slate-300 group-hover:text-slate-100"
                  }`}
                >
                  District {d.district}
                </span>
                <div className="flex items-center gap-1.5">
                  {emergentCount > 0 && (
                    <span className="flex items-center gap-0.5 text-[10px] font-bold text-orange-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-orange-400 inline-block" />
                      {emergentCount}
                    </span>
                  )}
                  <span
                    className={`text-xs font-bold tabular-nums ${
                      selected ? "text-orange-400" : "text-slate-500"
                    }`}
                  >
                    {count}
                  </span>
                </div>
              </div>
              <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${
                    selected ? "bg-orange-500" : "bg-slate-600 group-hover:bg-slate-500"
                  }`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
