import { useState, useMemo, useRef, useEffect } from "react";
import { useAdvanced } from "./useAdvanced";
import { searchPlaces } from "./lib/search";
import { patternOf } from "./lib/advice";
import { typeLabel } from "./lib/inspections";
import { SITE } from "./site";

const MAX_RESULTS = 8;

/**
 * Find a place by name or street. Searches the whole export, not the
 * filtered shortlist: "is this place on the list?" is the first question
 * anyone asks, and "no" is an answer too.
 */
export default function SearchBox({ facilities, threshold, onSelect, large = false }) {
  const { copy } = useAdvanced();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const boxRef = useRef(null);
  const id = large ? "place-search-hero" : "place-search";
  const listId = `${id}-results`;

  const results = useMemo(() => {
    const q = query.trim();
    if (q.length < 2 || !facilities) return [];
    return searchPlaces(facilities.features, q, MAX_RESULTS);
  }, [query, facilities]);

  useEffect(() => setCursor(0), [query]);

  useEffect(() => {
    function onDocClick(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function choose(feature) {
    onSelect(feature);
    setQuery(feature.properties.name ?? "");
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
          name="place-search"
          id={id}
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder={large ? `Search a ${SITE.name} restaurant, market or truck` : copy.searchPlaceholder}
          aria-label={copy.searchPlaceholder}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={showDropdown && results.length > 0}
          aria-controls={listId}
          aria-activedescendant={showDropdown && results.length > 0 ? `${listId}-${cursor}` : undefined}
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
            <ul id={listId} role="listbox">
              {results.map((f, i) => {
                const p = f.properties;
                const onList = p.rank <= threshold;
                const pattern = patternOf(p);
                return (
                  <li
                    key={p.rank}
                    id={`${listId}-${i}`}
                    role="option"
                    aria-selected={i === cursor}
                    onMouseEnter={() => setCursor(i)}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => choose(f)}
                    className={`flex min-h-[44px] w-full cursor-pointer items-center justify-between gap-3 border-b border-rule px-3.5 py-2 text-left last:border-b-0 md:min-h-0 ${
                      large ? "md:min-h-[44px]" : ""
                    } ${i === cursor ? "bg-paper-edge" : "hover:bg-paper-sunk"}`}
                  >
                    <span className="min-w-0 flex-1">
                      <span className={`block truncate text-ink ${large ? "text-[14px]" : "text-[12.5px]"}`}>
                        {p.name}
                      </span>
                      <span className="block truncate text-[11px] text-ink-3">
                        {p.address}
                        {", "}
                        {typeLabel(p.facility_type)}
                        {pattern ? `, ${pattern.toLowerCase()}` : ""}
                      </span>
                    </span>
                    <span
                      title={onList ? "On the current shortlist" : "Outside the current shortlist"}
                      className={`tnum shrink-0 px-1.5 py-0.5 text-[10.5px] font-semibold ${
                        onList ? "bg-ink text-paper" : "bg-paper-edge text-ink-3"
                      }`}
                    >
                      #{p.rank}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
