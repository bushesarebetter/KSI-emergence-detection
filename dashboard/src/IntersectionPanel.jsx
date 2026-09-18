import CrashHistoryChart from "./CrashHistoryChart";
import ShapChart from "./ShapChart";
import StreetViewPanel from "./StreetViewPanel";
import { useAdvanced } from "./useAdvanced";
import { formatPercentile } from "./lib/format";

import { CANDIDATE_COUNT } from "./constants";

const TIERS = [
  { max: 50, hex: "#7F1D1D", label: "Highest risk" },
  { max: 100, hex: "#C2410C", label: "High risk" },
  { max: 200, hex: "#D97706", label: "Elevated risk" },
  { max: Infinity, hex: "#E8B563", label: "Moderate risk" },
];

const tierFor = (rank) => TIERS.find((t) => rank <= t.max);

function parseProp(v) {
  return typeof v === "string" ? JSON.parse(v) : (v ?? []);
}

export default function IntersectionPanel({ intersection, onClose }) {
  const { advanced, copy } = useAdvanced();
  const visible = intersection !== null;

  const raw = intersection?.properties ?? {};
  // deck.gl hands back the original feature object, so these are normally real
  // arrays already -- the parse is kept so any caller that round-trips a feature
  // through JSON (table click, saved view, deep link) still works.
  const p = {
    ...raw,
    crash_history: parseProp(raw.crash_history),
    shap_features: parseProp(raw.shap_features),
  };
  const [lon, lat] = intersection?.geometry?.coordinates ?? [0, 0];
  const tier = tierFor(p.rank ?? 1);

  return (
    <aside
      aria-hidden={!visible}
      className={`fixed bottom-0 right-0 top-0 z-40 w-full max-w-[24rem] border-l border-rule-strong bg-paper transition-transform duration-300 ease-out ${
        visible ? "translate-x-0 shadow-paper" : "translate-x-full"
      }`}
    >
      {visible && (
        <div className="flex h-full flex-col">
          {/* Masthead of the record */}
          <header className="shrink-0 border-b border-rule-strong px-6 pb-5 pt-5">
            <div className="mb-3 flex items-start justify-between gap-4">
              <div className="flex items-baseline gap-2.5">
                <span
                  className="tnum font-serif text-[38px] font-medium leading-none"
                  style={{ color: tier.hex }}
                >
                  {p.rank}
                </span>
                <span className="text-[11px] text-ink-3">
                  {copy.detailOf(CANDIDATE_COUNT.toLocaleString())}
                </span>
              </div>
              <button
                onClick={onClose}
                aria-label="Close"
                className="-mr-1 text-[22px] leading-none text-ink-3 transition-colors hover:text-ink"
              >
                ×
              </button>
            </div>

            <h2 className="font-serif text-[20px] font-medium leading-[1.2] text-ink">
              {p.intersection_name}
            </h2>

            <p className="mt-2 text-[11.5px] text-ink-2">
              <span style={{ color: tier.hex }} className="font-semibold">
                {tier.label}
              </span>
              <span className="mx-1.5 text-rule-strong">/</span>
              District {p.council_district}
              {advanced && (
                <>
                  <span className="mx-1.5 text-rule-strong">/</span>
                  {formatPercentile(p.percentile)} pct.
                </>
              )}
            </p>

            <div className="mt-3 flex flex-wrap gap-1.5">
              <Tag>{p.is_crash_active ? copy.detailCrashActive : copy.detailCrashSilent}</Tag>
              {p.is_known_emergent && <Tag emphasis>{copy.detailEmergent}</Tag>}
            </div>
          </header>

          <div className="flex-1 overflow-y-auto">
            <Block heading={copy.detailHistory}>
              <CrashHistoryChart crash_history={p.crash_history} />
            </Block>

            <Block heading={copy.detailSignals} note={copy.detailSignalsNote}>
              <ShapChart shap_features={p.shap_features} />
            </Block>

            <Block heading={copy.detailStreetView} last>
              <StreetViewPanel lat={lat} lon={lon} />
              <nav className="mt-3">
                <ExternalLink href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lon}`}>
                  Full-screen Street View
                </ExternalLink>
                <ExternalLink href={`https://www.google.com/maps/search/?api=1&query=${lat},${lon}`}>
                  Open in Google Maps
                </ExternalLink>
                <ExternalLink href={`https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}`}>
                  Directions
                </ExternalLink>
              </nav>

              {advanced && (
                <p className="mt-4 font-mono text-[10.5px] text-ink-3">
                  {lat.toFixed(6)}, {lon.toFixed(6)}
                </p>
              )}
            </Block>
          </div>
        </div>
      )}
    </aside>
  );
}

function Block({ heading, note, children, last = false }) {
  return (
    <section className={`px-6 py-5 ${last ? "" : "border-b border-rule"}`}>
      <h3 className="label">{heading}</h3>
      {note && <p className="mt-1.5 text-[11px] leading-snug text-ink-3">{note}</p>}
      <div className="mt-3.5">{children}</div>
    </section>
  );
}

function Tag({ children, emphasis = false }) {
  return (
    <span
      className={`border px-2 py-[3px] text-[10.5px] font-medium ${
        emphasis
          ? "border-risk-1 bg-risk-1 text-paper"
          : "border-rule-strong bg-paper-sunk text-ink-2"
      }`}
    >
      {children}
    </span>
  );
}

function ExternalLink({ href, children }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex items-center justify-between border-b border-rule py-2.5 text-[13px] text-ink-2 transition-colors last:border-b-0 hover:text-ink"
    >
      {children}
      <span aria-hidden="true" className="text-ink-3 transition-transform group-hover:translate-x-0.5">
        →
      </span>
    </a>
  );
}
