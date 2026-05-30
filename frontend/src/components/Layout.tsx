import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/hotspots", label: "Geospatial Hotspots" },
  { to: "/network", label: "Network / Link Analysis" },
  { to: "/predictive", label: "Predictive & Anomaly" },
  { to: "/assistant", label: "Ask the Data" },
];

export default function Layout() {
  return (
    <div className="flex h-full">
      <aside className="w-64 shrink-0 bg-ksp-panel border-r border-white/10 p-4">
        <div className="mb-6">
          <div className="text-lg font-semibold">KSP Crime Intelligence</div>
          <div className="text-xs text-white/50">SCRB · Karnataka</div>
        </div>
        <nav className="space-y-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `block rounded px-3 py-2 text-sm ${
                  isActive ? "bg-ksp-accent text-white" : "text-white/70 hover:bg-white/5"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
