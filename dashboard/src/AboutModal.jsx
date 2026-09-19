import { useEffect } from "react";
import { useAdvanced } from "./useAdvanced";
import { useCatch, useComposition } from "./useMeta";
import { DEFAULT_THRESHOLD, REPO_URL } from "./constants";

export default function AboutModal({ onClose, onNavigate }) {
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
      className="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-ink/40 p-4 sm:p-8"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <article className="relative my-auto w-full max-w-[38rem] border border-rule-strong bg-paper">
        <button
          onClick={onClose}
          aria-label="Close"
          className="absolute right-4 top-3 text-[20px] leading-none text-ink-3 hover:text-ink"
        >
          ×
        </button>

        <div className="border-b border-rule-strong px-7 py-5">
          <p className="label mb-2">{advanced ? "Methodology" : "About this map"}</p>
          <h2 id="about-title" className="font-serif text-[26px] font-medium leading-[1.15] text-ink">
            {advanced ? "Forward run, 2025 to 2027" : "Finding dangerous corners before anyone is hurt"}
          </h2>
        </div>

        <div className="px-7 py-6">{advanced ? <Technical /> : <Plain />}</div>

        <p className="flex flex-wrap gap-x-5 gap-y-1 border-t border-rule px-7 py-4 text-[11.5px] text-ink-3">
          <a
            href="/privacy"
            onClick={(e) => {
              if (!onNavigate) return;
              e.preventDefault();
              onClose();
              onNavigate("/privacy");
            }}
            className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink"
          >
            Privacy and terms
          </a>
          <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink">
            Code on GitHub
          </a>
          <a href={`${REPO_URL}/issues`} target="_blank" rel="noopener noreferrer" className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink">
            Report a problem
          </a>
        </p>
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
  const randomCatch = lift ? Math.max(1, Math.round(caught / lift)) : null;

  return (
    <>
      <Section heading="The problem">
        <p>
          Traffic safety money follows crashes that already happened. San Diego reviews
          intersections with five or more prior crashes, about fourteen locations a year. A
          corner that is becoming dangerous, with no record yet, is invisible to that process.
        </p>
      </Section>

      <Section heading="What this is">
        <p>
          A ranking of every San Diego intersection with no serious-crash history, ordered by
          how likely it is to produce one. It uses crash records the city already collects, 2016
          through 2024. No new data, no cameras, no sensors.
        </p>
        {isCombined && (
          <p>
            The list on the map also holds {known.toLocaleString()} intersections that have
            already had a serious crash
            {screen > 0 && <> and {screen.toLocaleString()} that meet the City&rsquo;s own screening rule</>}.
            Those sit at the top of the list by record, and the map marks them.
          </p>
        )}
      </Section>

      <Section heading="How to read it">
        <p>
          Darker dots carry higher predicted risk. Click one and you get its crash record year by
          year, the pattern behind it, and what the model saw.
        </p>
        <p>
          &ldquo;How busy it is&rdquo; uses the City of San Diego&rsquo;s own traffic counts,
          the average number of vehicles a day, where the City has counted that street at or
          within a block of the corner. Dividing crashes a year by the vehicles entering, in
          millions, gives the rate engineers use to compare a busy arterial with a quiet
          street; a raw count alone makes every quiet street look safe.
        </p>
        <p>
          &ldquo;Police have logged&rdquo; counts San Diego Police collision reports filed to
          that intersection since the model&rsquo;s cutoff; most reports are filed to a block
          address instead and are not counted, so the figure is a floor. Whether a corner
          has signals or stop signs comes from OpenStreetMap and changes the advice for
          turns.
        </p>
        <p>
          The lines under &ldquo;If you use this corner&rdquo; quote the record (say, three
          left-turn crashes in six years) and give the standard road practice for that kind of
          crash. They are general advice. None of them would have prevented any particular
          crash, and they are no substitute for looking at the corner yourself.
        </p>
      </Section>

      <Section heading="How well it works">
        <p>
          Of the {total} intersections that had a serious crash in 2025, the model&rsquo;s list
          of {DEFAULT_THRESHOLD} had flagged {caught} of them beforehand.
          {randomCatch != null && (
            <> Picking {DEFAULT_THRESHOLD} corners at random would have caught about {randomCatch}.</>
          )}{" "}
          It still misses most of them. Read the list as a place to start looking rather than a
          verdict on any single corner.
        </p>
      </Section>

      <Section heading="What it is not">
        <p>
          Independent student research. It is not an official City of San Diego hazard
          assessment. A dot here does not mean an intersection is unsafe today, and the absence
          of one does not mean it is safe.
        </p>
      </Section>

      <p className="mt-7 border-t border-rule pt-4 text-[11px] text-ink-3">
        Crash data: SWITRS via TIMS, UC Berkeley SafeTREC. Traffic counts: City of San Diego
        open data. Road network: OpenStreetMap. Publication forthcoming.
      </p>
    </>
  );
}

