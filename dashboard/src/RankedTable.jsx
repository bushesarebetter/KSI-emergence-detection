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
import { humanizeSignal, inclusionReason, techLabel } from "./lib/signals";
import { patternOf } from "./lib/advice";
import { passesFilters } from "./lib/filters";
import { crashRate, fmtPerYear, roundVehicles } from "./lib/rates";
import { trafficFor } from "./useTraffic";

const PAGE_SIZE = 50;
const DRAWER_HEIGHT = "42vh";
const TOGGLE_HEIGHT = 40;

function rankColor(rank) {
  if (rank <= 50) return "#7F1D1D";
  if (rank <= 100) return "#C2410C";
  if (rank <= 200) return "#D97706";
  return "#B8963F"; // pale amber darkened for text legibility on paper
}

const makeColumns = (advanced, traffic) => [
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
    cell: ({ getValue }) => <span className="tnum text-ink-3">D{getValue()}</span>,
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
    id: "rate",
    header: advanced ? "Crashes/yr" : "Crashes a year",
    accessorFn: (f) => crashRate(f.properties.crash_history)?.perYear ?? 0,
    cell: ({ getValue }) => <span className="tnum">{fmtPerYear(getValue())}</span>,
  },
  {
    id: "trend",
    header: "Trend",
    accessorFn: (f) => crashRate(f.properties.crash_history)?.trend ?? "",
    cell: ({ getValue }) => {
      const t = getValue();
      return <span className={t === "rising" ? "font-semibold text-risk-1" : "text-ink-3"}>{t}</span>;
    },
  },
  {
    id: "adt",
    header: advanced ? "ADT" : "Vehicles a day",
    // Unknown sorts to the bottom in either direction by reading as zero.
    accessorFn: (f) => trafficFor(traffic, f)?.entering ?? 0,
    cell: ({ row, getValue }) => {
      const v = getValue();
      if (!v) return <span className="text-ink-3">no count</span>;
      const t = trafficFor(traffic, row.original);
      return (
        <span className="tnum">
          {roundVehicles(v).toLocaleString()}
          {t && !t.complete && <span className="text-ink-3" title="Only one street is counted here">+</span>}
        </span>
      );
    },
  },
  {
    id: "signal",
    header: advanced ? "Top signal" : "What happens here",
    accessorFn: (f) => f.properties.shap_features?.[0]?.display_label ?? "",
    enableSorting: false,
    // Plain mode names the crash pattern ("Left turns", "After dark"), which is
    // what a reader can act on; technical mode shows the top SHAP feature. A
    // known or City-screen site has no model signals, so it says why it is listed.
    cell: ({ row, getValue }) => {
      const props = row.original.properties;
      const reason = inclusionReason(props, advanced);
      const text = reason ?? (advanced ? techLabel(getValue()) : patternOf(props) ?? humanizeSignal(getValue()));
      return <span className="text-[12px] text-ink-3">{text}</span>;
    },
  },
];

export default function RankedTable({ intersections, filters, onSelectIntersection, traffic = null, recent = null, control = null }) {
  const { advanced } = useAdvanced();
  const columns = useMemo(() => makeColumns(advanced, traffic), [advanced, traffic]);
  const [open, setOpen] = useState(false);
  const [pageIndex, setPageIndex] = useState(0);
  const [globalFilter, setGlobalFilter] = useState("");

  const filteredFeatures = useMemo(() => {
    if (!intersections) return [];
    let feats = intersections.features.filter((f) => passesFilters(f.properties, filters));
    if (globalFilter) {
      const q = globalFilter.toLowerCase();
      feats = feats.filter((f) => f.properties.intersection_name.toLowerCase().includes(q));
    }
    // TanStack caches each row's accessor values on first read, so a column that
    // depends on traffic.json would keep "no count" from before the file landed.
    // Returning a fresh array when traffic changes gives the table new rows.
    return traffic ? [...feats] : feats;
  }, [intersections, filters, globalFilter, traffic]);

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
    const csv = intersectionsToCsv(all, { traffic, recent, control });
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
      <button
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-0 left-1/2 z-30 flex -translate-x-1/2 items-center gap-2 border border-b-0 border-rule-strong bg-paper px-5 text-[12px] font-medium text-ink-2 shadow-paper hover:text-ink md:left-[calc(50%+10.25rem)]"
        style={{ height: TOGGLE_HEIGHT }}
      >
        <svg width="13" height="10" viewBox="0 0 13 10" fill="none" aria-hidden="true">
          <rect x="0" y="0" width="13" height="2" fill="currentColor" />
          <rect x="0" y="4" width="13" height="2" fill="currentColor" />
          <rect x="0" y="8" width="13" height="2" fill="currentColor" />
        </svg>
        {advanced ? "Ranked table" : "Full list"}
        <span className="tnum bg-paper-edge px-1.5 py-0.5 text-[10.5px] text-ink-2">{total}</span>
        <span aria-hidden="true" className="ml-0.5 text-ink-3">{open ? "▾" : "▴"}</span>
      </button>

      <div
        className="fixed left-0 right-0 z-20 flex flex-col overflow-hidden border-t border-rule-strong bg-paper transition-all duration-300 ease-in-out md:left-[20.5rem]"
        style={{ bottom: TOGGLE_HEIGHT, height: open ? DRAWER_HEIGHT : 0 }}
      >
        <div className="flex shrink-0 items-center gap-3 border-b border-rule px-5 py-2.5">
          <div className="relative flex-1 max-w-xs">
            <input
              type="text"
              placeholder={advanced ? "Search intersections" : "Filter this list by name"}
              value={globalFilter}
              onChange={handleSearch}
              aria-label="Filter this list by name"
              className="w-full border border-rule-strong bg-paper-sunk px-3 py-1.5 text-[13px] text-ink placeholder-ink-3 focus:border-ink focus:bg-paper focus:outline-none"
            />
          </div>
          <span className="tnum ml-auto text-[11.5px] text-ink-3">
            {total} site{total !== 1 ? "s" : ""}
          </span>
          <button
            onClick={downloadCsv}
            className="border border-ink bg-ink px-3 py-1.5 text-[12px] font-semibold text-paper hover:border-ink-2 hover:bg-ink-2"
          >
            Download CSV
          </button>
        </div>

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
                  className="cursor-pointer border-b border-rule hover:bg-paper-sunk"
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
          {total === 0 && (
            <p className="px-5 py-6 text-[13px] text-ink-3">
              No corners match these filters. Widen the shortlist or pick a different kind of crash.
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center justify-between border-t border-rule px-5 py-2 text-[11.5px] text-ink-3">
          <span>{total === 0 ? "No results" : `${start} to ${end} of ${total}`}</span>
          <div className="flex items-center gap-2">
            <span>
              {pageCount === 0 ? "0" : pageIndex + 1} / {pageCount}
            </span>
            <button
              onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
              disabled={pageIndex === 0}
              className="border border-rule-strong px-2.5 py-1 hover:bg-paper-edge hover:text-ink disabled:cursor-not-allowed disabled:opacity-30"
            >
              Previous
            </button>
            <button
              onClick={() => setPageIndex((p) => Math.min(pageCount - 1, p + 1))}
              disabled={pageIndex >= pageCount - 1}
              className="border border-rule-strong px-2.5 py-1 hover:bg-paper-edge hover:text-ink disabled:cursor-not-allowed disabled:opacity-30"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
