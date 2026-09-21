import { useMemo } from "react";
import PageFrame from "./PageFrame";
import { useCatch, useMeta } from "./useMeta";
import { trafficFor } from "./useTraffic";
import { recordFor, controlFor, CONTROL_LABEL } from "./useSiteData";
import { adviceFor, patternOf } from "./lib/advice";
import { crashRate, ratePerMillionEntering, roundVehicles, fmtPerYear } from "./lib/rates";
import { measuresFor, fmtRange, screenGap, CITY_SCREEN } from "./lib/countermeasures";
import { liftSentence } from "./lib/tiers";
import { citation } from "./lib/ask";
import { councilUrl } from "./lib/council";
import { fmtDate } from "./Sidebar";
import { CITY } from "./city";
import { DEFAULT_THRESHOLD, CANDIDATE_COUNT } from "./constants";

const TIERS = [
  { max: 50, hex: "#7F1D1D", label: "Highest risk" },
  { max: 100, hex: "#C2410C", label: "High risk" },
  { max: 200, hex: "#D97706", label: "Elevated risk" },
  { max: Infinity, hex: "#B8963F", label: "Moderate risk" },
];
const tierFor = (rank) => TIERS.find((t) => rank <= t.max);

/**
 * One corner as a page: everything the panel shows, without the map, so it
 * prints as a sheet, embeds in a news story, and reads on a phone from a link.
 */
