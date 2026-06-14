import { useState } from "react";
import Header from "./Header";
import FilterBar from "./FilterBar";
import DistrictSummary from "./DistrictSummary";
import MapView from "./MapView";
import RankedTable from "./RankedTable";
import IntersectionPanel from "./IntersectionPanel";
import StatsRow from "./StatsRow";
import useIntersections from "./useIntersections";

const DEFAULT_FILTERS = { threshold: 200, districts: [], crashActiveOnly: false };

export default function App() {
  const { intersections, districts, loading, error } = useIntersections();
  const [selectedIntersection, setSelectedIntersection] = useState(null);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-950">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-slate-400 text-sm">Loading dashboard…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-950">
        <span className="text-red-400 text-sm">{error}</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-slate-950">
      <Header />
      <main className="flex flex-1 overflow-hidden">
        <aside className="w-72 flex flex-col border-r border-slate-800 bg-slate-900 overflow-y-auto shrink-0">
          <StatsRow intersections={intersections} filters={filters} />
          <FilterBar filters={filters} onFiltersChange={setFilters} intersections={intersections} />
          <DistrictSummary
            districts={districts}
            filters={filters}
            onFiltersChange={setFilters}
            intersections={intersections}
          />
        </aside>
        <div className="relative flex-1 overflow-hidden">
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
