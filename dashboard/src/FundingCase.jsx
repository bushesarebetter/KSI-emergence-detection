import PageFrame from "./PageFrame";
import { useCatch } from "./useMeta";
import { CRASH_COST, CRASH_COST_SOURCE, PROGRAM } from "./lib/crashcost";
import { MEASURES, fmtMoney, fmtRange, FHWA_PSC, CMF_CLEARINGHOUSE } from "./lib/countermeasures";
import { DEFAULT_THRESHOLD, REPO_URL } from "./constants";
import { CITY } from "./city";
import { track } from "./lib/track";

const FUNDS = [
  {
    name: "Highway Safety Improvement Program (HSIP)",
    who: "Federal money, run in California by Caltrans Local Assistance. Cities apply in periodic calls for projects; applications are scored on benefit-cost ratio, which is what this map's numbers feed.",
    url: "https://dot.ca.gov/programs/local-assistance/fed-and-state-programs/highway-safety-improvement-program",
  },
  {
    name: "Safe Streets and Roads for All (SS4A)",
    who: "U.S. Department of Transportation grants for planning and for building safety projects, open to cities directly.",
    url: "https://www.transportation.gov/grants/SS4A",
  },
  {
    name: "Active Transportation Program (ATP)",
    who: "California Transportation Commission money for walking and cycling projects, which most pedestrian and bike fixes on this list are.",
    url: "https://catc.ca.gov/programs/active-transportation-program",
  },
  {
    name: "Safe Routes to School (within the ATP)",
    who: "Money for crossings, sidewalks and signals near schools. Corners on this map flagged as near a school qualify on their face.",
    url: "https://catc.ca.gov/programs/active-transportation-program",
  },
  {
    name: `${CITY.fullName} Vision Zero and the capital budget`,
    who: "The City's own program and its annual budget hearings, where residents and council offices can ask for specific corners.",
    url: CITY.visionZeroUrl,
  },
];

const SOURCES = [
  { label: CRASH_COST_SOURCE.label, url: CRASH_COST_SOURCE.url },
  { label: "FHWA Proven Safety Countermeasures", url: FHWA_PSC },
  { label: "CMF Clearinghouse (crash modification factors)", url: CMF_CLEARINGHOUSE },
  { label: "This project's methodology and decision log", url: `${REPO_URL}#readme` },
];

function Section({ heading, children }) {
  return (
    <section className="mt-10">
      <h2 className="label mb-3">{heading}</h2>
      <div className="space-y-4 font-serif text-[17px] leading-[1.55] text-ink-2">{children}</div>
    </section>
  );
}

const Link = ({ href, children }) => (
  <a href={href} target="_blank" rel="noopener noreferrer" className="border-b border-ink/25 text-ink hover:border-ink">
    {children}
  </a>
);

/**
 * The funding case, written for a council staffer or a grant writer: the gap
 * the City's review leaves, the arithmetic of fixing a corner before the crash,
 * where the money is, and what this map hands a grant application. Every
 * figure names its source and its assumption.
 */
