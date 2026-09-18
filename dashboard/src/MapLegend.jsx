import { useState } from "react";
import { useAdvanced } from "./useAdvanced";
import { useComposition } from "./useMeta";

// Sequential ramp, dark → light. Ordering is carried by lightness as well as
// hue, so the tiers stay distinguishable in greyscale and to colourblind readers.
export const RISK_TIERS = [
  { lo: 1, hi: 50, hex: "#7F1D1D", r: 7 },
  { lo: 51, hi: 100, hex: "#C2410C", r: 6.5 },
  { lo: 101, hi: 200, hex: "#D97706", r: 6 },
  { lo: 201, hi: null, hex: "#E8B563", r: 5.5 }, // through the current threshold
];

const TIER_LABELS = ["Highest risk", "High", "Elevated", "Moderate"];

/**
 * Map key.
 *
 * Fully opaque: a translucent panel reads as unfinished over light basemap
 * tiles. A printed map carries a solid key box with a hairline border; so does
 * this. The last tier's range follows the selected shortlist size rather than
 * being pinned to 500, and a combined export adds a row for known sites.
 */
export default function MapLegend({ threshold }) {
  const { advanced } = useAdvanced();
  const { known, screen, isCombined } = useComposition();
  // Expanded it covers roughly half a phone screen, so it starts closed on
  // narrow viewports and open where there is room.
  const [open, setOpen] = useState(
    () => typeof window === "undefined" || window.innerWidth >= 768
  );

  const visible = RISK_TIERS.filter((t) => t.lo <= threshold);
  const range = (t) => `${t.lo}–${t.hi ?? threshold}`;

  return (
    <div className="absolute bottom-16 left-4 z-10 border border-rule-strong bg-paper shadow-paper">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-8 px-4 py-2.5 text-left transition-colors hover:bg-paper-edge"
      >
        <span className="label">{advanced ? "Predicted risk" : "Map key"}</span>
        <span
          aria-hidden="true"
          className={`text-ink-3 transition-transform ${open ? "" : "rotate-180"}`}
        >
          <svg width="9" height="9" viewBox="0 0 10 10" fill="none">
            <path d="M2 6.5l3-3 3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
        </span>
      </button>

      {open && (
        <div className="min-w-[210px] border-t border-rule px-4 pb-4 pt-3">
          <ul className="space-y-[7px]">
            {visible.map((t, i) => (
              <li key={t.lo} className="flex items-center gap-3">
                <svg width="16" height="16" className="shrink-0" aria-hidden="true">
                  <circle cx="8" cy="8" r={t.r} fill={t.hex} />
                </svg>
                <span className="flex-1 text-[12.5px] leading-none text-ink">
                  {TIER_LABELS[i]}
                </span>
                <span className="tnum text-[11px] leading-none text-ink-3">{range(t)}</span>
              </li>
            ))}
          </ul>

          {isCombined && (
            <div className="mt-3.5 space-y-[9px] border-t border-rule pt-3">
              {known > 0 && (
                <div className="flex items-center gap-3">
                  <svg width="16" height="16" className="shrink-0" aria-hidden="true">
                    <circle cx="8" cy="8" r={6} fill="#7F1D1D" stroke="#17150F" strokeWidth="2.4" />
                  </svg>
                  <span className="text-[12px] leading-[1.3] text-ink">
                    {advanced ? "Known KSI site" : "Already had a serious crash"}
                    <span className="block text-[11px] text-ink-3">
                      {known} on this list · not a prediction
                    </span>
                  </span>
                </div>
              )}
              {screen > 0 && (
                <div className="flex items-center gap-3">
                  <svg width="16" height="16" className="shrink-0" aria-hidden="true">
                    <circle cx="8" cy="8" r={6} fill="#C2410C" stroke="#17150F" strokeWidth="1.4" strokeDasharray="2 1.6" />
                  </svg>
                  <span className="text-[12px] leading-[1.3] text-ink">
                    {advanced ? "City screen (≥5 crashes/yr)" : "On the City's own list"}
                    <span className="block text-[11px] text-ink-3">{screen} on this list</span>
                  </span>
                </div>
              )}
            </div>
          )}

          <div className="mt-3.5 space-y-[9px] border-t border-rule pt-3">
            <div className="flex items-center gap-3">
              <svg width="16" height="16" className="shrink-0" aria-hidden="true">
                <circle cx="8" cy="8" r={5} fill="#7F1D1D" />
                <circle cx="8" cy="8" r={7.4} fill="none" stroke="#17150F" strokeWidth="1.6" />
              </svg>
              <span className="text-[12px] leading-[1.3] text-ink">
                {advanced ? "2025 KSI, caught" : "Serious crash in 2025"}
                <span className="block text-[11px] text-ink-3">
                  {advanced ? `top-${threshold} hit` : "this list flagged it"}
                </span>
              </span>
            </div>

            <div className="flex items-center gap-3">
              <svg width="16" height="16" className="shrink-0" aria-hidden="true">
                <circle cx="8" cy="8" r={5} fill="#7F1D1D" />
                <circle
                  cx="8" cy="8" r={7.4} fill="none"
                  stroke="#8A8272" strokeWidth="1.2" strokeDasharray="2.2 2"
                />
              </svg>
              <span className="text-[12px] leading-[1.3] text-ink">
                {advanced ? "2025 KSI, missed" : "Serious crash in 2025"}
                <span className="block text-[11px] text-ink-3">
                  {advanced ? `outside top-${threshold}` : "this list missed it"}
                </span>
              </span>
            </div>
          </div>

          <p className="mt-3.5 border-t border-rule pt-2.5 text-[11px] leading-[1.4] text-ink-3">
            {advanced ? "Dot size ∝ rank tier" : "Larger dot = higher risk. Click one for detail."}
          </p>
        </div>
      )}
    </div>
  );
}

