import { useState, useMemo } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  flexRender,
} from "@tanstack/react-table";
import { formatScore, intersectionsToCsv } from "./lib/format";

const PAGE_SIZE = 50;
const DRAWER_HEIGHT = "42vh";
const TOGGLE_HEIGHT = 40;

function rankColor(rank) {
  if (rank <= 50) return "#ef4444";
  if (rank <= 100) return "#f97316";
  if (rank <= 200) return "#fbbf24";
  return "#fde68a";
}

const COLUMNS = [
  {
    id: "rank",
    header: "Rank",
    accessorFn: (f) => f.properties.rank,
    cell: ({ getValue }) => {
      const r = getValue();
      return (
        <span className="font-semibold tabular-nums" style={{ color: rankColor(r) }}>
          #{r}
        </span>
      );
    },
  },
  { id: "name", header: "Intersection", accessorFn: (f) => f.properties.intersection_name },
  {
    id: "district",
    header: "D",
    accessorFn: (f) => f.properties.council_district,
    cell: ({ getValue }) => (
      <span className="text-slate-500">D{getValue()}</span>
    ),
  },
  {
    id: "pct",
    header: "Pct.",
    accessorFn: (f) => f.properties.percentile,
    cell: ({ getValue }) => `${formatScore(getValue())}th`,
  },
  { id: "crashes", header: "Crashes", accessorFn: (f) => f.properties.crashes_training },
  {
    id: "signal",
    header: "Top signal",
    accessorFn: (f) => f.properties.shap_features?.[0]?.display_label ?? "—",
    enableSorting: false,
    cell: ({ getValue }) => (
      <span className="text-slate-500 text-xs">{getValue()}</span>
    ),
  },
];

