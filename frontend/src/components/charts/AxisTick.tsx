import { useCallback } from "react";
import { CHART } from "./theme";
import { useLang } from "../../i18n";

/**
 * Recharts tick renderer that clips long category labels instead of letting
 * them overflow their band. District and crime-sub-head names ("Dakshina
 * Kannada", "Outraging Modesty of Women") otherwise run past the plot edge or
 * collide with each other. The full value stays available in the tooltip.
 */
export function truncatedTick(maxChars: number, opts: { angle?: number; fontSize?: number } = {}) {
  const { angle = 0, fontSize = 11 } = opts;

  return function Tick(props: any) {
    const { x, y, payload, textAnchor } = props;
    const raw = String(payload?.value ?? "");
    const text = raw.length > maxChars ? `${raw.slice(0, maxChars - 1).trimEnd()}…` : raw;

    return (
      <g transform={`translate(${x},${y})`}>
        <text
          x={0}
          y={0}
          dy={angle ? 4 : 4}
          textAnchor={textAnchor ?? (angle ? "end" : "middle")}
          transform={angle ? `rotate(${angle})` : undefined}
          fill={CHART.axisTick.fill}
          fontSize={fontSize}
          fontFamily={CHART.axisTick.fontFamily}
        >
          {text}
          {raw !== text && <title>{raw}</title>}
        </text>
      </g>
    );
  };
}

/** Average glyph advance as a fraction of the font size, per script. */
const ADVANCE = {
  /** The Latin mono axis face. */
  en: 0.62,
  /** Kannada in Noto Sans Kannada: conjuncts (ಕ್ಕ) and vowel signs run visibly wider,
   *  so the same character count needs roughly a fifth more room. */
  kn: 0.78,
};

/**
 * Chars that fit in `px` at `fontSize` for the mono axis face (~0.6em advance).
 * Prefer `useCharsFor()` in components — it accounts for the active script.
 */
export function charsFor(px: number, fontSize = 11): number {
  return Math.max(4, Math.floor(px / (fontSize * ADVANCE.en)));
}

/**
 * Language-aware `charsFor`. Kannada axis labels would otherwise overflow their band:
 * the char budget is computed from a Latin advance width the script does not share.
 */
export function useCharsFor(): (px: number, fontSize?: number) => number {
  const { lang } = useLang();
  return useCallback(
    (px: number, fontSize = 11) => Math.max(4, Math.floor(px / (fontSize * ADVANCE[lang]))),
    [lang]
  );
}

/**
 * Category-axis width for a horizontal bar chart, from the container's measured
 * width: wide enough to read, never so wide that the bars get squeezed out of a
 * narrow panel. `0` means "not measured yet" — fall back to the roomy value.
 */
export function catAxisWidth(containerWidth: number): number {
  if (containerWidth <= 0) return 148;
  return Math.round(Math.min(160, Math.max(80, containerWidth * 0.32)));
}
