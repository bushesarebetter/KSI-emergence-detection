import { useState, useMemo } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  flexRender,
} from "@tanstack/react-table";
import { formatPercentile, facilitiesToCsv } from "./lib/format";
import { useAdvanced } from "./useAdvanced";
import { humanizeSignal, techLabel } from "./lib/signals";
import { patternOf } from "./lib/advice";
import { passesFilters } from "./lib/filters";
import { inspectionStats, typeLabel } from "./lib/inspections";
import { searchPlaces } from "./lib/search";
import { tierFor, GRADE_COLORS } from "./lib/rankTier";

const PAGE_SIZE = 50;
const DRAWER_HEIGHT = "42vh";
const TOGGLE_HEIGHT = 40;

const makeColumns = (advanced) => [
  {
    id: "rank",
    header: "Rank",
    accessorFn: (f) => f.properties.rank,
    cell: ({ getValue }) => {
      const r = getValue();
      return <span className="tnum font-semibold" style={{ color: tierFor(r).hex }}>#{r}</span>;
    },
  },
  {
    id: "name",
    header: "Place",
    accessorFn: (f) => f.properties.name,
    cell: ({ row, getValue }) => (
      <span>
        <span className="block text-ink">{getValue()}</span>
        <span className="block text-[11px] text-ink-3">{row.original.properties.address}</span>
      </span>
    ),
  },
  { id: "type", header: advanced ? "Type" : "Kind", accessorFn: (f) => typeLabel(f.properties.facility_type) },
  {
    id: "district",
    header: advanced ? "D" : "District",
    accessorFn: (f) => f.properties.council_district ?? 0,
    cell: ({ getValue }) => <span className="tnum text-ink-3">{getValue() ? `D${getValue()}` : ""}</span>,
  },
  ...(advanced
    ? [{ id: "pct", header: "Pct.", accessorFn: (f) => f.properties.percentile, cell: ({ getValue }) => formatPercentile(getValue()) }]
    : []),
  {
    id: "last",
    header: advanced ? "Last score" : "Last inspection",
    accessorFn: (f) => inspectionStats(f.properties)?.lastScore ?? 0,
    cell: ({ row, getValue }) => {
      const s = inspectionStats(row.original.properties);
      if (!s) return <span className="text-ink-3">no record</span>;
      return (
        <span className="tnum">
          {s.lastScore != null ? getValue() : ""}
          {s.lastGrade && <span className="ml-1.5 font-semibold" style={{ color: GRADE_COLORS[s.lastGrade] ?? "#55503F" }}>{s.lastGrade}</span>}
          <span className="ml-1.5 text-[11px] text-ink-3">{s.last.date?.slice(0, 7)}</span>
        </span>
      );
    },
  },
  {
    id: "majors",
    header: advanced ? "Majors 36 mo" : "Major violations, 3 yr",
    accessorFn: (f) => inspectionStats(f.properties)?.majors36 ?? 0,
    cell: ({ getValue }) => <span className={`tnum ${getValue() > 0 ? "text-ink" : "text-ink-3"}`}>{getValue()}</span>,
  },
  {
    id: "trend",
    header: "Trend",
    accessorFn: (f) => inspectionStats(f.properties)?.trend ?? "",
    cell: ({ getValue }) => {
      const t = getValue();
      return <span className={t === "worsening" ? "font-semibold text-risk-1" : "text-ink-3"}>{t}</span>;
    },
  },
  {
    id: "signal",
    header: advanced ? "Top signal" : "What inspectors found",
    accessorFn: (f) => f.properties.shap_features?.[0]?.display_label ?? "",
    enableSorting: false,
    cell: ({ row, getValue }) => {
      const props = row.original.properties;
      const text = advanced ? techLabel(getValue()) : patternOf(props) ?? humanizeSignal(getValue());
      return <span className="text-[12px] text-ink-3">{text}</span>;
    },
  },
];

export default function RankedTable({ facilities, filters, onSelect }) {
  const { advanced } = useAdvanced();
  const columns = useMemo(() => makeColumns(advanced), [advanced]);
  const [open, setOpen] = useState(false);
  const [pageIndex, setPageIndex] = useState(0);
  const [globalFilter, setGlobalFilter] = useState("");

  const filteredFeatures = useMemo(() => {
    if (!facilities) return [];
    const feats = facilities.features.filter((f) => passesFilters(f.properties, filters));
    if (!globalFilter.trim()) return feats;
    return searchPlaces(feats, globalFilter, feats.length);
  }, [facilities, filters, globalFilter]);

  const table = useReactTable({
    data: filteredFeatures,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    state: { pagination: { pageIndex, pageSize: PAGE_SIZE }, globalFilter },
    onPaginationChange: (updater) => {
      const next = typeof updater === "function" ? updater({ pageIndex, pageSize: PAGE_SIZE }) : updater;
      setPageIndex(next.pageIndex);
    },
    manualPagination: false,
  });

  function downloadCsv() {
    if (!facilities) return;
    const all = [...facilities.features].sort((a, b) => a.properties.rank - b.properties.rank);
    const blob = new Blob([facilitiesToCsv(all)], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "food-safety-risk.csv";
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
          <div className="relative max-w-xs flex-1">
            <input
              type="text"
              placeholder="Filter this list by name or street"
              value={globalFilter}
              onChange={(e) => { setGlobalFilter(e.target.value); setPageIndex(0); }}
              aria-label="Filter this list by name or street"
              className="w-full border border-rule-strong bg-paper-sunk px-3 py-1.5 text-[13px] text-ink placeholder-ink-3 focus:border-ink focus:bg-paper focus:outline-none"
            />
          </div>
          <span className="tnum ml-auto text-[11.5px] text-ink-3">{total} {total === 1 ? "place" : "places"}</span>
          <button onClick={downloadCsv} className="border border-ink bg-ink px-3 py-1.5 text-[12px] font-semibold text-paper hover:border-ink-2 hover:bg-ink-2">
            Download CSV
          </button>
        </div>

        <div className="flex-1 overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 border-b border-rule-strong bg-paper">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      className={`label select-none whitespace-nowrap px-5 py-2.5 text-left ${header.column.getCanSort() ? "cursor-pointer hover:text-ink" : ""}`}
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
                  onClick={() => { onSelect(row.original); setOpen(false); }}
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
              No places match these filters. Widen the shortlist or pick a different kind of place.
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center justify-between border-t border-rule px-5 py-2 text-[11.5px] text-ink-3">
          <span>{total === 0 ? "No results" : `${start} to ${end} of ${total}`}</span>
          <div className="flex items-center gap-2">
            <span>{pageCount === 0 ? "0" : pageIndex + 1} / {pageCount}</span>
            <button onClick={() => setPageIndex((p) => Math.max(0, p - 1))} disabled={pageIndex === 0} className="border border-rule-strong px-2.5 py-1 hover:bg-paper-edge hover:text-ink disabled:cursor-not-allowed disabled:opacity-30">
              Previous
            </button>
            <button onClick={() => setPageIndex((p) => Math.min(pageCount - 1, p + 1))} disabled={pageIndex >= pageCount - 1} className="border border-rule-strong px-2.5 py-1 hover:bg-paper-edge hover:text-ink disabled:cursor-not-allowed disabled:opacity-30">
              Next
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
