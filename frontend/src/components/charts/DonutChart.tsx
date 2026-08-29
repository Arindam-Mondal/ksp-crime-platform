import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { tooltipStyle, tooltipItemStyle, tooltipLabelStyle } from "./theme";
import { useElementWidth } from "../../lib/useElementWidth";

export interface DonutDatum {
  /** Stable English key: drives the colour lookup and the React key. Never translate it. */
  name: string;
  value: number;
  /** Optional display text. Falls back to `name`, so English callers pass nothing. */
  label?: string;
}

/**
 * Below this container width there isn't room for a readable legend column
 * beside the ring (ring + gap + ~150px of label), so the legend moves under it.
 * The panel this sits in can be ~260px wide on a 1280px laptop, which is where
 * the side-by-side layout used to truncate every label away to nothing.
 */
const STACK_BELOW = 400;

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
  /** Preferred ring size. Scales down when the container can't afford it. */
  height?: number;
}) {
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  const [ref, width] = useElementWidth<HTMLDivElement>();
  // Recharts keys the slice on `name`, so the tooltip hands us the English key back —
  // map it to the display label on the way out.
  const labelOf = (name: string) => data.find((d) => d.name === name)?.label ?? name;

  // width === 0 is "not measured yet" — assume wide so first paint is the
  // richer layout rather than a flash of the stacked one.
  const stacked = width > 0 && width < STACK_BELOW;
  const ring = stacked
    ? Math.min(height, Math.max(150, width - 32))
    : width > 0
    ? Math.min(height, Math.max(130, width * 0.44))
    : height;

  return (
    <div
      ref={ref}
      className={stacked ? "flex flex-col items-center gap-4" : "flex items-center gap-5"}
    >
      <div className="relative shrink-0" style={{ width: ring, height: ring }}>
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
              formatter={(v: number, n: string) => [
                `${v.toLocaleString()} (${Math.round((v / total) * 100)}%)`,
                labelOf(n),
              ]}
            />
          </PieChart>
        </ResponsiveContainer>
        {(centerValue || centerLabel) && (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-4 text-center">
            {centerValue && (
              <span className="tabular max-w-full truncate text-xl font-semibold text-white sm:text-2xl">
                {centerValue}
              </span>
            )}
            {centerLabel && (
              <span className="max-w-full truncate text-[11px] uppercase tracking-wider text-muted">
                {centerLabel}
              </span>
            )}
          </div>
        )}
      </div>

      <ul
        className={
          stacked
            ? // 190px floor, not 140: a second column only appears when each one
              // can still hold a full label like "Under Investigation"
              "grid w-full gap-x-5 gap-y-1.5 [grid-template-columns:repeat(auto-fit,minmax(190px,1fr))]"
            : "min-w-0 flex-1 space-y-1.5"
        }
      >
        {data.map((d, i) => (
          <li key={d.name} className="flex items-center gap-2.5 text-sm">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ background: colors(d.name, i) }}
            />
            <span className="min-w-0 flex-1 truncate text-white/80" title={d.label ?? d.name}>
              {d.label ?? d.name}
            </span>
            <span className="tabular shrink-0 text-white/60">
              {Math.round((d.value / total) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
