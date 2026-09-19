import PageFrame from "./PageFrame";

export default function NotFound({ onNavigate }) {
  const path = typeof window === "undefined" ? "" : window.location.pathname;
  const go = (p) => (e) => {
    e.preventDefault();
    onNavigate(p);
  };

  return (
    <PageFrame onNavigate={onNavigate}>
      <p className="label mb-4">404</p>
      <h1 className="font-serif text-[36px] font-medium leading-[1.08] tracking-[-0.02em] text-ink sm:text-[44px]">
        There is no page at <span className="font-mono text-[0.6em] font-normal">{path}</span>
      </h1>
      <p className="mt-5 max-w-[46ch] font-serif text-[17px] leading-[1.55] text-ink-2">
        The map lives at <span className="font-mono text-[14px]">/map</span>. A link to one
        intersection looks like <span className="font-mono text-[14px]">/map?site=43</span>, where
        the number is its rank.
      </p>
      <p className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-[14px]">
        <a href="/" onClick={go("/")} className="border-b border-ink/25 text-ink hover:border-ink">
          Home
        </a>
        <a href="/map" onClick={go("/map")} className="border-b border-ink/25 text-ink hover:border-ink">
          Open the map
        </a>
      </p>
    </PageFrame>
  );
}
