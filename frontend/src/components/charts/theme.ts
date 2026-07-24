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
// Crime heads per the FIR ERD's CrimeHead master.
export const HEAD_COLORS: Record<string, string> = {
  "Crimes Against Body": "#f472b6",
  "Crimes Against Property": "#5b7fff",
  "Crimes Against Women": "#a78bfa",
  "Economic Offences": "#38bdf8",
  "Cyber Crime": "#22d3ee",
  "Crimes Against Public Order": "#f59e0b",
  "Special & Local Laws": "#fb923c",
  Others: "#8a94ad",
  Other: "#8a94ad",
};

// GravityOffence lookup (Heinous / Non-Heinous).
export const GRAVITY_COLORS: Record<string, string> = {
  Heinous: "#ef4444",
  "Non-Heinous": "#38bdf8",
};

// CaseStatusMaster values.
export const STATUS_COLORS: Record<string, string> = {
  "Under Investigation": "#f59e0b",
  "Charge Sheeted": "#34d399",
  "Pending Trial": "#a78bfa",
  Convicted: "#10b981",
  Acquitted: "#22d3ee",
  "Closed - False Case": "#8a94ad",
  "Closed - Undetected": "#ef4444",
  "Closed - Others": "#64748b",
  Transferred: "#f472b6",
};

// CaseCategory values (FIR / Zero FIR / UDR / PAR).
export const CATEGORY_COLORS: Record<string, string> = {
  FIR: "#5b7fff",
  "Zero FIR": "#22d3ee",
  UDR: "#f59e0b",
  PAR: "#a78bfa",
};

export const GENDER_COLORS: Record<string, string> = {
  Male: "#5b7fff",
  Female: "#f472b6",
  Transgender: "#f59e0b",
};

// General-purpose categorical palette (age groups, urban/rural, etc.).
export const PALETTE = ["#5b7fff", "#38bdf8", "#22d3ee", "#34d399", "#f59e0b", "#f472b6", "#a78bfa"];
