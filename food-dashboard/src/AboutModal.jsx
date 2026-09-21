import { useEffect } from "react";
import { useAdvanced } from "./useAdvanced";
import { useCatch, useMeta, useSample } from "./useMeta";
import { DEFAULT_THRESHOLD, REPO_URL } from "./constants";
import { SITE } from "./site";

export default function AboutModal({ onClose, onNavigate }) {
  const { advanced } = useAdvanced();

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const link = (path, label) => (
    <a
      href={path}
      onClick={(e) => {
        if (!onNavigate) return;
        e.preventDefault();
        onClose();
        onNavigate(path);
      }}
      className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink"
    >
      {label}
    </a>
  );

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="about-title"
      className="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-ink/40 p-4 sm:p-8"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <article className="relative my-auto w-full max-w-[38rem] border border-rule-strong bg-paper">
        <button onClick={onClose} aria-label="Close" className="absolute right-4 top-3 text-[20px] leading-none text-ink-3 hover:text-ink">×</button>

        <div className="border-b border-rule-strong px-7 py-5">
          <p className="label mb-2">{advanced ? "Methodology" : "About this map"}</p>
          <h2 id="about-title" className="font-serif text-[26px] font-medium leading-[1.15] text-ink">
            {advanced ? "Forward run, next routine inspection" : "Finding the kitchens that are slipping, before the inspection"}
          </h2>
        </div>

        <div className="px-7 py-6">{advanced ? <Technical /> : <Plain />}</div>

        <p className="flex flex-wrap gap-x-5 gap-y-1 border-t border-rule px-7 py-4 text-[11.5px] text-ink-3">
          {link("/privacy", "Privacy and terms")}
          <a href={SITE.regulator.resultsUrl} target="_blank" rel="noopener noreferrer" className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink">
            The County&rsquo;s inspection search
          </a>
          <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink">Code on GitHub</a>
          <a href={`${REPO_URL}/issues`} target="_blank" rel="noopener noreferrer" className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink">Report a problem</a>
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
  const { caught, total, lift, scored } = useCatch(DEFAULT_THRESHOLD);
  const sample = useSample();
  const randomCatch = lift ? Math.max(1, Math.round(caught / lift)) : null;

  return (
    <>
      {sample && (
        <p className="mb-6 border border-risk-2 px-4 py-3 font-serif text-[15px] leading-[1.55] text-ink">
          This is the site before its model. Every place, address and inspection shown is invented so
          the pages could be built and reviewed. Nothing here describes a real business.
        </p>
      )}

      <Section heading="The problem">
        <p>
          {SITE.regulator.short.charAt(0).toUpperCase() + SITE.regulator.short.slice(1)} inspects about{" "}
          {SITE.regulator.facilityCount.toLocaleString()} restaurants, markets, food trucks and school
          kitchens, one to three times a year depending on how much risky food handling each does.
          A kitchen that is slipping waits its turn like one that is not, and the grade card in the
          window says what was found last time, not what is happening now.
        </p>
      </Section>

      <Section heading="What this is">
        <p>
          A ranking of {SITE.name} food facilities by how likely the County&rsquo;s next routine
          inspection is to find a major violation: the kind, such as food held at the wrong
          temperature or a blocked hand sink, that the County says must be fixed on the spot. It uses
          only what the County already publishes about each place: its scores visit by visit, the
          violations cited, reinspections and closures, what kind of place it is and how often it is
          inspected, and the record of the places around it.
        </p>
      </Section>

      <Section heading="How to read it">
        <p>
          Darker dots carry higher predicted risk. A rank is a position in the ordering and
          carries no probability of its own; a place&rsquo;s panel says how often places ranked
          that high went on to have a major violation, with the counts. Click a dot and you get its scores, what inspectors found by
          theme, and what to look for yourself.
        </p>
        <p>
          The grade card is the County&rsquo;s official statement. A is {SITE.regulator.grades.A}, B
          is {SITE.regulator.grades.B}, C is {SITE.regulator.grades.C}. A B or C means the last
          inspection found at least one major violation, and a reinspection usually follows.
        </p>
        <p>
          The lines under &ldquo;If you eat here&rdquo; quote the record and give the standard thing a
          customer can check for that kind of finding. They are general practice. None of them is a
          finding about any particular visit.
        </p>
      </Section>

      <Section heading="How well it works">
        {scored ? (
          <p>
            Of the {total} places that had a major violation at their next inspection, the list of{" "}
            {DEFAULT_THRESHOLD} had flagged {caught} beforehand.
            {randomCatch != null && <> Picking {DEFAULT_THRESHOLD} at random would have caught about {randomCatch}.</>}{" "}
            It still misses most of them. Read the list as a place to start looking rather than a
            verdict on any one kitchen.
          </p>
        ) : (
          <p>
            Not yet scored. The list is checked against the routine inspections that follow it, and
            the first figure appears once a season of them is in.
          </p>
        )}
      </Section>

      <Section heading="What it is not">
        <p>
          Independent student research. It is not a {SITE.county} assessment. A dot here does not
          mean a place is unsafe today, and the absence of one does not mean it is safe. If a record
          here differs from the County&rsquo;s, the County&rsquo;s is right.
        </p>
      </Section>

      <p className="mt-7 border-t border-rule pt-4 text-[11px] text-ink-3">{SITE.attributions}</p>
    </>
  );
}

