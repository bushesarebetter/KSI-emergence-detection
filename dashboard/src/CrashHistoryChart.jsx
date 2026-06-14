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

const LEGEND = [
  { color: "#475569", label: "PDO" },
  { color: "#f97316", label: "Injury" },
  { color: "#ef4444", label: "KSI" },
];

export default function CrashHistoryChart({ crash_history }) {
  return (
    <div>
      <ResponsiveContainer width="100%" height={145}>
        <BarChart data={crash_history} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <XAxis
            dataKey="year"
            tick={{ fontSize: 10, fill: "#64748b" }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 10, fill: "#64748b" }}
            tickLine={false}
            axisLine={false}
            width={24}
          />
          <Tooltip {...DARK_TOOLTIP} />
          <Bar dataKey="pdo" stackId="a" fill="#475569" />
          <Bar dataKey="injury" stackId="a" fill="#f97316" />
          <Bar dataKey="ksi" stackId="a" fill="#ef4444" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
      <div className="flex justify-center gap-4 mt-1.5">
        {LEGEND.map(({ color, label }) => (
          <span key={label} className="flex items-center gap-1.5 text-xs text-slate-500">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: color }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
