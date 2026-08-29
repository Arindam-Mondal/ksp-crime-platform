import { useEffect, useRef } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  MapPinned,
  Users,
  Building2,
  Share2,
  TrendingUp,
  UserCog,
  FileText,
  Sparkles,
  ShieldHalf,
  PanelLeftClose,
  PanelLeftOpen,
  X,
  LucideIcon,
} from "lucide-react";
import Tooltip from "./Tooltip";
import LanguageToggle from "./LanguageToggle";
import { useT, type TranslationKey } from "../i18n";
import type { HealthState } from "./Layout";

/** Nav entries carry a catalog key, not a label — the label is resolved at render so
 *  the sidebar and the mobile top bar both follow the active language. */
export const NAV: { to: string; labelKey: TranslationKey; icon: LucideIcon; end?: boolean }[] = [
  { to: "/", labelKey: "nav.dashboard", icon: LayoutDashboard, end: true },
  { to: "/hotspots", labelKey: "nav.hotspots", icon: MapPinned },
  { to: "/demographics", labelKey: "nav.demographics", icon: Users },
  { to: "/sociological", labelKey: "nav.sociological", icon: Building2 },
  { to: "/network", labelKey: "nav.network", icon: Share2 },
  { to: "/operations", labelKey: "nav.operations", icon: UserCog },
  { to: "/predictive", labelKey: "nav.predictive", icon: TrendingUp },
  { to: "/reports", labelKey: "nav.reports", icon: FileText },
  { to: "/assistant", labelKey: "nav.assistant", icon: Sparkles },
];

