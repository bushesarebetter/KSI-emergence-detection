import { useMemo, useState } from "react";
import CrashHistoryChart from "./CrashHistoryChart";
import ShapChart from "./ShapChart";
import StreetViewPanel from "./StreetViewPanel";
import { useAdvanced } from "./useAdvanced";
import { useComposition, useCatch } from "./useMeta";
import { trafficFor } from "./useTraffic";
import { recordFor, controlFor, CONTROL_LABEL } from "./useSiteData";
import { councilUrl } from "./lib/council";
import { measuresFor, fmtRange, screenGap, CITY_SCREEN } from "./lib/countermeasures";
import { CRASH_COST, CRASH_COST_SOURCE } from "./lib/crashcost";
import { councilMessage, citation } from "./lib/ask";
import { track } from "./lib/track";
import { fmtDate } from "./Sidebar";
import { formatPercentile } from "./lib/format";
import { inclusionReason, sourceLine, sourceOf } from "./lib/signals";
import { adviceFor, patternOf } from "./lib/advice";
import { crashRate, ratePerMillionEntering, roundVehicles, fmtPerYear } from "./lib/rates";
import { nearbySites } from "./lib/geo";
import { CANDIDATE_COUNT, DEFAULT_THRESHOLD } from "./constants";

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

/**
 * The record for one intersection, read top to bottom: what happened here, how
 * busy it is and how often crashes happen, what to do about it, why the model
 * ranked it, other flagged corners nearby, and a look at the corner.
 */
