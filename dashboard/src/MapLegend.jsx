import { useState } from "react";
import { useAdvanced } from "./useAdvanced";

// YlOrRd-derived colorblind-safe ramp (red = highest risk, yellow = lower risk)
const RISK_TIERS = [
  { range: "1–50", color: "#ef4444", radius: 7 },
  { range: "51–100", color: "#f97316", radius: 6.5 },
  { range: "101–200", color: "#fbbf24", radius: 6 },
  { range: "201–500", color: "#fde68a", radius: 5.5 },
];

function tierVisible(range, threshold) {
  return parseInt(range.split("–")[0], 10) <= threshold;
}

/**
 * Collapsible so it does not eat the map on a phone, and opaque rather than
 * translucent because the Google basemap may be light or dark depending on
 * whether a dark style is attached to the Map ID -- a semi-transparent panel
 * that reads fine over dark tiles becomes unreadable over light ones.
 */
export default function MapLegend({ threshold }) {
  const { advanced, copy } = useAdvanced();
  // Expanded, the legend covers roughly half a phone screen, so it starts closed
  // on narrow viewports and open where there is room for it.
  const [open, setOpen] = useState(
    () => typeof window === "undefined" || window.innerWidth >= 768
  );

  const visible = RISK_TIERS.filter((t) => tierVisible(t.range, threshold));
  const sub = (fn) => (typeof fn === "function" ? fn(threshold) : fn);

  return (
    <div className="absolute bottom-14 left-3 z-10 overflow-hidden rounded-xl border border-slate-700 bg-slate-900 shadow-2xl">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-6 px-3.5 py-2.5 text-left transition-colors hover:bg-slate-800"
      >
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          {copy.legendTitle}
        </span>
        <span className={`text-slate-500 transition-transform ${open ? "rotate-180" : ""}`}>
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
            <path d="M2 4l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </span>
      </button>

      {open && (
        <div className="min-w-[180px] px-3.5 pb-3.5">
          <div className="flex flex-col gap-2">
            {visible.map(({ range, color, radius }, i) => (
              <div key={range} className="flex items-center gap-2.5">
                <svg width="18" height="18" className="shrink-0" aria-hidden="true">
                  <circle
                    cx="9" cy="9" r={radius} fill={color}
                    stroke="rgba(255,255,255,0.25)" strokeWidth="1.5"
                  />
                </svg>
                <div className="min-w-0">
                  <div className="text-xs font-medium leading-tight text-slate-200">
                    {copy.legendTiers[i]}
                  </div>
                  <div className="text-[10px] text-slate-500">{copy.legendRange(range)}</div>
                </div>
              </div>
            ))}

            <div className="mt-0.5 flex items-center gap-2.5 border-t border-slate-700/60 pt-2.5">
              <svg width="18" height="18" className="shrink-0" aria-hidden="true">
                <circle cx="9" cy="9" r={5} fill="#ef4444" />
                <circle cx="9" cy="9" r={8} fill="none" stroke="white" strokeWidth="2" />
              </svg>
              <div className="min-w-0">
                <div className="text-xs font-medium leading-tight text-slate-200">
                  {copy.legendCaught}
                </div>
                <div className="text-[10px] text-emerald-500/80">{sub(copy.legendCaughtSub)}</div>
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              <svg width="18" height="18" className="shrink-0" aria-hidden="true">
                <circle cx="9" cy="9" r={5} fill="#ef4444" />
                <circle cx="9" cy="9" r={8} fill="none" stroke="#64748b" strokeOpacity="0.5" strokeWidth="1.5" />
              </svg>
              <div className="min-w-0">
                <div className="text-xs font-medium leading-tight text-slate-200">
                  {copy.legendMissed}
                </div>
                <div className="text-[10px] text-slate-500">{sub(copy.legendMissedSub)}</div>
              </div>
            </div>
          </div>

          <div className="mt-3 border-t border-slate-700/60 pt-2.5 text-[10px] leading-snug text-slate-500">
            {copy.legendSize}
            {!advanced && (
              <div className="mt-1 text-slate-600">{copy.mapHint}</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
