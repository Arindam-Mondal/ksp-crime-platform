import { LucideIcon } from "lucide-react";
import { ReactNode } from "react";

export default function EmptyState({
  icon: Icon,
  title,
  hint,
  children,
}: {
  icon: LucideIcon;
  title: string;
  hint?: string;
  children?: ReactNode;
}) {
  return (
    <div className="grid h-full min-h-[200px] place-items-center px-6 py-10 text-center animate-fade-in">
      <div className="max-w-sm">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-line bg-surface-2 text-accent-soft shadow-glow">
          <Icon size={24} strokeWidth={1.75} />
        </div>
        <h3 className="mt-4 text-sm font-semibold text-white/90">{title}</h3>
        {hint && <p className="mx-auto mt-1.5 max-w-xs text-xs leading-relaxed text-muted">{hint}</p>}
        {children && <div className="mt-4">{children}</div>}
      </div>
    </div>
  );
}
