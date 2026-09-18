import { useRef, useState } from "react";
import { humanizeSignal } from "./lib/signals";

const TIERS = [
  { max: 50, hex: "#7F1D1D", label: "Highest risk" },
  { max: 100, hex: "#C2410C", label: "High risk" },
  { max: 200, hex: "#D97706", label: "Elevated risk" },
  { max: Infinity, hex: "#B8963F", label: "Moderate risk" },
];
const tierFor = (rank) => TIERS.find((t) => rank <= t.max);

// Finger must travel this far downward before a drag counts as a dismiss, so an
// accidental brush while reading does not close the sheet.
const DISMISS_PX = 64;

function parseProp(v) {
  return typeof v === "string" ? JSON.parse(v) : (v ?? []);
}

/**
 * Phone detail sheet. Deliberately the bare minimum: what it is, how risky, the
 * one main reason, and a way to look at it. Everything else lives on desktop.
 *
 * Capped at under half the viewport so the map -- the thing the user came for --
 * stays visible above it. Slides from below (deeper = enters from below), and
 * dismisses on a downward swipe past a threshold or via the explicit close
 * control, so touch users are never gesture-only.
 */
export default function MobileSheet({ feature, onClose }) {
  const [dragY, setDragY] = useState(0);
  const dragging = useRef(false);
  const startY = useRef(0);

  const open = feature !== null;
  const p = feature?.properties ?? {};
  const [lon, lat] = feature?.geometry?.coordinates ?? [0, 0];
  const tier = tierFor(p.rank ?? 1);
  const reason = humanizeSignal(parseProp(p.shap_features)?.[0]?.display_label);

  const onTouchStart = (e) => {
    startY.current = e.touches[0].clientY;
    dragging.current = true;
  };
  const onTouchMove = (e) => {
    if (!dragging.current) return;
    const dy = e.touches[0].clientY - startY.current;
    if (dy > 0) setDragY(dy);
  };
  const onTouchEnd = () => {
    dragging.current = false;
    if (dragY > DISMISS_PX) onClose();
    setDragY(0);
  };

  return (
    <section
      aria-hidden={!open}
      aria-label="Intersection detail"
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
      className={`fixed inset-x-0 bottom-0 z-40 max-h-[46dvh] overflow-y-auto border-t border-rule-strong bg-paper shadow-paper ${
        dragging.current ? "" : "transition-transform duration-250 ease-out"
      }`}
      style={{
        transform: open ? `translateY(${dragY}px)` : "translateY(100%)",
        paddingBottom: "max(16px, env(safe-area-inset-bottom))",
      }}
    >
      {open && (
        <>
          {/* Drag handle: the platform-standard affordance for "this swipes down". */}
          <div className="flex justify-center pt-2.5" aria-hidden="true">
            <span className="h-1 w-9 rounded-full bg-rule-strong" />
          </div>

          <div className="flex items-start justify-between gap-3 px-5 pt-2">
            <div className="min-w-0 flex-1">
              <p className="text-[12px] text-ink-2">
                <span className="tnum font-semibold" style={{ color: tier.hex }}>
                  #{p.rank}
                </span>
                <span className="mx-1.5 text-rule-strong">/</span>
                <span style={{ color: tier.hex }} className="font-semibold">
                  {tier.label}
                </span>
                <span className="mx-1.5 text-rule-strong">/</span>
                District {p.council_district}
              </p>
              <h2 className="mt-1 font-serif text-[21px] font-medium leading-[1.2] text-ink">
                {p.intersection_name}
              </h2>
            </div>

            <button
              onClick={onClose}
              aria-label="Close"
              className="-mr-2 -mt-1 flex h-11 w-11 shrink-0 items-center justify-center text-ink-3 active:bg-paper-edge"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              </svg>
            </button>
          </div>

          {p.is_known_emergent && (
            <p className="mx-5 mt-3 border-l-2 border-risk-1 pl-3 text-[13px] text-ink-2">
              Had a serious crash in 2025.
            </p>
          )}

          <p className="mx-5 mt-3 border-t border-rule pt-3 text-[14px] leading-[1.5] text-ink-2">
            {reason}
          </p>

          <a
            href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lon}`}
            target="_blank"
            rel="noopener noreferrer"
            className="mx-5 mt-3 flex min-h-[44px] items-center justify-between border-t border-rule pt-3 text-[15px] font-medium text-ink active:opacity-70"
          >
            Look at this intersection
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path d="M2 7h10M8 3l4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </a>
        </>
      )}
    </section>
  );
}
