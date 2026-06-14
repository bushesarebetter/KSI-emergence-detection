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
