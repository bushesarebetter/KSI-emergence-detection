import { useMemo } from "react";
import { useAdvanced } from "./useAdvanced";
import { chipsFor, typesFor } from "./lib/filters";
import { THRESHOLDS } from "./constants";

const chip = (on) =>
  `min-h-[32px] border px-2.5 py-1 text-[12px] leading-none ${
    on ? "border-ink bg-ink text-paper" : "border-rule-strong bg-transparent text-ink-2 hover:border-ink hover:text-ink"
  }`;

/**
 * Three choices, each a row of buttons: how many places to show, what kind
 * of place, and what inspectors found. Chips only appear for kinds and
 * findings some listed place actually has.
 */
export default function FilterBar({ filters, onFiltersChange, facilities }) {
  const { copy } = useAdvanced();
  const chips = useMemo(() => chipsFor(facilities, filters.threshold), [facilities, filters.threshold]);
  const types = useMemo(() => typesFor(facilities, filters.threshold), [facilities, filters.threshold]);

  const set = (patch) => onFiltersChange({ ...filters, ...patch });
  const toggleType = (key) => {
    const has = filters.types.includes(key);
    set({ types: has ? filters.types.filter((t) => t !== key) : [...filters.types, key] });
  };

  return (
    <div className="px-6 py-5">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <p className="label">{copy.filterTitle}</p>
        <p className="text-[11px] text-ink-3">{copy.filterUnit}</p>
      </div>
      <div role="group" aria-label={copy.filterTitle} className="flex flex-wrap gap-1.5">
        {THRESHOLDS.map((t) => (
          <button key={t} onClick={() => set({ threshold: t })} aria-pressed={filters.threshold === t} className={`tnum ${chip(filters.threshold === t)}`}>
            {t}
          </button>
        ))}
      </div>

      {types.length > 1 && (
        <>
          <div className="mb-3 mt-6 flex items-baseline justify-between gap-3">
            <p className="label">{copy.typeTitle}</p>
            <p className="text-[11px] text-ink-3">any you pick</p>
          </div>
          <div role="group" aria-label={copy.typeTitle} className="flex flex-wrap gap-1.5">
            {types.map((t) => (
              <button key={t.key} onClick={() => toggleType(t.key)} aria-pressed={filters.types.includes(t.key)} className={chip(filters.types.includes(t.key))}>
                {t.label}{" "}
                <span className="tnum ml-1 opacity-60">{t.count}</span>
              </button>
            ))}
          </div>
        </>
      )}

      {chips.length > 0 && (
        <>
          <div className="mb-3 mt-6 flex items-baseline justify-between gap-3">
            <p className="label">{copy.patternTitle}</p>
            <p className="text-[11px] text-ink-3">{copy.patternUnit}</p>
          </div>
          <div role="group" aria-label={copy.patternTitle} className="flex flex-wrap gap-1.5">
            <button onClick={() => set({ pattern: null })} aria-pressed={filters.pattern === null} className={chip(filters.pattern === null)}>
              Any
            </button>
            {chips.map((c) => (
              <button key={c.key} onClick={() => set({ pattern: filters.pattern === c.key ? null : c.key })} aria-pressed={filters.pattern === c.key} className={chip(filters.pattern === c.key)}>
                {c.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
