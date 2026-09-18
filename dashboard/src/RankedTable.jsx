import { useState, useMemo } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  flexRender,
} from "@tanstack/react-table";
import { formatScore, intersectionsToCsv } from "./lib/format";
import { useAdvanced } from "./useAdvanced";
import { humanizeSignal } from "./lib/signals";

const PAGE_SIZE = 50;
const DRAWER_HEIGHT = "42vh";
const TOGGLE_HEIGHT = 40;

function rankColor(rank) {
  if (rank <= 50) return "#7F1D1D";
  if (rank <= 100) return "#C2410C";
  if (rank <= 200) return "#D97706";
  return "#B8963F"; // pale amber darkened for text legibility on paper
}

const makeColumns = (advanced) => [
  {
    id: "rank",
    header: "Rank",
    accessorFn: (f) => f.properties.rank,
    cell: ({ getValue }) => {
      const r = getValue();
      return (
        <span className="tnum font-semibold" style={{ color: rankColor(r) }}>
          #{r}
        </span>
      );
    },
  },
  { id: "name", header: "Intersection", accessorFn: (f) => f.properties.intersection_name },
  {
    id: "district",
    header: advanced ? "D" : "District",
    accessorFn: (f) => f.properties.council_district,
    cell: ({ getValue }) => (
      <span className="tnum text-ink-3">D{getValue()}</span>
    ),
  },
  // Percentile is a precise but opaque way to say "near the top of a list of
  // 26,045", and it duplicates the rank column for anyone not reading closely.
  // Advanced users still want it.
  ...(advanced
    ? [{
        id: "pct",
        header: "Pct.",
        accessorFn: (f) => f.properties.percentile,
        cell: ({ getValue }) => `${formatScore(getValue())}th`,
      }]
    : []),
  {
    id: "crashes",
    header: advanced ? "Crashes" : "Crashes since 2016",
    accessorFn: (f) => f.properties.crashes_training,
  },
  {
    id: "signal",
    header: advanced ? "Top signal" : "Main reason",
    accessorFn: (f) => f.properties.shap_features?.[0]?.display_label ?? "—",
    enableSorting: false,
    cell: ({ getValue }) => (
      <span className="text-[12px] text-ink-3">
        {advanced ? getValue() : humanizeSignal(getValue())}
      </span>
    ),
  },
];

export default function RankedTable({ intersections, filters, onSelectIntersection }) {
  const { advanced, copy } = useAdvanced();
  const columns = useMemo(() => makeColumns(advanced), [advanced]);
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
    columns,
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
        className="fixed bottom-0 left-1/2 z-30 flex -translate-x-1/2 items-center gap-2 border border-b-0 border-rule-strong bg-paper px-5 text-[12px] font-medium text-ink-2 shadow-paper transition-colors hover:text-ink md:left-[calc(50%+10.25rem)]"
        style={{ height: TOGGLE_HEIGHT }}
      >
        <svg width="13" height="10" viewBox="0 0 13 10" fill="none" aria-hidden="true">
          <rect x="0" y="0" width="13" height="2" rx="1" fill="currentColor" />
          <rect x="0" y="4" width="13" height="2" rx="1" fill="currentColor" />
          <rect x="0" y="8" width="13" height="2" rx="1" fill="currentColor" />
        </svg>
        {advanced ? "Ranked Table" : "Full list"}
        <span className="tnum bg-paper-edge px-1.5 py-0.5 text-[10.5px] text-ink-2">{total}</span>
        <span aria-hidden="true" className="ml-0.5 text-ink-3">{open ? "▾" : "▴"}</span>
      </button>

      {/* Drawer */}
      <div
        className="fixed left-0 right-0 z-20 flex flex-col overflow-hidden border-t border-rule-strong bg-paper transition-all duration-300 ease-in-out md:left-[20.5rem]"
        style={{ bottom: TOGGLE_HEIGHT, height: open ? DRAWER_HEIGHT : 0 }}
      >
        {/* Toolbar */}
        <div className="flex shrink-0 items-center gap-3 border-b border-rule px-5 py-2.5">
          <div className="relative flex-1 max-w-xs">
            <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[12px] text-ink-3">
              ⌕
            </span>
            <input
              type="text"
              placeholder={advanced ? "Search intersections…" : "Filter this list…"}
              value={globalFilter}
              onChange={handleSearch}
              className="w-full border border-rule-strong bg-paper-sunk py-1.5 pl-7 pr-3 text-[13px] text-ink placeholder-ink-3 focus:border-ink focus:bg-paper focus:outline-none"
            />
          </div>
          <span className="tnum ml-auto text-[11.5px] text-ink-3">
            {total} site{total !== 1 ? "s" : ""}
          </span>
          <button
            onClick={downloadCsv}
            className="flex items-center gap-1.5 border border-ink bg-ink px-3 py-1.5 text-[12px] font-semibold text-paper transition-opacity hover:opacity-85"
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
            <thead className="sticky top-0 border-b border-rule-strong bg-paper">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      className={`label select-none whitespace-nowrap px-5 py-2.5 text-left ${
                        header.column.getCanSort() ? "cursor-pointer hover:text-ink" : ""
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
              {rows.map((row) => (
                <tr
                  key={row.id}
                  className="cursor-pointer border-b border-rule transition-colors hover:bg-paper-sunk"
                  onClick={() => {
                    onSelectIntersection(row.original);
                    setOpen(false);
                  }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="whitespace-nowrap px-5 py-2 text-[13px] text-ink-2">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex shrink-0 items-center justify-between border-t border-rule px-5 py-2 text-[11.5px] text-ink-3">
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
              className="border border-rule-strong px-2.5 py-1 transition-colors hover:bg-paper-edge hover:text-ink disabled:cursor-not-allowed disabled:opacity-30"
            >
              ‹
            </button>
            <button
              onClick={() => setPageIndex((p) => Math.min(pageCount - 1, p + 1))}
              disabled={pageIndex >= pageCount - 1}
              className="border border-rule-strong px-2.5 py-1 transition-colors hover:bg-paper-edge hover:text-ink disabled:cursor-not-allowed disabled:opacity-30"
            >
              ›
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
