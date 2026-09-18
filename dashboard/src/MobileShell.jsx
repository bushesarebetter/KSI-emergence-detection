import { useState } from "react";
import MapView from "./MapView";
import SearchBox from "./SearchBox";
import MobileSheet from "./MobileSheet";
import AboutModal from "./AboutModal";

// The sheet occupies the lower ~46% of the screen, so a selected dot centred on
// the map would land underneath it. Push the map so the dot sits in the visible
// upper half instead.
const SHEET_OFFSET_PX = 140;

/**
 * Phone layout.
 *
 * Not the desktop layout with things hidden -- a separate shell built from the
 * brief "the map must dominate, bare minimum, as few settings as possible".
 * Four elements: the map, a search field, an info control, and a detail sheet
 * on tap. No shortlist selector (fixed at the README's top-500), no district
 * filter, no legend, no table. The welcome screen explains that darker dots
 * mean higher risk; the sheet names the tier on tap. That is the whole key.
 */
export default function MobileShell({ intersections, filters, selected, onSelect }) {
  const [aboutOpen, setAboutOpen] = useState(false);

  return (
    <div className="relative h-dvh w-full overflow-hidden bg-paper">
      <MapView
        intersections={intersections}
        filters={filters}
        selectedIntersection={selected}
        onSelectIntersection={onSelect}
        showLegend={false}
        selectionOffsetY={SHEET_OFFSET_PX}
      />

      {/* Floating bar, kept clear of the notch / Dynamic Island. */}
      <div
        className="absolute inset-x-3 z-10 flex items-stretch gap-2"
        style={{ top: "max(12px, env(safe-area-inset-top))" }}
      >
        <div className="min-w-0 flex-1 shadow-paper">
          <SearchBox
            intersections={intersections}
            threshold={filters.threshold}
            onSelect={onSelect}
          />
        </div>

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

      <MobileSheet feature={selected} onClose={() => onSelect(null)} />

      {aboutOpen && <AboutModal onClose={() => setAboutOpen(false)} />}
    </div>
  );
}
