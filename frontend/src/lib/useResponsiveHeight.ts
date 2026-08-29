import { useEffect, useState } from "react";

/**
 * Pixel height for canvas-rendered surfaces (the force graph, maps) that need a
 * number rather than a CSS clamp. Mirrors `clamp(min, vh * fraction, max)`.
 *
 * A 520px graph on a 667px-tall phone leaves no room for anything else, so the
 * surface gives back height on short viewports and caps on tall ones.
 */
export function useResponsiveHeight(max: number, min = 320, fraction = 0.55): number {
  const compute = () =>
    typeof window === "undefined"
      ? max
      : Math.round(Math.min(max, Math.max(min, window.innerHeight * fraction)));

  const [height, setHeight] = useState(compute);

  useEffect(() => {
    const onResize = () => setHeight(compute());
    window.addEventListener("resize", onResize);
    window.addEventListener("orientationchange", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("orientationchange", onResize);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [max, min, fraction]);

  return height;
}

export default useResponsiveHeight;
