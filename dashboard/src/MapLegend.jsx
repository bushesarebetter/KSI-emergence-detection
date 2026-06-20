// YlOrRd-derived colorblind-safe ramp (red = highest risk, yellow = lower risk)
const RISK_TIERS = [
  { range: "1–50",   color: "#ef4444", label: "Highest risk",  radius: 8 },
  { range: "51–100", color: "#f97316", label: "High risk",     radius: 7 },
  { range: "101–200",color: "#fbbf24", label: "Elevated risk", radius: 6 },
  { range: "201–500",color: "#fde68a", label: "Moderate risk", radius: 5 },
];

function tierVisible(range, threshold) {
  const lo = parseInt(range.split("–")[0], 10);
  return lo <= threshold;
}

export default function MapLegend({ threshold }) {
  const visible = RISK_TIERS.filter((t) => tierVisible(t.range, threshold));

  return (
    <div className="absolute bottom-10 left-3 z-10 bg-slate-900/92 backdrop-blur-sm border border-slate-700/60 rounded-xl p-4 shadow-2xl min-w-[172px]">
      <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-3">
        Predicted risk
      </div>

      <div className="flex flex-col gap-2.5">
        {visible.map(({ range, color, label, radius }) => (
          <div key={range} className="flex items-center gap-2.5">
            <svg width="20" height="20" className="shrink-0" aria-hidden="true">
              <circle
                cx="10"
                cy="10"
                r={radius}
                fill={color}
                stroke="rgba(255,255,255,0.2)"
                strokeWidth="1.5"
              />
            </svg>
            <div className="min-w-0">
              <div className="text-xs font-medium text-slate-300 leading-tight">{label}</div>
              <div className="text-[10px] text-slate-600">Rank {range}</div>
            </div>
          </div>
        ))}

        <div className="flex items-center gap-2.5 pt-2.5 mt-0.5 border-t border-slate-700/50">
          <svg width="20" height="20" className="shrink-0" aria-hidden="true">
            <circle cx="10" cy="10" r={6} fill="#ef4444" />
            <circle cx="10" cy="10" r={9} fill="none" stroke="white" strokeWidth="2" />
          </svg>
          <div className="min-w-0">
            <div className="text-xs font-medium text-slate-300 leading-tight">2025 KSI, caught</div>
            <div className="text-[10px] text-slate-600">out-of-fold top-500 hit</div>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <svg width="20" height="20" className="shrink-0" aria-hidden="true">
            <circle cx="10" cy="10" r={6} fill="#ef4444" />
            <circle cx="10" cy="10" r={9} fill="none" stroke="black" strokeWidth="2" />
          </svg>
          <div className="min-w-0">
            <div className="text-xs font-medium text-slate-300 leading-tight">2025 KSI, missed</div>
            <div className="text-[10px] text-slate-600">out-of-fold top-500 miss</div>
          </div>
        </div>
      </div>

      <div className="mt-3 pt-2.5 border-t border-slate-700/50 text-[10px] text-slate-600 leading-snug">
        Dot size ∝ rank tier
      </div>
    </div>
  );
}
