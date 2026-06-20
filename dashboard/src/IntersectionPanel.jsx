import CrashHistoryChart from "./CrashHistoryChart";
import ShapChart from "./ShapChart";
import { formatPercentile } from "./lib/format";

function riskColor(rank) {
  if (rank <= 50) return "#ef4444";
  if (rank <= 100) return "#f97316";
  if (rank <= 200) return "#fbbf24";
  return "#fde68a";
}

function riskLabel(rank) {
  if (rank <= 50) return "Highest risk";
  if (rank <= 100) return "High risk";
  if (rank <= 200) return "Elevated risk";
  return "Moderate risk";
}

function parseProp(v) {
  return typeof v === "string" ? JSON.parse(v) : (v ?? []);
}

export default function IntersectionPanel({ intersection, onClose }) {
  const visible = intersection !== null;
  const raw = intersection?.properties ?? {};
  // MapLibre serialises array/object properties to JSON strings on click events;
  // parse them back here so all entry paths (map click and table click) are safe.
  const p = {
    ...raw,
    crash_history: parseProp(raw.crash_history),
    shap_features: parseProp(raw.shap_features),
  };
  const coords = intersection?.geometry?.coordinates ?? [0, 0];
  const lon = coords[0];
  const lat = coords[1];
  const color = riskColor(p.rank);

  return (
    <div
      className={`fixed right-0 top-12 bottom-0 w-90 bg-slate-900 border-l border-slate-800 shadow-2xl z-20 transition-transform duration-300 ease-in-out ${
        visible ? "translate-x-0" : "translate-x-full"
      }`}
    >
      {visible && (
        <>
          {/* Sticky header */}
          <div className="sticky top-0 bg-slate-900 border-b border-slate-800 px-4 py-3 flex items-start justify-between z-10">
            <div className="flex flex-col gap-1">
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold tabular-nums" style={{ color }}>
                  #{p.rank}
                </span>
                <span className="text-xs text-slate-600">of 26,045</span>
              </div>
              <div className="text-xs font-medium" style={{ color: color + "bb" }}>
                {riskLabel(p.rank)} · {formatPercentile(p.percentile)} pct.
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-slate-600 hover:text-slate-300 text-xl leading-none ml-4 transition-colors mt-0.5"
              aria-label="Close"
            >
              ×
            </button>
          </div>

          <div className="overflow-y-auto px-4 py-4 space-y-5">
            {/* Intersection name */}
            <div className="text-sm font-semibold text-slate-100 leading-snug">
              {p.intersection_name}
            </div>

            {/* Status badges */}
            <div className="flex flex-wrap gap-1.5">
              <span className="bg-slate-800 text-slate-300 text-xs font-medium px-2.5 py-1 rounded-full border border-slate-700">
                District {p.council_district}
              </span>
              {p.is_crash_active ? (
                <span className="bg-green-950/60 text-green-400 text-xs font-medium px-2.5 py-1 rounded-full border border-green-900/60">
                  Crash active
                </span>
              ) : (
                <span className="bg-slate-800 text-slate-500 text-xs font-medium px-2.5 py-1 rounded-full border border-slate-700">
                  Crash silent
                </span>
              )}
              {p.is_known_emergent && (
                <span className="bg-orange-950/60 text-orange-400 text-xs font-medium px-2.5 py-1 rounded-full border border-orange-900/60">
                  2025 KSI positive
                </span>
              )}
            </div>

            <hr className="border-slate-800" />

            {/* Crash history */}
            <div>
              <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-3">
                Crash History (2016–2025)
              </div>
              <CrashHistoryChart crash_history={p.crash_history} />
            </div>

            <hr className="border-slate-800" />

            {/* SHAP features */}
            <div>
              <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-1">
                Model Signals
              </div>
              <div className="text-[10px] text-slate-600 mb-3">
                All values measured as of Jan 1, 2025 (training cutoff)
              </div>
              <ShapChart shap_features={p.shap_features} />
            </div>

            <hr className="border-slate-800" />

            {/* External link */}
            <a
              href={`https://maps.google.com?q=${lat},${lon}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-orange-400 transition-colors"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                <path
                  d="M6 1C4.07 1 2.5 2.57 2.5 4.5 2.5 7.25 6 11 6 11S9.5 7.25 9.5 4.5C9.5 2.57 7.93 1 6 1zm0 4.75a1.25 1.25 0 110-2.5 1.25 1.25 0 010 2.5z"
                  fill="currentColor"
                />
              </svg>
              View in Google Maps
            </a>
          </div>
        </>
      )}
    </div>
  );
}