export default function RankedTable({ intersections, filters, onSelectIntersection }) {
  const [open, setOpen] = useState(false);
  const [pageIndex, setPageIndex] = useState(0);
  const [globalFilter, setGlobalFilter] = useState("");

  const filteredFeatures = useMemo(() => {
    if (!intersections) return [];
    let feats = intersections.features.filter((f) => f.properties.rank <= filters.threshold);
    if (filters.districts.length > 0) {
      const dset = new Set(filters.districts);
      feats = feats.filter((f) => dset.has(f.properties.council_district));
    }
    if (globalFilter) {
      const q = globalFilter.toLowerCase();
      feats = feats.filter((f) =>
        f.properties.intersection_name.toLowerCase().includes(q)
      );
    }
    return feats;
  }, [intersections, filters, globalFilter]);

  const table = useReactTable({
    data: filteredFeatures,
    columns: COLUMNS,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    state: {
      pagination: { pageIndex, pageSize: PAGE_SIZE },
      globalFilter,
    },
    onPaginationChange: (updater) => {
      const next = typeof updater === "function"
        ? updater({ pageIndex, pageSize: PAGE_SIZE })
        : updater;
      setPageIndex(next.pageIndex);
    },
    manualPagination: false,
  });

  function handleSearch(e) {
    setGlobalFilter(e.target.value);
    setPageIndex(0);
  }

  function downloadCsv() {
    if (!intersections) return;
    const all = [...intersections.features].sort((a, b) => a.properties.rank - b.properties.rank);
    const csv = intersectionsToCsv(all);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "ksi-top1000.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const rows = table.getRowModel().rows;
  const total = filteredFeatures.length;
  const start = pageIndex * PAGE_SIZE + 1;
  const end = Math.min(start + PAGE_SIZE - 1, total);
  const pageCount = Math.ceil(total / PAGE_SIZE);

  return (
    <>
      {/* Toggle button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-0 left-1/2 -translate-x-1/2 z-30 bg-slate-900 border border-slate-700 border-b-0 shadow-xl rounded-t-lg px-5 text-xs font-semibold text-slate-400 hover:text-orange-400 hover:border-orange-500/40 transition-colors flex items-center gap-2"
        style={{ height: TOGGLE_HEIGHT }}
      >
        <svg width="13" height="10" viewBox="0 0 13 10" fill="none" aria-hidden="true">
          <rect x="0" y="0" width="13" height="2" rx="1" fill="currentColor" />
          <rect x="0" y="4" width="13" height="2" rx="1" fill="currentColor" />
          <rect x="0" y="8" width="13" height="2" rx="1" fill="currentColor" />
        </svg>
        Ranked Table
        <span className="bg-slate-800 text-slate-500 text-[10px] px-1.5 py-0.5 rounded-full tabular-nums">
          {total}
        </span>
        <span className="text-slate-600 ml-0.5">{open ? "▾" : "▴"}</span>
      </button>

      {/* Drawer */}
      <div
        className="fixed left-0 right-0 bg-slate-900 border-t border-slate-800 z-20 overflow-hidden transition-all duration-300 ease-in-out flex flex-col"
        style={{ bottom: TOGGLE_HEIGHT, height: open ? DRAWER_HEIGHT : 0 }}
      >
        {/* Toolbar */}
        <div className="flex items-center gap-3 px-4 py-2.5 border-b border-slate-800 shrink-0">
          <div className="relative flex-1 max-w-xs">
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-600 text-xs pointer-events-none">
              ⌕
            </span>
            <input
              type="text"
              placeholder="Search intersections…"
              value={globalFilter}
              onChange={handleSearch}
              className="w-full text-sm border border-slate-700 rounded-lg pl-7 pr-3 py-1.5 bg-slate-800 text-slate-300 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-orange-500/40 focus:border-orange-500/50 transition-colors"
            />
          </div>
          <span className="text-xs text-slate-600 ml-auto">
            {total} site{total !== 1 ? "s" : ""}
          </span>
          <button
            onClick={downloadCsv}
            className="flex items-center gap-1.5 text-xs bg-orange-500 hover:bg-orange-400 active:bg-orange-600 text-white rounded-lg px-3 py-1.5 font-semibold transition-colors"
          >
            <svg width="10" height="11" viewBox="0 0 10 11" fill="none" aria-hidden="true">
              <path d="M5 1v6M2 5.5L5 8.5l3-3M1 10h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            CSV
          </button>
        </div>

        {/* Table */}
        <div className="overflow-auto flex-1">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-slate-900 border-b border-slate-800">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      className={`px-4 py-2.5 text-left text-[10px] font-semibold text-slate-500 uppercase tracking-wider select-none whitespace-nowrap ${
                        header.column.getCanSort() ? "cursor-pointer hover:text-slate-300" : ""
                      }`}
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.getIsSorted() === "asc" && " ↑"}
                      {header.column.getIsSorted() === "desc" && " ↓"}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr
                  key={row.id}
                  className={`cursor-pointer transition-colors hover:bg-slate-800 ${
                    i % 2 === 1 ? "bg-slate-900/50" : "bg-slate-900"
                  }`}
                  onClick={() => {
                    onSelectIntersection(row.original);
                    setOpen(false);
                  }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-2 text-slate-300 whitespace-nowrap">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex justify-between items-center px-4 py-2 border-t border-slate-800 text-xs text-slate-600 shrink-0">
          <span>
            {total === 0 ? "No results" : `${start}–${end} of ${total}`}
          </span>
          <div className="flex items-center gap-2">
            <span>
              {pageCount === 0 ? "0" : pageIndex + 1} / {pageCount}
            </span>
            <button
              onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
              disabled={pageIndex === 0}
              className="border border-slate-700 rounded-md px-2.5 py-1 disabled:opacity-30 disabled:cursor-not-allowed hover:bg-slate-800 hover:border-slate-600 hover:text-slate-300 transition-colors"
            >
              ‹
            </button>
            <button
              onClick={() => setPageIndex((p) => Math.min(pageCount - 1, p + 1))}
              disabled={pageIndex >= pageCount - 1}
              className="border border-slate-700 rounded-md px-2.5 py-1 disabled:opacity-30 disabled:cursor-not-allowed hover:bg-slate-800 hover:border-slate-600 hover:text-slate-300 transition-colors"
            >
              ›
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
