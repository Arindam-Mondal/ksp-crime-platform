// Typed API client for the FIR-ERD backend.
// - Dev: leave VITE_API_BASE unset → relative paths, Vite proxies /api + /health to :9000.
// - Prod (SPA on Slate, API on AppSail): set VITE_API_BASE to the API origin at build time,
//   e.g. VITE_API_BASE=https://<project>.catalystserverless.com  (or your API Gateway URL).
const API_BASE = String(((import.meta as any).env?.VITE_API_BASE ?? "")).replace(/\/$/, "");

async function get<T>(path: string): Promise<T> {
  const res = await fetch(API_BASE + path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// --- shared shapes ---
export interface NameCount { name: string; count: number }
export interface GroupCount { group: string; count: number }
export interface HourCount { hour: number; count: number }
export interface MonthCount { month: string; count: number }

// --- cases ---
export interface CaseRow {
  id: number; crime_no: string; case_no: string; category: string; gravity: string;
  head: string; sub_head: string; status: string; district: string; station: string;
  registered: string; incident: string; sections: string[];
  n_victims: number; n_accused: number; n_arrests: number; cstype: string;
  lat: number | null; lon: number | null;
}
export interface Meta {
  districts: string[]; heads: string[]; sub_heads: string[];
  categories: string[]; statuses: string[];
}

// --- analytics ---
export interface Summary {
  total_cases: number; fir_cases: number; districts: number; police_stations: number;
  chargesheet_rate: number; pendency_rate: number; conviction_rate: number;
  heinous_share: number; cyber_share: number; avg_report_delay_days: number;
  median_days_to_chargesheet: number; arrests_total: number; repeat_offenders: number;
  top_district: string | null; top_district_count: number;
  top_sub_head: string | null; top_sub_head_count: number;
}
export interface CrimeHeadCount { crime_head: string; count: number }
export interface SubHeadCount {
  sub_head: string; crime_head: string; count: number;
  heinous_share: number; chargesheet_rate: number;
}
export interface CategoryCount { category: string; count: number }
export interface GravityCount { gravity: string; count: number }
export interface StatusCount { status: string; count: number; in_court: boolean }
export interface FunnelStage { stage: string; count: number }
export interface FunnelLeak { label: string; count: number }
export interface CaseFunnel { stages: FunnelStage[]; leakage: FunnelLeak[] }
export type MonthPoint = { month: string; total: number } & Record<string, number | string>;
export interface SectionCount {
  act: string; section: string; label: string; description: string; count: number;
}
export interface ArrestAnalytics {
  total: number; arrests: number; surrenders: number; out_of_state: number;
  by_month: MonthCount[];
  days_to_arrest_by_head: { crime_head: string; median_days_to_arrest: number; arrained_cases: number }[];
  top_districts: { district: string; count: number }[];
}
export interface OfficerRow {
  employee_id: number; name: string; rank: string; station: string; district: string;
  chargesheets: number; arrests: number; chargesheet_success: number;
}
export interface OfficerWorkload {
  total_employees: number; active_investigators: number;
  by_rank: { rank: string; count: number }[]; top: OfficerRow[];
}
export interface CourtRow {
  court: string; district: string; cases: number;
  pending_trial: number; convicted: number; acquitted: number;
}
export interface Demographics {
  victim_age_groups: GroupCount[]; accused_age_groups: GroupCount[];
  victim_gender: GroupCount[]; accused_gender: GroupCount[];
  police_victims: number;
  complainant_occupation: GroupCount[]; complainant_religion: GroupCount[];
  complainant_caste: GroupCount[]; complainant_gender: GroupCount[];
}
export interface InvestigationTiming {
  report_delay: { sub_head: string; avg_days: number; cases: number }[];
  days_to_chargesheet: { crime_head: string; median_days: number; cases: number }[];
}

// --- hotspots ---
export interface DistrictCount { district: string; cases: number }
export interface HotspotCell { lat: number; lon: number; count: number }
export interface DistrictStat {
  district: string; cases: number; per_100k: number | null; heinous_share: number;
  chargesheet_rate: number; pendency_rate: number; recent_90d: number; risk_score: number;
  lat: number | null; lon: number | null;
}
export interface StationBreakdown {
  district: string; total: number;
  stations: { station: string; cases: number; heinous: number; lat: number | null; lon: number | null }[];
  by_type: NameCount[];
  by_hour: HourCount[];
}

// --- socio-economic correlation ---
export interface SocioItem {
  district: string; cases: number; per_100k: number; population: number;
  urban_pct: number; literacy_pct: number; pop_density: number;
  rate_rank: number; volume_rank: number; rank_shift: number;
}
export interface SocioCorrelations {
  urbanization: number | null; literacy: number | null; density: number | null;
}
export interface Socioeconomic {
  items: SocioItem[]; correlations: SocioCorrelations; method: string;
}

// --- modus operandi ---
export interface MoSignature {
  n_cases: number;
  top_crimes: { name: string; share: number }[];
  time_profile: { bucket: string; count: number }[];
  dominant_time: string | null;
  top_sections: string[];
  heinous_share: number;
  jurisdictions: string[];
}
export interface MoMatch {
  person_id: string; name: string; gender: string; cases: number; similarity: number;
  shared_crimes: string[]; shared_sections: number; districts: string[];
  different_jurisdiction: boolean; is_associate: boolean;
}
export interface MoProfile { signature: MoSignature; matches: MoMatch[] }

// --- network / person ---
export interface OffenderCount {
  person_id: string; name: string; gender: string; cases: number;
  arrests: number; districts: number; associates: number; community_id: number | null;
}
export interface EgoNode { id: string; name: string; gender: string; cases: number; is_root: boolean; community_id: number | null }
export interface EgoEdge { source: string; target: string; weight: number }
export interface EgoGraph { root: string; nodes: EgoNode[]; edges: EgoEdge[] }

export interface Community {
  id: number; size: number; members: string[]; districts: string[]; total_cases: number;
}

export interface CrimeRow {
  id: number; crime_no: string; sub_head: string; head: string; gravity: string;
  sections: string[]; district: string; station: string; datetime: string;
  status: string; cstype: string; lat: number | null; lon: number | null;
}
export interface Associate {
  person_id: string; name: string; gender: string; shared: number; top_shared_crime: string;
}
export interface ArrestEvent {
  date: string; type: string; district: string; state: string;
  crime_no: string; sub_head: string;
}
export interface TimelinePoint { month: string; count: number }
export interface PersonProfile {
  person: { id: string; name: string; gender: string; age: number | null; districts: string[] };
  stats: {
    total_cases: number; heinous_cases: number; first_seen: string | null;
    last_seen: string | null; districts: string[]; co_accused: number;
    arrests: number; surrenders: number; chargesheet_rate: number; top_crime: string | null;
  };
  threat: { score: number; level: string };
  crimes: CrimeRow[];
  arrest_history: ArrestEvent[];
  timeline: TimelinePoint[];
  crime_mix: { by_type: NameCount[]; by_head: NameCount[] };
  top_sections: NameCount[];
  associates: Associate[];
}
export interface RelationshipShared {
  id: number; crime_no: string; sub_head: string; gravity: string;
  district: string; datetime: string; status: string;
}
export interface Relationship { a: string; b: string; shared: RelationshipShared[] }

// --- alerts / anomalies ---
export interface SpikeAlert {
  district: string; sub_head: string; recent: number; baseline: number;
  ratio: number; z: number; severity: string; lat: number | null; lon: number | null;
  last_seen: string;
}
export interface Anomaly {
  kind: string; subject: string; period: string; observed: number;
  expected: number; z: number; severity: string; description: string;
  /**
   * Catalog key + values for rendering `description` in the active language. Optional
   * so an older/leaner backend response still renders — the UI falls back to the
   * English `description`, which stays authoritative for LLM grounding either way.
   */
  template?: string;
  params?: Record<string, string | number>;
}

// --- AI intelligence report ---
/** `label` is the English rendering; `label_key` (optional, for older responses) is the
 *  catalog key so the KPI can be shown in the reader's language. */
export interface ReportKpi { label: string; label_key?: string; value: string }
export interface IntelReport {
  scope: string; subject: string; subject_id: string | null; generated_at: string;
  /** How to label `subject`: a district name translates, a person's name never does. */
  subject_kind?: "district" | "person" | "state";
  narrative: string; provider: string; model: string;
  kpis: ReportKpi[];
  hotspots: { district: string; cases: number; risk_score: number }[];
  offenders: { person_id: string; name: string; cases: number }[];
  alerts: SpikeAlert[];
  anomalies: Anomaly[];
}
export interface AskResponse {
  question: string; answer: string; provider: string; model: string; grounded_on: string[];
}

export const api = {
  health: () => get<{ status: string; data_mode: string; cases_loaded: number }>("/health"),
  meta: () => get<Meta>("/api/cases/meta"),
  cases: (params: string = "") => get<{ total: number; items: CaseRow[] }>("/api/cases" + params),

  // Analytics
  summary: () => get<Summary>("/api/analytics/summary"),
  byCrimeHead: () => get<{ items: CrimeHeadCount[] }>("/api/analytics/by-crime-head"),
  bySubHead: () => get<{ items: SubHeadCount[] }>("/api/analytics/by-sub-head"),
  byCategory: () => get<{ items: CategoryCount[] }>("/api/analytics/by-category"),
  byGravity: () => get<{ items: GravityCount[] }>("/api/analytics/by-gravity"),
  byStatus: () =>
    get<{ items: StatusCount[]; chargesheet_rate: number; pendency_rate: number }>("/api/analytics/by-status"),
  caseFunnel: () => get<CaseFunnel>("/api/analytics/case-funnel"),
  byMonth: () => get<{ heads: string[]; items: MonthPoint[] }>("/api/analytics/by-month"),
  topSections: () => get<{ items: SectionCount[] }>("/api/analytics/top-sections"),
  arrests: () => get<ArrestAnalytics>("/api/analytics/arrests"),
  officers: () => get<OfficerWorkload>("/api/analytics/officers"),
  courts: () => get<{ total_courts: number; items: CourtRow[] }>("/api/analytics/courts"),
  demographics: () => get<Demographics>("/api/analytics/demographics"),
  investigation: () => get<InvestigationTiming>("/api/analytics/investigation"),
  socioeconomic: () => get<Socioeconomic>("/api/analytics/socioeconomic"),

  // Hotspots
  byDistrict: () => get<{ items: DistrictCount[] }>("/api/hotspots/by-district"),
  cells: () => get<{ items: HotspotCell[] }>("/api/hotspots/cells"),
  byHour: (subHead?: string) =>
    get<{ items: HourCount[] }>("/api/hotspots/by-hour" + (subHead ? `?sub_head=${encodeURIComponent(subHead)}` : "")),
  districts: () => get<{ items: DistrictStat[] }>("/api/hotspots/districts"),
  stations: (district: string) =>
    get<StationBreakdown>(`/api/hotspots/stations?district=${encodeURIComponent(district)}`),

  // Network
  topOffenders: () => get<{ items: OffenderCount[] }>("/api/network/top-offenders"),
  ego: (personId: string) => get<EgoGraph>(`/api/network/ego/${personId}`),
  communities: () => get<{ clusters: Community[]; total_clusters: number }>("/api/network/communities"),
  person: (personId: string) => get<PersonProfile>(`/api/network/person/${personId}`),
  mo: (personId: string) => get<MoProfile>(`/api/network/mo/${personId}`),
  relationship: (a: string, b: string) => get<Relationship>(`/api/network/relationship/${a}/${b}`),

  // Predictive / alerts
  riskScores: () => get<{ method: string; items: DistrictStat[] }>("/api/predictive/risk-scores"),
  anomalies: () => get<{ method: string; count: number; items: Anomaly[] }>("/api/predictive/anomalies"),
  spikes: () => get<{ count: number; items: SpikeAlert[] }>("/api/alerts/spikes"),

  // NL query + report. `lang` is the only place the reader's language reaches the API:
  // it changes generated text, and both endpoints are uncached, so unlike the aggregate
  // endpoints there is no cache to fork. Everything else stays English-keyed.
  ask: (question: string, lang: string = "en") =>
    post<AskResponse>("/api/assistant/ask", { question, lang }),
  report: (scope: string, id?: string, lang: string = "en") =>
    post<IntelReport>("/api/report", { scope, id, lang }),
};