export default function CornerCard({ rank, intersections, traffic, recent, control, onNavigate }) {
  const meta = useMeta();
  const { candidates } = useCatch(DEFAULT_THRESHOLD);
  const feature = useMemo(
    () => intersections?.features.find((f) => f.properties.rank === Number(rank)) ?? null,
    [intersections, rank]
  );
  const go = (p) => (e) => { e.preventDefault(); onNavigate(p); };

  if (!intersections) {
    return (
      <PageFrame onNavigate={onNavigate}>
        <div className="h-3 w-2/3 animate-pulse bg-paper-edge" />
      </PageFrame>
    );
  }
  if (!feature) {
    return (
      <PageFrame onNavigate={onNavigate}>
        <p className="label mb-4">Not on the list</p>
        <h1 className="font-serif text-[32px] font-medium leading-[1.1] text-ink">There is no corner ranked {rank} in this export.</h1>
        <p className="mt-4 text-[14px]"><a href="/map" onClick={go("/map")} className="border-b border-ink/25 text-ink hover:border-ink">Open the map</a></p>
      </PageFrame>
    );
  }

  const p = feature.properties;
  const tier = tierFor(p.rank);
  const ctrl = controlFor(control, feature);
  const advice = adviceFor(p, { control: ctrl });
  const measures = measuresFor(p, ctrl);
  const rate = crashRate(p.crash_history);
  const t = trafficFor(traffic, feature);
  const police = recordFor(recent, feature);
  const gap = screenGap(p.crash_history);
  const perMev = rate && t?.entering ? ratePerMillionEntering(rate.perYear, t.entering) : null;
  const lift = liftSentence(p.rank, meta);
  const denominator = candidates ?? CANDIDATE_COUNT;
  const since = recent?.source?.since ? fmtDate(recent.source.since).replace(/ \d+,/, "") : "the cutoff";
  const pattern = patternOf(p);

  return (
    <PageFrame onNavigate={onNavigate}>
      <p className="label mb-3">
        {CITY.name}, rank <span className="tnum">{p.rank}</span> of {denominator.toLocaleString()}, {CITY.districts.short} {p.council_district}
      </p>
      <h1 className="font-serif text-[34px] font-medium leading-[1.08] tracking-[-0.02em] text-ink sm:text-[42px]">
        {p.intersection_name}
      </h1>
      <p className="mt-3 text-[13px] text-ink-2">
        <span style={{ color: tier.hex }} className="font-semibold">{tier.label}</span>
        {pattern && <>, {pattern.toLowerCase()}</>}
        {ctrl && <>, {CONTROL_LABEL[ctrl].toLowerCase()}</>}
        {p.near_school && <>, {p.near_school.meters} m from {p.near_school.name}</>}
        {p.is_known_emergent && <>, <span className="text-risk-1">serious crash in 2025</span></>}
      </p>
      {lift && <p className="mt-2 max-w-[60ch] text-[12.5px] leading-[1.5] text-ink-3">{lift}</p>}

      <p className="print-hide mt-5 flex flex-wrap gap-x-5 gap-y-2 text-[13px]">
        <a href={`/map?site=${p.rank}`} onClick={go(`/map?site=${p.rank}`)} className="border-b border-ink/25 text-ink hover:border-ink">Open on the map</a>
        <button onClick={() => window.print()} className="border-b border-ink/25 text-ink hover:border-ink">Print this page</button>
        <a href={councilUrl(p.council_district)} target="_blank" rel="noopener noreferrer" className="border-b border-ink/25 text-ink hover:border-ink">
          District {p.council_district} council office
        </a>
      </p>

      <Section heading="If you use this corner">
        {advice.length ? (
          <ul>
            {advice.map((it) => (
              <li key={it.key} className="border-b border-rule py-3 first:pt-0 last:border-b-0">
                <p className="label">{it.pattern}</p>
                <p className="mt-1.5 text-[14px] leading-[1.5] text-ink">{it.fact}</p>
                {it.driving && <p className="mt-1 text-[14px] leading-[1.5] text-ink-2"><b className="font-semibold text-ink">Driving:</b> {it.driving}</p>}
                {it.walking && <p className="mt-1 text-[14px] leading-[1.5] text-ink-2"><b className="font-semibold text-ink">Walking:</b> {it.walking}</p>}
                {it.cycling && <p className="mt-1 text-[14px] leading-[1.5] text-ink-2"><b className="font-semibold text-ink">On a bike:</b> {it.cycling}</p>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[14px] text-ink-2">Nothing in this corner&rsquo;s top signals names a hazard you can act on; the model listed it for the road it sits on and what is around it.</p>
        )}
      </Section>

      <Section heading="The record">
        <ul className="space-y-2 text-[14px] leading-[1.5] text-ink-2">
          {rate && (
            <li>
              <b className="tnum font-semibold text-ink">{fmtPerYear(rate.perYear)}</b> crashes a year over {rate.years} years, {rate.trend}
              {rate.injuries > 0 && <>; {rate.injuries} of the {rate.total} hurt someone</>}.
            </li>
          )}
          {t ? (
            <li><b className="tnum font-semibold text-ink">{roundVehicles(t.entering).toLocaleString()}</b> vehicles a day{t.complete ? "" : " on the counted street alone"} (City counts).</li>
          ) : (
            <li>No City traffic count at or near this corner.</li>
          )}
          {perMev != null && <li>About <b className="tnum font-semibold text-ink">{perMev < 0.1 ? perMev.toFixed(2) : perMev.toFixed(1)}</b> crashes per million vehicles entering{t && !t.complete ? ", or fewer" : ""}.</li>}
          {recent && (
            <li>
              {police
                ? <>Police have logged <b className="tnum font-semibold text-ink">{police.count}</b> {police.count === 1 ? "crash" : "crashes"} here since {since}, {police.injured + police.killed} people hurt, the latest on {fmtDate(police.last)}.</>
                : <>No police-reported crash logged at this intersection since {since}.</>}{" "}
              <span className="text-ink-3">Reports filed to a block address are not counted.</span>
            </li>
          )}
          {gap && (
            <li>
              {gap.gap === 0
                ? <>In {gap.year} it met the City&rsquo;s review threshold of {CITY_SCREEN} injury crashes in a year.</>
                : <>In {gap.year} it was <b className="tnum font-semibold text-ink">{gap.gap}</b> injury {gap.gap === 1 ? "crash" : "crashes"} short of the {CITY_SCREEN} that trigger the City&rsquo;s own review.</>}
            </li>
          )}
        </ul>
      </Section>

      <Section heading="What fixing it might involve">
        <ul>
          {measures.map((m) => (
            <li key={m.key} className="flex items-baseline justify-between gap-4 border-b border-rule py-2 last:border-b-0 text-[13.5px]">
              <span className="min-w-0">
                <span className="text-ink">{m.name}</span>
                {m.reduction && <span className="block text-[12px] text-ink-3">{m.reduction}</span>}
              </span>
              <span className="tnum shrink-0 text-ink-2">{fmtRange(m.cost, m.per)}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[12px] text-ink-3">Costs are rough; reductions are FHWA&rsquo;s.</p>
      </Section>

      <Section heading="Cite this corner">
        <p className="font-mono text-[12px] leading-[1.6] text-ink-2">
          {citation({ feature, candidates: denominator, url: `${CITY.siteUrl}/corner/${p.rank}` })}
        </p>
      </Section>
    </PageFrame>
  );
}

function Section({ heading, children }) {
  return (
    <section className="mt-9">
      <h2 className="label mb-3">{heading}</h2>
      {children}
    </section>
  );
}
