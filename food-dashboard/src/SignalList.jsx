import { useAdvanced } from "./useAdvanced";
import { humanizeSignal, techLabel } from "./lib/signals";

/**
 * The model's top signals for one place. Plain mode rewrites each label as
 * a sentence; technical mode shows the label as the export wrote it, with
 * its SHAP value.
 */
export default function SignalList({ shap_features }) {
  const { advanced } = useAdvanced();
  const features = (shap_features ?? []).slice(0, 5);
  if (!features.length) return <p className="text-[13px] text-ink-3">No signals in the export for this place.</p>;

  return (
    <ol>
      {features.map((f, i) => (
        <li key={f.feature_name ?? i} className="flex gap-3.5 border-b border-rule py-2.5 last:border-b-0">
          <span className="tnum mt-[2px] shrink-0 font-mono text-[10.5px] text-ink-3">{String(i + 1).padStart(2, "0")}</span>
          <span className="min-w-0 flex-1 text-[13px] leading-[1.45] text-ink-2">
            {advanced ? techLabel(f.display_label) : humanizeSignal(f.display_label)}
          </span>
          {advanced && typeof f.shap_value === "number" && (
            <span className="tnum shrink-0 font-mono text-[11px] text-ink-3">{f.shap_value >= 0 ? "+" : ""}{f.shap_value.toFixed(2)}</span>
          )}
        </li>
      ))}
    </ol>
  );
}
