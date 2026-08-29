import { ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

/**
 * Label tooltip for icon-only controls (the collapsed sidebar rail).
 *
 * Rendered through a portal with `position: fixed` on purpose: the nav scrolls
 * on short screens, and an absolutely-positioned tooltip would be clipped by
 * that overflow container.
 *
 * It is decorative for assistive tech (`aria-hidden`) — the accessible name
 * must come from the trigger's own `aria-label`.
 */
export default function Tooltip({
  label,
  disabled = false,
  className = "",
  children,
}: {
  label: ReactNode;
  disabled?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const anchor = useRef<HTMLDivElement | null>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  const show = useCallback(() => {
    if (disabled || !anchor.current) return;
    const r = anchor.current.getBoundingClientRect();
    setPos({
      top: Math.min(Math.max(r.top + r.height / 2, 24), window.innerHeight - 24),
      // 14px clears the rail's right border, not just the trigger's box
      left: r.right + 14,
    });
  }, [disabled]);

  const hide = useCallback(() => setPos(null), []);

  // A collapse toggle or route change can move the trigger while the tooltip is
  // open; drop it rather than leave it stranded.
  useEffect(() => {
    if (!pos) return;
    window.addEventListener("scroll", hide, true);
    window.addEventListener("resize", hide);
    return () => {
      window.removeEventListener("scroll", hide, true);
      window.removeEventListener("resize", hide);
    };
  }, [pos, hide]);

  useEffect(() => {
    if (disabled) setPos(null);
  }, [disabled]);

  return (
    <div
      ref={anchor}
      className={className}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {pos &&
        createPortal(
          <div
            aria-hidden="true"
            style={{ top: pos.top, left: pos.left }}
            className="pointer-events-none fixed z-tooltip -translate-y-1/2 whitespace-nowrap rounded-lg border border-line-strong bg-surface-2 px-2.5 py-1.5 text-xs font-medium text-white/90 shadow-card animate-fade-in"
          >
            {label}
          </div>,
          document.body
        )}
    </div>
  );
}
