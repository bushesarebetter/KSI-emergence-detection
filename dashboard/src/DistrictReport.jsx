import { useMemo } from "react";
import PageFrame from "./PageFrame";
import { trafficFor } from "./useTraffic";
import { recordFor } from "./useSiteData";
import { patternOf, patternKeys, FILTER_PATTERNS } from "./lib/advice";
import { crashRate, fmtPerYear, roundVehicles } from "./lib/rates";
import { councilUrl } from "./lib/council";
import { fmtDate } from "./Sidebar";
import { DEFAULT_THRESHOLD } from "./constants";

const DISTRICTS = [1, 2, 3, 4, 5, 6, 7, 8, 9];

/**
 * One page per council district, written to be printed and forwarded: how many
 * listed corners the district has, the ten at the top, what kinds of crashes
 * they carry, which are rising, and what the police have logged since the
 * model's cutoff. Every number comes from the same files the map reads.
 */
export default function DistrictReport({ district, intersections, traffic, recent, onNavigate, onOpenMap }) {
  const d = Number(district);
  const go = (p) => (e) => { e.preventDefault(); onNavigate(p); };

  const data = useMemo(() => {
    if (!intersections) return null;
    const mine = intersections.features.filter((f) => f.properties.council_district === d);
    const listed = mine.filter((f) => f.properties.rank <= DEFAULT_THRESHOLD).sort((a, b) => a.properties.rank - b.properties.rank);
    const top100 = listed.filter((f) => f.properties.rank <= 100).length;
    const mix = FILTER_PATTERNS.map(({ key, label }) => ({
      key, label, count: listed.filter((f) => patternKeys(f.properties).has(key)).length,
    }));
    const rising = listed
      .map((f) => ({ f, r: crashRate(f.properties.crash_history) }))
      .filter((x) => x.r?.trend === "rising")
      .sort((a, b) => b.r.recentPerYear - a.r.recentPerYear)
      .slice(0, 5);
    let police = 0, policeCorners = 0, hurt = 0;
    for (const f of listed) {
      const rec = recordFor(recent, f);
      if (rec) { police += rec.count; policeCorners += 1; hurt += rec.injured + rec.killed; }
    }
    const emergent = listed.filter((f) => f.properties.is_known_emergent).length;
    return { listed, top100, mix, rising, police, policeCorners, hurt, emergent };
  }, [intersections, d, recent]);

  return (
    <PageFrame onNavigate={onNavigate}>
      <p className="label mb-4">Council District {d}</p>
      <h1 className="font-serif text-[36px] font-medium leading-[1.08] tracking-[-0.02em] text-ink sm:text-[44px]">
        Corners to look at in District {d}
      </h1>

      {!data ? (
        <div className="mt-8 space-y-3">
          <div className="h-3 w-3/4 animate-pulse bg-paper-edge" />
          <div className="h-3 w-1/2 animate-pulse bg-paper-edge" />
        </div>
      ) : (
        <>
          <p className="mt-5 max-w-[52ch] font-serif text-[17px] leading-[1.55] text-ink-2">
            Of the {DEFAULT_THRESHOLD} San Diego intersections the model ranks most likely to see a
            serious crash next, {data.listed.length} are in District {d}, {data.top100} of them in the
            top 100. {data.emergent > 0 && <>{data.emergent} already had a serious crash in 2025.</>}
          </p>

          <p className="print-hide mt-5 flex flex-wrap gap-x-5 gap-y-2 text-[13px]">
            <button onClick={() => onOpenMap(d)} className="border-b border-ink/25 text-ink hover:border-ink">
              Open the map for District {d}
            </button>
            <button onClick={() => window.print()} className="border-b border-ink/25 text-ink hover:border-ink">
              Print this page
            </button>
            <a href={councilUrl(d)} target="_blank" rel="noopener noreferrer" className="border-b border-ink/25 text-ink hover:border-ink">
              District {d} council office
            </a>
          </p>

          <Section heading="The top ten">
            <ol className="border-t border-rule">
              {data.listed.slice(0, 10).map((f) => {
                const p = f.properties;
                const r = crashRate(p.crash_history);
                const t = trafficFor(traffic, f);
                const pattern = patternOf(p);
                return (
                  <li key={p.rank} className="flex items-baseline gap-4 border-b border-rule py-2.5">
                    <span className="tnum w-10 shrink-0 font-serif text-[18px] font-medium text-ink">{p.rank}</span>
                    <span className="min-w-0 flex-1">
                      <a href={`/map?site=${p.rank}`} onClick={go(`/map?site=${p.rank}`)} className="text-[14px] text-ink hover:underline">
                        {p.intersection_name}
                      </a>
                      <span className="block text-[11.5px] text-ink-3">
                        {pattern ? `${pattern}. ` : ""}
                        {r ? `${fmtPerYear(r.perYear)} crashes a year, ${r.trend}. ` : ""}
                        {t ? `${roundVehicles(t.entering).toLocaleString()}${t.complete ? "" : "+"} vehicles a day.` : ""}
                      </span>
                    </span>
                  </li>
                );
              })}
            </ol>
          </Section>

          <Section heading="What kind of crashes">
            <table className="w-full text-[13px]">
              <tbody>
                {data.mix.map(({ key, label, count }) => (
                  <tr key={key} className="border-b border-rule">
                    <td className="py-2 text-ink">{label}</td>
                    <td className="tnum py-2 text-right text-ink-2">{count} of {data.listed.length} corners</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-[11.5px] text-ink-3">A corner can count under more than one kind.</p>
          </Section>

          <Section heading="Rising">
            {data.rising.length ? (
              <ul className="border-t border-rule">
                {data.rising.map(({ f, r }) => (
                  <li key={f.properties.rank} className="flex items-baseline gap-4 border-b border-rule py-2.5 text-[13px]">
                    <span className="tnum w-10 shrink-0 text-ink-3">#{f.properties.rank}</span>
                    <span className="flex-1 text-ink">{f.properties.intersection_name}</span>
                    <span className="tnum shrink-0 text-ink-2">
                      {fmtPerYear(r.recentPerYear)} a year since 2022, {fmtPerYear(r.earlierPerYear)} before
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[13px] text-ink-2">No listed corner in this district has a rising crash rate.</p>
            )}
          </Section>

          <Section heading="Since the model's cutoff">
            {recent ? (
              <p className="text-[14px] leading-[1.55] text-ink-2">
                Police have logged {data.police} {data.police === 1 ? "crash" : "crashes"} at {data.policeCorners} of these
                corners since {recent.source?.since ? fmtDate(recent.source.since) : "the cutoff"}, {data.hurt}{" "}
                {data.hurt === 1 ? "person" : "people"} hurt, in reports through{" "}
                {recent.source?.through ? fmtDate(recent.source.through) : "the latest file"}. Reports filed to a block address
                rather than an intersection are not counted.
              </p>
            ) : (
              <p className="text-[13px] text-ink-3">Police reports are not loaded.</p>
            )}
          </Section>

          <Section heading="What to do with this">
            <p className="text-[14px] leading-[1.55] text-ink-2">
              Each corner on the map shows its crash record, how busy it is, and what a driver,
              walker or cyclist can do differently there. The district office can ask the City&rsquo;s
              transportation department to look at a corner before it reaches the five-crash
              review. This page is independent student research and not a City assessment.
            </p>
          </Section>

          <p className="print-hide mt-10 flex flex-wrap gap-x-4 gap-y-1 border-t border-rule pt-4 text-[12px] text-ink-3">
            Other districts:
            {DISTRICTS.filter((n) => n !== d).map((n) => (
              <a key={n} href={`/district/${n}`} onClick={go(`/district/${n}`)} className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink">
                {n}
              </a>
            ))}
          </p>
        </>
      )}
    </PageFrame>
  );
}

function Section({ heading, children }) {
  return (
    <section className="mt-10">
      <h2 className="label mb-3">{heading}</h2>
      {children}
    </section>
  );
}
