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
        // flex-wrap: toolbars in `actions` drop to their own line rather than
        // squeezing the title to nothing on narrow panels
        <header className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2.5 border-b border-line px-5 py-3.5">
          <div className="flex min-w-0 flex-1 items-center gap-2.5">
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
              {/* On a phone `truncate` threw away most of the sentence (as
                  little as 35% survived); wrap to two lines there instead. */}
              {subtitle && <p className="line-clamp-2 text-xs text-muted sm:truncate">{subtitle}</p>}
            </div>
          </div>
          {actions && <div className="shrink-0">{actions}</div>}
        </header>
      )}
      <div className={`p-5 ${bodyClassName}`}>{children}</div>
    </section>
  );
}