export default function IntersectionPanel({
  intersection,
  onClose,
  traffic = null,
  recent = null,
  control = null,
  intersections = null,
  onSelectIntersection = () => {},
}) {
  const { advanced, copy } = useAdvanced();
  const { isCombined, topN } = useComposition();
  const { candidates } = useCatch(DEFAULT_THRESHOLD);
  const [copied, setCopied] = useState(false);
  const [messageCopied, setMessageCopied] = useState(false);
  const [citeCopied, setCiteCopied] = useState(false);
  const visible = intersection !== null;

  const raw = intersection?.properties ?? {};
  // deck.gl hands back the original feature object, so these are normally
  // arrays already. The parse is kept so a caller that round-trips a feature
  // through JSON (table click, saved view, deep link) still works.
  const p = {
    ...raw,
    crash_history: parseProp(raw.crash_history),
    shap_features: parseProp(raw.shap_features),
  };
  const [lon, lat] = intersection?.geometry?.coordinates ?? [0, 0];
  const tier = tierFor(p.rank ?? 1);
  const source = sourceOf(p);
  const isPrediction = source === "predicted";
  const line = sourceLine(p, advanced);
  const reason = inclusionReason(p, advanced);
  const ctrl = controlFor(control, intersection);
  const advice = adviceFor(p, { control: ctrl });
  const measures = visible ? measuresFor(p, ctrl) : [];
  const gap = screenGap(p.crash_history);
  const nearby = useMemo(() => nearbySites(intersection, intersections), [intersection, intersections]);

  const headColor = source === "known" ? "#7F1D1D" : tier.hex;
  const denominator = isCombined && topN ? topN : (candidates ?? CANDIDATE_COUNT);

  async function copyMessage() {
    try {
      const text = councilMessage({
        feature: intersection,
        traffic: trafficFor(traffic, intersection),
        police: recordFor(recent, intersection),
        control: ctrl,
        candidates: denominator,
        url: window.location.href,
      });
      await navigator.clipboard.writeText(text);
      track("copy-message");
      setMessageCopied(true);
      setTimeout(() => setMessageCopied(false), 2000);
    } catch {
      /* clipboard blocked */
    }
  }

  async function copyCitation() {
    try {
      await navigator.clipboard.writeText(citation({ feature: intersection, candidates: denominator, url: window.location.href }));
      track("copy-citation");
      setCiteCopied(true);
      setTimeout(() => setCiteCopied(false), 1500);
    } catch {
      /* clipboard blocked */
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      track("copy-link");
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked: the address bar still holds the link */
    }
  }

  return (
    <aside
      aria-hidden={!visible}
      className={`fixed bottom-0 right-0 top-0 z-40 w-full max-w-[24rem] border-l border-rule-strong bg-paper transition-transform duration-300 ease-out ${
        visible ? "translate-x-0 shadow-paper print-sheet" : "translate-x-full"
      }`}
    >
      {visible && (
        <div className="flex h-full flex-col">
          <header className="shrink-0 border-b border-rule-strong px-6 pb-5 pt-5">
            <div className="mb-3 flex items-start justify-between gap-4">
              <div className="flex items-baseline gap-2.5">
                <span
                  className="tnum font-serif text-[38px] font-medium leading-none"
                  style={{ color: headColor }}
                >
                  {p.rank}
                </span>
                <span className="text-[11px] text-ink-3">
                  {isCombined
                    ? advanced
                      ? `of ${denominator.toLocaleString()} on the combined list`
                      : `of ${denominator.toLocaleString()} on the list`
                    : copy.detailOf(denominator.toLocaleString())}
                </span>
              </div>
              <div className="print-hide flex items-center gap-4">
                <button
                  onClick={() => { track("print-corner"); window.print(); }}
                  className="border-b border-ink/25 text-[11px] text-ink-3 hover:border-ink hover:text-ink"
                >
                  Print
                </button>
                <button
                  onClick={copyLink}
                  className="border-b border-ink/25 text-[11px] text-ink-3 hover:border-ink hover:text-ink"
                >
                  {copied ? "Copied" : "Copy link"}
                </button>
                <button
                  onClick={onClose}
                  aria-label="Close"
                  className="-mr-1 text-[22px] leading-none text-ink-3 hover:text-ink"
                >
                  ×
                </button>
              </div>
            </div>

            <h2 className="font-serif text-[20px] font-medium leading-[1.2] text-ink">
              {p.intersection_name}
            </h2>

            <p className="mt-2 text-[11.5px] text-ink-2">
              {isPrediction ? (
                <span style={{ color: tier.hex }} className="font-semibold">{tier.label}</span>
              ) : (
                <span style={{ color: headColor }} className="font-semibold">{line}</span>
              )}
              <span className="mx-1.5 text-rule-strong">/</span>
              District {p.council_district}
              {advanced && isPrediction && p.percentile != null && (
                <>
                  <span className="mx-1.5 text-rule-strong">/</span>
                  {formatPercentile(p.percentile)} pct.
                </>
              )}
              {advanced && !isPrediction && p.model_rank != null && (
                <>
                  <span className="mx-1.5 text-rule-strong">/</span>
                  model rank #{p.model_rank}
                </>
              )}
            </p>

            <div className="mt-3 flex flex-wrap gap-1.5">
              <Tag>{p.is_crash_active ? copy.detailCrashActive : copy.detailCrashSilent}</Tag>
              {p.is_known_emergent && <Tag emphasis>{copy.detailEmergent}</Tag>}
              {p.city_screen && source !== "screen" && (
                <Tag>{advanced ? "Also on City screen" : "Also on the City's list"}</Tag>
              )}
              {ctrl && <Tag>{CONTROL_LABEL[ctrl]}</Tag>}
              {p.near_school && <Tag>{p.near_school.meters} m from {p.near_school.name}</Tag>}
            </div>
          </header>

          <div className="print-scroll flex-1 overflow-y-auto">
            <Block heading={copy.detailHistory}>
              <CrashHistoryChart crash_history={p.crash_history} />
            </Block>

            <Block heading={copy.detailExposure} note={copy.detailExposureNote}>
              <Exposure p={p} feature={intersection} traffic={traffic} recent={recent} advanced={advanced} />
            </Block>

            <Block heading={copy.detailAdvice} note={copy.detailAdviceNote}>
              {advice.length > 0 ? (
                <ul>
                  {advice.map((it) => (
                    <li key={it.key} className="border-b border-rule py-3 first:pt-0 last:border-b-0">
                      <p className="label">{it.pattern}</p>
                      <p className="mt-1.5 text-[13px] leading-[1.5] text-ink">{it.fact}</p>
                      {it.driving && <Action who="Driving">{it.driving}</Action>}
                      {it.walking && <Action who="Walking">{it.walking}</Action>}
                      {it.cycling && <Action who="On a bike">{it.cycling}</Action>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[13px] leading-[1.55] text-ink-2">
                  {isPrediction ? copy.detailNoAdvice : reason}
                </p>
              )}
            </Block>

            <Block heading={copy.detailCase} note={copy.detailCaseNote}>
              {gap && (
                <p className="text-[13px] leading-[1.5] text-ink-2">
                  {gap.gap === 0 ? (
                    <>In {gap.year} this corner met the City&rsquo;s own review threshold of {CITY_SCREEN} injury crashes in a year.</>
                  ) : (
                    <>
                      In {gap.year} it was{" "}
                      <span className="tnum font-medium text-ink">{gap.gap}</span> injury{" "}
                      {gap.gap === 1 ? "crash" : "crashes"} short of the {CITY_SCREEN} that trigger the City&rsquo;s own review.
                    </>
                  )}
                </p>
              )}
              <ul className="mt-3">
                {measures.map((m) => (
                  <li key={m.key} className="border-b border-rule py-2.5 last:border-b-0">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="text-[13px] font-medium text-ink">{m.name}</span>
                      <span className="tnum shrink-0 text-[11.5px] text-ink-2">{fmtRange(m.cost, m.per)}</span>
                    </div>
                    <p className="mt-0.5 text-[12px] leading-[1.45] text-ink-3">{m.what}{m.reduction ? ` ${m.reduction}.` : ""}</p>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-[12px] leading-[1.5] text-ink-3">
                One prevented serious-injury crash is worth about {Math.round(CRASH_COST.serious / 1e5) / 10} million
                dollars to society ({CRASH_COST_SOURCE.short}). Costs are rough; reductions are FHWA&rsquo;s.
              </p>
              <div className="print-hide mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-[13px]">
                <button
                  onClick={copyMessage}
                  className="bg-ink px-4 py-2 text-[13px] font-semibold text-paper hover:bg-ink-2"
                >
                  {messageCopied ? "Message copied" : "Copy a message to the council office"}
                </button>
                <ExternalLink href={councilUrl(p.council_district)}>District {p.council_district} contact page</ExternalLink>
                <button onClick={copyCitation} className="border-b border-ink/25 text-[12px] text-ink-3 hover:border-ink hover:text-ink">
                  {citeCopied ? "Citation copied" : "Copy a citation"}
                </button>
              </div>
            </Block>

            <Block
              heading={isPrediction ? copy.detailSignals : advanced ? "Why it is on the list" : "Why it's on the list"}
              note={isPrediction ? copy.detailSignalsNote : null}
            >
              {isPrediction || p.shap_features.length > 0 ? (
                <ShapChart shap_features={p.shap_features} />
              ) : (
                <p className="text-[13px] leading-[1.55] text-ink-2">{reason}</p>
              )}
            </Block>

            {nearby.length > 0 && (
              <Block heading={copy.detailNearby}>
                <ul>
                  {nearby.map(({ feature, meters }) => {
                    const q = feature.properties;
                    const pattern = patternOf(q);
                    return (
                      <li key={q.rank} className="border-b border-rule last:border-b-0">
                        <button
                          onClick={() => onSelectIntersection(feature)}
                          className="flex w-full items-baseline gap-3 py-2.5 text-left hover:bg-paper-sunk"
                        >
                          <span className="tnum shrink-0 font-semibold" style={{ color: tierFor(q.rank).hex }}>
                            #{q.rank}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block text-[13px] leading-snug text-ink">{q.intersection_name}</span>
                            <span className="block text-[11px] text-ink-3">
                              {Math.round(meters / 10) * 10} m away{pattern ? `, ${pattern.toLowerCase()}` : ""}
                            </span>
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </Block>
            )}

            <Block heading={copy.detailStreetView} last>
              <div className="print-hide">
                <StreetViewPanel lat={lat} lon={lon} />
              </div>
              <nav className="print-hide mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-[13px]">
                <ExternalLink href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lon}`}>
                  Street View, full screen
                </ExternalLink>
                <ExternalLink href={`https://www.google.com/maps/search/?api=1&query=${lat},${lon}`}>
                  Google Maps
                </ExternalLink>
                <ExternalLink href={`https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}`}>
                  Directions
                </ExternalLink>
                <ExternalLink href={councilUrl(p.council_district)}>
                  Tell the District {p.council_district} council office
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

/**
 * Vehicles a day from the City's counts, crashes a year from the record, and
 * the two combined into a rate per million entering vehicles, which is how a
 * busy arterial and a quiet street can be compared at all.
 */
function Exposure({ p, feature, traffic, recent, advanced }) {
  const rate = crashRate(p.crash_history);
  const t = trafficFor(traffic, feature);
  const police = recordFor(recent, feature);
  const since = recent?.source?.since ? fmtDate(recent.source.since).replace(/ \d+,/, "") : "the cutoff";
  const entering = t?.entering ?? null;
  const perMev = rate && entering ? ratePerMillionEntering(rate.perYear, entering) : null;

  return (
    <div className="space-y-3 text-[13px] leading-[1.5] text-ink-2">
      {t ? (
        <p>
          <Big>{roundVehicles(entering).toLocaleString()}</Big> vehicles a day{" "}
          {t.complete
            ? "enter this corner"
            : "on the one street the City has counted here, so the true total is higher"}
          :{" "}
          {t.legs.map((l, i) => (
            <span key={l.street}>
              {i > 0 && ", "}
              {roundVehicles(l.adt).toLocaleString()} on {l.street}
              {l.year ? ` (${l.method === "nearby" ? "counted a block away, " : ""}${l.year})` : ""}
            </span>
          ))}
          .
        </p>
      ) : (
        <p>The City has no traffic count at or near this corner.</p>
      )}

      {rate && (
        <p>
          <Big>{fmtPerYear(rate.perYear)}</Big> crashes a year over {rate.years} years, {rate.trend}
          {rate.trend !== "steady" && (
            <>
              : {fmtPerYear(rate.recentPerYear)} a year since 2022 against {fmtPerYear(rate.earlierPerYear)} before
            </>
          )}
          .{rate.injuries > 0 && <> {rate.injuries} of the {rate.total} crashes hurt someone.</>}
        </p>
      )}

      {recent && (
        <p className="border-t border-rule pt-3">
          {police ? (
            <>
              Police have logged{" "}
              <span className="tnum font-medium text-ink">{police.count}</span>{" "}
              {police.count === 1 ? "crash" : "crashes"} here since {since}
              {police.injured + police.killed > 0 && (
                <>, {police.injured + police.killed} {police.injured + police.killed === 1 ? "person" : "people"} hurt</>
              )}
              , the latest on {fmtDate(police.last)}.
            </>
          ) : (
            <>No police-reported crash logged at this intersection since {since}.</>
          )}{" "}
          <span className="text-ink-3">Reports filed to a block address are not counted.</span>
        </p>
      )}

      {perMev != null && (
        <p className="border-t border-rule pt-3">
          {advanced ? (
            <>
              <span className="tnum font-medium text-ink">{perMev.toFixed(2)}</span> crashes per million
              entering vehicles{!t.complete && " (one-leg denominator: a ceiling)"}.
            </>
          ) : (
            <>
              About <span className="tnum font-medium text-ink">{perMev < 0.1 ? perMev.toFixed(2) : perMev.toFixed(1)}</span>{" "}
              crashes for every million vehicles that pass through
              {!t.complete && ", or fewer, since only one street is counted"}.
            </>
          )}
        </p>
      )}
    </div>
  );
}

function Big({ children }) {
  return <span className="tnum font-serif text-[26px] font-medium leading-none text-ink">{children}</span>;
}

function Action({ who, children }) {
  return (
    <p className="mt-1.5 text-[13px] leading-[1.5] text-ink-2">
      <span className="font-semibold text-ink">{who}:</span> {children}
    </p>
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
        emphasis ? "border-risk-1 bg-risk-1 text-paper" : "border-rule-strong bg-paper-sunk text-ink-2"
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
      className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink"
    >
      {children}
    </a>
  );
}
