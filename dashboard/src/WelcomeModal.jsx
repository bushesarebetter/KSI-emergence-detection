import { useAdvanced } from "./useAdvanced";
import { useCatch } from "./useMeta";
import { DEFAULT_THRESHOLD } from "./constants";

/**
 * Shown once, on first visit to the map.
 *
 * Set as the opening of a printed report: kicker, headline, then two short
 * paragraphs and the caveat. The caveat carries the same weight as the claim,
 * because a reader who finds the limitation on their own after trusting the
 * headline is a reader you have lost. Its numbers come from meta.json.
 */
export default function WelcomeModal() {
  const { seenWelcome, dismissWelcome, advanced, toggle } = useAdvanced();
  const { caught, total } = useCatch(DEFAULT_THRESHOLD);

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
          <p className="label mb-3">San Diego, independent research</p>
          <h1
            id="welcome-title"
            className="font-serif text-[32px] font-medium leading-[1.08] tracking-[-0.02em] text-ink sm:text-[38px]"
          >
            Where serious crashes are&nbsp;likely to happen next
          </h1>
        </div>

        <div className="space-y-4 px-8 py-6 font-serif text-[16px] leading-[1.55] text-ink-2">
          <p>
            Every dot is a San Diego corner with no serious crash on record. Darker means the
            model expects one sooner.
          </p>
          <p>
            Click a dot. You will see the crashes recorded there, what kind they were, and what
            to do differently the next time you pass through.
          </p>
          <p className="border-t border-rule pt-4 text-[15px] text-ink-3">
            Of the {total} corners that had a serious crash in 2025, this list of{" "}
            {DEFAULT_THRESHOLD} had flagged {caught}. It misses most of them. Use it to decide
            where to look, and look before you judge.
          </p>
        </div>

        <div className="flex flex-col gap-3 border-t border-rule-strong px-8 py-5 sm:flex-row sm:items-center sm:justify-between">
          <button
            onClick={dismissWelcome}
            className="bg-ink px-6 py-2.5 text-[13px] font-semibold text-paper hover:bg-ink-2"
          >
            View the map
          </button>
          <button
            onClick={() => {
              if (!advanced) toggle();
              dismissWelcome();
            }}
            className="border-b border-ink/25 pb-px text-left text-[12px] text-ink-3 hover:border-ink hover:text-ink sm:text-right"
          >
            I work in traffic safety. Use technical terms.
          </button>
        </div>
      </article>
    </div>
  );
}
