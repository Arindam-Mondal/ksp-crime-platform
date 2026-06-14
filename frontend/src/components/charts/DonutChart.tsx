import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { tooltipStyle, tooltipItemStyle, tooltipLabelStyle } from "./theme";

export interface DonutDatum {
  name: string;
  value: number;
}

export default function DonutChart({
  data,
  colors,
  centerLabel,
  centerValue,
  height = 220,
}: {
  data: DonutDatum[];
  colors: (name: string, i: number) => string;
  centerLabel?: string;
  centerValue?: string;
  height?: number;
}) {
  const total = data.reduce((s, d) => s + d.value, 0) || 1;

  return (
    <div className="flex items-center gap-5">
      <div className="relative shrink-0" style={{ width: height, height }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius="62%"
              outerRadius="92%"
              paddingAngle={2}
              stroke="none"
            >
              {data.map((d, i) => (
                <Cell key={d.name} fill={colors(d.name, i)} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={tooltipLabelStyle}
              itemStyle={tooltipItemStyle}
              formatter={(v: number, n: string) => [`${v.toLocaleString()} (${Math.round((v / total) * 100)}%)`, n]}
            />
          </PieChart>
        </ResponsiveContainer>
        {(centerValue || centerLabel) && (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            {centerValue && <span className="tabular text-2xl font-semibold text-white">{centerValue}</span>}
            {centerLabel && <span className="text-[11px] uppercase tracking-wider text-muted">{centerLabel}</span>}
          </div>
        )}
      </div>
      <ul className="min-w-0 flex-1 space-y-1.5">
        {data.map((d, i) => (
          <li key={d.name} className="flex items-center gap-2.5 text-sm">
            <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: colors(d.name, i) }} />
            <span className="min-w-0 flex-1 truncate text-white/80">{d.name}</span>
            <span className="tabular shrink-0 text-white/60">
              {Math.round((d.value / total) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
