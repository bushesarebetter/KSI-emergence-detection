import { useAdvanced } from "./useAdvanced";

/**
 * Shown once, on first visit.
 *
 * Without this the dashboard opens on a map of coloured dots with no statement
 * of what the dots mean or why they were chosen. The three points below are the
 * minimum needed to read the map honestly -- including the limitation, which is
 * here rather than buried in the methodology because a reviewer who discovers it
 * themselves after trusting the headline is a reviewer you have lost.
 */
export default function WelcomeModal() {
  const { seenWelcome, dismissWelcome, advanced, toggle } = useAdvanced();

  if (seenWelcome) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="welcome-title"
      onClick={(e) => e.target === e.currentTarget && dismissWelcome()}
    >
      <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl sm:p-7">
        <div className="mb-1 flex items-center gap-2.5">
          <span className="h-2 w-2 rounded-full bg-orange-500 shadow-[0_0_6px_#f97316]" />
          <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
            San Diego
          </span>
        </div>

        <h1 id="welcome-title" className="mb-4 text-lg font-bold leading-snug text-slate-100">
          Where serious crashes are likely to happen next
        </h1>

        <div className="space-y-4 text-sm leading-relaxed text-slate-400">
          <Point n="1" title="These intersections have no serious-crash history.">
            That is the point. San Diego reviews intersections that already have five
            or more crashes — so a street corner trending toward danger stays
            invisible until someone is badly hurt there.
          </Point>

          <Point n="2" title="Red dots are the model's highest-risk sites.">
            A model trained on crash records through 2024 ranked every intersection in
            the city. Tap any dot to see its crash history and why it ranked where it did.
          </Point>

          <Point n="3" title="It is right some of the time, not most of the time.">
            Of the 108 intersections that had a serious crash in 2025, this shortlist of
            500 flagged 24 in advance — about 11 times better than picking at random,
            and far from complete. Treat it as a starting point for review, not a verdict.
          </Point>
        </div>

        <button
          onClick={dismissWelcome}
          className="mt-6 w-full rounded-lg bg-orange-500 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-orange-400"
        >
          Show me the map
        </button>

        <button
          onClick={() => { if (!advanced) toggle(); dismissWelcome(); }}
          className="mt-2 w-full py-1.5 text-xs text-slate-500 transition-colors hover:text-slate-300"
        >
          I work in traffic safety — use technical terms
        </button>
      </div>
    </div>
  );
}

function Point({ n, title, children }) {
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-800 text-[11px] font-bold text-orange-400">
        {n}
      </span>
      <div className="min-w-0">
        <div className="mb-0.5 font-semibold text-slate-200">{title}</div>
        <div className="text-[13px] text-slate-400">{children}</div>
      </div>
    </div>
  );
}
