import { useState } from "react";
import { useAdvanced } from "./useAdvanced";
import SearchBox from "./SearchBox";
import AboutModal from "./AboutModal";

/**
 * Masthead.
 *
 * Structured like the top of a broadsheet: wordmark in the editorial serif, a
 * thin edition line under it stating scope and provenance, then a rule. The
 * edition line is doing real work — it tells a first-time visitor what period
 * this covers and that it is independent research, which is the context that
 * makes everything below legible.
 */
export default function Header({ intersections, threshold, onSelectIntersection, onHome }) {
  const { advanced, toggle } = useAdvanced();
  const [aboutOpen, setAboutOpen] = useState(false);

  return (
    <>
      <header className="shrink-0 border-b border-rule-strong bg-paper">
        <div className="flex flex-col gap-3 px-5 py-3 lg:flex-row lg:items-center lg:justify-between lg:gap-8 lg:py-2.5">
          {/* Wordmark + edition line. The wordmark is a real link to the home
              page -- so open-in-new-tab and screen readers behave -- with the
              click intercepted for in-app navigation when a handler is given. */}
          <div className="flex items-baseline gap-3">
            <h1 className="font-serif text-[19px] font-semibold leading-none tracking-[-0.01em] text-ink">
              <a
                href="/"
                title="Home"
                onClick={(e) => {
                  if (!onHome) return;
                  e.preventDefault();
                  onHome();
                }}
                className="border-b border-transparent transition-colors hover:border-ink"
              >
                {advanced ? "KSI Emergence" : "Intersection Risk"}
              </a>
            </h1>
            <span aria-hidden="true" className="hidden h-3 w-px bg-rule-strong sm:block" />
            <p className="hidden text-[11px] leading-none text-ink-3 sm:block">
              San&nbsp;Diego
              <span className="mx-1.5 text-rule-strong">/</span>
              {advanced ? "Forward run 2025–2027" : "Predicting 2025–2027"}
            </p>
          </div>

          <div className="flex items-center gap-3 lg:flex-1 lg:justify-end">
            <div className="min-w-0 flex-1 lg:max-w-[22rem]">
              <SearchBox
                intersections={intersections}
                threshold={threshold}
                onSelect={onSelectIntersection}
              />
            </div>

            <RegisterToggle advanced={advanced} onToggle={toggle} />

            <button
              onClick={() => setAboutOpen(true)}
              className="shrink-0 whitespace-nowrap border-b border-ink/25 pb-px text-[12px] text-ink-2 transition-colors hover:border-ink hover:text-ink"
            >
              {advanced ? "Methodology" : "How this works"}
            </button>
          </div>
        </div>
      </header>

      {aboutOpen && <AboutModal onClose={() => setAboutOpen(false)} />}
    </>
  );
}

/**
 * Segmented control rather than a single button, because a lone button labelled
 * with its current state ("Plain language") reads ambiguously — people cannot
 * tell whether it describes the mode they are in or the one they will get.
 */
function RegisterToggle({ advanced, onToggle }) {
  return (
    <div
      role="group"
      aria-label="Terminology"
      className="hidden shrink-0 border border-rule-strong sm:flex"
    >
      {[
        { key: false, label: "Plain" },
        { key: true, label: "Technical" },
      ].map(({ key, label }) => (
        <button
          key={label}
          onClick={() => advanced !== key && onToggle()}
          aria-pressed={advanced === key}
          title={
            key
              ? "Traffic-safety terminology (KSI, recall@K)"
              : "Everyday language"
          }
          className={`px-2.5 py-1 text-[11px] font-medium transition-colors ${
            advanced === key
              ? "bg-ink text-paper"
              : "bg-transparent text-ink-3 hover:text-ink"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
