import { useState, useMemo } from "react";
import SearchBox from "./SearchBox";
import AboutModal from "./AboutModal";
import { Footer } from "./PageFrame";
import { useCatch, useComposition } from "./useMeta";
import { sourceLine, sourceOf } from "./lib/signals";
import { patternOf } from "./lib/advice";
import { DEFAULT_THRESHOLD, CANDIDATE_COUNT } from "./constants";

const TIERS = [
  { max: 50, hex: "#7F1D1D", label: "Highest risk" },
  { max: 100, hex: "#C2410C", label: "High risk" },
  { max: 200, hex: "#D97706", label: "Elevated risk" },
  { max: Infinity, hex: "#B8963F", label: "Moderate risk" },
];
const tierFor = (rank) => TIERS.find((t) => rank <= t.max);

/**
 * The front door.
 *
 * One question, one search, one button, one figure, one caveat. The specimen
 * on the right is the only imagery: three real rows from the ranking, each
 * with the crash pattern behind it, because the product is the list.
 *
 * Every number is read from /data/meta.json, so this page cannot claim a
 * figure the export did not produce.
 */
export default function Landing({ intersections, error, onEnter, onNavigate, notice }) {
  const [aboutOpen, setAboutOpen] = useState(false);
  const { caught, total, lift, candidates } = useCatch(DEFAULT_THRESHOLD);
  const { isCombined, known, screen, topN } = useComposition();
  const randomCatch = lift ? Math.max(1, Math.round(caught / lift)) : null;
  const listSize = isCombined && topN ? topN : DEFAULT_THRESHOLD;

  const specimen = useMemo(() => {
    if (!intersections) return null;
    return [...intersections.features]
      .sort((a, b) => a.properties.rank - b.properties.rank)
      .slice(0, 3);
  }, [intersections]);

  return (
    <div className="flex min-h-dvh flex-col bg-paper">
      <header className="border-b border-rule-strong">
        <div className="mx-auto flex max-w-[76rem] items-center justify-between px-5 py-3 md:px-8">
          <a href="/" className="font-serif text-[17px] font-semibold tracking-[-0.01em] text-ink">
            Intersection Risk
            <span className="ml-2 hidden text-[11px] font-normal text-ink-3 sm:inline">San Diego</span>
          </a>
          <button
            onClick={() => setAboutOpen(true)}
            className="border-b border-ink/25 pb-px text-[12px] text-ink-2 hover:border-ink hover:text-ink"
          >
            How this works
          </button>
        </div>
      </header>

      {notice}

      <main className="mx-auto grid w-full max-w-[76rem] flex-1 grid-cols-1 gap-12 px-5 pb-28 pt-12 md:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] md:gap-16 md:px-8 md:pb-16 md:pt-20">
        <section>
          <p className="label mb-4">San Diego, independent research</p>

          <h1 className="font-serif text-[40px] font-medium leading-[1.04] tracking-[-0.025em] text-ink sm:text-[52px] md:text-[60px]">
            Is your intersection
            <br />
            on the list?
          </h1>

          <p className="mt-6 max-w-[42ch] font-serif text-[18px] leading-[1.5] text-ink-2 md:text-[20px]">
            {isCombined ? (
              <>
                The {listSize.toLocaleString()} San Diego intersections most worth a second look:
                where serious crashes have already happened, and where the model expects the
                next ones.
              </>
            ) : (
              <>
                San Diego street corners that have never had a serious crash, ranked by how
                likely they are to have one next.
              </>
            )}
          </p>

          <div className="mt-8 max-w-[34rem]">
            <SearchBox
              large
              intersections={intersections}
              threshold={DEFAULT_THRESHOLD}
              onSelect={(feature) => onEnter(feature)}
            />
            <p className="mt-2 text-[12px] text-ink-3">Try one street name, like El Cajon or Genesee.</p>
          </div>

          <div className="mt-8 flex flex-wrap items-center gap-5">
            <button
              onClick={() => onEnter(null)}
              className="bg-ink px-6 py-3 text-[14px] font-semibold text-paper hover:bg-ink-2"
            >
              See the full map
            </button>
            <button
              onClick={() => setAboutOpen(true)}
              className="border-b border-ink/25 pb-px text-[13px] text-ink-2 hover:border-ink hover:text-ink"
            >
              How this works
            </button>
          </div>

          {/* The one figure the project rests on, then the caveat at the same size. */}
          <div className="mt-12 border-t border-rule pt-8">
            <p className="tnum font-serif text-[56px] font-medium leading-none text-ink">
              {caught}
              <span className="text-ink-3"> of {total}</span>
            </p>
            <p className="mt-3 max-w-[44ch] text-[14px] leading-[1.5] text-ink-2">
              intersections that had a serious crash in 2025 were already on the model&rsquo;s
              list of {DEFAULT_THRESHOLD}.
              {randomCatch != null && (
                <> Picking {DEFAULT_THRESHOLD} corners at random would have caught about {randomCatch}.</>
              )}
            </p>
            <p className="mt-4 text-[13px] text-ink-3">
              <span className="tnum font-medium text-ink-2">
                {(candidates ?? CANDIDATE_COUNT).toLocaleString()}
              </span>{" "}
              intersections ranked, each with no serious crash on record before 2025.
            </p>
          </div>

          <p className="mt-8 max-w-[46ch] font-serif text-[16px] italic leading-[1.55] text-ink-2">
            The list still misses most of them. Use it to decide where to look first, and look
            before you judge any one corner.
          </p>

          {isCombined && (
            <p className="mt-4 max-w-[46ch] text-[13px] leading-[1.55] text-ink-3">
              This list also holds {known.toLocaleString()} intersections that have already had a
              serious crash
              {screen > 0 && <> and {screen.toLocaleString()} on the City&rsquo;s own screening list</>}.
              Those are records rather than predictions, and the map marks them as such.
            </p>
          )}

          {error && (
            <p className="mt-6 bg-paper-sunk px-4 py-3 text-[13px] text-ink-2">
              The ranking did not load: {error}
            </p>
          )}
        </section>

        <aside className="md:pt-16">
          <div className="border border-rule-strong bg-paper">
            <div className="flex items-baseline justify-between border-b border-rule-strong px-5 py-3">
              <p className="label">{isCombined ? "Top of the list" : "Top of the ranking"}</p>
              <p className="tnum text-[11px] text-ink-3">2025 to 2027</p>
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
                const source = sourceOf(p);
                const color = source === "known" ? "#7F1D1D" : tier.hex;
                const line = source === "predicted" ? tier.label : sourceLine(p, false);
                const pattern = patternOf(p);
                return (
                  <li key={p.rank} className="border-b border-rule last:border-b-0">
                    <button
                      onClick={() => onEnter(f)}
                      className="flex w-full items-start gap-4 px-5 py-4 text-left hover:bg-paper-sunk"
                    >
                      <span
                        className="tnum shrink-0 pt-[3px] font-serif text-[22px] font-medium leading-none"
                        style={{ color }}
                      >
                        {p.rank}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[14.5px] font-medium leading-snug text-ink">
                          {p.intersection_name}
                        </span>
                        <span className="mt-1 block text-[11.5px] text-ink-3">
                          <span style={{ color }} className="font-semibold">{line}</span>
                          {pattern && (
                            <>
                              <span className="mx-1.5 text-rule-strong">/</span>
                              {pattern}
                            </>
                          )}
                          <span className="mx-1.5 text-rule-strong">/</span>
                          District {p.council_district}
                          {p.is_known_emergent && (
                            <>
                              <span className="mx-1.5 text-rule-strong">/</span>
                              <span className="text-risk-1">serious crash in 2025</span>
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
              <button
                onClick={() => onEnter(null)}
                className="border-b border-ink/25 text-[12px] text-ink-2 hover:border-ink hover:text-ink"
              >
                See all {listSize.toLocaleString()} on the map
              </button>
            </div>
          </div>

          <p className="mt-4 text-[11px] leading-[1.5] text-ink-3">
            Darker means higher predicted risk. The model learned from crash records for 2016
            through 2024 and has not been retrained since. The 2025 crashes it is scored against
            came later.
          </p>
        </aside>
      </main>

      <Footer onNavigate={onNavigate} />

      {/* On a phone the main button scrolls away; keep one within thumb reach. */}
      <div
        className="fixed inset-x-0 bottom-0 z-30 border-t border-rule-strong bg-paper px-4 pt-3 md:hidden"
        style={{ paddingBottom: "max(12px, env(safe-area-inset-bottom))" }}
      >
        <button
          onClick={() => onEnter(null)}
          className="block w-full bg-ink py-3 text-center text-[15px] font-semibold text-paper"
        >
          See the full map
        </button>
      </div>

      {aboutOpen && <AboutModal onClose={() => setAboutOpen(false)} onNavigate={onNavigate} />}
    </div>
  );
}
