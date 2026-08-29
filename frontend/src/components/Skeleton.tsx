import { CSSProperties } from "react";

export function Skeleton({
  className = "",
  style,
}: {
  className?: string;
  style?: CSSProperties;
}) {
  return <div className={`skeleton rounded-lg ${className}`} style={style} />;
}

// Loading placeholder shaped like a bar chart (rising bars).
// Fills its container by default so it matches responsive chart frames; pass an
// explicit height only where there is no sized parent.
export function ChartSkeleton({ height }: { height?: number }) {
  const bars = [40, 65, 50, 80, 55, 72, 48, 90, 60, 70, 45, 85];
  return (
    <div className="flex h-full items-end gap-2" style={height ? { height } : undefined}>
      {bars.map((h, i) => (
        <div
          key={i}
          className="skeleton flex-1 rounded-t-md"
          style={{ height: `${h}%`, animationDelay: `${i * 70}ms` }}
        />
      ))}
    </div>
  );
}

export function ListSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3" style={{ animationDelay: `${i * 50}ms` }}>
          <Skeleton className="h-9 w-9 shrink-0 rounded-lg" />
          <Skeleton className="h-9 flex-1" />
        </div>
      ))}
    </div>
  );
}

export function TableSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div className="space-y-2.5">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  );
}
