import { useEffect } from "react";
import { useAdvanced } from "./useAdvanced";
import { useCatch, useComposition } from "./useMeta";
import { DEFAULT_THRESHOLD } from "./constants";

export default function AboutModal({ onClose }) {
  const { advanced } = useAdvanced();

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="about-title"
      className="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-ink/25 p-4 backdrop-blur-[2px] sm:p-8"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <article className="relative my-auto w-full max-w-[38rem] border border-rule-strong bg-paper shadow-paper">
        <button
          onClick={onClose}
          aria-label="Close"
          className="absolute right-4 top-3 text-[20px] leading-none text-ink-3 transition-colors hover:text-ink"
        >
          ×
        </button>

        <div className="border-b border-rule-strong px-7 py-5">
          <p className="label mb-2">{advanced ? "Methodology" : "About this map"}</p>
          <h2 id="about-title" className="font-serif text-[26px] font-medium leading-[1.15] text-ink">
            {advanced
              ? "Forward run, 2025–2027"
              : "Finding dangerous corners before anyone is hurt"}
          </h2>
        </div>

        <div className="px-7 py-6">{advanced ? <Technical /> : <Plain />}</div>
      </article>
    </div>
  );
}

function Section({ heading, children }) {
  return (
    <section className="mb-6 last:mb-0">
      <h3 className="label mb-2">{heading}</h3>
      <div className="space-y-3 font-serif text-[15px] leading-[1.6] text-ink-2">{children}</div>
    </section>
  );
}

function Plain() {
  const { caught, total, lift } = useCatch(DEFAULT_THRESHOLD);
  const { isCombined, known, screen } = useComposition();
  const liftRounded = lift == null ? null : Math.round(lift);

  return (
    <>
      <Section heading="The problem">
        <p>
          Traffic safety money mostly follows crashes that already happened. San Diego
          reviews intersections with five or more prior crashes — about fourteen
          locations a year. A corner that is becoming dangerous, but has no record yet,
          is invisible to that process.
        </p>
      </Section>

      <Section heading="What this is">
        <p>
          A ranking of the San Diego intersections <em>below</em> the City&rsquo;s five-crash
          review line, ordered by how likely each is to produce a serious crash. It is built
          from crash records the city already collects, 2016 through 2024 — no new data, no
          cameras, no sensors.
        </p>
        {isCombined && (
          <p>
            The list on the map also includes {known.toLocaleString()} intersections that
            have already had a serious crash
            {screen > 0 && <> and {screen.toLocaleString()} that meet the City&rsquo;s own screening rule</>}.
            Those are records, not predictions; they sit at the top of the list and are
            marked as such.
          </p>
        )}
      </Section>

      <Section heading="How well it works">
        <p>
          Of the {total} intersections that had a serious crash in 2025, the model&rsquo;s
          shortlist of {DEFAULT_THRESHOLD} flagged {caught} of them beforehand
          {liftRounded != null && <>. That is roughly {liftRounded} times better than choosing at random</>}
          — and it still misses most of them.
        </p>
        <p>
          Read the shortlist as a place to start looking, not as a verdict on any single
          corner.
        </p>
      </Section>

      <Section heading="What it is not">
        <p>
          Independent student research, not an official City of San Diego hazard
          assessment. A dot here does not mean an intersection is unsafe today, and the
          absence of one does not mean it is safe.
        </p>
      </Section>

      <p className="mt-7 border-t border-rule pt-4 text-[11px] text-ink-3">
        Crash data: SWITRS via TIMS, UC Berkeley SafeTREC. Road network: OpenStreetMap.
        Publication forthcoming.
      </p>
    </>
  );
}

function Technical() {
  const { caught, total, lift } = useCatch(DEFAULT_THRESHOLD);

  return (
    <>
      <Section heading="Model">
        <p>
          XGBoost Tweedie regression on 47 features — crash history (20), road
          infrastructure (21), and spatial-neighbor structure (6). Hyperparameters fixed
          by nested cross-validation and frozen. Trained on 2016–2021 features against
          2022–2024 KSI outcomes on the sub-threshold candidate set; applied to the
          2025–2027 cohort by predict-only scoring, never refit.
        </p>
      </Section>

      <Section heading="Signals">
        <p>
          SHAP splits the decision roughly 53% road infrastructure, 32% crash history,
          15% corridor context. Top drivers: recency of the last crash, road functional
          class (arterial vs. local), intersection geometry, and transit proximity. Once
          the sites the City already flags are removed, crash counts flatten and road
          design carries the weight — much of it exposure by proxy, since arterials carry
          more traffic. Adding measured traffic volume (ADT) did not improve the ranking,
          which points the same way: the signal is substantially exposure.
        </p>
      </Section>

      <Section heading="Reported honestly">
        <p>
          The edge over a crash-count persistence baseline is small — a few events at the
          top of the list — and consistent across both the random and spatial-block CV
          splits at the any-KSI threshold. The severe (≥2-KSI) threshold has too few
          positives to model; a raw crash-count baseline catches more of those.
        </p>
        <p>
          Forward run recall@{DEFAULT_THRESHOLD} (≥1 KSI, {total} positives): {caught}/{total}
          {total > 0 && <> = {((100 * caught) / total).toFixed(1)}%</>}
          {lift != null && <>, {lift.toFixed(1)}× random</>}.
        </p>
      </Section>

      <Section heading="Candidate set">
        <p>
          Intersections inside City of San Diego limits below the City&rsquo;s screening
          bar — fewer than five injury-or-fatal crashes in the feature window, so none are
          on its high-crash review. State-highway crashes excluded; crashes assigned to
          nodes within a 76.2 m buffer.
        </p>
      </Section>

      <p className="mt-7 border-t border-rule pt-4 font-mono text-[11px] text-ink-3">
        SWITRS via TIMS · OSM/OSMnx · see docs/METHODOLOGY.md, DECISIONS.md D11/D17
      </p>
    </>
  );
}
