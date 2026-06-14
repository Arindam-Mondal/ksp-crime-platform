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
export interface OffenderCount { person_id: string; name: string; gender?: string; incidents: number; }
export interface RiskScore {
  district: string; incidents: number; socio_economic_index: number; risk_score: number;
}
export interface EgoNode {
  id: string; name: string; gender: string; incidents: number; is_root: boolean;
}
export interface EgoEdge { source: string; target: string; weight: number }
export interface EgoGraph {
  root: string;
  nodes: EgoNode[];
  edges: EgoEdge[];
}

// --- Person profile ---
export interface CrimeRow {
  id: string; crime_type: string; crime_head: string; ipc_section: string;
  severity: string; district: string; datetime: string; status: string;
  mo_tags: string; weapon: string; lat: number | null; lon: number | null;
}
export interface Associate {
  person_id: string; name: string; gender: string; shared: number; top_shared_crime: string;
}
export interface NameCount { name: string; count: number }
export interface TimelinePoint { month: string; count: number }
export interface PersonProfile {
  person: {
    id: string; name: string; age: number | null; age_group: string;
    gender: string; address_district: string; role: string;
  };
  stats: {
    total_incidents: number; as_victim: number; first_seen: string | null;
    last_seen: string | null; districts: string[]; co_offenders: number;
    clearance_rate: number; weapon_incidents: number; top_crime: string | null;
  };
  threat: { score: number; level: string };
  crimes: CrimeRow[];
  timeline: TimelinePoint[];
  crime_mix: { by_type: NameCount[]; by_severity: NameCount[] };
  top_mo: NameCount[];
  associates: Associate[];
}
export interface RelationshipShared {
  id: string; crime_type: string; severity: string; district: string; datetime: string; status: string;
}
export interface Relationship { a: string; b: string; shared: RelationshipShared[] }
export interface AskResponse {
  question: string; answer: string; provider: string; model: string; grounded_on: string[];
}

// --- Enriched analytics ---
export interface Summary {
  total_incidents: number; districts: number; crime_types: number;
  clearance_rate: number; cyber_share: number; severe_share: number;
  weapon_share: number; avg_fir_delay: number;
  top_district: string | null; top_district_count: number;
  top_crime: string | null; top_crime_count: number;
}
export interface CrimeTypeCount {
  crime_type: string; crime_head: string; severity: string; count: number;
}
export interface CrimeHeadCount { crime_head: string; count: number; }
export interface StatusCount { status: string; count: number; cleared: boolean; }
export interface SeverityCount { severity: string; count: number; }
export type MonthPoint = { month: string; total: number } & Record<string, number | string>;
export interface GroupCount { group: string; count: number; }
export interface GenderCount { gender: string; count: number; }
export interface Demographics {
  victim_age_groups: GroupCount[];
  offender_age_groups: GroupCount[];
  victim_gender: GenderCount[];
  offender_gender: GenderCount[];
  urban_rural: GroupCount[];
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
  person: (personId: string) => get<PersonProfile>(`/api/network/person/${personId}`),
  relationship: (a: string, b: string) => get<Relationship>(`/api/network/relationship/${a}/${b}`),
  riskScores: () => get<{ method: string; items: RiskScore[] }>("/api/predictive/risk-scores"),
  ask: (question: string) => post<AskResponse>("/api/assistant/ask", { question }),

  // Enriched analytics
  summary: () => get<Summary>("/api/analytics/summary"),
  byCrimeType: () => get<{ items: CrimeTypeCount[] }>("/api/analytics/by-crime-type"),
  byCrimeHead: () => get<{ items: CrimeHeadCount[] }>("/api/analytics/by-crime-head"),
  byStatus: () => get<{ items: StatusCount[]; clearance_rate: number }>("/api/analytics/by-status"),
  bySeverity: () => get<{ items: SeverityCount[] }>("/api/analytics/by-severity"),
  byMonth: () => get<{ heads: string[]; items: MonthPoint[] }>("/api/analytics/by-month"),
  demographics: () => get<Demographics>("/api/analytics/demographics"),
};
