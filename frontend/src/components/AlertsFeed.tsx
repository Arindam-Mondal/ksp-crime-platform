import { AlertTriangle, TrendingUp } from "lucide-react";
import { SpikeAlert } from "../lib/api";
import { useT } from "../i18n";
import { useDataLabel } from "../i18n/data";
import Badge from "./Badge";

export default function AlertsFeed({ items, limit }: { items: SpikeAlert[]; limit?: number }) {
  const t = useT();
  const d = useDataLabel();
  const shown = limit ? items.slice(0, limit) : items;
  if (shown.length === 0) {
    return <div className="px-1 py-6 text-center text-sm text-muted">{t("alerts.none")}</div>;
  }
  return (
    <ul className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
      {shown.map((a) => {
        const critical = a.severity === "Critical";
        return (
          <li
            key={`${a.district}-${a.sub_head}`}
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
                {/* The sub-head IS the alert's subject — truncating it made
                    three different "Online Financial …" alerts identical on a
                    phone. Let it wrap and keep the ratio beside it. */}
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-sm font-semibold text-white/90">
                    {d("crimeSubHead", a.sub_head)}
                  </span>
                  <span className={`tabular inline-flex items-center gap-0.5 text-sm font-bold ${critical ? "text-danger" : "text-warning"}`}>
                    <TrendingUp size={13} /> {a.ratio}×
                  </span>
                </div>
                {/* One interpolated sentence rather than inline spans: the clause order
                    differs in Kannada, so the numbers can't be positional fragments.
                    tabular-nums (not the mono face) keeps the digits aligned without
                    forcing Kannada text through JetBrains Mono. */}
                <div className="mt-0.5 text-xs tabular-nums text-muted">
                  <span className="text-white/70">{d("district", a.district)}</span>{" "}
                  · {t("alerts.trendCompare", { recent: a.recent, baseline: a.baseline })}
                </div>
              </div>
              <span className="shrink-0">
                <Badge variant={critical ? "danger" : "warning"}>
                  {d("severity", a.severity)}
                </Badge>
              </span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function AlertsEmpty() {
  const t = useT();
  return (
    <div className="flex items-center gap-2 text-sm text-success">
      <AlertTriangle size={15} /> {t("alerts.allClear")}
    </div>
  );
}
