import { useState, useId } from "react";
import { GLOSSARY } from "./lib/copy";
import { useAdvanced } from "./useAdvanced";

/**
 * A term with its definition one hover (or tap) away.
 *
 * This is the load-bearing half of progressive disclosure: plain wording on the
 * surface, the precise meaning available without leaving the page. Tap support
 * matters because hover does not exist on touch devices, where a tooltip that
 * only responds to hover is simply invisible.
 */
export default function Term({ id, children, className = "" }) {
  const entry = GLOSSARY[id];
  const { advanced } = useAdvanced();
  const [open, setOpen] = useState(false);
  const tooltipId = useId();

  if (!entry) return children ?? null;

  const label = children ?? (advanced ? entry.technical : entry.term);

  return (
    <span className="relative inline-block">
      <button
        type="button"
        aria-describedby={open ? tooltipId : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className={`cursor-help border-b border-dotted border-slate-500 hover:border-orange-400 hover:text-orange-300 transition-colors ${className}`}
      >
        {label}
      </button>

      {open && (
        <span
          id={tooltipId}
          role="tooltip"
          className="absolute left-0 top-full z-50 mt-1.5 block w-60 rounded-lg border border-slate-700 bg-slate-800 p-3 text-xs font-normal leading-relaxed text-slate-300 shadow-2xl"
        >
          <span className="mb-1 block font-semibold text-slate-100">
            {advanced ? entry.technical : entry.term}
          </span>
          {entry.definition}
          {!advanced && (
            <span className="mt-1.5 block text-[10px] text-slate-500">
              Technical term: {entry.technical}
            </span>
          )}
        </span>
      )}
    </span>
  );
}
