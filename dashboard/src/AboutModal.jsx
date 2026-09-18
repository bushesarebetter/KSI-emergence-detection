import { useEffect } from "react";
import { useAdvanced } from "./useAdvanced";

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
          A ranking of every San Diego intersection with <em>no</em> serious-crash
          history, ordered by how likely it is to produce one. It is built from crash
          records the city already collects, 2016 through 2024 — no new data, no
          cameras, no sensors.
        </p>
      </Section>

      <Section heading="How well it works">
        <p>
          Of the 108 intersections that had a serious crash in 2025, a shortlist of 500
          flagged 24 of them beforehand. That is roughly eleven times better than
          choosing at random — and it still misses most of them.
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
  return (
    <>
      <Section heading="Model">
        <p>
          XGBoost Tweedie regression on 20 crash-history features, hyperparameters fixed
          by nested cross-validation and frozen thereafter. Trained once on 2016–2021
          features against 2022–2024 KSI outcomes; applied to the 2025–2027 candidate
          cohort by predict-only scoring, never refit.
        </p>
      </Section>

      <Section heading="Signals">
        <p>
          Dominant features are crash-timing: recency of last crash, and structural
          acceleration from a previously stable baseline (changepoint detection).
          Cumulative volume outweighs short-term recency. Built-environment features
          showed a consistent +0.02 Spearman on the verified run but did not replicate
          on the 2025 forward run, so the deployed model stays crash-history only.
        </p>
      </Section>

      <Section heading="Reported honestly">
        <p>
          At the ≥2-KSI threshold a persistence baseline — rank by recent crash count
          and trend — ties the tuned model exactly, 10/21 on the random split. The
          model’s validated edge is at the broader ≥1-KSI threshold. With 21 positives,
          the bootstrap CI on recall@500 spans [28.6%, 71.4%].
        </p>
        <p>
          Forward run recall@500 (≥1 KSI, 108 positives): 24/108 = 22.2%, 11.6× random.
        </p>
      </Section>

      <Section heading="Candidate set">
        <p>
          26,045 intersections inside City of San Diego limits with no KSI history
          through 2024. State-highway crashes excluded; crashes assigned to nodes within
          a 76.2 m buffer.
        </p>
      </Section>

      <p className="mt-7 border-t border-rule pt-4 font-mono text-[11px] text-ink-3">
        SWITRS via TIMS · OSM/OSMnx · see docs/METHODOLOGY.md, DECISIONS.md D11/D17
      </p>
    </>
  );
}
