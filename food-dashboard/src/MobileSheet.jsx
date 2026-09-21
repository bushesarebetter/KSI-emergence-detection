import { useRef, useState } from "react";
import { adviceFor } from "./lib/advice";
import { humanizeSignal } from "./lib/signals";
import { inspectionStats, typeLabel } from "./lib/inspections";
import { fmtMonth } from "./lib/dates";
import { tierFor, GRADE_COLORS } from "./lib/rankTier";
import { SITE } from "./site";

// A finger must travel this far downward before a drag counts as a dismiss.
const DISMISS_PX = 64;

/**
 * Phone detail sheet: what it is, how risky, what inspectors found, the one
 * thing to look for, and a way to see more. Under half the viewport so the
 * map stays visible above it.
 */
export default function MobileSheet({ feature, onClose, onNavigate }) {
  const [dragY, setDragY] = useState(0);
  const dragging = useRef(false);
  const startY = useRef(0);

  const open = feature !== null;
  const p = feature?.properties ?? {};
  const [lon, lat] = feature?.geometry?.coordinates ?? [0, 0];
  const tier = tierFor(p.rank ?? 1);
  const stats = feature ? inspectionStats(p) : null;
  const [advice] = feature ? adviceFor(p, { max: 1 }) : [];
  const fallback = humanizeSignal(p.shap_features?.[0]?.display_label) || "Ranked on the pattern of its scores. Look for the posted grade card.";

  const onTouchStart = (e) => { startY.current = e.touches[0].clientY; dragging.current = true; };
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
      aria-label="Place detail"
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
      className={`fixed inset-x-0 bottom-0 z-40 max-h-[48dvh] overflow-y-auto border-t border-rule-strong bg-paper shadow-paper ${dragging.current ? "" : "transition-transform duration-250 ease-out"}`}
      style={{ transform: open ? `translateY(${dragY}px)` : "translateY(100%)", paddingBottom: "max(16px, env(safe-area-inset-bottom))" }}
    >
      {open && (
        <>
          <div className="flex justify-center pt-2.5" aria-hidden="true">
            <span className="h-[3px] w-9 bg-rule-strong" />
          </div>

          <div className="flex items-start justify-between gap-3 px-5 pt-2">
            <div className="min-w-0 flex-1">
              <p className="text-[12px] text-ink-2">
                <span className="tnum font-semibold" style={{ color: tier.hex }}>#{p.rank}</span>
                <span className="mx-1.5 text-rule-strong">/</span>
                <span style={{ color: tier.hex }} className="font-semibold">{tier.label}</span>
                <span className="mx-1.5 text-rule-strong">/</span>
                {typeLabel(p.facility_type)}
              </p>
              <h2 className="mt-1 font-serif text-[21px] font-medium leading-[1.2] text-ink">{p.name}</h2>
              <p className="mt-0.5 text-[12px] text-ink-3">{p.address}</p>
              {stats?.lastGrade && (
                <span className="mt-2 inline-block border px-2 py-[3px] text-[10.5px] font-semibold" style={{ color: GRADE_COLORS[stats.lastGrade], borderColor: GRADE_COLORS[stats.lastGrade] }}>
                  Grade {stats.lastGrade}, {fmtMonth(stats.last.date)}
                </span>
              )}
            </div>
            <button onClick={onClose} aria-label="Close" className="-mr-2 -mt-1 flex h-11 w-11 shrink-0 items-center justify-center text-ink-3 active:bg-paper-edge">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              </svg>
            </button>
          </div>

          <div className="mx-5 mt-3 border-t border-rule pt-3">
            {advice ? (
              <>
                <p className="label">{advice.pattern}</p>
                <p className="mt-1 text-[14px] leading-[1.5] text-ink">{advice.fact}</p>
                {advice.look && <p className="mt-1.5 text-[14px] leading-[1.5] text-ink-2">Look for: {advice.look}</p>}
              </>
            ) : (
              <p className="text-[14px] leading-[1.5] text-ink-2">{fallback}</p>
            )}
          </div>

          {stats && (
            <p className="mx-5 mt-3 border-t border-rule pt-3 text-[13px] leading-[1.5] text-ink-3">
              {stats.majors36} major and {stats.minors36} minor violations in the last three years across {stats.count} visits
              {stats.closures > 0 && <>; closed {stats.closures} {stats.closures === 1 ? "time" : "times"}</>}.
              {stats.trend !== "steady" && <> Scores {stats.trend}.</>}
            </p>
          )}

          <div className="mx-5 mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-rule pt-3 text-[14px]">
            <a href={`/place/${p.rank}`} onClick={(e) => { e.preventDefault(); onNavigate(`/place/${p.rank}`); }} className="min-h-[44px] bg-ink px-4 py-3 font-semibold text-paper active:opacity-80">
              The full record
            </a>
            <a href={SITE.regulator.resultsUrl} target="_blank" rel="noopener noreferrer" className="border-b border-ink/30 text-[13px] text-ink-2">
              The County&rsquo;s record
            </a>
          </div>

          <a
            href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lon}`}
            target="_blank"
            rel="noopener noreferrer"
            className="mx-5 mt-3 block min-h-[44px] border-t border-rule pt-3 text-[15px] font-medium text-ink active:opacity-70"
          >
            <span className="border-b border-ink/30">Look at this place in Street View</span>
          </a>
        </>
      )}
    </section>
  );
}
