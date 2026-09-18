import { useState } from "react";
import { useAdvanced } from "./useAdvanced";
import SearchBox from "./SearchBox";

const RUN_CHIPS = [
  { label: "Train", value: "2016–2024" },
  { label: "Predict", value: "2025–2027" },
  { label: "Mode", value: "Forward run" },
];

export default function Header({ intersections, threshold, onSelectIntersection }) {
  const { advanced, toggle, copy } = useAdvanced();
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      <header className="flex h-auto shrink-0 flex-col gap-2 border-b border-slate-800 bg-slate-950 px-4 py-2.5 md:h-12 md:flex-row md:items-center md:justify-between md:gap-4 md:py-0">
        <div className="flex items-center justify-between gap-3 md:justify-start">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="h-2 w-2 shrink-0 rounded-full bg-orange-500 shadow-[0_0_6px_#f97316]" />
            <span className="truncate text-sm font-semibold tracking-tight text-slate-100">
              {copy.appName}
            </span>
            <span className="hidden select-none text-slate-700 sm:inline">·</span>
            <span className="hidden truncate text-xs text-slate-500 sm:block">
              {advanced ? "San Diego" : copy.tagline}
            </span>
          </div>

          {/* Advanced toggle stays reachable on mobile, where the chips are hidden. */}
          <button
            onClick={toggle}
            aria-pressed={advanced}
            title={
              advanced
                ? "Switch to plain language"
                : "Switch to traffic-safety terminology (KSI, recall@K)"
            }
            className={`shrink-0 rounded-md border px-2.5 py-1 text-[11px] font-medium transition-colors md:hidden ${
              advanced
                ? "border-orange-500/40 bg-orange-500/10 text-orange-400"
                : "border-slate-700 bg-slate-800 text-slate-400"
            }`}
          >
            {advanced ? "Technical" : "Plain"}
          </button>
        </div>

        {/* Search: the first thing most people want, so it gets prime position. */}
        <div className="w-full md:max-w-xs md:flex-1">
          <SearchBox
            intersections={intersections}
            threshold={threshold}
            onSelect={onSelectIntersection}
          />
        </div>

        <div className="flex items-center gap-2">
          {advanced &&
            RUN_CHIPS.map(({ label, value }) => (
              <span
                key={label}
                className="hidden items-center gap-1.5 rounded-md border border-slate-700/60 bg-slate-800 px-2.5 py-1 text-xs lg:flex"
              >
                <span className="font-medium text-slate-500">{label}</span>
                <span className="text-slate-300">{value}</span>
              </span>
            ))}

          <button
            onClick={toggle}
            aria-pressed={advanced}
            title={
              advanced
                ? "Switch to plain language"
                : "Switch to traffic-safety terminology (KSI, recall@K)"
            }
            className={`hidden rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors md:block ${
              advanced
                ? "border-orange-500/40 bg-orange-500/10 text-orange-400"
                : "border-slate-700 bg-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            {advanced ? "Technical terms" : "Plain language"}
          </button>

          <button
            onClick={() => setModalOpen(true)}
            className="flex shrink-0 items-center gap-1.5 rounded-md border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs text-slate-400 transition-colors hover:border-orange-500/50 hover:text-orange-400"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="shrink-0">
              <circle cx="6" cy="6" r="5.5" stroke="currentColor" />
              <path d="M6 5.5v3M6 3.5h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <span className="whitespace-nowrap">{copy.aboutButton}</span>
          </button>
        </div>
      </header>

      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          onClick={(e) => e.target === e.currentTarget && setModalOpen(false)}
        >
          <div className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-2xl">
            <div className="mb-4 flex items-start justify-between">
              <h2 className="text-sm font-semibold text-slate-100">{copy.aboutTitle}</h2>
              <button
                onClick={() => setModalOpen(false)}
                aria-label="Close"
                className="ml-4 text-xl leading-none text-slate-500 transition-colors hover:text-slate-300"
              >
                ×
              </button>
            </div>

            {advanced ? <TechnicalBody /> : <PlainBody />}
          </div>
        </div>
      )}
    </>
  );
}

function PlainBody() {
  return (
    <div className="space-y-3.5 text-sm leading-relaxed text-slate-400">
      <p>
        <strong className="text-slate-200">The problem.</strong> Traffic safety money
        mostly follows crashes that already happened. San Diego reviews intersections
        with five or more prior crashes — about 14 locations a year. An intersection
        getting more dangerous but without that history yet is invisible to it.
      </p>
      <p>
        <strong className="text-slate-200">What this does.</strong> It ranks every
        intersection in the city that has <em>no</em> serious-crash history, by how
        likely it is to produce one. The ranking comes from a model trained on San
        Diego crash records from 2016 to 2024 — nothing but crash data the city
        already collects.
      </p>
      <p>
        <strong className="text-slate-200">How well it works.</strong> Of the 108
        intersections that had a serious crash in 2025, a shortlist of 500 flagged 24
        in advance. That is roughly 11 times better than choosing at random, and it
        still misses most of them. A shortlist is a place to start looking, not a
        prediction about any single corner.
      </p>
      <p>
        <strong className="text-slate-200">What it is not.</strong> This is
        independent student research, not an official City of San Diego hazard
        assessment. A dot here does not mean an intersection is unsafe today, and the
        absence of one does not mean it is safe.
      </p>
      <p className="text-xs italic text-slate-600">Publication forthcoming.</p>
    </div>
  );
}

function TechnicalBody() {
  return (
    <div className="space-y-3 text-sm leading-relaxed text-slate-400">
      <p>
        Predictions from an XGBoost Tweedie model trained on San Diego crash records
        2016–2024. The label window is 2025–2027; 2025 outcomes are complete and
        validate the model. 2026–2027 outcomes land by 2029.
      </p>
      <p>
        Primary signals are crash-timing features: recency of last crash, and whether
        crash frequency structurally accelerated from a previously stable baseline
        (changepoint detection). Cumulative crash volume outweighs short-term recency.
        Built-environment features show a small consistent positive signal on the
        verified run, but it did not replicate on the 2025 forward run, so the deployed
        model stays crash-history only.
      </p>
      <p>
        <strong className="text-slate-300">Reported honestly:</strong> at the ≥2-KSI
        threshold a persistence baseline (rank by recent crash count and trend) ties
        the tuned model exactly — 10/21 both, random split. The model's validated edge
        is at the broader ≥1-KSI threshold. With 21 positives, bootstrap CIs on
        recall@500 span [28.6%, 71.4%].
      </p>
      <p>
        Forward run recall@500 (≥1 KSI, 108 positives): 24/108 = 22.2%, 11.6× random.
        Predict-only scoring; the model never fit on any 2025 outcome.
      </p>
      <p>
        San Diego's annual review flags intersections with ≥5 prior crashes. By
        construction none of the 108 confirmed 2025 emergent sites would appear on it.
      </p>
      <p className="text-xs italic text-slate-600">Publication forthcoming.</p>
    </div>
  );
}
