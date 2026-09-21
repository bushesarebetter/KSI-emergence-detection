import { useState, useEffect, useRef, useCallback } from "react";
import Header from "./Header";
import Sidebar from "./Sidebar";
import MapView from "./MapView";
import RankedTable from "./RankedTable";
import IntersectionPanel from "./IntersectionPanel";
import WelcomeModal from "./WelcomeModal";
import MobileShell from "./MobileShell";
import Landing from "./Landing";
import Privacy from "./Privacy";
import NotFound from "./NotFound";
import Notice from "./Notice";
import DistrictReport from "./DistrictReport";
import FundingCase from "./FundingCase";
import CornerCard from "./CornerCard";
import useIntersections from "./useIntersections";
import useMediaQuery from "./useMediaQuery";
import usePageMeta from "./usePageMeta";
import useTraffic from "./useTraffic";
import { useOptionalJson } from "./useSiteData";
import { readSiteFromUrl, writeSiteToUrl, readDistrictFromUrl, writeDistrictToUrl } from "./useDeepLink";
import { AdvancedProvider, useAdvanced } from "./useAdvanced";
import { MetaProvider, useMetaFetch, useCatch } from "./useMeta";
import { DEFAULT_THRESHOLD, CANDIDATE_COUNT } from "./constants";
import { CITY } from "./city";

const DEFAULT_FILTERS = { threshold: DEFAULT_THRESHOLD, districts: [], pattern: null };
const PHONE = "(max-width: 767px)";

const DESCRIPTIONS = {
  landing: `Every ${CITY.name} intersection with no serious crash on record, ranked by how likely one is next.`,
  map: `The map of ${CITY.name} intersections ranked by serious-crash risk for 2025 to 2027, with the crash record, traffic, and what to do differently at each one.`,
  privacy: "What this site collects (nothing of its own), what Google Maps and the host collect, and the terms the ranking is offered under.",
  district: `A printable report of the listed corners in one ${CITY.name} council district: the top ten, the kinds of crashes, and which are rising.`,
  funding: `The case for fixing ${CITY.name} intersections before the crash: what a crash costs, what a fix costs, where the money is, and what to ask for.`,
  corner: `One ${CITY.name} intersection on a page: its crash record, how busy it is, what to do differently there, and what fixing it might involve.`,
  notfound: "That page does not exist.",
};

/**
 * Five views, no router. `/` is the landing page, `/map` the application,
 * `/privacy` the privacy and terms page, `/district/N` a printable district
 * report, `/corner/N` one corner as a page; anything else is a 404. A deep link (`/?site=43`) goes straight to
 * the map, because someone sent a link to one corner should land on it.
 */
function viewFromLocation() {
  if (typeof window === "undefined") return { view: "landing", district: null };
  const { pathname, search } = window.location;
  const path = pathname.replace(/\/+$/, "") || "/";
  if (path === "/map") return { view: "map", district: null };
  if (path === "/") {
    const q = new URLSearchParams(search);
    return { view: q.has("site") || q.has("district") ? "map" : "landing", district: null };
  }
  if (path === "/privacy") return { view: "privacy", district: null };
  if (path === "/funding") return { view: "funding", district: null };
  const m = /^\/district\/([1-9])$/.exec(path);
  if (m) return { view: "district", district: Number(m[1]) };
  const c = /^\/corner\/([1-9]\d{0,4})$/.exec(path);
  if (c) return { view: "corner", district: null, corner: Number(c[1]) };
  return { view: "notfound", district: null };
}

