import { LucideIcon } from "lucide-react";

type Delta = { value: string; direction: "up" | "down"; tone?: "good" | "bad" | "neutral" };

export default function StatCard({
  label,
  value,
  icon: Icon,
  caption,
  delta,
  accent = "accent",
}: {
  label: string;
  value: string;
  icon: LucideIcon;
  caption?: string;
  delta?: Delta;
  accent?: "accent" | "success" | "warning" | "danger" | "info";
}) {
  const accentText = {
    accent: "text-accent-soft",
    success: "text-success",
    warning: "text-warning",
    danger: "text-danger",
    info: "text-info",
  }[accent];

  // Values are mostly short numbers, but a few are place names ("Bengaluru
  // City"). Step the size down for those rather than truncating a district out
  // of recognition — the card is 4-up and only ~205px wide inside at 1280.
  const valueSize =
    value.length > 16 ? "text-lg sm:text-xl" : value.length > 11 ? "text-xl sm:text-2xl" : "text-2xl sm:text-3xl";

  const deltaTone =
    delta?.tone === "bad"
      ? "text-danger bg-danger/10"
      : delta?.tone === "neutral"
      ? "text-muted bg-white/5"
      : "text-success bg-success/10";

  return (
    <div className="group relative overflow-hidden rounded-2xl border border-line bg-surface/80 p-5 shadow-card backdrop-blur-sm transition-all duration-300 hover:border-line-strong hover:shadow-card-hover animate-fade-in-up">
      {/* corner accent wash */}
      <div className="pointer-events-none absolute -right-10 -top-10 h-28 w-28 rounded-full bg-accent/10 blur-2xl transition-opacity duration-300 group-hover:opacity-80 opacity-50" />
      <div className="relative flex items-start justify-between gap-2">
        <span className="min-w-0 text-xs font-medium uppercase tracking-wider text-muted">{label}</span>
        <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-line bg-surface-2 ${accentText}`}>
          <Icon size={17} strokeWidth={2} />
        </span>
      </div>
      {/* flex-wrap: at 4-up with the sidebar expanded the card is ~186px wide
          inside, and a delta like "▲ 63.3% convicted" would otherwise squeeze
          the value down to a truncated "64.…" */}
      <div className="relative mt-3 flex flex-wrap items-end gap-x-2 gap-y-1.5">
        {/* min-w-0 + truncate: long values like a district name ("Bengaluru
            City") otherwise run past the card at 2-up on a phone. */}
        <span
          title={value}
          className={`tabular min-w-0 truncate font-semibold leading-none tracking-tight text-white ${valueSize}`}
        >
          {value}
        </span>
        {delta && (
          <span className={`tabular mb-0.5 shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${deltaTone}`}>
            {delta.direction === "up" ? "▲" : "▼"} {delta.value}
          </span>
        )}
      </div>
      {caption && <p className="relative mt-1.5 truncate text-xs text-muted">{caption}</p>}
    </div>
  );
}
