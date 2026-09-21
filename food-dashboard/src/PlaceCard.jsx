import { useMemo } from "react";
import PageFrame from "./PageFrame";
import InspectionChart from "./InspectionChart";
import SignalList from "./SignalList";
import { useCatch, useMeta } from "./useMeta";
import { inspectionStats, themeCounts, typeLabel } from "./lib/inspections";
import { adviceFor, patternOf } from "./lib/advice";
import { liftSentence } from "./lib/tiers";
import { citation } from "./lib/ask";
import { fmtDate, fmtMonth } from "./lib/dates";
import { tierFor, GRADE_COLORS } from "./lib/rankTier";
import { DEFAULT_THRESHOLD, CANDIDATE_COUNT } from "./constants";
import { SITE } from "./site";

/**
 * One place as a page: everything the panel shows, without the map, so it
 * prints, embeds in a story, and reads on a phone from a link.
 */
export default function PlaceCard({ rank, facilities, onNavigate }) {
  const meta = useMeta();
  const { candidates } = useCatch(DEFAULT_THRESHOLD);
  const feature = useMemo(() => facilities?.features.find((f) => f.properties.rank === Number(rank)) ?? null, [facilities, rank]);
  const go = (p) => (e) => { e.preventDefault(); onNavigate(p); };

  if (!facilities) {
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
        <h1 className="font-serif text-[32px] font-medium leading-[1.1] text-ink">There is no place ranked {rank} in this export.</h1>
        <p className="mt-4 text-[14px]"><a href="/map" onClick={go("/map")} className="border-b border-ink/25 text-ink hover:border-ink">Open the map</a></p>
      </PageFrame>
    );
  }

  const p = feature.properties;
  const tier = tierFor(p.rank);
  const stats = inspectionStats(p);
  const themes = themeCounts(p.violations);
  const advice = adviceFor(p);
  const lift = liftSentence(p.rank, meta);
  const denominator = candidates || CANDIDATE_COUNT || meta?.candidates || 0;
  const pattern = patternOf(p);

  return (
    <PageFrame onNavigate={onNavigate}>
      <p className="label mb-3">
        {SITE.name}, rank <span className="tnum">{p.rank}</span> of {denominator.toLocaleString()}, {typeLabel(p.facility_type)}
        {p.council_district && <>, {SITE.districts.short} {p.council_district}</>}
      </p>
      <h1 className="font-serif text-[34px] font-medium leading-[1.08] tracking-[-0.02em] text-ink sm:text-[42px]">{p.name}</h1>
      <p className="mt-2 text-[14px] text-ink-2">{p.address}</p>
      <p className="mt-3 text-[13px] text-ink-2">
        <span style={{ color: tier.hex }} className="font-semibold">{tier.label}</span>
        {stats?.lastGrade && <>, <span style={{ color: GRADE_COLORS[stats.lastGrade] }} className="font-semibold">grade {stats.lastGrade}</span> in {fmtMonth(stats.last.date)}</>}
        {pattern && <>, {pattern.toLowerCase()}</>}
        {p.is_known_positive && <>, <span className="text-risk-1">major violation at the next inspection</span></>}
      </p>
      {lift && <p className="mt-2 max-w-[60ch] text-[12.5px] leading-[1.5] text-ink-3">{lift}</p>}

      <p className="print-hide mt-5 flex flex-wrap gap-x-5 gap-y-2 text-[13px]">
        <a href={`/map?place=${p.rank}`} onClick={go(`/map?place=${p.rank}`)} className="border-b border-ink/25 text-ink hover:border-ink">Open on the map</a>
        <button onClick={() => window.print()} className="border-b border-ink/25 text-ink hover:border-ink">Print this page</button>
        <a href={SITE.regulator.resultsUrl} target="_blank" rel="noopener noreferrer" className="border-b border-ink/25 text-ink hover:border-ink">The County&rsquo;s record</a>
      </p>

      <Section heading="If you eat here">
        {advice.length ? (
          <ul>
            {advice.map((it) => (
              <li key={it.key} className="border-b border-rule py-3 first:pt-0 last:border-b-0">
                <p className="label">{it.pattern}</p>
                <p className="mt-1.5 text-[14px] leading-[1.5] text-ink">{it.fact}</p>
                {it.look && <p className="mt-1 text-[14px] leading-[1.5] text-ink-2"><b className="font-semibold text-ink">Look for:</b> {it.look}</p>}
                {it.act && <p className="mt-1 text-[14px] leading-[1.5] text-ink-2"><b className="font-semibold text-ink">Then:</b> {it.act}</p>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[14px] text-ink-2">Nothing in this place&rsquo;s record names a finding you can check for at the table. Look for the posted grade card.</p>
        )}
        <p className="mt-3 text-[12px] text-ink-3">General practice for the kind of finding recorded, not a verdict on any visit.</p>
      </Section>

      <Section heading="The record">
        {stats ? (
          <>
            <InspectionChart inspections={p.inspections} />
            <p className="mt-3 text-[14px] leading-[1.55] text-ink-2">
              <b className="tnum font-semibold text-ink">{stats.count}</b> visits on record, the last on {fmtDate(stats.last.date)}
              {stats.lastScore != null && <> with a score of <b className="tnum font-semibold text-ink">{stats.lastScore}</b></>}.{" "}
              <b className="tnum font-semibold text-ink">{stats.majors36}</b> major and <b className="tnum font-semibold text-ink">{stats.minors36}</b> minor
              violations in the last three years{stats.closures > 0 && <>; closed {stats.closures} {stats.closures === 1 ? "time" : "times"}</>}.
              {stats.trend !== "steady" && <> Scores are {stats.trend}.</>}
            </p>
          </>
        ) : (
          <p className="text-[14px] text-ink-3">No inspections in the export for this place.</p>
        )}
        {themes.length > 0 && (
          <ul className="mt-4">
            {themes.map((t) => (
              <li key={t.theme} className="flex items-baseline justify-between gap-4 border-b border-rule py-2 last:border-b-0 text-[13.5px]">
                <span className="text-ink">{t.label}</span>
                <span className="tnum shrink-0 text-ink-2">{t.count} {t.count === 1 ? "finding" : "findings"}{t.major > 0 && <>, <span className="text-risk-1">{t.major} major</span></>}, latest {fmtMonth(t.last)}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section heading="Why the model ranked it here">
        <SignalList shap_features={p.shap_features} />
      </Section>

      <Section heading="Cite this place">
        <p className="font-mono text-[12px] leading-[1.6] text-ink-2">{citation({ feature, candidates: denominator, url: `${SITE.siteUrl}/place/${p.rank}` })}</p>
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
