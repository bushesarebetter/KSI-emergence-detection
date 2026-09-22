import { useState } from "react";
import { useAdvanced } from "./useAdvanced";

// Sequential ramp, dark to light; lightness carries the order so the tiers
// survive greyscale and colourblind viewing.
export const RISK_TIERS = [
  { lo: 1, hi: 50, hex: "#7F1D1D", r: 7 },
  { lo: 51, hi: 100, hex: "#C2410C", r: 6.5 },
  { lo: 101, hi: 200, hex: "#D97706", r: 6 },
  { lo: 201, hi: null, hex: "#E8B563", r: 5.5 },
];

const TIER_LABELS = ["Highest risk", "High", "Elevated", "Moderate"];

export default function MapLegend({ threshold }) {
  const { advanced } = useAdvanced();
  const [open, setOpen] = useState(() => typeof window === "undefined" || window.innerWidth >= 768);

  const visible = RISK_TIERS.filter((t) => t.lo <= threshold);
  const range = (t) => `${t.lo} to ${t.hi ?? threshold}`;

  return (
    <div className="absolute bottom-16 left-4 z-10 border border-rule-strong bg-paper shadow-paper">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-8 px-4 py-2.5 text-left hover:bg-paper-edge"
      >
        <span className="label">{advanced ? "Predicted risk" : "Map key"}</span>
        <span aria-hidden="true" className={`text-ink-3 ${open ? "" : "rotate-180"}`}>
          <svg width="9" height="9" viewBox="0 0 10 10" fill="none">
            <path d="M2 6.5l3-3 3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
        </span>
      </button>

      {open && (
        <div className="min-w-[220px] border-t border-rule px-4 pb-4 pt-3">
          <ul className="space-y-[7px]">
            {visible.map((t, i) => (
              <li key={t.lo} className="flex items-center gap-3">
                <svg width="16" height="16" className="shrink-0" aria-hidden="true">
                  <circle cx="8" cy="8" r={t.r} fill={t.hex} />
                </svg>
                <span className="flex-1 text-[12.5px] leading-none text-ink">{TIER_LABELS[i]}</span>
                <span className="tnum text-[11px] leading-none text-ink-3">{range(t)}</span>
              </li>
            ))}
          </ul>

          <p className="mt-3.5 border-t border-rule pt-2.5 text-[11px] leading-[1.4] text-ink-3">
            {advanced
              ? "Dot size follows rank tier."
              : "Bigger and darker means higher predicted risk. Click a dot to see what inspectors found there."}
          </p>
        </div>
      )}
    </div>
  );
}