export default function FundingCase({ onNavigate }) {
  const { caught, total } = useCatch(DEFAULT_THRESHOLD);
  const go = (p) => (e) => { e.preventDefault(); onNavigate(p); };
  const cheapest = MEASURES.find((m) => m.key === "lpi");
  const left = MEASURES.find((m) => m.key === "protectedLeft");
  const perSerious = Math.floor(CRASH_COST.serious / cheapest.cost[1]);

  return (
    <PageFrame onNavigate={onNavigate}>
      <p className="label mb-4">The funding case</p>
      <h1 className="font-serif text-[36px] font-medium leading-[1.08] tracking-[-0.02em] text-ink sm:text-[44px]">
        Fix the corner before the crash, for a fraction of what the crash costs.
      </h1>
      <p className="mt-5 max-w-[52ch] font-serif text-[18px] leading-[1.55] text-ink-2">
        {CITY.name} spends its safety money where people have already been hurt. This page is the
        case for spending some of it one step earlier, with the numbers a budget office or a
        grant application needs.
      </p>

      <p className="print-hide mt-5 flex flex-wrap gap-x-5 gap-y-2 text-[13px]">
        <a href="/map" onClick={go("/map")} className="border-b border-ink/25 text-ink hover:border-ink">Open the map</a>
        <a href="/district/1" onClick={go("/district/1")} className="border-b border-ink/25 text-ink hover:border-ink">District reports</a>
        <button onClick={() => { track("print-funding"); window.print(); }} className="border-b border-ink/25 text-ink hover:border-ink">Print this page</button>
      </p>

      <Section heading="The gap">
        <p>
          The City reviews an intersection once it records {CITY.screen.threshold} or more{" "}
          {CITY.screen.unit}, about {CITY.screen.reviewsPerYear} corners a year. Everything below that bar is invisible to the
          review until it crosses it, usually because someone was badly hurt. This map ranks
          the corners below the bar by how likely a serious crash is next. Of the {total} corners
          that had one in 2025, the top {DEFAULT_THRESHOLD} had flagged {caught} a year in advance.
        </p>
      </Section>

      <Section heading="The arithmetic">
        <p>
          The Federal Highway Administration puts the societal cost of one fatal crash at about{" "}
          {fmtMoney(CRASH_COST.fatal)} and one serious-injury crash at about {fmtMoney(CRASH_COST.serious)}{" "}
          ({CRASH_COST_SOURCE.short}). A {cheapest.name.toLowerCase()} costs {fmtRange(cheapest.cost)} per
          corner and cuts pedestrian crashes by 13%. A {left.name.toLowerCase()} costs {fmtRange(left.cost)}.
          One prevented serious-injury crash pays for {cheapest.name.toLowerCase()}s at roughly {perSerious} corners.
        </p>
        <p>
          For the whole shortlist, this project&rsquo;s own estimate ({PROGRAM.label}): treating the top {PROGRAM.sites} corners
          would cost the City about {fmtMoney(PROGRAM.cityCost)} after the {Math.round(PROGRAM.federalShare * 100)}% federal share
          under HSIP, against about {fmtMoney(PROGRAM.preventedHarm)} of harm prevented if the fixes are {Math.round(PROGRAM.effectiveness * 100)}% effective,
          a benefit-cost ratio near {PROGRAM.bcr}:1. Two assumptions carry that figure and are stated
          in the repository: the program cost per corner and the treatment effectiveness. The
          crash costs themselves are FHWA&rsquo;s, and the harm is measured from the crashes that
          went on to happen.
        </p>
      </Section>

      <Section heading="What fixes cost">
        <p>
          Every corner on the map lists the FHWA proven countermeasures that match its crash
          pattern, with a rough installed cost. The full table, from cheapest up:
        </p>
        <ol className="border-t border-rule font-sans text-[13.5px]">
          {[...MEASURES].sort((a, b) => a.cost[0] - b.cost[0]).map((m) => (
            <li key={m.key} className="flex items-baseline gap-4 border-b border-rule py-2.5">
              <span className="min-w-0 flex-1">
                <span className="block text-ink">{m.name}</span>
                <span className="block text-[12px] text-ink-3">{m.reduction || "Cuts the conflict at its source"}</span>
              </span>
              <span className="tnum shrink-0 text-ink-2">{fmtRange(m.cost, m.per)}</span>
            </li>
          ))}
        </ol>
        <p className="font-sans text-[12px] text-ink-3">
          Costs are order-of-magnitude figures for a typical urban corner; a City bid can land
          outside them. Reductions are the figures FHWA publishes for each measure.
        </p>
      </Section>

      <Section heading="Where the money is">
        <ul className="border-t border-rule font-sans">
          {FUNDS.map((f) => (
            <li key={f.name} className="border-b border-rule py-3">
              <Link href={f.url}><span className="text-[14px]">{f.name}</span></Link>
              <p className="mt-1 text-[13px] leading-[1.5] text-ink-2">{f.who}</p>
            </li>
          ))}
        </ul>
      </Section>

      <Section heading="What this map hands a grant application">
        <p>
          An HSIP application is a benefit-cost worksheet: the crash record at the site, the
          traffic it carries, the countermeasure, its crash modification factor and its cost.
          Each corner here already carries the first four and a rough fifth, plus the crashes
          police have logged since the model&rsquo;s cutoff and how far the corner sits from the
          City&rsquo;s own threshold. The CSV download has the same columns for every site.
        </p>
      </Section>

      <Section heading="What you can do">
        <p>
          Open a corner you know and use &ldquo;Copy a message&rdquo; to send its record and its
          fix to your council office; the district link is on the same panel. Print your
          district&rsquo;s report and bring it to the budget hearing. Ask, in writing, for an
          engineering review of one corner. A review costs a few thousand dollars and is the step
          every fix on this list starts with.
        </p>
      </Section>

      <Section heading="Sources">
        <ul className="font-sans text-[13px]">
          {SOURCES.map((s) => (
            <li key={s.url} className="py-1"><Link href={s.url}>{s.label}</Link></li>
          ))}
        </ul>
      </Section>
    </PageFrame>
  );
}
