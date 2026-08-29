import { ReactNode } from "react";
import { useElementWidth } from "../../lib/useElementWidth";

/**
 * Sized chart container that hands its measured width to the chart inside.
 *
 * Panels change width with the grid AND with the sidebar rail, so charts pick
 * axis widths, label budgets and orientation from this rather than from
 * viewport breakpoints. Width is 0 before the first measurement — callers must
 * treat 0 as "wide".
 */
export default function ChartFrame({
  className = "",
  children,
}: {
  className?: string;
  children: (width: number) => ReactNode;
}) {
  const [ref, width] = useElementWidth<HTMLDivElement>();
  return (
    <div ref={ref} className={className}>
      {children(width)}
    </div>
  );
}
