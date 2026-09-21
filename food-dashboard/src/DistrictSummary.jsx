import { useMemo } from "react";
import { useAdvanced } from "./useAdvanced";
import { passesFilters } from "./lib/filters";
import { SITE } from "./site";

/**
 * Listed places by council district, for the current shortlist and filters
 * other than district. Click one to filter the map to it; click again to
 * clear. Places outside the City have no district and are counted apart.
 */
export default function DistrictSummary({ facilities, filters, onFiltersChange }) {
  const { advanced } = useAdvanced();

  const rows = useMemo(() => {
    if (!facilities) return [];
    const base = { ...filters, districts: [] };
    const counts = {};
    let outside = 0;
    for (const f of facilities.features) {
      if (!passesFilters(f.properties, base)) continue;
      const d = f.properties.council_district;
      if (d) counts[d] = (counts[d] || 0) + 1;
      else outside += 1;
    }
    const list = Object.entries(counts).map(([d, n]) => ({ d: Number(d), n })).sort((a, b) => b.n - a.n);
    return outside ? [...list, { d: null, n: outside }] : list;
  }, [facilities, filters]);

  const toggle = (d) => {
    const on = filters.districts.length === 1 && filters.districts[0] === d;
    onFiltersChange({ ...filters, districts: on ? [] : [d] });
  };

  return (
    <div className="px-6 py-5">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <p className="label">{advanced ? "By district" : `By ${SITE.districts.label.toLowerCase()}`}</p>
        <p className="text-[11px] text-ink-3">select to filter the map</p>
      </div>
      <ul>
        {rows.map(({ d, n }) => {
          const on = d != null && filters.districts.length === 1 && filters.districts[0] === d;
          return (
            <li key={d ?? "outside"}>
              <button
                onClick={() => d != null && toggle(d)}
                aria-pressed={on}
                disabled={d == null}
                className={`flex w-full items-baseline justify-between gap-3 border-b border-rule py-1.5 text-left text-[13px] ${
                  on ? "font-semibold text-ink" : "text-ink-2 hover:text-ink"
                } disabled:cursor-default`}
              >
                <span>{d != null ? `${SITE.districts.short} ${d}` : "Outside the City"}</span>
                <span className="tnum text-ink-3">{n}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
