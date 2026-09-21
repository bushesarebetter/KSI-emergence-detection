import { useState, useEffect, useRef, useCallback } from "react";
import Header from "./Header";
import Sidebar from "./Sidebar";
import MapView from "./MapView";
import RankedTable from "./RankedTable";
import PlacePanel from "./PlacePanel";
import PlaceCard from "./PlaceCard";
import WelcomeModal from "./WelcomeModal";
import MobileShell from "./MobileShell";
import Landing from "./Landing";
import Privacy from "./Privacy";
import NotFound from "./NotFound";
import Notice from "./Notice";
import SampleBanner from "./SampleBanner";
import useFacilities from "./useFacilities";
import useMediaQuery from "./useMediaQuery";
import usePageMeta from "./usePageMeta";
import { readPlaceFromUrl, writePlaceToUrl, readDistrictFromUrl, writeDistrictToUrl } from "./useDeepLink";
import { AdvancedProvider, useAdvanced } from "./useAdvanced";
import { MetaProvider, useMetaFetch, useCatch } from "./useMeta";
import { DEFAULT_THRESHOLD } from "./constants";
import { SITE } from "./site";

const DEFAULT_FILTERS = { threshold: DEFAULT_THRESHOLD, districts: [], types: [], pattern: null };
const PHONE = "(max-width: 767px)";

const DESCRIPTIONS = {
  landing: `${SITE.name} restaurants, markets and food trucks ranked by how likely the County's next inspection is to find a major violation.`,
  map: `The map of ${SITE.name} food facilities ranked by the risk of a major violation at the next routine inspection, with each place's scores, what inspectors found, and what to look for.`,
  privacy: "What this site collects (nothing of its own), what Google Maps and the host collect, and the terms the ranking is offered under.",
  place: `One ${SITE.name} food facility on a page: its inspection scores, what inspectors found, and what to look for yourself.`,
  notfound: "That page does not exist.",
};

/**
 * Four views, no router. `/` is the landing page, `/map` the application,
 * `/place/N` one place as a page, `/privacy` the terms; anything else is a
 * 404. A deep link (`/map?place=43`) opens that place.
 */
function viewFromLocation() {
  if (typeof window === "undefined") return { view: "landing", place: null };
  const { pathname, search } = window.location;
  const path = pathname.replace(/\/+$/, "") || "/";
  if (path === "/map") return { view: "map", place: null };
  if (path === "/") {
    const q = new URLSearchParams(search);
    return { view: q.has("place") || q.has("district") ? "map" : "landing", place: null };
  }
  if (path === "/privacy") return { view: "privacy", place: null };
  const c = /^\/place\/([1-9]\d{0,4})$/.exec(path);
  if (c) return { view: "place", place: Number(c[1]) };
  return { view: "notfound", place: null };
}

