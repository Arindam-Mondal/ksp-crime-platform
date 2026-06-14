import { useEffect, useState } from "react";
import { avatarUrl, initials, tileColor } from "../lib/avatar";

export default function Avatar({
  id,
  gender,
  name,
  size = 40,
  ring,
  className = "",
}: {
  id: string;
  gender?: string;
  name: string;
  size?: number;
  ring?: string; // optional ring color (e.g. threat tint)
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [id]); // retry when the person changes

  const ringStyle = ring ? { boxShadow: `0 0 0 2px ${ring}` } : undefined;
  const base = "shrink-0 overflow-hidden rounded-full bg-surface-2 object-cover";

  if (failed || !id) {
    return (
      <div
        className={`grid place-items-center rounded-full font-bold text-white ${className}`}
        style={{ width: size, height: size, background: tileColor(id || "?"), fontSize: size * 0.38, ...ringStyle }}
        title={name}
      >
        {initials(name)}
      </div>
    );
  }

  return (
    <img
      src={avatarUrl(id, gender)}
      alt={name}
      title={name}
      width={size}
      height={size}
      loading="lazy"
      onError={() => setFailed(true)}
      className={`${base} ${className}`}
      style={{ width: size, height: size, ...ringStyle }}
    />
  );
}
