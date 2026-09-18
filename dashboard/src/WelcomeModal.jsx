import { useAdvanced } from "./useAdvanced";
import { useCatch } from "./useMeta";
import { DEFAULT_THRESHOLD } from "./constants";

/**
 * Shown once, on first visit.
 *
 * Composed as the opening of a printed report rather than an onboarding dialog:
 * kicker, headline, standfirst, then three numbered notes. The third note states
 * the limitation up front. A reviewer who discovers that themselves after
 * trusting the headline is a reviewer you have lost, so it is given the same
 * weight as the claim. Its numbers come from meta.json, like everywhere else.
 */
export default function WelcomeModal() {
  const { seenWelcome, dismissWelcome, advanced, toggle } = useAdvanced();
  const { caught, total, lift } = useCatch(DEFAULT_THRESHOLD);
  const liftRounded = lift == null ? null : Math.round(lift);

  if (seenWelcome) return null;

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto bg-ink/30 p-4 backdrop-blur-[2px] sm:p-8"
      role="dialog"
      aria-modal="true"
      aria-labelledby="welcome-title"
      onClick={(e) => e.target === e.currentTarget && dismissWelcome()}
    >
      <article className="my-auto w-full max-w-[36rem] border border-rule-strong bg-paper shadow-paper">
        <div className="border-b border-rule-strong px-8 pb-6 pt-7">
          <p className="label mb-3">San Diego · Independent research</p>

          <h1
            id="welcome-title"
            className="font-serif text-[34px] font-medium leading-[1.08] tracking-[-0.02em] text-ink sm:text-[40px]"
          >
            Where serious crashes are&nbsp;likely to happen next
          </h1>

          <p className="mt-4 max-w-[46ch] font-serif text-[16px] leading-[1.55] text-ink-2">
            A ranking of San Diego street corners that have never had a serious crash —
            ordered by how likely they are to have one.
          </p>
        </div>

        <ol className="px-8 py-6">
          <Note n="01" title="These intersections have no serious-crash history.">
            That is the point. The city reviews corners that already have five or more
            crashes, so a street getting more dangerous stays invisible until someone is
            badly hurt there.
          </Note>

          <Note n="02" title="Darker dots are higher predicted risk.">
            A model trained on crash records through 2024 ranked every intersection in
            the city. Click any dot for its crash history and the reasons behind its
            rank.
          </Note>

          <Note n="03" title="It is right some of the time — not most of the time." last>
            Of the {total} intersections that had a serious crash in 2025, a shortlist of{" "}
            {DEFAULT_THRESHOLD} flagged {caught} in advance
            {liftRounded != null && <> — about {liftRounded} times better than chance</>}, and
            still missing most. Treat it as somewhere to start looking, not a verdict.
          </Note>
        </ol>

        <div className="flex flex-col gap-3 border-t border-rule-strong px-8 py-5 sm:flex-row sm:items-center sm:justify-between">
          <button
            onClick={dismissWelcome}
            className="bg-ink px-6 py-2.5 text-[13px] font-semibold text-paper transition-opacity hover:opacity-85"
          >
            View the map
          </button>

          <button
            onClick={() => {
              if (!advanced) toggle();
              dismissWelcome();
            }}
            className="border-b border-ink/25 pb-px text-left text-[12px] text-ink-3 transition-colors hover:border-ink hover:text-ink sm:text-right"
          >
            I work in traffic safety — use technical terms
          </button>
        </div>
      </article>
    </div>
  );
}

function Note({ n, title, children, last = false }) {
  return (
    <li className={`flex gap-5 ${last ? "" : "mb-5 border-b border-rule pb-5"}`}>
      <span className="tnum mt-[3px] shrink-0 font-mono text-[11px] text-ink-3">{n}</span>
      <div className="min-w-0">
        <h2 className="mb-1 text-[14px] font-semibold leading-snug text-ink">{title}</h2>
        <p className="text-[13.5px] leading-[1.55] text-ink-2">{children}</p>
      </div>
    </li>
  );
}
