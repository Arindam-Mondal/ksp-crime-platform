// Shared Recharts styling so every chart looks intentionally designed and consistent.
import type { CSSProperties } from "react";

export const CHART = {
  accent: "#5b7fff",
  accentSoft: "#869bff",
  grid: "#1e2840",
  axisTick: { fontSize: 11, fill: "#8a94ad", fontFamily: "JetBrains Mono, monospace" },
  gradientId: "accentBar",
};

export const tooltipStyle: CSSProperties = {
  background: "rgba(17, 23, 38, 0.96)",
  border: "1px solid #2c3a5c",
  borderRadius: 10,
  boxShadow: "0 10px 30px -12px rgba(0,0,0,0.7)",
  fontSize: 12,
  padding: "8px 12px",
};

export const tooltipLabelStyle: CSSProperties = {
  color: "#b6c0d8",
  fontWeight: 600,
  marginBottom: 2,
};

export const tooltipItemStyle: CSSProperties = {
  color: "#e6eaf2",
  fontFamily: "JetBrains Mono, monospace",
};

// Soft highlight that follows the cursor on bar/area charts.
export const cursorFill = { fill: "rgba(91, 127, 255, 0.08)" };

export function formatNumber(n: number): string {
  return n.toLocaleString();
}

// Categorical color maps shared across the dashboard & demographics views.
export const HEAD_COLORS: Record<string, string> = {
  "Property Crime": "#5b7fff",
  "Economic Offence": "#38bdf8",
  "Crime Against Person": "#f472b6",
  "Special & Local Laws": "#f59e0b",
  Other: "#8a94ad",
};

export const SEVERITY_COLORS: Record<string, string> = {
  Low: "#10b981",
  Medium: "#38bdf8",
  High: "#f59e0b",
  Severe: "#ef4444",
};

export const STATUS_COLORS: Record<string, string> = {
  "Charge-sheeted": "#10b981",
  Closed: "#22d3ee",
  "Under Investigation": "#f59e0b",
  "Pending Trial": "#a78bfa",
};

export const GENDER_COLORS: Record<string, string> = {
  Male: "#5b7fff",
  Female: "#f472b6",
};

// General-purpose categorical palette (age groups, urban/rural, etc.).
export const PALETTE = ["#5b7fff", "#38bdf8", "#22d3ee", "#34d399", "#f59e0b", "#f472b6", "#a78bfa"];
