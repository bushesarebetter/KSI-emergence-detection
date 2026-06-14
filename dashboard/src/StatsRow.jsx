export default function StatsRow({ intersections, filters }) {
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
    { label: "Window", value: "2024–26" },
    { label: "Sites shown", value: shown.length },
    { label: "Emergent", value: emergentCount, accent: true },
    { label: "Top district", value: topEntry ? `D${topEntry[0]}` : "—" },
  ];

  return (
    <div className="grid grid-cols-2 gap-px bg-slate-800 border-b border-slate-800 shrink-0">
      {stats.map(({ label, value, accent }) => (
        <div key={label} className="flex flex-col gap-1 px-4 py-3 bg-slate-900">
          <span className="text-[10px] font-semibold text-slate-600 uppercase tracking-widest">
            {label}
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
