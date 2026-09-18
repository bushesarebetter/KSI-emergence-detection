import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from "recharts";
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

// Severity reads as a value ramp on the same ink/risk axis the rest of the
// interface uses: the worse the outcome, the darker the bar.
const SERIES = [
  { key: "pdo", color: "#C9C1B0", plain: "Damage only", technical: "PDO" },
  { key: "injury", color: "#D97706", plain: "Injury", technical: "Injury" },
  { key: "ksi", color: "#7F1D1D", plain: "Serious or fatal", technical: "KSI" },
];

const AXIS = { fontSize: 10, fill: "#8A8272", fontFamily: '"IBM Plex Mono", monospace' };

export default function CrashHistoryChart({ crash_history }) {
  const { advanced } = useAdvanced();

  return (
    <div>
      <ResponsiveContainer width="100%" height={140}>
        <BarChart data={crash_history} margin={{ top: 4, right: 2, left: -22, bottom: 0 }}>
          <XAxis dataKey="year" tick={AXIS} tickLine={false} axisLine={{ stroke: "#DCD5C7" }} />
          <YAxis
            allowDecimals={false}
            tick={AXIS}
            tickLine={false}
            axisLine={false}
            width={26}
          />
          <Tooltip {...PAPER_TOOLTIP} />
          {SERIES.map(({ key, color }) => (
            <Bar key={key} dataKey={key} stackId="a" fill={color} />
          ))}
        </BarChart>
      </ResponsiveContainer>

      <ul className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1">
        {SERIES.map(({ key, color, plain, technical }) => (
          <li key={key} className="flex items-center gap-1.5 text-[11px] text-ink-3">
            <span className="inline-block h-2 w-2" style={{ backgroundColor: color }} />
            {advanced ? technical : plain}
          </li>
        ))}
      </ul>
    </div>
  );
}
