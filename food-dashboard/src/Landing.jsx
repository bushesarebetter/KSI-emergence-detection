import { useState, useMemo } from "react";
import SearchBox from "./SearchBox";
import AboutModal from "./AboutModal";
import SampleBanner from "./SampleBanner";
import { Footer } from "./PageFrame";
import { useCatch, useSample } from "./useMeta";
import { patternOf } from "./lib/advice";
import { inspectionStats, typeLabel } from "./lib/inspections";
import { fmtMonth } from "./lib/dates";
import { tierFor, GRADE_COLORS } from "./lib/rankTier";
import { DEFAULT_THRESHOLD } from "./constants";
import { SITE } from "./site";

/**
 * The front door. One claim, one search, one button, the arithmetic, and the
 * caveat. The specimen on the right is the only imagery: three rows from the
 * ranking, each with what inspectors found, because the product is the list.
 */
export default function Landing({ facilities, error, onEnter, onNavigate, notice }) {
  const [aboutOpen, setAboutOpen] = useState(false);
  const { caught, total, lift, candidates, scored } = useCatch(DEFAULT_THRESHOLD);
  const sample = useSample();
  const randomCatch = lift ? Math.max(1, Math.round(caught / lift)) : null;
  const go = (p) => (e) => { e.preventDefault(); onNavigate(p); };

  const specimen = useMemo(() => {
    if (!facilities) return null;
    return [...facilities.features].sort((a, b) => a.properties.rank - b.properties.rank).slice(0, 3);
  }, [facilities]);

  return (
    <div className="flex min-h-dvh flex-col bg-paper">
      <header className="border-b border-rule-strong">
        <div className="mx-auto flex max-w-[76rem] items-center justify-between px-5 py-3 md:px-8">
          <a href="/" className="font-serif text-[17px] font-semibold tracking-[-0.01em] text-ink">
            {SITE.shortTitle}
            <span className="ml-2 hidden text-[11px] font-normal text-ink-3 sm:inline">{SITE.name}</span>
          </a>
          <nav className="flex items-center gap-5 text-[12px]">
            <a href={SITE.regulator.resultsUrl} target="_blank" rel="noopener noreferrer" className="hidden border-b border-ink/25 pb-px text-ink-2 hover:border-ink hover:text-ink sm:inline">
              The County&rsquo;s inspection search
            </a>
            <button onClick={() => setAboutOpen(true)} className="border-b border-ink/25 pb-px text-ink-2 hover:border-ink hover:text-ink">
              How this works
            </button>
          </nav>
        </div>
      </header>
      <SampleBanner />

      {notice}

      <main className="mx-auto grid w-full max-w-[76rem] flex-1 grid-cols-1 gap-12 px-5 pb-28 pt-12 md:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] md:gap-16 md:px-8 md:pb-16 md:pt-20">
        <section>
          <p className="label mb-4">{SITE.name}, independent research</p>

          <h1 className="font-serif text-[40px] font-medium leading-[1.04] tracking-[-0.025em] text-ink sm:text-[52px] md:text-[60px]">
            The places most likely
            <br />
            to fail their next inspection.
          </h1>

          <p className="mt-6 max-w-[44ch] font-serif text-[18px] leading-[1.5] text-ink-2 md:text-[20px]">
            {DEFAULT_THRESHOLD} {SITE.name} restaurants, markets and food trucks, ranked by how likely the
            County&rsquo;s next routine inspection is to find a major violation, with what inspectors found
            last time and what to look for yourself.
          </p>

          <div className="mt-8 max-w-[34rem]">
            <SearchBox large facilities={facilities} threshold={DEFAULT_THRESHOLD} onSelect={(f) => onEnter(f)} />
            <p className="mt-2 text-[12px] text-ink-3">{SITE.searchHint}</p>
          </div>

          <div className="mt-8 flex flex-wrap items-center gap-5">
            <button onClick={() => onEnter(null)} className="bg-ink px-6 py-3 text-[14px] font-semibold text-paper hover:bg-ink-2">
              See the full map
            </button>
            <button onClick={() => setAboutOpen(true)} className="border-b border-ink/25 pb-px text-[13px] text-ink-2 hover:border-ink hover:text-ink">
              How this works
            </button>
          </div>

          <div className="mt-12 border-t border-rule pt-8">
            <p className="max-w-[46ch] font-serif text-[20px] leading-[1.4] text-ink md:text-[22px]">
              The County inspects about {SITE.regulator.facilityCount.toLocaleString()} places that sell food,
              one to three times a year. A kitchen that is slipping waits its turn like one that is not.
            </p>
            <p className="mt-2 text-[12px] text-ink-3">
              The grade card in the window says what was found last time. This map is the case for
              looking at some places sooner.
            </p>
          </div>

          <div className="mt-8">
            {scored ? (
              <>
                <p className="tnum font-serif text-[56px] font-medium leading-none text-ink">
                  {caught}
                  <span className="text-ink-3"> of {total}</span>
                </p>
                <p className="mt-3 max-w-[44ch] text-[14px] leading-[1.5] text-ink-2">
                  places that had a major violation at their next inspection were already on this list of{" "}
                  {DEFAULT_THRESHOLD}.
                  {randomCatch != null && <> Picking {DEFAULT_THRESHOLD} at random would have caught about {randomCatch}.</>}
                  {sample && <> Sample numbers.</>}
                </p>
              </>
            ) : (
              <p className="max-w-[44ch] text-[14px] leading-[1.5] text-ink-2">
                Not yet scored. The list is checked against the inspections that follow it; the first
                figure appears once a season of them is in.
              </p>
            )}
            {candidates > 0 && (
              <p className="mt-4 text-[13px] text-ink-3">
                <span className="tnum font-medium text-ink-2">{candidates.toLocaleString()}</span> places ranked.
              </p>
            )}
          </div>

          <p className="mt-8 max-w-[46ch] font-serif text-[16px] italic leading-[1.55] text-ink-2">
            The list will always miss most of them. Use it to decide where to look first, and read
            the grade card before you judge any one kitchen.
          </p>

          {error && <p className="mt-6 bg-paper-sunk px-4 py-3 text-[13px] text-ink-2">The ranking did not load: {error}</p>}
        </section>

        <aside className="md:pt-16">
          <div className="border border-rule-strong bg-paper">
            <div className="flex items-baseline justify-between border-b border-rule-strong px-5 py-3">
              <p className="label">Top of the ranking</p>
              <p className="tnum text-[11px] text-ink-3">next routine inspection</p>
            </div>

            <ol>
              {(specimen ?? [null, null, null]).map((f, i) => {
                if (!f) {
                  return (
                    <li key={i} className="border-b border-rule px-5 py-4 last:border-b-0">
                      <div className="h-3 w-2/3 animate-pulse bg-paper-edge" />
                      <div className="mt-2 h-2.5 w-1/3 animate-pulse bg-paper-edge" />
                    </li>
                  );
                }
                const p = f.properties;
                const tier = tierFor(p.rank);
                const pattern = patternOf(p);
                const s = inspectionStats(p);
                return (
                  <li key={p.rank} className="border-b border-rule last:border-b-0">
                    <button onClick={() => onEnter(f)} className="flex w-full items-start gap-4 px-5 py-4 text-left hover:bg-paper-sunk">
                      <span className="tnum shrink-0 pt-[3px] font-serif text-[22px] font-medium leading-none" style={{ color: tier.hex }}>
                        {p.rank}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[14.5px] font-medium leading-snug text-ink">{p.name}</span>
                        <span className="block text-[11.5px] text-ink-3">{p.address}</span>
                        <span className="mt-1 block text-[11.5px] text-ink-3">
                          <span style={{ color: tier.hex }} className="font-semibold">{tier.label}</span>
                          <span className="mx-1.5 text-rule-strong">/</span>
                          {typeLabel(p.facility_type)}
                          {s?.lastGrade && (
                            <>
                              <span className="mx-1.5 text-rule-strong">/</span>
                              <span style={{ color: GRADE_COLORS[s.lastGrade] }} className="font-semibold">grade {s.lastGrade}</span> {fmtMonth(s.last.date)}
                            </>
                          )}
                          {pattern && (
                            <>
                              <span className="mx-1.5 text-rule-strong">/</span>
                              {pattern.toLowerCase()}
                            </>
                          )}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>

            <div className="border-t border-rule-strong px-5 py-3">
              <button onClick={() => onEnter(null)} className="border-b border-ink/25 text-[12px] text-ink-2 hover:border-ink hover:text-ink">
                See all {DEFAULT_THRESHOLD} on the map
              </button>
            </div>
          </div>

          <p className="mt-4 text-[11px] leading-[1.5] text-ink-3">
            Darker means higher predicted risk. Every fact shown about a place is the County&rsquo;s own
            published inspection record; the rank is a prediction about the next routine inspection,
            not a statement about the food today.
          </p>

          <p className="mt-6 border-t border-rule pt-4 text-[13px] leading-[1.55] text-ink-2">
            Eat somewhere often? Open it, read what inspectors found, and know what to look for the
            next time you are there.{" "}
            <a href="/privacy" onClick={go("/privacy")} className="border-b border-ink/25 text-ink hover:border-ink">Terms</a>.
          </p>
        </aside>
      </main>

      <Footer onNavigate={onNavigate} />

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-rule-strong bg-paper px-4 pt-3 md:hidden" style={{ paddingBottom: "max(12px, env(safe-area-inset-bottom))" }}>
        <button onClick={() => onEnter(null)} className="block w-full bg-ink py-3 text-center text-[15px] font-semibold text-paper">
          See the full map
        </button>
      </div>

      {aboutOpen && <AboutModal onClose={() => setAboutOpen(false)} onNavigate={onNavigate} />}
    </div>
  );
}