export default function App() {
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
  const { facilities, loading, error } = useFacilities();
  const { dismissWelcome } = useAdvanced();
  const [selected, setSelected] = useState(null);
  const [filters, setFilters] = useState(() => {
    const d = readDistrictFromUrl();
    return d ? { ...DEFAULT_FILTERS, districts: [d] } : DEFAULT_FILTERS;
  });
  const [{ view, place }, setLocation] = useState(viewFromLocation);
  const [pointOverlay, setPointOverlay] = useState(null);
  const isPhone = useMediaQuery(PHONE);

  // Deep link in, read once at mount.
  const initialPlace = useRef(readPlaceFromUrl());
  useEffect(() => {
    if (!facilities || initialPlace.current == null) return;
    const wanted = initialPlace.current;
    initialPlace.current = null;
    const feature = facilities.features.find((f) => f.properties.rank === wanted);
    if (feature) setSelected(feature);
  }, [facilities]);

  // Deep link out: the address bar is the share link.
  useEffect(() => {
    if (initialPlace.current != null || view !== "map") return;
    writePlaceToUrl(selected?.properties.rank ?? null);
  }, [selected, view]);

  useEffect(() => {
    if (view !== "map") return;
    writeDistrictToUrl(filters.districts.length === 1 ? filters.districts[0] : null);
  }, [filters.districts, view]);

  useEffect(() => {
    const onPop = () => setLocation(viewFromLocation());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((path, { place: wantedPlace = null } = {}) => {
    const url = new URL(path, window.location.origin);
    if (wantedPlace) url.searchParams.set("place", String(wantedPlace));
    window.history.pushState(null, "", url);
    window.scrollTo(0, 0);
    const next = viewFromLocation();
    setLocation(next);
    const wanted = Number(url.searchParams.get("place"));
    if (next.view === "map" && wanted && facilities) {
      const feature = facilities.features.find((f) => f.properties.rank === wanted);
      if (feature) setSelected(feature);
    }
  }, [facilities]);

  const enterMap = useCallback((feature = null) => {
    navigate("/map", { place: feature?.properties.rank ?? null });
    if (feature) setSelected(feature);
    dismissWelcome();
  }, [navigate, dismissWelcome]);

  const goHome = useCallback(() => {
    setSelected(null);
    navigate("/");
  }, [navigate]);

  const sel = selected?.properties;
  const { candidates } = useCatch(DEFAULT_THRESHOLD);
  usePageMeta({
    title:
      view === "map"
        ? sel ? `#${sel.rank} ${sel.name}` : "Map"
        : view === "privacy" ? "Privacy and terms"
        : view === "place" ? `Place ${place}`
        : view === "notfound" ? "Page not found"
        : null,
    description:
      view === "map" && sel
        ? `${sel.name}, ${sel.address}, ranked #${sel.rank} of ${(candidates || 0).toLocaleString()} ${SITE.name} food facilities for the risk of a major violation at the next inspection, with its scores and what inspectors found.`
        : DESCRIPTIONS[view],
  });

  if (view === "privacy") return <Privacy onNavigate={navigate} />;
  if (view === "notfound") return <NotFound onNavigate={navigate} />;
  if (view === "place") return <PlaceCard rank={place} facilities={facilities} onNavigate={navigate} />;

  if (view === "landing") {
    return (
      <Landing
        facilities={facilities}
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
            <a href="/" onClick={(e) => { e.preventDefault(); goHome(); }} className="border-b border-ink/25 text-ink hover:border-ink">Back to the front page</a>
          </p>
        </div>
      </div>
    );
  }

  if (isPhone) {
    return (
      <>
        <WelcomeModal />
        <MobileShell
          facilities={facilities}
          filters={DEFAULT_FILTERS}
          selected={selected}
          onSelect={setSelected}
          pointOverlay={pointOverlay}
          onPoint={setPointOverlay}
          onNavigate={navigate}
        />
        <Notice placement="fixed" onNavigate={navigate} />
      </>
    );
  }

  return (
    <div className="flex h-dvh flex-col bg-paper">
      <WelcomeModal />

      <Header facilities={facilities} threshold={filters.threshold} onSelect={setSelected} onHome={goHome} onNavigate={navigate} />
      <SampleBanner fixed />

      <a href="#map-area" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-[90] focus:bg-ink focus:px-3 focus:py-2 focus:text-[13px] focus:text-paper">
        Skip to the map and list
      </a>

      <main className="relative flex flex-1 overflow-hidden">
        <aside className="print-hide w-[20.5rem] shrink-0 border-r border-rule-strong">
          <Sidebar facilities={facilities} filters={filters} onFiltersChange={setFilters} onPoint={setPointOverlay} onSelect={setSelected} />
        </aside>

        <div id="map-area" tabIndex={-1} className="print-hide relative min-w-0 flex-1 focus:outline-none">
          <MapView facilities={facilities} filters={filters} selected={selected} onSelect={setSelected} pointOverlay={pointOverlay} />
          <RankedTable facilities={facilities} filters={filters} onSelect={setSelected} />
        </div>

        <PlacePanel feature={selected} onClose={() => setSelected(null)} facilities={facilities} onSelect={setSelected} onNavigate={navigate} />
      </main>

      <Notice placement="fixed" onNavigate={navigate} />
    </div>
  );
}

function LoadingShell({ isPhone }) {
  const bar = (w, h = "h-3") => <div className={`${h} ${w} animate-pulse bg-paper-edge`} />;
  return (
    <div className="flex h-dvh flex-col bg-paper" aria-busy="true" aria-live="polite">
      <div className="flex h-12 shrink-0 items-center border-b border-rule-strong px-5">{bar("w-36", "h-4")}</div>
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
          <p className="label absolute left-5 top-5">Loading places</p>
        </div>
      </div>
    </div>
  );
}
