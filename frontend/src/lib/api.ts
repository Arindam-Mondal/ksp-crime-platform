// Typed API client. In dev, Vite proxies these paths to the FastAPI backend (:9000).

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export interface DistrictCount { district: string; incidents: number; }
export interface HotspotCell { lat: number; lon: number; count: number; }
export interface HourCount { hour: number; count: number; }
export interface OffenderCount { person_id: string; name: string; incidents: number; }
export interface RiskScore {
  district: string; incidents: number; socio_economic_index: number; risk_score: number;
}
export interface EgoGraph {
  root: string;
  nodes: { id: string; name: string }[];
  edges: { source: string; target: string; weight: number }[];
}
export interface AskResponse {
  question: string; answer: string; provider: string; model: string; grounded_on: string[];
}

export const api = {
  health: () => get<{ status: string; data_mode: string; incidents_loaded: number }>("/health"),
  meta: () => get<{ districts: string[]; crime_types: string[] }>("/api/incidents/meta"),
  byDistrict: () => get<{ items: DistrictCount[] }>("/api/hotspots/by-district"),
  cells: () => get<{ items: HotspotCell[] }>("/api/hotspots/cells"),
  byHour: (crime?: string) =>
    get<{ items: HourCount[] }>("/api/hotspots/by-hour" + (crime ? `?crime_type=${encodeURIComponent(crime)}` : "")),
  topOffenders: () => get<{ items: OffenderCount[] }>("/api/network/top-offenders"),
  ego: (personId: string) => get<EgoGraph>(`/api/network/ego/${personId}`),
  riskScores: () => get<{ method: string; items: RiskScore[] }>("/api/predictive/risk-scores"),
  ask: (question: string) => post<AskResponse>("/api/assistant/ask", { question }),
};
