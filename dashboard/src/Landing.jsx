import { useState, useMemo } from "react";
import SearchBox from "./SearchBox";
import AboutModal from "./AboutModal";
import { CATCH_STATS } from "./CatchFigure";
import { DEFAULT_THRESHOLD, CANDIDATE_COUNT, REPO_URL } from "./constants";

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
 * Built from three references and one anti-reference. gov.uk: state the purpose
 * in the hero, address the reader as "you", one primary call to action, no
 * hyperbole. Walk Score: the type-an-address-get-an-answer pattern -- but its
 * hero ("Live Where You Love") says nothing, so ours is a plain question. NYC's
 * Vision Zero View: twenty filters on the first screen is the thing to avoid.
 *
 * So: one question, one search, one button, three numbers, one honest caveat.
 * The specimen on the right is the only "imagery" -- three real rows from the
 * ranking, because showing the actual product beats any illustration.
 */
export default function Landing({ intersections, error, onEnter }) {
  const [aboutOpen, setAboutOpen] = useState(false);
  const { caught, total } = CATCH_STATS[DEFAULT_THRESHOLD];

  const specimen = useMemo(() => {
    if (!intersections) return null;
    return [...intersections.features]
      .sort((a, b) => a.properties.rank - b.properties.rank)
      .slice(0, 3);
  }, [intersections]);

  return (
    <div className="flex min-h-dvh flex-col bg-paper">
      {/* Masthead: thinner than the app's -- the search lives in the hero. */}
      <header className="border-b border-rule-strong">
        <div className="mx-auto flex max-w-[76rem] items-center justify-between px-5 py-3 md:px-8">
          <a
            href="/"
            title="Home"
            className="font-serif text-[17px] font-semibold tracking-[-0.01em] text-ink"
          >
            Intersection Risk
            <span className="ml-2 hidden text-[11px] font-normal text-ink-3 sm:inline">San&nbsp;Diego</span>
          </a>
          <button
            onClick={() => setAboutOpen(true)}
            className="border-b border-ink/25 pb-px text-[12px] text-ink-2 transition-colors hover:border-ink hover:text-ink"
          >
            How this works
          </button>
        </div>
      </header>

      <main className="mx-auto grid w-full max-w-[76rem] flex-1 grid-cols-1 gap-12 px-5 pb-16 pt-12 md:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] md:gap-16 md:px-8 md:pt-20">
        {/* ── Hero ─────────────────────────────────────────────────────────── */}
        <section>
          <p className="label mb-4">San Diego · Independent research</p>

          <h1 className="font-serif text-[40px] font-medium leading-[1.04] tracking-[-0.025em] text-ink sm:text-[52px] md:text-[60px]">
            Is your intersection
            <br />
            on the list?
          </h1>

          <p className="mt-6 max-w-[42ch] font-serif text-[18px] leading-[1.5] text-ink-2 md:text-[20px]">
            A ranking of San Diego street corners that have never had a serious crash —
            ordered by how likely they are to have one.
          </p>

          <div className="mt-8 max-w-[34rem]">
            <SearchBox
              large
              intersections={intersections}
              threshold={DEFAULT_THRESHOLD}
              onSelect={(feature) => onEnter(feature)}
            />
            <p className="mt-2 text-[12px] text-ink-3">
              Try a street name — “El Cajon”, “Genesee”, “Balboa”.
            </p>
          </div>

          <div className="mt-8 flex flex-wrap items-center gap-4">
            <button
              onClick={() => onEnter(null)}
              className="group inline-flex items-center gap-2.5 bg-ink px-6 py-3 text-[14px] font-semibold text-paper transition-opacity hover:opacity-85"
            >
              See the full map
              <span aria-hidden="true" className="transition-transform group-hover:translate-x-0.5">→</span>
            </button>
            <button
              onClick={() => setAboutOpen(true)}
              className="border-b border-ink/25 pb-px text-[13px] text-ink-2 transition-colors hover:border-ink hover:text-ink"
            >
              How this works
            </button>
          </div>

          {/* ── Three numbers ──────────────────────────────────────────────── */}
          <dl className="mt-12 grid grid-cols-1 gap-6 border-y border-rule py-6 sm:grid-cols-3 sm:gap-8">
            <Figure value={CANDIDATE_COUNT.toLocaleString()} label="intersections ranked, all with no serious-crash history" />
            <Figure
              value={<><span>{caught}</span><span className="text-ink-3"> of {total}</span></>}
              label="that had a serious crash in 2025 were flagged in advance"
            />
            <Figure
              value="Open"
              label={
                <>
                  source, MIT licensed.{" "}
                  <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink">
                    Read the code
                  </a>
                </>
              }
            />
          </dl>

          {/* ── The caveat, given the same weight as the claim ─────────────── */}
          <p className="mt-8 max-w-[46ch] font-serif text-[16px] italic leading-[1.55] text-ink-2">
            It is right some of the time, not most of the time — about eleven times better
            than picking at random, and still missing most. Treat it as a place to start
            looking, not a verdict on any single corner.
          </p>

          {error && (
            <p className="mt-6 border-l-2 border-risk-1 pl-4 text-[13px] text-ink-2">
              Couldn’t load the ranking right now: {error}
            </p>
          )}
        </section>

        {/* ── Specimen: the top of the actual list ───────────────────────── */}
        <aside className="md:pt-16">
          <div className="border border-rule-strong bg-paper shadow-paper">
            <div className="flex items-baseline justify-between border-b border-rule-strong px-5 py-3">
              <p className="label">Top of the ranking</p>
              <p className="tnum text-[11px] text-ink-3">2025–2027</p>
            </div>

            <ol>
              {(specimen ?? [null, null, null]).map((f, i) => {
                if (!f) {
                  return (
                    <li key={i} className="border-b border-rule px-5 py-4 last:border-b-0">
                      <div className="h-3 w-2/3 animate-pulse bg-paper-edge" />
                    </li>
                  );
                }
                const p = f.properties;
                const tier = tierFor(p.rank);
                return (
                  <li key={p.rank} className="border-b border-rule last:border-b-0">
                    <button
                      onClick={() => onEnter(f)}
                      className="group flex w-full items-start gap-4 px-5 py-4 text-left transition-colors hover:bg-paper-sunk"
                    >
                      <span
                        className="tnum shrink-0 pt-[3px] font-serif text-[22px] font-medium leading-none"
                        style={{ color: tier.hex }}
                      >
                        {p.rank}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[14.5px] font-medium leading-snug text-ink group-hover:underline">
                          {p.intersection_name}
                        </span>
                        <span className="mt-1 block text-[11.5px] text-ink-3">
                          <span style={{ color: tier.hex }} className="font-semibold">{tier.label}</span>
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
                      <span aria-hidden="true" className="pt-1 text-ink-3 transition-transform group-hover:translate-x-0.5">→</span>
                    </button>
                  </li>
                );
              })}
            </ol>

            <div className="border-t border-rule-strong px-5 py-3">
              <button
                onClick={() => onEnter(null)}
                className="text-[12px] text-ink-2 transition-colors hover:text-ink"
              >
                See all {DEFAULT_THRESHOLD} on the map →
              </button>
            </div>
          </div>

          <p className="mt-4 text-[11px] leading-[1.5] text-ink-3">
            Darker means higher predicted risk. Ranked by a model trained on crash records
            2016–2024; it was never retrained, and is being scored against 2025 outcomes it
            has not seen.
          </p>
        </aside>
      </main>

      <footer className="border-t border-rule">
        <div className="mx-auto flex max-w-[76rem] flex-col gap-1 px-5 py-4 text-[11px] text-ink-3 sm:flex-row sm:items-center sm:justify-between md:px-8">
          <p>Crash data: SWITRS via TIMS, UC Berkeley SafeTREC · Road network: OpenStreetMap</p>
          <p>Independent student research. Not an official City of San Diego assessment.</p>
        </div>
      </footer>

      {aboutOpen && <AboutModal onClose={() => setAboutOpen(false)} />}
    </div>
  );
}

function Figure({ value, label }) {
  return (
    <div>
      <dt className="tnum font-serif text-[34px] font-medium leading-none text-ink">{value}</dt>
      <dd className="mt-2 max-w-[22ch] text-[12.5px] leading-[1.45] text-ink-2">{label}</dd>
    </div>
  );
}