function Technical() {
  const { caught, total, lift } = useCatch(DEFAULT_THRESHOLD);
  const { isCombined, known, screen, topN } = useComposition();

  return (
    <>
      <Section heading="Model">
        <p>
          XGBoost Tweedie regression on 20 crash-history features, hyperparameters fixed by
          nested cross-validation and frozen. Trained once on 2016 to 2021 features against 2022
          to 2024 KSI outcomes, then applied to the 2025 to 2027 candidate cohort by predict-only
          scoring, never refit.
        </p>
      </Section>

      <Section heading="Signals">
        <p>
          The dominant features are crash timing: recency of the last crash, and structural
          acceleration from a previously stable baseline (changepoint detection). Cumulative
          volume outweighs short-term recency. Built-environment features added a consistent
          +0.02 Spearman on the verified run and did not replicate on the 2025 forward run, so
          the deployed model stays crash-history only.
        </p>
        <p>
          The countermeasure prompts in the detail panel read the crash-type features present in
          a site&rsquo;s top signals (left-turn, night, bicycle, pedestrian, broadside counts over
          the feature window) and attach the standard road-user countermeasure for that crash
          type. They are prompts, and they carry no model weight.
        </p>
      </Section>

      <Section heading="Reported honestly">
        <p>
          At the 2-or-more-KSI threshold a persistence baseline, rank by recent crash count and
          trend, ties the tuned model exactly at 10/21 on the random split. The model&rsquo;s
          validated edge is at the broader 1-or-more threshold. With 21 positives, the bootstrap
          CI on recall@500 spans [28.6%, 71.4%].
        </p>
        <p>
          Forward run recall@{DEFAULT_THRESHOLD} (1 or more KSI, {total} positives): {caught}/{total}
          {total > 0 && <> = {((100 * caught) / total).toFixed(1)}%</>}
          {lift != null && <>, {lift.toFixed(1)}× random</>}.
        </p>
      </Section>

      <Section heading="Exposure">
        <p>
          City of San Diego ADT counts (2023 to 2026 file), matched to a site when a count on
          one of its streets names the other street as a segment limit, else the nearest
          count on the same street within 250 m. Entering volume is the sum over matched
          streets of the most recent count; a one-street match is flagged as a ceiling on the
          rate. Rate per MEV = crashes/yr (2016 to 2024) ÷ (entering ADT × 365 / 10⁶). Trend
          compares 2022 to 2024 against 2016 to 2021 (rising at ×1.5 and +1/yr).
        </p>
        <p>
          Recent reports: SDPD collision file (City open data), intersection rows only,
          matched on the unordered street pair since 2025-01-01. Control: OSM
          highway=traffic_signals or highway=stop nodes within 25 m of the site.
        </p>
      </Section>

      <Section heading="Candidate set">
        <p>
          26,045 intersections inside City of San Diego limits with no KSI history through 2024.
          State-highway crashes excluded; crashes assigned to nodes within a 76.2 m buffer.
        </p>
        {isCombined && (
          <p>
            The exported list is the combined top-{topN}: {known} known-KSI sites (feature-window
            KSI of 1 or more, all spine nodes), then {screen} City-screen sites (5 or more crashes
            in the last feature year), then model predictions. Tiers are stacked in that order
            (src/export/combined_list.py). The catch statistics above score the model ranking
            alone.
          </p>
        )}
      </Section>

      <p className="mt-7 border-t border-rule pt-4 font-mono text-[11px] text-ink-3">
        SWITRS via TIMS, OSM/OSMnx. See docs/METHODOLOGY.md and DECISIONS.md D11, D17, D19.
      </p>
    </>
  );
}