export default function App() {
  // meta.json is small and independent of the intersections file, so it is
  // fetched once here and read anywhere without prop-threading.
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
  const traffic = useTraffic();
  const recent = useOptionalJson("/data/recent.json");
  const control = useOptionalJson("/data/control.json");
  const { dismissWelcome } = useAdvanced();
  const [selectedIntersection, setSelectedIntersection] = useState(null);
  const [filters, setFilters] = useState(() => {
    const d = readDistrictFromUrl();
    return d ? { ...DEFAULT_FILTERS, districts: [d] } : DEFAULT_FILTERS;
  });
  const [{ view, district, corner }, setLocation] = useState(viewFromLocation);
  const [routeOverlay, setRouteOverlay] = useState(null);
  const isPhone = useMediaQuery(PHONE);

  // Deep link in: read once at mount into a ref so the write effect below
  // cannot strip the parameter before the data has loaded and consumed it.
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

  // A single selected district is part of the share link too.
  useEffect(() => {
    if (view !== "map") return;
    writeDistrictToUrl(filters.districts.length === 1 ? filters.districts[0] : null);
  }, [filters.districts, view]);

  // Browser back and forward between views.
  useEffect(() => {
    const onPop = () => setLocation(viewFromLocation());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  // Every in-app navigation goes through here so the URL and the view agree.
  // `path` may carry its own query (`/map?site=12`).
  const navigate = useCallback((path, { site = null } = {}) => {
    const url = new URL(path, window.location.origin);
    if (site) url.searchParams.set("site", String(site));
    window.history.pushState(null, "", url);
    window.scrollTo(0, 0);
    const next = viewFromLocation();
    setLocation(next);
    // A link to one corner from a report opens that corner.
    const wanted = Number(url.searchParams.get("site"));
    if (next.view === "map" && wanted && intersections) {
      const feature = intersections.features.find((f) => f.properties.rank === wanted);
      if (feature) setSelectedIntersection(feature);
    }
  }, [intersections]);

  // Entering the map from the landing page. Someone who has read the hero has
  // had the welcome, so it is marked seen rather than shown again.
  const enterMap = useCallback(
    (feature = null) => {
      navigate("/map", { site: feature?.properties.rank ?? null });
      if (feature) setSelectedIntersection(feature);
      dismissWelcome();
    },
    [navigate, dismissWelcome]
  );

  const goHome = useCallback(() => {
    setSelectedIntersection(null);
    navigate("/");
  }, [navigate]);

  // From a district report: the map, filtered to that district.
  const openMapForDistrict = useCallback(
    (d) => {
      setFilters((f) => ({ ...f, districts: [d] }));
      dismissWelcome();
      navigate("/map");
    },
    [navigate, dismissWelcome]
  );

  const sel = selectedIntersection?.properties;
  const { candidates } = useCatch(DEFAULT_THRESHOLD);
  usePageMeta({
    title:
      view === "map"
        ? sel
          ? `#${sel.rank} ${sel.intersection_name}`
          : "Map"
        : view === "privacy"
          ? "Privacy and terms"
          : view === "district"
            ? `District ${district} report`
            : view === "funding"
              ? "The funding case"
            : view === "corner"
              ? `Corner ${corner}`
            : view === "notfound"
              ? "Page not found"
              : null,
    description:
      view === "map" && sel
        ? `${sel.intersection_name}, ranked #${sel.rank} of ${(candidates ?? CANDIDATE_COUNT).toLocaleString()} ${CITY.name} intersections for serious-crash risk in 2025 to 2027, with its crash record and what to do differently there.`
        : DESCRIPTIONS[view],
  });

  if (view === "privacy") return <Privacy onNavigate={navigate} />;
  if (view === "notfound") return <NotFound onNavigate={navigate} />;
  if (view === "funding") return <FundingCase onNavigate={navigate} />;
  if (view === "corner") {
    return (
      <CornerCard
        rank={corner}
        intersections={intersections}
        traffic={traffic}
        recent={recent}
        control={control}
        onNavigate={navigate}
      />
    );
  }
  if (view === "district") {
    return (
      <DistrictReport
        district={district}
        intersections={intersections}
        traffic={traffic}
        recent={recent}
        control={control}
        onNavigate={navigate}
        onOpenMap={openMapForDistrict}
      />
    );
  }

  // The landing paints at once; only the map view waits for the data.
  if (view === "landing") {
    return (
      <Landing
        intersections={intersections}
        error={error}
        onEnter={enterMap}
        onNavigate={navigate}
        notice={<Notice placement="inline" onNavigate={navigate} />}
      />
    );
  }

  if (loading) return <LoadingShell isPhone={isPhone} />;

  if (error) {
    return (
      <div className="flex h-dvh items-center justify-center bg-paper p-8">
        <div className="max-w-sm bg-paper-sunk px-6 py-5">
          <p className="label mb-2 text-risk-1">The data did not load</p>
          <p className="font-serif text-[15px] leading-relaxed text-ink-2">{error}</p>
          <p className="mt-4 text-[13px]">
            <a href="/" onClick={(e) => { e.preventDefault(); goHome(); }} className="border-b border-ink/25 text-ink hover:border-ink">
              Back to the front page
            </a>
          </p>
        </div>
      </div>
    );
  }

  // Phone gets its own shell: map, search, route, info, tap-sheet. Nothing else.
  if (isPhone) {
    return (
      <>
        <WelcomeModal />
        <MobileShell
          intersections={intersections}
          filters={DEFAULT_FILTERS}
          selected={selectedIntersection}
          onSelect={setSelectedIntersection}
          traffic={traffic}
          recent={recent}
          control={control}
          routeOverlay={routeOverlay}
          onRoute={setRouteOverlay}
        />
        <Notice placement="fixed" onNavigate={navigate} />
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
        onNavigate={navigate}
      />

      <a
        href="#map-area"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-[90] focus:bg-ink focus:px-3 focus:py-2 focus:text-[13px] focus:text-paper"
      >
        Skip to the map and list
      </a>

      <main className="relative flex flex-1 overflow-hidden">
        <aside className="print-hide w-[20.5rem] shrink-0 border-r border-rule-strong">
          <Sidebar
            intersections={intersections}
            districts={districts}
            filters={filters}
            onFiltersChange={setFilters}
            traffic={traffic}
            recent={recent}
            onNavigate={navigate}
            onRoute={setRouteOverlay}
            onSelectIntersection={setSelectedIntersection}
          />
        </aside>

        <div id="map-area" tabIndex={-1} className="print-hide relative min-w-0 flex-1 focus:outline-none">
          <MapView
            intersections={intersections}
            filters={filters}
            selectedIntersection={selectedIntersection}
            onSelectIntersection={setSelectedIntersection}
            routeOverlay={routeOverlay}
          />
          <RankedTable
            intersections={intersections}
            filters={filters}
            onSelectIntersection={setSelectedIntersection}
            traffic={traffic}
            recent={recent}
            control={control}
          />
        </div>

        <IntersectionPanel
          intersection={selectedIntersection}
          onClose={() => setSelectedIntersection(null)}
          traffic={traffic}
          recent={recent}
          control={control}
          intersections={intersections}
          onSelectIntersection={setSelectedIntersection}
          onNavigate={navigate}
        />
      </main>

      <Notice placement="fixed" onNavigate={navigate} />
    </div>
  );
}

/**
 * The page's own shape while the 1.6 MB export loads: masthead, column and map
 * area in place, with grey bars where the text will be. A spinner in the middle
 * of a blank page tells the reader nothing about what is coming.
 */
function LoadingShell({ isPhone }) {
  const bar = (w, h = "h-3") => <div className={`${h} ${w} animate-pulse bg-paper-edge`} />;
  return (
    <div className="flex h-dvh flex-col bg-paper" aria-busy="true" aria-live="polite">
      <div className="flex h-12 shrink-0 items-center border-b border-rule-strong px-5">
        {bar("w-36", "h-4")}
      </div>
      <div className="flex flex-1 overflow-hidden">
        {!isPhone && (
          <div className="w-[20.5rem] shrink-0 space-y-4 border-r border-rule-strong p-6">
            {bar("w-24", "h-2")}
            {bar("w-full", "h-6")}
            {bar("w-5/6", "h-6")}
            <div className="pt-4">{bar("w-2/3")}</div>
            {bar("w-1/2")}
            <div className="pt-6">{bar("w-1/3", "h-2")}</div>
            {bar("w-full")}
            {bar("w-11/12")}
            {bar("w-4/5")}
          </div>
        )}
        <div className="relative flex-1 bg-paper-sunk">
          <p className="label absolute left-5 top-5">Loading intersections</p>
        </div>
      </div>
    </div>
  );
}
