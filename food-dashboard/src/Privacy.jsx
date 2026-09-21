import PageFrame from "./PageFrame";
import { REPO_URL } from "./constants";
import { SITE } from "./site";

const ANALYTICS_SRC = import.meta.env.VITE_ANALYTICS_SRC || "";

function hostOf(url) {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

function Section({ heading, children }) {
  return (
    <section className="mb-8 last:mb-0">
      <h2 className="label mb-2">{heading}</h2>
      <div className="space-y-3 font-serif text-[16px] leading-[1.6] text-ink-2">{children}</div>
    </section>
  );
}

const Link = ({ href, children }) => (
  <a href={href} target="_blank" rel="noopener noreferrer" className="border-b border-ink/25 text-ink hover:border-ink">
    {children}
  </a>
);

export default function Privacy({ onNavigate }) {
  return (
    <PageFrame onNavigate={onNavigate}>
      <p className="label mb-4">Updated September 2026</p>
      <h1 className="mb-10 font-serif text-[36px] font-medium leading-[1.08] tracking-[-0.02em] text-ink sm:text-[44px]">
        Privacy and terms
      </h1>

      <Section heading="What this site collects">
        <p>
          Nothing of its own. There is no account and no cookie set by this site. The one form,
          &ldquo;Near an address&rdquo;, sends what you type to Google, as you type, to suggest
          addresses, and then to locate the one you choose; this site does not store any of it.
          Three settings live in your browser&rsquo;s local storage: whether you have seen the
          welcome note, whether you dismissed the cookie note, and whether you chose technical
          wording. Clearing site data removes them.
        </p>
        {ANALYTICS_SRC ? (
          <p>
            Page views are counted by a script loaded from {hostOf(ANALYTICS_SRC)}. It records
            the page, the referrer and a coarse location; it does not set a cookie.
          </p>
        ) : (
          <p>No analytics script runs on this site.</p>
        )}
      </Section>

      <Section heading="Google Maps">
        <p>
          The basemap and Street View are drawn by Google Maps, loaded from Google&rsquo;s servers
          when the map opens. Google receives your IP address and the map tiles you request,
          and may set its own cookies.{" "}
          <Link href="https://policies.google.com/privacy">Google&rsquo;s privacy policy</Link> covers
          that.
        </p>
      </Section>

      <Section heading="Hosting">
        <p>
          The site is served by Render, which keeps ordinary web-server logs: IP address, request
          path and time. <Link href="https://render.com/privacy">Render&rsquo;s privacy policy</Link>{" "}
          covers those.
        </p>
      </Section>

      <Section heading="Terms of use">
        <p>
          The ranking is independent student research, provided as is and without warranty of any
          kind. It is not a {SITE.county} assessment and does not replace one. The rank is a
          prediction about the next routine inspection; it is not a statement about the food, the
          people or the premises today. A place on the map is not unsafe because it is listed, and
          a place that is not listed is not safe because it is absent.
        </p>
        <p>
          Every fact shown about a place, its scores, grades, closures and violations, is the
          County&rsquo;s own published inspection record, shown as published. The grade card posted
          at the premises is the official statement, and the County&rsquo;s{" "}
          <Link href={SITE.regulator.resultsUrl}>inspection search</Link> is the record of reference.
          If a record here differs from the County&rsquo;s, the County&rsquo;s is right and this
          site should be corrected; use the link below. The checks under &ldquo;If you eat here&rdquo;
          are general food-safety practice for the kind of finding recorded; none of them is a
          finding about any particular visit.
        </p>
        <p>
          You may quote or reuse the ranking with attribution. The code is released under the
          MIT licence at <Link href={REPO_URL}>GitHub</Link>. Inspection results are published by
          the {SITE.regulator.name}; the facility list is the County&rsquo;s open data, in the
          public domain.
        </p>
      </Section>

      <Section heading="Contact">
        <p>
          Questions and corrections: <Link href={`${REPO_URL}/issues`}>open an issue on GitHub</Link>.
          The authors are {SITE.authors}. A business that believes its record is shown wrongly
          should say so there; the record will be checked against the County&rsquo;s and corrected.
        </p>
      </Section>
    </PageFrame>
  );
}
