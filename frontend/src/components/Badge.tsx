import { ReactNode } from "react";

type Variant = "accent" | "success" | "warning" | "danger" | "info" | "neutral";

const VARIANTS: Record<Variant, string> = {
  accent: "text-accent-soft bg-accent/10 ring-accent/25",
  success: "text-success bg-success/10 ring-success/25",
  warning: "text-warning bg-warning/10 ring-warning/25",
  danger: "text-danger bg-danger/10 ring-danger/25",
  info: "text-info bg-info/10 ring-info/25",
  neutral: "text-muted bg-white/5 ring-white/10",
};

export default function Badge({
  children,
  variant = "neutral",
  dot = false,
  className = "",
}: {
  children: ReactNode;
  variant?: Variant;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${VARIANTS[variant]} ${className}`}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}