/** Focusable elements inside the drawer, for the mobile focus trap. */
const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function Sidebar({
  collapsed,
  onToggleCollapsed,
  mobileOpen,
  onCloseMobile,
  health,
}: {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  health: HealthState;
}) {
  const asideRef = useRef<HTMLElement | null>(null);
  const t = useT();

  // Below lg the sidebar is a modal drawer: trap Tab inside it while open.
  useEffect(() => {
    if (!mobileOpen) return;
    const node = asideRef.current;
    if (!node) return;

    const first = node.querySelector<HTMLElement>(FOCUSABLE);
    first?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const items = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (items.length === 0) return;
      const start = items[0];
      const end = items[items.length - 1];
      if (e.shiftKey && document.activeElement === start) {
        e.preventDefault();
        end.focus();
      } else if (!e.shiftKey && document.activeElement === end) {
        e.preventDefault();
        start.focus();
      }
    };

    node.addEventListener("keydown", onKeyDown);
    return () => node.removeEventListener("keydown", onKeyDown);
  }, [mobileOpen]);

  // The rail only exists at lg+. In the drawer the labels are always visible,
  // so tooltips (and the icon-only treatment) are desktop-collapsed-only.
  const rail = collapsed && !mobileOpen;

  const statusText = health.online
    ? t("status.online")
    : health.loading
    ? t("status.connecting")
    : t("status.offline");
  const statusDetail = health.online
    ? t("status.detail", { mode: health.mode, count: health.cases.toLocaleString() })
    : statusText;

  return (
    <>
      {/* Drawer backdrop (mobile only) */}
      <div
        onClick={onCloseMobile}
        aria-hidden="true"
        className={`no-print fixed inset-0 z-backdrop bg-bg/70 backdrop-blur-sm transition-opacity duration-200 lg:hidden ${
          mobileOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />

      <aside
        ref={asideRef}
        id="primary-nav"
        role={mobileOpen ? "dialog" : undefined}
        aria-modal={mobileOpen ? true : undefined}
        aria-label={mobileOpen ? t("chrome.navigation") : undefined}
        className={`no-print safe-left fixed inset-y-0 left-0 z-drawer flex w-[272px] flex-col border-r border-line bg-surface/95 backdrop-blur-xl transition-[width,transform] duration-200 ease-out lg:static lg:translate-x-0 lg:bg-surface/60 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        } ${rail ? "lg:w-[76px]" : "lg:w-[264px]"}`}
      >
        {/* Brand + collapse toggle */}
        <div
          className={`flex shrink-0 items-center gap-3 py-5 ${rail ? "justify-center px-3" : "px-5"}`}
        >
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-accent to-info text-white shadow-glow">
            <ShieldHalf size={20} strokeWidth={2.25} />
          </div>
          {!rail && (
            <>
              <div className="min-w-0 flex-1 leading-tight">
                <div className="truncate text-[15px] font-extrabold tracking-tight text-white">
                  {t("brand.nameLead")}{" "}
                  <span className="text-accent-soft">{t("brand.nameAccent")}</span>
                </div>
                <div className="truncate text-[11px] font-medium tracking-wide text-muted">
                  {t("brand.tagline")}
                </div>
              </div>
              <button
                type="button"
                onClick={onCloseMobile}
                aria-label={t("chrome.closeNav")}
                className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-muted transition-colors hover:bg-white/[0.06] hover:text-white lg:hidden"
              >
                <X size={18} />
              </button>
            </>
          )}
        </div>

        {/* Nav */}
        <nav
          aria-label={t("chrome.primaryNav")}
          className={`flex-1 space-y-1 overflow-y-auto overflow-x-hidden py-2 ${rail ? "px-3" : "px-3"}`}
        >
          {!rail && (
            <div className="px-3 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted/70">
              {t("nav.section")}
            </div>
          )}
          {NAV.map((n) => (
            <Tooltip key={n.to} label={t(n.labelKey)} disabled={!rail}>
              <NavLink
                to={n.to}
                end={n.end}
                aria-label={rail ? t(n.labelKey) : undefined}
                className={({ isActive }) =>
                  `group relative flex items-center rounded-xl text-sm font-medium transition-colors duration-200 ${
                    rail ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2.5"
                  } ${
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
                    {!rail && <span className="truncate">{t(n.labelKey)}</span>}
                  </>
                )}
              </NavLink>
            </Tooltip>
          ))}
        </nav>

        {/* Language — directly above the status block, so it sits in the persistent
            chrome rather than inside any one page. */}
        <div className="shrink-0 px-3 pb-2">
          <LanguageToggle variant={rail ? "compact" : "segmented"} />
        </div>

        {/* System status */}
        <div className={`shrink-0 ${rail ? "px-3" : "px-3"}`}>
          {rail ? (
            <Tooltip label={statusDetail}>
              <div
                className="grid h-10 w-full place-items-center rounded-xl border border-line bg-surface-2/60"
                role="status"
                aria-label={statusDetail}
              >
                <StatusDot health={health} />
              </div>
            </Tooltip>
          ) : (
            <div className="rounded-xl border border-line bg-surface-2/60 px-3.5 py-3" role="status">
              <div className="flex items-center gap-2">
                <StatusDot health={health} />
                <span className="text-xs font-semibold text-white/85">{statusText}</span>
              </div>
              <div className="tabular mt-1.5 flex items-center justify-between text-[11px] text-muted">
                <span>{t("status.dataMode", { mode: health.mode })}</span>
                <span>
                  {health.online
                    ? t("status.firCount", { count: health.cases.toLocaleString() })
                    : t("common.none")}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Collapse toggle — desktop only; the drawer closes with X / Escape */}
        <div className={`hidden shrink-0 pb-4 pt-3 lg:block ${rail ? "px-3" : "px-3"}`}>
          <Tooltip label={t("chrome.expandSidebar")} disabled={!rail}>
            <button
              type="button"
              onClick={onToggleCollapsed}
              aria-expanded={!collapsed}
              aria-controls="primary-nav"
              aria-label={collapsed ? t("chrome.expandSidebar") : t("chrome.collapseSidebar")}
              className={`flex w-full items-center rounded-xl py-2 text-xs font-medium text-muted transition-colors hover:bg-white/[0.04] hover:text-white/90 ${
                rail ? "justify-center px-0" : "gap-2.5 px-3"
              }`}
            >
              {collapsed ? (
                <PanelLeftOpen size={18} strokeWidth={2} className="shrink-0" />
              ) : (
                <PanelLeftClose size={18} strokeWidth={2} className="shrink-0" />
              )}
              {!rail && (
                <>
                  <span className="truncate">{t("chrome.collapse")}</span>
                  <kbd className="tabular ml-auto rounded border border-line bg-bg/60 px-1.5 py-0.5 text-[10px] text-muted">
                    Ctrl B
                  </kbd>
                </>
              )}
            </button>
          </Tooltip>
        </div>
      </aside>
    </>
  );
}

function StatusDot({ health }: { health: HealthState }) {
  return (
    <span className="relative flex h-2 w-2 shrink-0">
      {health.online && (
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />
      )}
      <span
        className={`relative inline-flex h-2 w-2 rounded-full ${
          health.online ? "bg-success" : health.loading ? "bg-warning animate-pulse-dot" : "bg-danger"
        }`}
      />
    </span>
  );
}
