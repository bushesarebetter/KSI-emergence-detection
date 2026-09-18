import { useAdvanced } from "./useAdvanced";
import Term from "./Term";

export default function StatsRow({ intersections, filters }) {
  const { advanced, copy } = useAdvanced();

  const shown = intersections?.features.filter((f) => {
    const p = f.properties;
    if (p.rank > filters.threshold) return false;
    if (filters.districts.length > 0 && !filters.districts.includes(p.council_district)) return false;
    return true;
  }) ?? [];

  const emergentCount = intersections?.features.filter(
    (f) => f.properties.is_known_emergent === true
  ).length ?? 0;

  const districtCounts = {};
  shown.forEach((f) => {
    const d = f.properties.council_district;
    districtCounts[d] = (districtCounts[d] || 0) + 1;
  });
  const topEntry = Object.entries(districtCounts).sort((a, b) => b[1] - a[1])[0];

  const stats = [
    { label: copy.statWindow, value: advanced ? "2025–27" : "2025–2027" },
    { label: copy.statShown, value: shown.length },
    // In plain mode the label already says "had a serious crash in 2025", so the
    // KSI glossary term is attached there rather than spelled into the label.
    { label: copy.statEmergent, value: emergentCount, accent: true, term: "ksi" },
    {
      label: copy.statTopDistrict,
      value: topEntry ? (advanced ? `D${topEntry[0]}` : `District ${topEntry[0]}`) : "—",
      term: "district",
    },
  ];

  return (
    <div className="grid shrink-0 grid-cols-2 gap-px border-b border-slate-800 bg-slate-800">
      {stats.map(({ label, value, accent, term }) => (
        <div key={label} className="flex flex-col gap-1 bg-slate-900 px-4 py-3">
          <span className="text-[10px] font-semibold uppercase leading-tight tracking-wider text-slate-500">
            {term ? <Term id={term}>{label}</Term> : label}
          </span>
          <span
            className={`text-lg font-bold leading-none tabular-nums ${
              accent ? "text-orange-400" : "text-slate-200"
            }`}
          >
            {value}
          </span>
        </div>
      ))}
    </div>
  );
}
