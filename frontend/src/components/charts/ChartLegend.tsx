/**
 * Legend rendered outside the chart frame.
 *
 * Recharts' built-in <Legend> lives inside the plot box, so at narrow widths it
 * wraps to three rows and eats the chart's height. Rendering it as ordinary
 * markup below the chart lets it wrap freely — and gives every chart in the app
 * one legend vocabulary (PRODUCT.md principle 5).
 */
export default function ChartLegend({
  items,
  className = "",
}: {
  items: { label: string; color: string }[];
  className?: string;
}) {
  if (items.length === 0) return null;

  return (
    <ul className={`mt-3 flex flex-wrap gap-x-4 gap-y-1.5 ${className}`}>
      {items.map((i) => (
        <li key={i.label} className="flex min-w-0 items-center gap-1.5 text-[11px] text-muted">
          <span className="h-2 w-2 shrink-0 rounded-sm" style={{ background: i.color }} />
          <span className="truncate" title={i.label}>
            {i.label}
          </span>
        </li>
      ))}
    </ul>
  );
}
