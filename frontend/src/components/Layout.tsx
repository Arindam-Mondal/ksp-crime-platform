import { useCallback, useEffect, useRef, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Menu, ShieldHalf } from "lucide-react";
import { api } from "../lib/api";
import Sidebar, { NAV } from "./Sidebar";
import LanguageToggle from "./LanguageToggle";
import { useT } from "../i18n";

export interface HealthState {
  online: boolean;
  loading: boolean;
  mode: string;
  cases: number;
}

const STORAGE_KEY = "ksp.sidebar.collapsed";
/** Below this the content area is too tight for a 264px sidebar (14" laptops). */
const AUTO_COLLAPSE_BELOW = 1440;

function initialCollapsed(): boolean {
  if (typeof window === "undefined") return false;
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "true") return true;
  if (stored === "false") return false;
  return window.innerWidth < AUTO_COLLAPSE_BELOW;
}

export default function Layout() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, retry: false });
  const location = useLocation();
  const t = useT();

  const [collapsed, setCollapsed] = useState(initialCollapsed);
  const [mobileOpen, setMobileOpen] = useState(false);
  const hamburger = useRef<HTMLButtonElement | null>(null);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((c) => {
      window.localStorage.setItem(STORAGE_KEY, String(!c));
      return !c;
    });
  }, []);

  const closeMobile = useCallback(() => setMobileOpen(false), []);

  // Navigating from the drawer should dismiss it and hand focus back.
  useEffect(() => {
    setMobileOpen((open) => {
      if (open) hamburger.current?.focus();
      return false;
    });
  }, [location.pathname]);

  // Escape closes the drawer; Ctrl/Cmd+B toggles the desktop rail.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMobileOpen((open) => {
          if (open) hamburger.current?.focus();
          return false;
        });
        return;
      }
      if (e.key.toLowerCase() === "b" && (e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey) {
        e.preventDefault();
        toggleCollapsed();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [toggleCollapsed]);

  // Lock background scroll while the drawer is open.
  useEffect(() => {
    if (!mobileOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [mobileOpen]);

  const healthState: HealthState = {
    online: health.isSuccess,
    loading: health.isLoading,
    mode: health.data?.data_mode ?? "—",
    cases: health.data?.cases_loaded ?? 0,
  };

  const current = NAV.find((n) => (n.end ? n.to === location.pathname : location.pathname.startsWith(n.to)));

  return (
    <div className="flex h-full">
      <a
        href="#main"
        className="no-print sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-tooltip focus:rounded-lg focus:border focus:border-line-strong focus:bg-surface-2 focus:px-3.5 focus:py-2 focus:text-sm focus:font-medium focus:text-white"
      >
        {t("chrome.skipToContent")}
      </a>

      <Sidebar
        collapsed={collapsed}
        onToggleCollapsed={toggleCollapsed}
        mobileOpen={mobileOpen}
        onCloseMobile={closeMobile}
        health={healthState}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar — the drawer's only entry point below lg */}
        <header className="no-print safe-top sticky top-0 z-sticky flex items-center gap-3 border-b border-line bg-surface/85 px-4 py-3 backdrop-blur-xl lg:hidden">
          <button
            ref={hamburger}
            type="button"
            onClick={() => setMobileOpen(true)}
            aria-label={t("chrome.openNav")}
            aria-expanded={mobileOpen}
            aria-controls="primary-nav"
            className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-line bg-surface-2/60 text-white/80 transition-colors hover:text-white"
          >
            <Menu size={18} strokeWidth={2} />
          </button>
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-accent to-info text-white">
            <ShieldHalf size={17} strokeWidth={2.25} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold tracking-tight text-white">
              {current ? t(current.labelKey) : t("brand.name")}
            </div>
            <div className="truncate text-[11px] text-muted">{t("brand.tagline")}</div>
          </div>
          {/* The drawer is the only other way to reach the switcher on mobile; keeping
              it in the bar means the language is one tap away from every page. */}
          <LanguageToggle className="shrink-0" />
          <span
            role="status"
            aria-label={
              healthState.online
                ? t("status.online")
                : healthState.loading
                ? t("status.connecting")
                : t("status.offline")
            }
            className={`h-2 w-2 shrink-0 rounded-full ${
              healthState.online ? "bg-success" : healthState.loading ? "bg-warning animate-pulse-dot" : "bg-danger"
            }`}
          />
        </header>

        <main id="main" className="flex-1 overflow-auto">
          {/* .safe-x owns the horizontal padding (4/6/8 + notch inset) */}
          <div className="safe-x mx-auto max-w-[1400px] py-5 sm:py-7">
            <div key={location.pathname} className="animate-fade-in">
              <Outlet />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
