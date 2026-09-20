import { useRef, useState } from "react";
import { humanizeSignal, inclusionReason, sourceLine, sourceOf } from "./lib/signals";
import { adviceFor } from "./lib/advice";
import { crashRate, fmtPerYear, roundVehicles } from "./lib/rates";
import { trafficFor } from "./useTraffic";
import { recordFor, controlFor } from "./useSiteData";

const TIERS = [
  { max: 50, hex: "#7F1D1D", label: "Highest risk" },
  { max: 100, hex: "#C2410C", label: "High risk" },
  { max: 200, hex: "#D97706", label: "Elevated risk" },
  { max: Infinity, hex: "#B8963F", label: "Moderate risk" },
];
const tierFor = (rank) => TIERS.find((t) => rank <= t.max);

// A finger must travel this far downward before a drag counts as a dismiss, so
// a brush while reading does not close the sheet.
const DISMISS_PX = 64;

function parseProp(v) {
  return typeof v === "string" ? JSON.parse(v) : (v ?? []);
}

/**
 * Phone detail sheet: what it is, how risky, the one thing to do differently,
 * and a way to look at it. Everything else lives on desktop.
 *
 * Under half the viewport so the map stays visible above it. Dismisses on a
 * downward swipe past a threshold or on the close control, so touch users are
 * never gesture-only.
 */
export default function MobileSheet({ feature, onClose, traffic = null, recent = null, control = null }) {
  const [dragY, setDragY] = useState(0);
  const dragging = useRef(false);
  const startY = useRef(0);

  const open = feature !== null;
  const p = feature?.properties ?? {};
  const [lon, lat] = feature?.geometry?.coordinates ?? [0, 0];
  const tier = tierFor(p.rank ?? 1);
  const source = sourceOf(p);
  const isPrediction = source === "predicted";
  const headColor = source === "known" ? "#7F1D1D" : tier.hex;

  const shap = parseProp(p.shap_features);
  const rate = crashRate(parseProp(p.crash_history));
  const t = trafficFor(traffic, feature);
  const police = recordFor(recent, feature);
  const sinceYear = (recent?.source?.since || "").slice(0, 4);
  const [advice] = adviceFor({ shap_features: shap }, { max: 1, control: controlFor(control, feature) });
  const fallback = isPrediction
    ? humanizeSignal(shap?.[0]?.display_label) || "Ranked on its crash rate. Slow down and leave more room than usual."
    : inclusionReason(p, false);

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
      className={`fixed inset-x-0 bottom-0 z-40 max-h-[48dvh] overflow-y-auto border-t border-rule-strong bg-paper shadow-paper ${
        dragging.current ? "" : "transition-transform duration-250 ease-out"
      }`}
      style={{
        transform: open ? `translateY(${dragY}px)` : "translateY(100%)",
        paddingBottom: "max(16px, env(safe-area-inset-bottom))",
      }}
    >
      {open && (
        <>
          <div className="flex justify-center pt-2.5" aria-hidden="true">
            <span className="h-[3px] w-9 bg-rule-strong" />
          </div>

          <div className="flex items-start justify-between gap-3 px-5 pt-2">
            <div className="min-w-0 flex-1">
              <p className="text-[12px] text-ink-2">
                <span className="tnum font-semibold" style={{ color: headColor }}>
                  #{p.rank}
                </span>
                <span className="mx-1.5 text-rule-strong">/</span>
                <span style={{ color: headColor }} className="font-semibold">
                  {isPrediction ? tier.label : sourceLine(p, false)}
                </span>
                <span className="mx-1.5 text-rule-strong">/</span>
                District {p.council_district}
              </p>
              <h2 className="mt-1 font-serif text-[21px] font-medium leading-[1.2] text-ink">
                {p.intersection_name}
              </h2>
              {p.is_known_emergent && (
                <span className="mt-2 inline-block bg-risk-1 px-2 py-[3px] text-[10.5px] font-semibold text-paper">
                  Serious crash in 2025
                </span>
              )}
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

          <div className="mx-5 mt-3 border-t border-rule pt-3">
            {advice ? (
              <>
                <p className="label">{advice.pattern}</p>
                <p className="mt-1 text-[14px] leading-[1.5] text-ink">{advice.fact}</p>
                {(advice.driving ?? advice.walking ?? advice.cycling) && (
                  <p className="mt-1.5 text-[14px] leading-[1.5] text-ink-2">
                    {advice.driving ?? advice.walking ?? advice.cycling}
                  </p>
                )}
              </>
            ) : (
              <p className="text-[14px] leading-[1.5] text-ink-2">{fallback}</p>
            )}
          </div>

          {(t || rate) && (
            <p className="mx-5 mt-3 border-t border-rule pt-3 text-[13px] leading-[1.5] text-ink-3">
              {t && <>About {roundVehicles(t.entering).toLocaleString()} vehicles a day{t.complete ? "" : " on the counted street"}. </>}
              {rate && <>{fmtPerYear(rate.perYear)} crashes a year, {rate.trend}. </>}
              {police && <>Police: {police.count} since {sinceYear}.</>}
            </p>
          )}

          <a
            href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lon}`}
            target="_blank"
            rel="noopener noreferrer"
            className="mx-5 mt-3 block min-h-[44px] border-t border-rule pt-3 text-[15px] font-medium text-ink active:opacity-70"
          >
            <span className="border-b border-ink/30">Look at this intersection in Street View</span>
          </a>
        </>
      )}
    </section>
  );
}
