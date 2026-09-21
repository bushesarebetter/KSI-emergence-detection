import { REPO_URL } from "./constants";
import { SITE } from "./site";
import SampleBanner from "./SampleBanner";

/**
 * The frame for text pages (privacy and terms, 404, one place as a page):
 * the same masthead and footer as the landing page, with a single measure of
 * text between them.
 */
export default function PageFrame({ onNavigate, wide = false, children }) {
  const go = (p) => (e) => {
    e.preventDefault();
    onNavigate(p);
  };

  return (
    <div className="flex min-h-dvh flex-col bg-paper">
      <header className="print-hide border-b border-rule-strong">
        <div className="mx-auto flex max-w-[76rem] items-center justify-between px-5 py-3 md:px-8">
          <a href="/" onClick={go("/")} className="font-serif text-[17px] font-semibold tracking-[-0.01em] text-ink">
            {SITE.shortTitle}
            <span className="ml-2 hidden text-[11px] font-normal text-ink-3 sm:inline">{SITE.name}</span>
          </a>
          <a href="/map" onClick={go("/map")} className="border-b border-ink/25 pb-px text-[12px] text-ink-2 hover:border-ink hover:text-ink">
            Open the map
          </a>
        </div>
      </header>
      <SampleBanner />

      <main className={`mx-auto w-full flex-1 px-5 pb-16 pt-12 md:px-8 md:pt-16 ${wide ? "max-w-[56rem]" : "max-w-[44rem]"}`}>{children}</main>

      <Footer onNavigate={onNavigate} />
    </div>
  );
}

export function Footer({ onNavigate }) {
  const go = (p) => (e) => {
    e.preventDefault();
    onNavigate(p);
  };
  return (
    <footer className="print-hide border-t border-rule">
      <div className="mx-auto max-w-[76rem] px-5 py-5 text-[11.5px] leading-[1.6] text-ink-3 md:px-8">
        <p>
          Independent student research by {SITE.authors}. It is not a {SITE.county} assessment, and the
          County&rsquo;s posted grade card is the official statement about any place.
        </p>
        <p className="mt-1">{SITE.attributions}</p>
        <p className="mt-2 flex flex-wrap gap-x-5 gap-y-1">
          <a href={SITE.regulator.resultsUrl} target="_blank" rel="noopener noreferrer" className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink">
            The County&rsquo;s inspection search
          </a>
          <a href="/privacy" onClick={go("/privacy")} className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink">
            Privacy and terms
          </a>
          <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink">
            Code on GitHub
          </a>
          <a href={`${REPO_URL}/issues`} target="_blank" rel="noopener noreferrer" className="border-b border-ink/25 text-ink-2 hover:border-ink hover:text-ink">
            Report a problem
          </a>
        </p>
      </div>
    </footer>
  );
}
