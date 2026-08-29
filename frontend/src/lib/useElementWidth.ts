import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Measures an element's own width with a ResizeObserver.
 *
 * Charts and legends in this app sit inside panels whose width depends on the
 * grid AND on whether the sidebar is collapsed — viewport breakpoints can't see
 * that. Components size themselves off this instead.
 *
 * Returns 0 until the first measurement. Callers must treat 0 as "assume wide"
 * so the first paint is never the degraded/stacked layout.
 */
export function useElementWidth<T extends HTMLElement>(): [
  (node: T | null) => void,
  number
] {
  const [width, setWidth] = useState(0);
  const observer = useRef<ResizeObserver | null>(null);

  const ref = useCallback((node: T | null) => {
    observer.current?.disconnect();
    observer.current = null;
    if (!node) return;

    setWidth(node.getBoundingClientRect().width);

    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      // borderBoxSize is not in older Safari; contentRect is the safe read.
      setWidth(entry.contentRect.width);
    });
    ro.observe(node);
    observer.current = ro;
  }, []);

  useEffect(() => () => observer.current?.disconnect(), []);

  return [ref, width];
}

export default useElementWidth;
