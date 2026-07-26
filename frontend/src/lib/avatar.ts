// Deterministic person avatars. Every accused/offender record in this dataset is
// synthetic, so we deliberately do NOT render photorealistic human faces for them —
// stock/generated portraits mapped to fictional "accused" profiles reads badly for a
// policing tool regardless of intent. Instead we render a stable initials tile, keyed
// off a hash of the person id so the same person always gets the same color.

export function hashId(id: string): number {
  let h = 5381;
  for (let i = 0; i < id.length; i++) h = ((h << 5) + h + id.charCodeAt(i)) >>> 0;
  return h;
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

// Stable tile color for the initials fallback.
const TILE = ["#5b7fff", "#38bdf8", "#22d3ee", "#34d399", "#f59e0b", "#f472b6", "#a78bfa"];
export function tileColor(id: string): string {
  return TILE[hashId(id) % TILE.length];
}
