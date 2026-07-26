import { initials, tileColor } from "../lib/avatar";

export default function Avatar({
  id,
  name,
  size = 40,
  ring,
  className = "",
}: {
  id: string;
  gender?: string; // accepted for API compatibility; no longer used for a photo lookup
  name: string;
  size?: number;
  ring?: string; // optional ring color (e.g. threat tint)
  className?: string;
}) {
  const ringStyle = ring ? { boxShadow: `0 0 0 2px ${ring}` } : undefined;

  // Deliberately initials-only: every offender/accused record here is synthetic, and
  // rendering realistic human photos against fictional "accused" profiles is worth
  // avoiding in a policing tool regardless of intent (see lib/avatar.ts).
  return (
    <div
      className={`grid shrink-0 place-items-center rounded-full font-bold text-white ${className}`}
      style={{ width: size, height: size, background: tileColor(id || "?"), fontSize: size * 0.38, ...ringStyle }}
      title={name}
    >
      {initials(name)}
    </div>
  );
}
