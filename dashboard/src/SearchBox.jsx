import { useState, useMemo, useRef, useEffect } from "react";
import { useAdvanced } from "./useAdvanced";

const MAX_RESULTS = 8;

/**
 * Find an intersection by name.
 *
 * This is the first question anyone asks -- "is my intersection on this list?" --
 * and until now the only way to answer it was to pan around a map of 26,000
 * candidates. Searching the full feature set rather than the filtered shortlist
 * is deliberate: a site ranked #900 should still be findable when the user is
 * looking at the top 200, because "not on the shortlist" is itself the answer
 * they came for.
 */
function scoreMatch(name, query) {
  const n = name.toLowerCase();
  const q = query.toLowerCase();
  const idx = n.indexOf(q);
  if (idx === -1) return -1;
  // Prefer matches at a word boundary, then earlier matches, then shorter names,
  // so "El Cajon" surfaces "El Cajon Boulevard & …" ahead of "… & Del Cajon".
  const atBoundary = idx === 0 || n[idx - 1] === " " || n[idx - 1] === "&";
  return (atBoundary ? 0 : 500) + idx + name.length * 0.01;
}

export default function SearchBox({ intersections, threshold, onSelect }) {
  const { copy } = useAdvanced();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const boxRef = useRef(null);

  const results = useMemo(() => {
    const q = query.trim();
    if (q.length < 2 || !intersections) return [];
    return intersections.features
      .map((f) => ({ f, score: scoreMatch(f.properties.intersection_name ?? "", q) }))
      .filter((r) => r.score >= 0)
      .sort((a, b) => a.score - b.score)
      .slice(0, MAX_RESULTS)
      .map((r) => r.f);
  }, [query, intersections]);

  useEffect(() => setCursor(0), [query]);

  // Close when clicking elsewhere on the page.
  useEffect(() => {
    function onDocClick(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function choose(feature) {
    onSelect(feature);
    setQuery(feature.properties.intersection_name ?? "");
    setOpen(false);
  }

  function onKeyDown(e) {
    if (!open || results.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((c) => (c + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) => (c - 1 + results.length) % results.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(results[cursor]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  const showDropdown = open && query.trim().length >= 2;

  return (
    <div ref={boxRef} className="relative w-full">
      <div className="relative">
        <svg
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
          width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true"
        >
          <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.5" />
          <path d="M9.5 9.5L13 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        <input
          type="search"
          name="intersection-search"
          id="intersection-search"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder={copy.searchPlaceholder}
          aria-label={copy.searchPlaceholder}
          autoComplete="off"
          className="w-full rounded-lg border border-slate-700 bg-slate-800/80 py-2 pl-9 pr-3 text-sm text-slate-200 placeholder:text-slate-500 focus:border-orange-500/60 focus:outline-none focus:ring-1 focus:ring-orange-500/30"
        />
      </div>

      {showDropdown && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1.5 overflow-hidden rounded-lg border border-slate-700 bg-slate-800 shadow-2xl">
          {results.length === 0 ? (
            <div className="px-3 py-3 text-xs text-slate-500">
              {copy.searchEmpty}
              <div className="mt-1 text-[11px] text-slate-600">{copy.searchHint}</div>
            </div>
          ) : (
            results.map((f, i) => {
              const p = f.properties;
              const onList = p.rank <= threshold;
              return (
                <button
                  key={p.rank}
                  onMouseEnter={() => setCursor(i)}
                  onClick={() => choose(f)}
                  className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left transition-colors ${
                    i === cursor ? "bg-slate-700/70" : "hover:bg-slate-700/40"
                  }`}
                >
                  <span className="min-w-0 flex-1 truncate text-xs text-slate-200">
                    {p.intersection_name}
                  </span>
                  <span
                    className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold tabular-nums ${
                      onList
                        ? "bg-orange-500/15 text-orange-400"
                        : "bg-slate-700 text-slate-400"
                    }`}
                  >
                    #{p.rank}
                  </span>
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
