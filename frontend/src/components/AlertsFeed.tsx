import { AlertTriangle, TrendingUp } from "lucide-react";
import { SpikeAlert } from "../lib/api";
import Badge from "./Badge";

export default function AlertsFeed({ items, limit }: { items: SpikeAlert[]; limit?: number }) {
  const shown = limit ? items.slice(0, limit) : items;
  if (shown.length === 0) {
    return <div className="px-1 py-6 text-center text-sm text-muted">No active spike alerts.</div>;
  }
  return (
    <ul className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
      {shown.map((a) => {
        const critical = a.severity === "Critical";
        return (
          <li
            key={`${a.district}-${a.crime_type}`}
            className={`relative overflow-hidden rounded-xl border px-4 py-3 ${
              critical ? "border-danger/30 bg-danger/[0.07]" : "border-warning/25 bg-warning/[0.05]"
            }`}
          >
            <div className="flex items-start gap-3">
              {/* pulsing indicator */}
              <span className="relative mt-1 flex h-2.5 w-2.5 shrink-0">
                <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${critical ? "bg-danger" : "bg-warning"}`} />
                <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${critical ? "bg-danger" : "bg-warning"}`} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-semibold text-white/90">{a.crime_type}</span>
                  <span className={`tabular inline-flex items-center gap-0.5 text-sm font-bold ${critical ? "text-danger" : "text-warning"}`}>
                    <TrendingUp size={13} /> {a.ratio}×
                  </span>
                </div>
                <div className="mt-0.5 text-xs text-muted">
                  <span className="text-white/70">{a.district}</span> · {a.recent} in 30d vs{" "}
                  <span className="tabular">{a.baseline}</span>/mo baseline
                </div>
              </div>
              <Badge variant={critical ? "danger" : "warning"}>{a.severity}</Badge>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function AlertsEmpty() {
  return (
    <div className="flex items-center gap-2 text-sm text-success">
      <AlertTriangle size={15} /> No active spikes — all categories within historical norms.
    </div>
  );
}
