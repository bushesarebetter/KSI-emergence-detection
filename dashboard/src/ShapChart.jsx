import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from "recharts";
import { humanizeSignal, techLabel } from "./lib/signals";
import { useAdvanced } from "./useAdvanced";

const PAPER_TOOLTIP = {
  contentStyle: {
    background: "#FBF9F5",
    border: "1px solid #B8AF9C",
    borderRadius: 0,
    color: "#17150F",
    fontSize: 12,
    fontFamily: '"Public Sans", Helvetica, Arial, sans-serif',
    boxShadow: "0 2px 3px rgba(23,21,15,0.08), 0 10px 28px -14px rgba(23,21,15,0.3)",
  },
  cursor: { fill: "rgba(23,21,15,0.05)" },
};

export default function ShapChart({ shap_features }) {
  const { advanced } = useAdvanced();
  const features = shap_features ?? [];

  // Plain mode is a numbered list of reasons, not a SHAP bar chart. Bar length
  // here encodes signed contribution to a Tweedie prediction, which is not a
  // quantity a non-specialist can read, and drawing it implies a precision the
  // plain wording deliberately avoids.
  if (!advanced) {
    return (
      <ol>
        {features.slice(0, 5).map((f, i) => (
          <li
            key={f.feature_name ?? i}
            className="flex gap-3.5 border-b border-rule py-2.5 last:border-b-0"
          >
            <span className="tnum mt-[2px] shrink-0 font-mono text-[10.5px] text-ink-3">
              {String(i + 1).padStart(2, "0")}
            </span>
            <span className="text-[13px] leading-[1.45] text-ink-2">
              {humanizeSignal(f.display_label)}
            </span>
          </li>
        ))}
      </ol>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={170}>
      <BarChart
        layout="vertical"
        data={features.map((f) => ({ ...f, display_label: techLabel(f.display_label) }))}
        margin={{ top: 0, right: 8, left: 8, bottom: 0 }}
      >
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="display_label"
          width={185}
          tick={{ fontSize: 10.5, fill: "#55503F", fontFamily: '"Public Sans", sans-serif' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => (v.length > 32 ? v.slice(0, 30) + "…" : v)}
        />
        <Tooltip {...PAPER_TOOLTIP} formatter={(v) => [v.toFixed(3), "SHAP"]} />
        <Bar dataKey="shap_value" fill="#7F1D1D" maxBarSize={9} />
      </BarChart>
    </ResponsiveContainer>
  );
}
