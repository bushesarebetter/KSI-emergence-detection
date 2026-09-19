import { useState, useMemo } from "react";
import { useAdvanced } from "./useAdvanced";
import { passesFilters } from "./lib/filters";

/**
 * districts.json carries a count per district at every shortlist size the
 * export knows about (top_50_count … top_1000_count). Use the exact key when
 * present; on an older file that lacks it, fall back to the largest size that
 * is present and no bigger than the threshold, so the bars never show a count
 * for a list larger than the one on the map.
 */
function countKey(threshold, sample) {
  const exact = `top_${threshold}_count`;
  if (!sample || exact in sample) return exact;
  const available = Object.keys(sample)
    .map((k) => /^top_(\d+)_count$/.exec(k))
    .filter(Boolean)
    .map((m) => Number(m[1]))
    .filter((k) => k <= threshold)
    .sort((a, b) => b - a);
  return available.length ? `top_${available[0]}_count` : exact;
}

// Counts per district under every active filter, computed from the loaded
// export so the bars agree with the map. districts.json only knows the
// shortlist sizes; it cannot know which kind of crash is selected.
function useCountsByDistrict(intersections, filters) {
  return useMemo(() => {
    if (!intersections) return null;
    const counts = {};
    const unrestricted = { ...filters, districts: [] };
    for (const f of intersections.features) {
      const p = f.properties;
      if (passesFilters(p, unrestricted)) counts[p.council_district] = (counts[p.council_district] || 0) + 1;
    }
    return counts;
  }, [intersections, filters.threshold, filters.pattern]);
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

/**
 * Distribution by council district, as a ranked table with inline bars.
 *
 * Council district is the unit of political action — each has a member who can
 * fund a change — so this doubles as a filter. The bar is drawn as a thin ink
 * rule under each row rather than a rounded track, keeping the one saturated
 * colour in the interface reserved for risk.
 */
export default function DistrictSummary({ districts, filters, onFiltersChange, intersections, onNavigate }) {
  const [sortBy, setSortBy] = useState("count");
  const { advanced } = useAdvanced();
  const key = countKey(filters.threshold, districts?.[0]);
  const emergentsByDistrict = useEmergentsByDistrict(intersections, filters.threshold);
  const live = useCountsByDistrict(intersections, filters);

  if (!districts) return null;

  const countFor = (d) => (live ? live[d.district] || 0 : d[key] ?? 0);
  const maxCount = Math.max(...districts.map(countFor), 1);
  const sorted = [...districts].sort((a, b) =>
    sortBy === "count" ? countFor(b) - countFor(a) : a.district - b.district
  );
  const anySelected = filters.districts.length > 0;

  function toggleDistrict(d) {
    const current = filters.districts;
    onFiltersChange({
      ...filters,
      districts: current.includes(d) ? current.filter((x) => x !== d) : [...current, d],
    });
  }

  return (
    <div className="px-6 pb-8 pt-5">
      <div className="mb-1 flex items-baseline justify-between gap-3">
        <p className="label">{advanced ? "By district" : "By council district"}</p>
        <button
          onClick={() => setSortBy((s) => (s === "count" ? "district" : "count"))}
          className="text-[11px] text-ink-3 hover:text-ink"
        >
          {sortBy === "count" ? "by count" : "by number"}
        </button>
      </div>

      <p className="mb-4 h-4 text-[11px] text-ink-3">
        {anySelected ? (
          <button
            onClick={() => onFiltersChange({ ...filters, districts: [] })}
            className="border-b border-ink/25 pb-px hover:border-ink hover:text-ink"
          >
            Clear {filters.districts.length} selected
          </button>
        ) : (
          "Select to filter the map"
        )}
      </p>

      <ul>
        {sorted.map((d) => {
          const count = countFor(d);
          const emergent = emergentsByDistrict[d.district] || 0;
          const selected = filters.districts.includes(d.district);
          const pct = (count / maxCount) * 100;

          return (
            <li key={d.district}>
              <button
                onClick={() => toggleDistrict(d.district)}
                aria-pressed={selected}
                className="group w-full border-b border-rule py-2.5 text-left"
              >
                <div className="mb-1.5 flex items-baseline justify-between gap-3">
                  <span
                    className={`text-[13px] ${
                      selected ? "font-semibold text-ink" : "text-ink-2 group-hover:text-ink"
                    }`}
                  >
                    {selected && <span aria-hidden="true">■&nbsp;</span>}
                    District {d.district}
                  </span>

                  <span className="flex shrink-0 items-baseline gap-2.5">
                    {emergent > 0 && (
                      <span
                        className="tnum text-[11px] text-risk-1"
                        title={`${emergent} had a serious crash in 2025`}
                      >
                        ●&nbsp;{emergent}
                      </span>
                    )}
                    <span
                      className={`tnum text-[13px] ${
                        selected ? "font-semibold text-ink" : "text-ink-3"
                      }`}
                    >
                      {count}
                    </span>
                  </span>
                </div>

                {/* Inline bar as a rule, not a track. */}
                <div className="h-px w-full bg-rule">
                  <div
                    className={`h-px ${
                      selected ? "bg-ink" : "bg-ink-3 group-hover:bg-ink-2"
                    }`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </button>
            </li>
          );
        })}
      </ul>

      <p className="mt-4 text-[11px] leading-[1.5] text-ink-3">
        <span className="text-risk-1">●</span> marks sites that went on to have a serious
        crash in 2025.
      </p>
      {onNavigate && (
        <p className="mt-3 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-[11px] text-ink-3">
          Printable report:
          {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((d) => (
            <a
              key={d}
              href={`/district/${d}`}
              onClick={(e) => { e.preventDefault(); onNavigate(`/district/${d}`); }}
              className="tnum border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink"
            >
              D{d}
            </a>
          ))}
        </p>
      )}
    </div>
  );
}
