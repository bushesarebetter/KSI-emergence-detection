import { useAdvanced } from "./useAdvanced";
import { useCatch, useSample } from "./useMeta";
import { DEFAULT_THRESHOLD } from "./constants";
import { SITE } from "./site";

/**
 * Shown once, on first visit to the map: kicker, headline, two short
 * paragraphs and the caveat, which carries the same weight as the claim.
 */
export default function WelcomeModal() {
  const { seenWelcome, dismissWelcome, advanced, toggle } = useAdvanced();
  const { caught, total, scored } = useCatch(DEFAULT_THRESHOLD);
  const sample = useSample();

  if (seenWelcome) return null;

  return (
    <div
      className="print-hide fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto bg-ink/40 p-4 sm:p-8"
      role="dialog"
      aria-modal="true"
      aria-labelledby="welcome-title"
      onClick={(e) => e.target === e.currentTarget && dismissWelcome()}
    >
      <article className="my-auto w-full max-w-[34rem] border border-rule-strong bg-paper">
        <div className="border-b border-rule-strong px-8 pb-6 pt-7">
          <p className="label mb-3">{SITE.name}, independent research</p>
          <h1 id="welcome-title" className="font-serif text-[32px] font-medium leading-[1.08] tracking-[-0.02em] text-ink sm:text-[38px]">
            The places most likely to fail their next&nbsp;inspection
          </h1>
        </div>

        <div className="space-y-4 px-8 py-6 font-serif text-[16px] leading-[1.55] text-ink-2">
          <p>
            Every dot is a {SITE.name} restaurant, market or food truck. Darker means the model
            expects the County&rsquo;s next routine inspection to find a major violation.
          </p>
          <p>
            Tap a dot. You will see its scores visit by visit, what inspectors found, and what
            to look for yourself the next time you are there.
          </p>
          <p className="border-t border-rule pt-4 text-[15px] text-ink-3">
            {sample ? (
              <>Every place shown is invented: this is the site before its model. Nothing here is a real business.</>
            ) : scored ? (
              <>
                Of the {total} places that had a major violation at their next inspection, this list of{" "}
                {DEFAULT_THRESHOLD} had flagged {caught}. It misses most of them. Use it to decide where
                to look, and read the grade card before you judge.
              </>
            ) : (
              <>
                The list has not yet been scored against the inspections that follow it. Use it to
                decide where to look, and read the grade card before you judge.
              </>
            )}
          </p>
        </div>

        <div className="flex flex-col gap-3 border-t border-rule-strong px-8 py-5 sm:flex-row sm:items-center sm:justify-between">
          <button onClick={dismissWelcome} className="bg-ink px-6 py-2.5 text-[13px] font-semibold text-paper hover:bg-ink-2">
            View the map
          </button>
          <button
            onClick={() => { if (!advanced) toggle(); dismissWelcome(); }}
            className="border-b border-ink/25 pb-px text-left text-[12px] text-ink-3 hover:border-ink hover:text-ink sm:text-right"
          >
            I work in environmental health. Use technical terms.
          </button>
        </div>
      </article>
    </div>
  );
}
