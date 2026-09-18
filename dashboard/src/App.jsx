import { useState } from "react";
import Header from "./Header";
import FilterBar from "./FilterBar";
import DistrictSummary from "./DistrictSummary";
import MapView from "./MapView";
import RankedTable from "./RankedTable";
import IntersectionPanel from "./IntersectionPanel";
import StatsRow from "./StatsRow";
import WelcomeModal from "./WelcomeModal";
import useIntersections from "./useIntersections";
import { AdvancedProvider } from "./useAdvanced";

const DEFAULT_FILTERS = { threshold: 200, districts: [], crashActiveOnly: false };

export default function App() {
  return (
    <AdvancedProvider>
      <Dashboard />
    </AdvancedProvider>
  );
}

function Dashboard() {
  const { intersections, districts, loading, error } = useIntersections();
  const [selectedIntersection, setSelectedIntersection] = useState(null);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  // On a phone the sidebar would cover the map, so it starts closed there and is
  // reachable from a toggle. On desktop it is always visible.
  const [sidebarOpen, setSidebarOpen] = useState(false);

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-950">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-orange-500 border-t-transparent" />
          <span className="text-sm text-slate-400">Loading intersections…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-950 p-8">
        <div className="max-w-sm text-center">
          <div className="mb-2 text-sm font-semibold text-red-400">Couldn’t load the data</div>
          <div className="text-xs leading-relaxed text-slate-500">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-950">
      <WelcomeModal />

      <Header
        intersections={intersections}
        threshold={filters.threshold}
        onSelectIntersection={setSelectedIntersection}
      />

      <main className="relative flex flex-1 overflow-hidden">
        <aside
          className={`absolute inset-y-0 left-0 z-30 flex w-72 shrink-0 flex-col overflow-y-auto border-r border-slate-800 bg-slate-900 transition-transform duration-200 md:relative md:translate-x-0 ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <StatsRow intersections={intersections} filters={filters} />
          <FilterBar filters={filters} onFiltersChange={setFilters} intersections={intersections} />
          <DistrictSummary
            districts={districts}
            filters={filters}
            onFiltersChange={setFilters}
            intersections={intersections}
          />
        </aside>

        {sidebarOpen && (
          <div
            className="absolute inset-0 z-20 bg-black/50 md:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        <div className="relative flex-1 overflow-hidden">
          <MapView
            intersections={intersections}
            filters={filters}
            selectedIntersection={selectedIntersection}
            onSelectIntersection={setSelectedIntersection}
          />

          <button
            onClick={() => setSidebarOpen((v) => !v)}
            className="absolute left-3 top-3 z-10 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-medium text-slate-300 shadow-lg md:hidden"
          >
            {sidebarOpen ? "Close" : "Filters"}
          </button>

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
