export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton rounded-lg ${className}`} />;
}

// Loading placeholder shaped like a bar chart (rising bars).
export function ChartSkeleton({ height = 300 }: { height?: number }) {
  const bars = [40, 65, 50, 80, 55, 72, 48, 90, 60, 70, 45, 85];
  return (
    <div className="flex items-end gap-2" style={{ height }}>
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
