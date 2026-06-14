// Deterministic person avatars. A stable hash of the person id picks a consistent
// randomuser.me portrait (men/women by gender) so each person always shows the same
// face. No API key — just an <img> URL. Falls back to initials if the image is blocked.

export function hashId(id: string): number {
  let h = 5381;
  for (let i = 0; i < id.length; i++) h = ((h << 5) + h + id.charCodeAt(i)) >>> 0;
  return h;
}

export function avatarUrl(id: string, gender?: string): string {
  const folder = gender === "F" ? "women" : "men";
  return `https://randomuser.me/api/portraits/${folder}/${hashId(id) % 100}.jpg`;
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