function Technical() {
  const { caught, total, lift, candidates, scored } = useCatch(DEFAULT_THRESHOLD);
  const meta = useMeta();

  return (
    <>
      <Section heading="Model">
        <p>
          {meta?.model ? `Export: ${meta.model} (run ${meta.run ?? "unknown"}, generated ${meta.generated ?? "n/a"}). ` : ""}
          Planned: gradient-boosted classifier on the County&rsquo;s inspection history, trained on
          earlier windows against the following routine inspection and applied to the current cohort
          by predict-only scoring, never refit on the label window. Hyperparameters fixed by nested
          cross-validation. The export carries each facility&rsquo;s top five SHAP features.
        </p>
      </Section>

      <Section heading="Label">
        <p>
          {meta?.label ?? "At least one major violation at the next routine inspection"}
          {meta?.label_window ? `, label window ${meta.label_window}` : ""}. Reinspections and
          complaint visits are features, never labels.
        </p>
      </Section>

      <Section heading="Signals">
        <p>
          Display labels use a fixed vocabulary (docs/FOOD_DATA_CONTRACT.md): last routine score,
          majors in the last N inspections, theme citation counts, closures, reinspections, risk
          category, facility type, score delta, months since inspection, complaints, neighbours&rsquo;
          mean score, ownership change. The plain-language rewrites read that vocabulary; an export
          that drifts from it fails the build check.
        </p>
      </Section>

      <Section heading="Data">
        <p>
          Candidate set: the County&rsquo;s Food Facility Permits open dataset (about 15,900 permits,
          public domain), active retail food facilities{candidates ? `, ${candidates.toLocaleString()} scored` : ""}.
          Inspection history: SD Food Info, the County&rsquo;s published results, routine and
          reinspection visits with scores, grades and cited items. Themes group the numbered items
          of the California retail food inspection report.
        </p>
      </Section>

      <Section heading="Reported honestly">
        {scored ? (
          <p>
            Forward run recall@{DEFAULT_THRESHOLD} ({total} positives): {caught}/{total}
            {total > 0 && <> = {((100 * caught) / total).toFixed(1)}%</>}
            {lift != null && <>, {lift.toFixed(1)}× random</>}. Bootstrap intervals and a
            persistence baseline (rank by last score and majors) are reported alongside once the
            pipeline writes them.
          </p>
        ) : (
          <p>No forward-run score yet. The catch table in meta.json is empty until the label window closes.</p>
        )}
      </Section>

      <p className="mt-7 border-t border-rule pt-4 font-mono text-[11px] text-ink-3">
        See docs/FOOD_DATA_CONTRACT.md and DECISIONS.md D29.
      </p>
    </>
  );
}
