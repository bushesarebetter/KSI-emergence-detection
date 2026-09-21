import { useState } from "react";
import MapView from "./MapView";
import SearchBox from "./SearchBox";
import MobileSheet from "./MobileSheet";
import AboutModal from "./AboutModal";
import NearPanel from "./NearPanel";

// The sheet occupies the lower half of the screen; push the map so a
// selected dot sits in the visible upper half.
const SHEET_OFFSET_PX = 140;

/**
 * Phone layout: the map, a search field, a near-me button, an info button,
 * and a detail sheet on tap. No shortlist selector, no filters, no table.
 */
export default function MobileShell({ facilities, filters, selected, onSelect, pointOverlay, onPoint, onNavigate }) {
  const [aboutOpen, setAboutOpen] = useState(false);
  const [nearOpen, setNearOpen] = useState(false);

  return (
    <div className="relative h-dvh w-full overflow-hidden bg-paper">
      <MapView
        facilities={facilities}
        filters={filters}
        selected={selected}
        onSelect={onSelect}
        showLegend={false}
        selectionOffsetY={SHEET_OFFSET_PX}
        pointOverlay={pointOverlay}
      />

      <div className="absolute inset-x-3 z-10 flex items-stretch gap-2" style={{ top: "max(12px, env(safe-area-inset-top))" }}>
        <div className="min-w-0 flex-1 shadow-paper">
          <SearchBox facilities={facilities} threshold={filters.threshold} onSelect={onSelect} />
        </div>

        <button
          onClick={() => setNearOpen(true)}
          aria-label="Near an address"
          title="Near an address"
          className={`flex h-11 w-11 shrink-0 items-center justify-center border shadow-paper active:bg-paper-edge ${pointOverlay ? "border-ink bg-ink text-paper" : "border-rule-strong bg-paper text-ink"}`}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
            <circle cx="9" cy="8" r="3" stroke="currentColor" strokeWidth="1.4" />
            <path d="M9 16c3.5-4 5.5-6.5 5.5-8.5a5.5 5.5 0 0 0-11 0C3.5 9.5 5.5 12 9 16z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
          </svg>
        </button>

        <button
          onClick={() => setAboutOpen(true)}
          aria-label="How this works"
          className="flex h-11 w-11 shrink-0 items-center justify-center border border-rule-strong bg-paper text-ink shadow-paper active:bg-paper-edge"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
            <circle cx="9" cy="9" r="7.5" stroke="currentColor" strokeWidth="1.4" />
            <path d="M9 8v5M9 5.5h.01" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <MobileSheet feature={selected} onClose={() => onSelect(null)} onNavigate={onNavigate} />

      {nearOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Near an address"
          className="fixed inset-0 z-[60] overflow-y-auto bg-paper"
          style={{ paddingTop: "max(12px, env(safe-area-inset-top))", paddingBottom: "max(16px, env(safe-area-inset-bottom))" }}
        >
          <div className="flex items-center justify-between border-b border-rule-strong px-5 pb-3">
            <p className="label">Near an address</p>
            <button onClick={() => setNearOpen(false)} aria-label="Close" className="-mr-2 flex h-11 w-11 items-center justify-center text-ink-3">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              </svg>
            </button>
          </div>
          <div className="px-5 py-4">
            <p className="mb-4 text-[13px] leading-[1.5] text-ink-2">The listed places within 500 m of an address, nearest first.</p>
            <NearPanel
              compact
              facilities={facilities}
              filters={filters}
              onPoint={onPoint}
              onSelect={(f) => { onSelect(f); setNearOpen(false); }}
            />
            {pointOverlay && (
              <button onClick={() => setNearOpen(false)} className="mt-5 block w-full bg-ink py-3 text-center text-[15px] font-semibold text-paper">
                Show on the map
              </button>
            )}
          </div>
        </div>
      )}

      {aboutOpen && <AboutModal onClose={() => setAboutOpen(false)} onNavigate={onNavigate} />}
    </div>
  );
}
