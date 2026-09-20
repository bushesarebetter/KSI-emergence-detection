import { useState, useMemo, useRef, useEffect } from "react";
import { useAdvanced } from "./useAdvanced";
import { CITY } from "./city";

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
 *
 * `large` is the hero variant for the landing page: bigger on every viewport.
 * The default is compact on desktop and 44px/16px on phones -- anything under
 * 16px makes iOS zoom the whole page when the field is focused.
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

export default function SearchBox({ intersections, threshold, onSelect, large = false }) {
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

  const inputClass = large
    ? "h-[54px] w-full border border-ink/30 bg-paper pl-12 pr-4 text-[17px] text-ink placeholder:text-ink-3 focus:border-ink focus:outline-none"
    : "h-11 w-full border border-rule-strong bg-paper-sunk pl-9 pr-3 text-[16px] text-ink placeholder:text-ink-3 focus:border-ink focus:bg-paper focus:outline-none md:h-auto md:py-[7px] md:text-[13px]";
  const iconSize = large ? 18 : 14;

  return (
    <div ref={boxRef} className="relative w-full">
      <div className="relative">
        <svg
          className={`pointer-events-none absolute top-1/2 -translate-y-1/2 text-ink-3 ${large ? "left-4" : "left-3"}`}
          width={iconSize} height={iconSize} viewBox="0 0 14 14" fill="none" aria-hidden="true"
        >
          <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.5" />
          <path d="M9.5 9.5L13 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        <input
          type="search"
          name="intersection-search"
          id={large ? "intersection-search-hero" : "intersection-search"}
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder={large ? `Search a ${CITY.name} intersection` : copy.searchPlaceholder}
          aria-label={copy.searchPlaceholder}
          autoComplete="off"
          className={inputClass}
        />
      </div>

      {showDropdown && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 border border-rule-strong bg-paper shadow-paper">
          {results.length === 0 ? (
            <div className="px-3.5 py-3 text-[12px] text-ink-2">
              {copy.searchEmpty}
              <div className="mt-1 text-[11px] text-ink-3">{copy.searchHint}</div>
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
                  className={`flex min-h-[44px] w-full items-center justify-between gap-3 border-b border-rule px-3.5 py-2 text-left last:border-b-0 md:min-h-0 ${
                    large ? "md:min-h-[44px]" : ""
                  } ${i === cursor ? "bg-paper-edge" : "hover:bg-paper-sunk"}`}
                >
                  <span className={`min-w-0 flex-1 truncate text-ink ${large ? "text-[14px]" : "text-[12.5px]"}`}>
                    {p.intersection_name}
                  </span>
                  <span
                    title={onList ? "On the current shortlist" : "Outside the current shortlist"}
                    className={`tnum shrink-0 px-1.5 py-0.5 text-[10.5px] font-semibold ${
                      onList ? "bg-ink text-paper" : "bg-paper-edge text-ink-3"
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
