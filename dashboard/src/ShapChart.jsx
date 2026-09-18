import { humanizeSignal } from "./lib/signals";
import { useAdvanced } from "./useAdvanced";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";

const DARK_TOOLTIP = {
  contentStyle: {
    background: "#1e293b",
    border: "1px solid #334155",
    borderRadius: 8,
    color: "#e2e8f0",
    fontSize: 12,
    boxShadow: "0 4px 16px rgba(0,0,0,0.5)",
  },
  cursor: { fill: "rgba(255,255,255,0.04)" },
};

export default function ShapChart({ shap_features }) {
  const { advanced } = useAdvanced();

  // Plain mode is a ranked list of reasons rather than a SHAP bar chart: the bar
  // lengths encode signed contribution to a Tweedie prediction, which is not a
  // quantity a non-specialist can read, and a chart implies a precision the plain
  // wording deliberately avoids.
  if (!advanced) {
    return (
      <ol className="space-y-2">
        {(shap_features ?? []).slice(0, 5).map((f, i) => (
          <li key={f.feature_name ?? i} className="flex gap-2.5">
            <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-slate-800 text-[10px] font-bold text-orange-400">
              {i + 1}
            </span>
            <span className="text-xs leading-relaxed text-slate-400">
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
        data={shap_features}
        margin={{ top: 0, right: 8, left: 8, bottom: 0 }}
      >
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="display_label"
          width={195}
          tick={{ fontSize: 11, fill: "#94a3b8" }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => (v.length > 32 ? v.slice(0, 30) + "…" : v)}
        />
        <Tooltip
          {...DARK_TOOLTIP}
          formatter={(v) => [v.toFixed(3), "SHAP"]}
        />
        <Bar dataKey="shap_value" fill="#f97316" radius={[0, 2, 2, 0]} maxBarSize={10} />
      </BarChart>
    </ResponsiveContainer>
  );
}
