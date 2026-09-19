import { useState } from "react";
import MapView from "./MapView";
import SearchBox from "./SearchBox";
import MobileSheet from "./MobileSheet";
import AboutModal from "./AboutModal";
import RoutePanel from "./RoutePanel";

// The sheet occupies the lower half of the screen, so a selected dot centred on
// the map would land underneath it. Push the map so the dot sits in the visible
// upper half instead.
const SHEET_OFFSET_PX = 140;

/**
 * Phone layout: the map, a search field, a route button, an info button, and a
 * detail sheet on tap. No shortlist selector, no district filter, no legend,
 * no table. The welcome screen explains that darker dots mean higher risk; the
 * sheet names the tier on tap.
 */
export default function MobileShell({
  intersections, filters, selected, onSelect,
  traffic = null, recent = null, control = null, routeOverlay = null, onRoute,
}) {
  const [aboutOpen, setAboutOpen] = useState(false);
  const [routeOpen, setRouteOpen] = useState(false);

  return (
    <div className="relative h-dvh w-full overflow-hidden bg-paper">
      <MapView
        intersections={intersections}
        filters={filters}
        selectedIntersection={selected}
        onSelectIntersection={onSelect}
        showLegend={false}
        selectionOffsetY={SHEET_OFFSET_PX}
        routeOverlay={routeOverlay}
        trafficControlClass="left-3"
        trafficControlStyle={{ top: "calc(max(12px, env(safe-area-inset-top)) + 54px)" }}
      />

      {/* Floating bar, kept clear of the notch. */}
      <div
        className="absolute inset-x-3 z-10 flex items-stretch gap-2"
        style={{ top: "max(12px, env(safe-area-inset-top))" }}
      >
        <div className="min-w-0 flex-1 shadow-paper">
          <SearchBox intersections={intersections} threshold={filters.threshold} onSelect={onSelect} />
        </div>

        <button
          onClick={() => setRouteOpen(true)}
          aria-label="Check my route"
          title="Check my route"
          className={`flex h-11 w-11 shrink-0 items-center justify-center border shadow-paper active:bg-paper-edge ${
            routeOverlay ? "border-ink bg-ink text-paper" : "border-rule-strong bg-paper text-ink"
          }`}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
            <circle cx="4" cy="14" r="2" stroke="currentColor" strokeWidth="1.4" />
            <circle cx="14" cy="4" r="2" stroke="currentColor" strokeWidth="1.4" />
            <path d="M5.5 12.5 12.5 5.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
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

      <MobileSheet
        feature={selected}
        onClose={() => onSelect(null)}
        traffic={traffic}
        recent={recent}
        control={control}
      />

      {routeOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Check my route"
          className="fixed inset-0 z-[60] overflow-y-auto bg-paper"
          style={{ paddingTop: "max(12px, env(safe-area-inset-top))", paddingBottom: "max(16px, env(safe-area-inset-bottom))" }}
        >
          <div className="flex items-center justify-between border-b border-rule-strong px-5 pb-3">
            <p className="label">Where do you drive?</p>
            <button
              onClick={() => setRouteOpen(false)}
              aria-label="Close"
              className="-mr-2 flex h-11 w-11 items-center justify-center text-ink-3"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              </svg>
            </button>
          </div>
          <div className="px-5 py-4">
            <p className="mb-4 text-[13px] leading-[1.5] text-ink-2">
              One address shows the listed corners near it. Two show the corners a driving
              route passes through.
            </p>
            <RoutePanel
              compact
              intersections={intersections}
              filters={filters}
              onRoute={onRoute}
              onSelect={(f) => { onSelect(f); setRouteOpen(false); }}
            />
            {routeOverlay && (
              <button
                onClick={() => setRouteOpen(false)}
                className="mt-5 block w-full bg-ink py-3 text-center text-[15px] font-semibold text-paper"
              >
                Show on the map
              </button>
            )}
          </div>
        </div>
      )}

      {aboutOpen && <AboutModal onClose={() => setAboutOpen(false)} />}
    </div>
  );
}
