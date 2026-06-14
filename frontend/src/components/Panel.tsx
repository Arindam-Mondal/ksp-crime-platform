import { ReactNode } from "react";
import { LucideIcon } from "lucide-react";

export default function Panel({
  title,
  subtitle,
  icon: Icon,
  actions,
  className = "",
  bodyClassName = "",
  children,
}: {
  title?: string;
  subtitle?: string;
  icon?: LucideIcon;
  actions?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={`group rounded-2xl border border-line bg-surface/80 shadow-card backdrop-blur-sm transition-all duration-300 hover:border-line-strong hover:shadow-card-hover animate-fade-in-up ${className}`}
    >
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-3.5">
          <div className="flex items-center gap-2.5 min-w-0">
            {Icon && (
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-line bg-surface-2 text-accent-soft">
                <Icon size={16} strokeWidth={2} />
              </span>
            )}
            <div className="min-w-0">
              {title && (
                <h2 className="truncate text-sm font-semibold tracking-tight text-white/90">
                  {title}
                </h2>
              )}
              {subtitle && <p className="truncate text-xs text-muted">{subtitle}</p>}
            </div>
          </div>
          {actions && <div className="shrink-0">{actions}</div>}
        </header>
      )}
      <div className={`p-5 ${bodyClassName}`}>{children}</div>
    </section>
  );
}
