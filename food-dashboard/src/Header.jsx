import { useState } from "react";
import { useAdvanced } from "./useAdvanced";
import SearchBox from "./SearchBox";
import AboutModal from "./AboutModal";
import { SITE } from "./site";

/**
 * Masthead: wordmark in the editorial serif, an edition line stating scope
 * and provenance, the search, the register toggle, and the about button.
 */
export default function Header({ facilities, threshold, onSelect, onHome, onNavigate }) {
  const { advanced, toggle } = useAdvanced();
  const [aboutOpen, setAboutOpen] = useState(false);

  return (
    <>
      <header className="print-hide shrink-0 border-b border-rule-strong bg-paper">
        <div className="flex flex-col gap-3 px-5 py-3 lg:flex-row lg:items-center lg:justify-between lg:gap-8 lg:py-2.5">
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
                className="border-b border-transparent hover:border-ink"
              >
                {advanced ? "Inspection Risk" : SITE.shortTitle}
              </a>
            </h1>
            <span aria-hidden="true" className="hidden h-3 w-px bg-rule-strong sm:block" />
            <p className="hidden text-[11px] leading-none text-ink-3 sm:block">
              {SITE.name}
              <span className="mx-1.5 text-rule-strong">/</span>
              {advanced ? "Forward run, next routine inspection" : "Predicting the next inspection"}
            </p>
          </div>

          <div className="flex items-center gap-3 lg:flex-1 lg:justify-end">
            <div className="min-w-0 flex-1 lg:max-w-[24rem]">
              <SearchBox facilities={facilities} threshold={threshold} onSelect={onSelect} />
            </div>

            <RegisterToggle advanced={advanced} onToggle={toggle} />

            <button
              onClick={() => setAboutOpen(true)}
              className="shrink-0 whitespace-nowrap border-b border-ink/25 pb-px text-[12px] text-ink-2 hover:border-ink hover:text-ink"
            >
              {advanced ? "Methodology" : "How this works"}
            </button>
          </div>
        </div>
      </header>

      {aboutOpen && <AboutModal onClose={() => setAboutOpen(false)} onNavigate={onNavigate} />}
    </>
  );
}

function RegisterToggle({ advanced, onToggle }) {
  return (
    <div role="group" aria-label="Terminology" className="hidden shrink-0 border border-rule-strong sm:flex">
      {[
        { key: false, label: "Plain" },
        { key: true, label: "Technical" },
      ].map(({ key, label }) => (
        <button
          key={label}
          onClick={() => advanced !== key && onToggle()}
          aria-pressed={advanced === key}
          title={key ? "Environmental-health terminology (CalCode items, recall@K)" : "Everyday language"}
          className={`px-2.5 py-1 text-[11px] font-medium ${
            advanced === key ? "bg-ink text-paper" : "bg-transparent text-ink-3 hover:text-ink"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
