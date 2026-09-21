import { useSample } from "./useMeta";

/**
 * Shown on every page while the export is the invented sample. It cannot be
 * dismissed: a reader who lands on a place page from a link must never take
 * a sample record for a real one.
 */
export default function SampleBanner({ fixed = false }) {
  const sample = useSample();
  if (!sample) return null;
  return (
    <div
      role="note"
      className={`print-hide border-b border-risk-2 bg-paper-edge px-4 py-2 text-[12px] leading-[1.5] text-ink ${fixed ? "shrink-0" : ""}`}
    >
      <div className="mx-auto max-w-[76rem] md:px-4">
        <span className="font-semibold text-risk-2">Sample data.</span> Every place on this site is
        invented so the site could be built before the model. No real business, address or
        inspection is shown.
      </div>
    </div>
  );
}
