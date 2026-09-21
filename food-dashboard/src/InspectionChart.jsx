import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ReferenceLine } from "recharts";
import { useAdvanced } from "./useAdvanced";
import { fmtShort, fmtDate } from "./lib/dates";
import { GRADE_COLORS } from "./lib/rankTier";

const AXIS = { fontSize: 10, fill: "#8A8272", fontFamily: '"IBM Plex Mono", monospace' };

function PaperTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{ background: "#FBF9F5", border: "1px solid #B8AF9C", padding: "8px 10px", fontSize: 12, fontFamily: '"Public Sans", Helvetica, Arial, sans-serif', color: "#17150F" }}>
      <div style={{ fontWeight: 600 }}>{fmtDate(d.date)}</div>
      <div style={{ color: "#55503F" }}>
        {d.type}{d.score != null ? `, score ${d.score}${d.grade ? ` (${d.grade})` : ""}` : ""}
        {d.major ? `, ${d.major} major` : ""}{d.minor ? `, ${d.minor} minor` : ""}{d.closed ? ", closed" : ""}
      </div>
    </div>
  );
}

/**
 * Score by visit. Bars are coloured by grade on the same severity axis the
 * rest of the interface uses; reinspections are drawn lighter, and complaint
 * visits, which carry no score, are shown as a tick on the axis so the
 * reader sees that inspectors came.
 */
export default function InspectionChart({ inspections }) {
  const { advanced } = useAdvanced();
  const data = (inspections ?? []).map((i) => ({ ...i, plotted: i.score ?? 0 }));

  return (
    <div>
      <ResponsiveContainer width="100%" height={140}>
        <BarChart data={data} margin={{ top: 4, right: 2, left: -22, bottom: 0 }}>
          <XAxis dataKey="date" tickFormatter={fmtShort} tick={AXIS} tickLine={false} axisLine={{ stroke: "#DCD5C7" }} interval="preserveStartEnd" />
          <YAxis domain={[50, 100]} ticks={[50, 80, 90, 100]} tick={AXIS} tickLine={false} axisLine={false} width={26} />
          <ReferenceLine y={90} stroke="#DCD5C7" strokeDasharray="2 3" />
          <Tooltip content={<PaperTooltip />} cursor={{ fill: "rgba(23,21,15,0.05)" }} />
          <Bar dataKey="plotted" isAnimationActive={false}>
            {data.map((d, i) => (
              <Cell
                key={i}
                fill={d.score == null ? "#B8AF9C" : GRADE_COLORS[d.grade] ?? "#C9C1B0"}
                fillOpacity={d.type === "reinspection" ? 0.55 : 1}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <ul className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1">
        {[["A", "A, 90 or more"], ["B", "B, 80 to 89"], ["C", "C, under 80"]].map(([g, label]) => (
          <li key={g} className="flex items-center gap-1.5 text-[11px] text-ink-3">
            <span className="inline-block h-2 w-2" style={{ backgroundColor: GRADE_COLORS[g] }} />
            {advanced ? g : label}
          </li>
        ))}
        <li className="flex items-center gap-1.5 text-[11px] text-ink-3">
          <span className="inline-block h-2 w-2 opacity-50" style={{ backgroundColor: "#7F1D1D" }} />
          reinspection
        </li>
      </ul>
    </div>
  );
}
