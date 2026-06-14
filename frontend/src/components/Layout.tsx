import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard,
  MapPinned,
  Users,
  Share2,
  TrendingUp,
  FileText,
  Sparkles,
  ShieldHalf,
  LucideIcon,
} from "lucide-react";
import { api } from "../lib/api";

const NAV: { to: string; label: string; icon: LucideIcon; end?: boolean }[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/hotspots", label: "Geospatial Hotspots", icon: MapPinned },
  { to: "/demographics", label: "Demographics", icon: Users },
  { to: "/network", label: "Network / Link Analysis", icon: Share2 },
  { to: "/predictive", label: "Predictive & Anomaly", icon: TrendingUp },
  { to: "/reports", label: "AI Reports", icon: FileText },
  { to: "/assistant", label: "Ask the Data", icon: Sparkles },
];

export default function Layout() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, retry: false });
  const online = health.isSuccess;
  const location = useLocation();

  return (
    <div className="flex h-full">
      <aside className="no-print flex w-64 shrink-0 flex-col border-r border-line bg-surface/60 backdrop-blur-xl">
        {/* Brand */}
        <div className="flex items-center gap-3 px-5 py-5">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-accent to-info text-white shadow-glow">
            <ShieldHalf size={20} strokeWidth={2.25} />
          </div>
          <div className="leading-tight">
            <div className="text-[15px] font-extrabold tracking-tight text-white">
              KSP <span className="text-accent-soft">Intel</span>
            </div>
            <div className="text-[11px] font-medium tracking-wide text-muted">SCRB · Karnataka</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-1 px-3 py-2">
          <div className="px-3 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted/70">
            Intelligence
          </div>
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? "bg-surface-2 text-white shadow-card"
                    : "text-muted hover:bg-white/[0.04] hover:text-white/90"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={`absolute left-0 top-1/2 h-5 -translate-y-1/2 rounded-r-full bg-accent transition-all duration-200 ${
                      isActive ? "w-1 opacity-100" : "w-0 opacity-0"
                    }`}
                  />
                  <n.icon
                    size={18}
                    strokeWidth={2}
                    className={`shrink-0 transition-colors ${
                      isActive ? "text-accent-soft" : "text-muted group-hover:text-white/80"
                    }`}
                  />
                  <span className="truncate">{n.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* System status */}
        <div className="mx-3 mb-4 rounded-xl border border-line bg-surface-2/60 px-3.5 py-3">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              {online && (
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />
              )}
              <span
                className={`relative inline-flex h-2 w-2 rounded-full ${
                  online ? "bg-success" : health.isLoading ? "bg-warning animate-pulse-dot" : "bg-danger"
                }`}
              />
            </span>
            <span className="text-xs font-semibold text-white/85">
              {online ? "System online" : health.isLoading ? "Connecting…" : "API offline"}
            </span>
          </div>
          <div className="tabular mt-1.5 flex items-center justify-between text-[11px] text-muted">
            <span>Data · {health.data?.data_mode ?? "—"}</span>
            <span>{online ? `${health.data!.incidents_loaded.toLocaleString()} rows` : "—"}</span>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <div className="mx-auto max-w-[1400px] px-6 py-7 lg:px-8">
          <div key={location.pathname} className="animate-fade-in">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
}
