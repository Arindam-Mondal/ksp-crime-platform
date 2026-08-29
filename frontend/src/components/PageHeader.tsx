import { LucideIcon } from "lucide-react";
import { ReactNode } from "react";

export default function PageHeader({
  icon: Icon,
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  icon: LucideIcon;
  eyebrow: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex min-w-0 items-start gap-3 sm:gap-3.5">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-line bg-surface-2 text-accent-soft shadow-card sm:h-11 sm:w-11">
          <Icon size={20} strokeWidth={2} />
        </span>
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent-soft/80">
            {eyebrow}
          </div>
          <h1 className="text-balance text-xl font-bold tracking-tight text-white sm:text-2xl">{title}</h1>
          {subtitle && <p className="mt-0.5 text-pretty text-sm text-muted">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
