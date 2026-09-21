import { useEffect, useMemo, useRef, useState } from "react";
import MessageBox from "./MessageBox";
import InspectionChart from "./InspectionChart";
import SignalList from "./SignalList";
import StreetViewPanel from "./StreetViewPanel";
import { useAdvanced } from "./useAdvanced";
import { useCatch, useMeta } from "./useMeta";
import { inspectionStats, themeCounts, typeLabel } from "./lib/inspections";
import { adviceFor, patternOf } from "./lib/advice";
import { liftSentence } from "./lib/tiers";
import { citation, recordText } from "./lib/ask";
import { nearbySites } from "./lib/geo";
import { fmtDate, fmtMonth } from "./lib/dates";
import { tierFor, GRADE_COLORS } from "./lib/rankTier";
import { track } from "./lib/track";
import { DEFAULT_THRESHOLD, CANDIDATE_COUNT } from "./constants";
import { SITE } from "./site";

/**
 * The detail panel: the record, what inspectors found, what to look for,
 * why the model ranked it here, what else is nearby, and a way to look at
 * it. Prints as a one-page sheet.
 */
export default function PlacePanel({ feature, onClose, facilities = null, onSelect = () => {}, onNavigate = null }) {
  const { advanced, copy } = useAdvanced();
  const { candidates } = useCatch(DEFAULT_THRESHOLD);
  const meta = useMeta();
  const [copied, setCopied] = useState(false);
  const [message, setMessage] = useState(null);
  const [status, setStatus] = useState("");
  const headingRef = useRef(null);

  const p = feature?.properties;
  const stats = useMemo(() => (p ? inspectionStats(p) : null), [p]);
  const themes = useMemo(() => (p ? themeCounts(p.violations) : []), [p]);
  const advice = useMemo(() => (p ? adviceFor(p) : []), [p]);
  const nearby = useMemo(() => (feature && facilities ? nearbySites(feature, facilities, 600, 3) : []), [feature, facilities]);

  useEffect(() => {
    setCopied(false);
    setStatus("");
    headingRef.current?.focus({ preventScroll: true });
  }, [feature]);

  useEffect(() => {
    if (!feature) return undefined;
    const onKey = (e) => e.key === "Escape" && !message && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [feature, onClose, message]);

  if (!feature) return null;

  const [lon, lat] = feature.geometry.coordinates;
  const tier = tierFor(p.rank);
  const denominator = candidates || CANDIDATE_COUNT || meta?.candidates || 0;
  const lift = liftSentence(p.rank, meta, { advanced });
  const pageUrl = `${window.location.origin}/place/${p.rank}`;

  async function copyLink() {
    const url = `${window.location.origin}/map?place=${p.rank}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setStatus("Link copied.");
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setMessage({ title: "Link to this place", text: url, copied: false });
    }
  }

  function showText(title, text) {
    track(title === "Citation" ? "copy-citation" : "copy-record");
    navigator.clipboard?.writeText(text).then(
      () => setMessage({ title, text, copied: true }),
      () => setMessage({ title, text, copied: false })
    );
  }

  return (
    <aside
      aria-label="Place detail"
      className="print-sheet absolute inset-y-0 right-0 z-30 flex w-full max-w-[26rem] flex-col border-l border-rule-strong bg-paper shadow-paper"
    >
      {message && <MessageBox title={message.title} text={message.text} copied={message.copied} onClose={() => setMessage(null)} />}

      <header className="shrink-0 border-b border-rule-strong px-6 pb-4 pt-5">
        <div className="flex items-start justify-between gap-3">
          <p className="text-[12px] text-ink-2">
            <span className="tnum font-serif text-[22px] font-medium leading-none" style={{ color: tier.hex }}>{p.rank}</span>
            <span className="ml-1.5">{copy.detailOf(denominator.toLocaleString())}</span>
          </p>
          <div className="print-hide flex items-center gap-3 text-[11.5px]">
            <button onClick={() => window.print()} className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink">Print</button>
            <button onClick={copyLink} className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink">{copied ? "Copied" : "Copy link"}</button>
            <button onClick={onClose} aria-label="Close" className="-mr-1 text-[20px] leading-none text-ink-3 hover:text-ink">×</button>
          </div>
        </div>
        <h2 ref={headingRef} tabIndex={-1} className="mt-2 font-serif text-[22px] font-medium leading-[1.2] text-ink focus:outline-none">
          {p.name}
        </h2>
        <p className="mt-1 text-[12.5px] text-ink-2">{p.address}</p>
        <span className="sr-only" aria-live="polite">{status}</span>
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Tag color={tier.hex}>{tier.label}</Tag>
          <Tag>{typeLabel(p.facility_type)}</Tag>
          {p.council_district && <Tag>{SITE.districts.short} {p.council_district}</Tag>}
          {p.risk_category && <Tag>Risk category {p.risk_category}</Tag>}
          {stats?.lastGrade && (
            <Tag color={GRADE_COLORS[stats.lastGrade]}>Grade {stats.lastGrade}, {fmtMonth(stats.last.date)}</Tag>
          )}
          {p.is_known_positive && <Tag color="#7F1D1D">Major violation at the next inspection</Tag>}
        </div>
        {lift && <p className="mt-3 text-[11.5px] leading-[1.5] text-ink-3">{lift}</p>}
      </header>

      <div className="print-scroll flex-1 overflow-y-auto">
        <Block heading={copy.detailHistory} note={copy.detailHistoryNote}>
          {stats ? (
            <>
              <InspectionChart inspections={p.inspections} />
              <p className="mt-3 text-[13px] leading-[1.55] text-ink-2">
                <span className="tnum font-medium text-ink">{stats.count}</span> visits on record, the last on{" "}
                {fmtDate(stats.last.date)}
                {stats.lastScore != null && <> with a score of <span className="tnum font-medium text-ink">{stats.lastScore}</span></>}.
                {" "}
                <span className="tnum font-medium text-ink">{stats.majors36}</span> major and{" "}
                <span className="tnum font-medium text-ink">{stats.minors36}</span> minor violations in the last three years
                {stats.closures > 0 && <>; closed <span className="tnum font-medium text-ink">{stats.closures}</span> {stats.closures === 1 ? "time" : "times"}</>}.
                {stats.trend !== "steady" && <> Scores are <span className={stats.trend === "worsening" ? "font-medium text-risk-1" : "font-medium text-ink"}>{stats.trend}</span>.</>}
              </p>
            </>
          ) : (
            <p className="text-[13px] text-ink-3">No inspections in the export for this place.</p>
          )}
        </Block>

        <Block heading={copy.detailFindings} note={copy.detailFindingsNote}>
          {themes.length ? (
            <ul>
              {themes.map((t) => (
                <li key={t.theme} className="flex items-baseline justify-between gap-3 border-b border-rule py-2 last:border-b-0 text-[13px]">
                  <span className="text-ink">{t.label}</span>
                  <span className="tnum shrink-0 text-ink-3">
                    {t.count} {t.count === 1 ? "finding" : "findings"}{t.major > 0 && <>, <span className="font-medium text-risk-1">{t.major} major</span></>}
                    <span className="ml-2 text-[11px]">{fmtMonth(t.last)}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] text-ink-3">No violations recorded in the last three years.</p>
          )}
        </Block>

        <Block heading={copy.detailAdvice} note={copy.detailAdviceNote}>
          {advice.length ? (
            <ul>
              {advice.map((it) => (
                <li key={it.key} className="border-b border-rule py-3 first:pt-0 last:border-b-0">
                  <p className="label">{it.pattern}</p>
                  <p className="mt-1.5 text-[13px] leading-[1.5] text-ink">{it.fact}</p>
                  {it.look && <Action who="Look for">{it.look}</Action>}
                  {it.act && <Action who="Then">{it.act}</Action>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] leading-[1.55] text-ink-2">{copy.detailNoAdvice}</p>
          )}
          <p className="mt-3 text-[11.5px] leading-[1.5] text-ink-3">
            General practice for the kind of finding recorded, not a verdict on any visit. The grade
            card in the window is the County&rsquo;s official statement.
          </p>
        </Block>

        <Block heading={copy.detailSignals} note={copy.detailSignalsNote}>
          <SignalList shap_features={p.shap_features} />
        </Block>

        {nearby.length > 0 && (
          <Block heading={copy.detailNearby}>
            <ul>
              {nearby.map(({ feature: f, meters }) => {
                const q = f.properties;
                const pattern = patternOf(q);
                return (
                  <li key={q.rank} className="border-b border-rule last:border-b-0">
                    <button onClick={() => onSelect(f)} className="flex w-full items-baseline gap-3 py-2.5 text-left hover:bg-paper-sunk">
                      <span className="tnum shrink-0 font-semibold" style={{ color: tierFor(q.rank).hex }}>#{q.rank}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[13px] leading-snug text-ink">{q.name}</span>
                        <span className="block text-[11px] text-ink-3">{Math.round(meters / 10) * 10} m away{pattern ? `, ${pattern.toLowerCase()}` : ""}</span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </Block>
        )}

        <Block heading={copy.detailStreetView} last>
          <div className="print-hide"><StreetViewPanel lat={lat} lon={lon} /></div>
          <nav className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-[12px]">
            <ExternalLink href={SITE.regulator.resultsUrl}>{copy.detailRecord}</ExternalLink>
            <ExternalLink href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${p.name} ${p.address}`)}`}>Google Maps</ExternalLink>
            <ExternalLink href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lon}`}>Street View, full screen</ExternalLink>
            {onNavigate && (
              <a href={`/place/${p.rank}`} onClick={(e) => { e.preventDefault(); onNavigate(`/place/${p.rank}`); }} className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink">
                This place as a page
              </a>
            )}
          </nav>
          <div className="print-hide mt-4 flex flex-wrap gap-x-4 gap-y-2 text-[12px]">
            <button onClick={() => showText("The record", recordText({ feature, candidates: denominator, url: pageUrl }))} className="bg-ink px-3.5 py-2 text-[12.5px] font-semibold text-paper hover:bg-ink-2">
              Copy the record
            </button>
            <button onClick={() => showText("Citation", citation({ feature, candidates: denominator, url: pageUrl }))} className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink">
              Copy a citation
            </button>
          </div>
          <p className="mt-3 font-mono text-[10.5px] text-ink-3">{lat.toFixed(6)}, {lon.toFixed(6)}</p>
        </Block>
      </div>
    </aside>
  );
}

function Tag({ children, color }) {
  return (
    <span className="border border-rule-strong px-2 py-[3px] text-[10.5px] font-semibold" style={color ? { color, borderColor: color } : undefined}>
      {children}
    </span>
  );
}

function Action({ who, children }) {
  return (
    <p className="mt-1 text-[13px] leading-[1.5] text-ink-2">
      <b className="font-semibold text-ink">{who}:</b> {children}
    </p>
  );
}

function Block({ heading, note, children, last = false }) {
  return (
    <section className={`px-6 py-5 ${last ? "" : "border-b border-rule"}`}>
      <h3 className="label">{heading}</h3>
      {note && <p className="mb-3 mt-1 text-[11.5px] text-ink-3">{note}</p>}
      {!note && <div className="mb-3" />}
      {children}
    </section>
  );
}

function ExternalLink({ href, children }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink">
      {children}
    </a>
  );
}
