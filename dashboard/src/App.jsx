import { useState, useEffect, useRef, useCallback } from "react";
import Header from "./Header";
import Sidebar from "./Sidebar";
import MapView from "./MapView";
import RankedTable from "./RankedTable";
import IntersectionPanel from "./IntersectionPanel";
import WelcomeModal from "./WelcomeModal";
import MobileShell from "./MobileShell";
import Landing from "./Landing";
import useIntersections from "./useIntersections";
import useMediaQuery from "./useMediaQuery";
import { readSiteFromUrl, writeSiteToUrl } from "./useDeepLink";
import { AdvancedProvider, useAdvanced } from "./useAdvanced";
import { MetaProvider, useMetaFetch } from "./useMeta";
import { DEFAULT_THRESHOLD } from "./constants";

const DEFAULT_FILTERS = { threshold: DEFAULT_THRESHOLD, districts: [], crashActiveOnly: false };
const PHONE = "(max-width: 767px)";

/**
 * Two views, no router: `/` is the landing page, `/map` is the application.
 * A deep link (`/?site=43`) goes straight to the map -- someone who was sent a
 * link to a specific corner should land on that corner, not on a pitch.
 */
function viewFromLocation() {
  if (typeof window === "undefined") return "landing";
  const { pathname, search } = window.location;
  if (pathname.startsWith("/map") || new URLSearchParams(search).has("site")) return "map";
  return "landing";
}

export default function App() {
  // meta.json is small and independent of the intersections file, so it is
  // fetched here once and made available everywhere without prop-threading.
  const meta = useMetaFetch();
  return (
    <AdvancedProvider>
      <MetaProvider meta={meta}>
        <Dashboard />
      </MetaProvider>
    </AdvancedProvider>
  );
}

function Dashboard() {
  const { intersections, districts, loading, error } = useIntersections();
  const { dismissWelcome } = useAdvanced();
  const [selectedIntersection, setSelectedIntersection] = useState(null);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [view, setView] = useState(viewFromLocation);
  const isPhone = useMediaQuery(PHONE);

  // Deep link in: read once at mount into a ref so the write effect below cannot
  // strip the parameter before the data has loaded and it has been consumed.
  const initialSite = useRef(readSiteFromUrl());
  useEffect(() => {
    if (!intersections || initialSite.current == null) return;
    const wanted = initialSite.current;
    initialSite.current = null;
    const feature = intersections.features.find((f) => f.properties.rank === wanted);
    if (feature) setSelectedIntersection(feature);
  }, [intersections]);

  // Deep link out: the address bar is the share link.
  useEffect(() => {
    if (initialSite.current != null || view !== "map") return;
    writeSiteToUrl(selectedIntersection?.properties.rank ?? null);
  }, [selectedIntersection, view]);

  // Browser back/forward between landing and map.
  useEffect(() => {
    const onPop = () => setView(viewFromLocation());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  // Entering the app from the landing page. Someone who has read the hero has
  // already had the welcome, so it is marked seen rather than shown again.
  const enterMap = useCallback(
    (feature = null) => {
      const url = new URL(window.location.href);
      url.pathname = "/map";
      if (feature) url.searchParams.set("site", String(feature.properties.rank));
      else url.searchParams.delete("site");
      window.history.pushState(null, "", url);
      if (feature) setSelectedIntersection(feature);
      dismissWelcome();
      setView("map");
    },
    [dismissWelcome]
  );

  // The wordmark in the app masthead. Going home clears the selection so the
  // URL comes back clean; the data stays in memory, so it is instant.
  const goHome = useCallback(() => {
    const url = new URL(window.location.href);
    url.pathname = "/";
    url.search = "";
    window.history.pushState(null, "", url);
    setSelectedIntersection(null);
    setView("landing");
  }, []);

  // The landing paints immediately; only the map view needs the data gate.
  if (view === "landing") {
    return <Landing intersections={intersections} error={error} onEnter={enterMap} />;
  }

  if (loading) {
    return (
      <div className="flex h-dvh items-center justify-center bg-paper">
        <div className="text-center">
          <div className="mx-auto mb-4 h-5 w-5 animate-spin rounded-full border border-rule-strong border-t-ink" />
          <p className="label">Loading intersections</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-dvh items-center justify-center bg-paper p-8">
        <div className="max-w-sm border-l-2 border-risk-1 pl-5">
          <p className="label mb-2 text-risk-1">Could not load data</p>
          <p className="font-serif text-[15px] leading-relaxed text-ink-2">{error}</p>
        </div>
      </div>
    );
  }

  // Phone gets its own shell: map, search, info, tap-sheet. Nothing else.
  if (isPhone) {
    return (
      <>
        <WelcomeModal />
        <MobileShell
          intersections={intersections}
          filters={DEFAULT_FILTERS}
          selected={selectedIntersection}
          onSelect={setSelectedIntersection}
        />
      </>
    );
  }

  return (
    <div className="flex h-dvh flex-col bg-paper">
      <WelcomeModal />

      <Header
        intersections={intersections}
        threshold={filters.threshold}
        onSelectIntersection={setSelectedIntersection}
        onHome={goHome}
      />

      <main className="relative flex flex-1 overflow-hidden">
        <aside className="w-[20.5rem] shrink-0 border-r border-rule-strong">
          <Sidebar
            intersections={intersections}
            districts={districts}
            filters={filters}
            onFiltersChange={setFilters}
          />
        </aside>

        <div className="relative min-w-0 flex-1">
          <MapView
            intersections={intersections}
            filters={filters}
            selectedIntersection={selectedIntersection}
            onSelectIntersection={setSelectedIntersection}
          />
          <RankedTable
            intersections={intersections}
            filters={filters}
            onSelectIntersection={setSelectedIntersection}
          />
        </div>

        <IntersectionPanel
          intersection={selectedIntersection}
          onClose={() => setSelectedIntersection(null)}
        />
      </main>
    </div>
  );
}
