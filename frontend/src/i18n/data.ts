/**
 * Kannada labels for *data* values — the strings that arrive from the API rather than
 * being authored in the UI.
 *
 * Why these live client-side: the backend serves precomputed aggregates keyed by the
 * English district name / crime head, and those keys are load-bearing — MapLibre joins
 * features on them, `@cached` aggregates are warmed by them, and React lists key on
 * them. Translating server-side would fork every cache entry and break those joins. So
 * the English value stays the key everywhere and we translate only at paint.
 *
 * Vocabularies mirror `data/generator/generate_synthetic.py`, which follows `ERD_SCHEMA.md`.
 * Deliberately absent: person names, FIR / crime numbers, and Act-Section citations
 * ("IPC 302"), which stay English in both languages because that is how police record
 * them — transliterating an accused's name in a policing tool is an identity hazard.
 *
 * Review confidence: district names and common police vocabulary are well-established.
 * The crime sub-heads and case statuses are the entries worth checking against official
 * SCRB Kannada wording before the demo.
 */
import { useCallback } from "react";
import { useLang } from "./index";

export type LabelKind =
  | "district"
  | "state"
  | "crimeHead"
  | "crimeSubHead"
  | "caseStatus"
  | "gravity"
  | "category"
  | "gender"
  | "caste"
  | "religion"
  | "occupation"
  | "severity"
  | "rank"
  | "designation"
  | "urbanisation"
  | "funnelStage"
  | "funnelLeakage"
  | "timeBucket"
  | "arrestType";

/** Kannada only — English is the identity mapping, so there is nothing to store for it. */
const KN: Record<LabelKind, Record<string, string>> = {
  // ------------------------------------------------- Karnataka's 31 districts --
  district: {
    "Bengaluru City": "ಬೆಂಗಳೂರು ನಗರ",
    "Bengaluru Rural": "ಬೆಂಗಳೂರು ಗ್ರಾಮಾಂತರ",
    Mysuru: "ಮೈಸೂರು",
    Mandya: "ಮಂಡ್ಯ",
    Hassan: "ಹಾಸನ",
    Tumakuru: "ತುಮಕೂರು",
    Kolar: "ಕೋಲಾರ",
    Chikkaballapur: "ಚಿಕ್ಕಬಳ್ಳಾಪುರ",
    Ramanagara: "ರಾಮನಗರ",
    Chamarajanagar: "ಚಾಮರಾಜನಗರ",
    Chitradurga: "ಚಿತ್ರದುರ್ಗ",
    Davanagere: "ದಾವಣಗೆರೆ",
    Shivamogga: "ಶಿವಮೊಗ್ಗ",
    Chikkamagaluru: "ಚಿಕ್ಕಮಗಳೂರು",
    Udupi: "ಉಡುಪಿ",
    "Dakshina Kannada": "ದಕ್ಷಿಣ ಕನ್ನಡ",
    "Uttara Kannada": "ಉತ್ತರ ಕನ್ನಡ",
    Belagavi: "ಬೆಳಗಾವಿ",
    Bagalkot: "ಬಾಗಲಕೋಟೆ",
    Vijayapura: "ವಿಜಯಪುರ",
    Kalaburagi: "ಕಲಬುರಗಿ",
    Bidar: "ಬೀದರ್",
    Raichur: "ರಾಯಚೂರು",
    Koppal: "ಕೊಪ್ಪಳ",
    Ballari: "ಬಳ್ಳಾರಿ",
    Vijayanagara: "ವಿಜಯನಗರ",
    Yadgir: "ಯಾದಗಿರಿ",
    Gadag: "ಗದಗ",
    Haveri: "ಹಾವೇರಿ",
    Dharwad: "ಧಾರವಾಡ",
    Kodagu: "ಕೊಡಗು",
    // Neighbouring-state districts (out-of-state arrests)
    Pune: "ಪುಣೆ",
    Kolhapur: "ಕೊಲ್ಹಾಪುರ",
    Solapur: "ಸೊಲ್ಲಾಪುರ",
    Chennai: "ಚೆನ್ನೈ",
    Coimbatore: "ಕೊಯಮತ್ತೂರು",
    Krishnagiri: "ಕೃಷ್ಣಗಿರಿ",
    Anantapur: "ಅನಂತಪುರ",
    Kurnool: "ಕರ್ನೂಲು",
    Hyderabad: "ಹೈದರಾಬಾದ್",
    Mahbubnagar: "ಮಹಬೂಬ್‌ನಗರ",
    Kasaragod: "ಕಾಸರಗೋಡು",
    Kannur: "ಕಣ್ಣೂರು",
  },

  state: {
    Karnataka: "ಕರ್ನಾಟಕ",
    Maharashtra: "ಮಹಾರಾಷ್ಟ್ರ",
    "Tamil Nadu": "ತಮಿಳುನಾಡು",
    "Andhra Pradesh": "ಆಂಧ್ರಪ್ರದೇಶ",
    Telangana: "ತೆಲಂಗಾಣ",
    Kerala: "ಕೇರಳ",
  },

  // ------------------------------------------------------------- CrimeHead ----
  crimeHead: {
    "Crimes Against Body": "ದೇಹದ ವಿರುದ್ಧ ಅಪರಾಧಗಳು",
    "Crimes Against Property": "ಆಸ್ತಿಯ ವಿರುದ್ಧ ಅಪರಾಧಗಳು",
    "Crimes Against Women": "ಮಹಿಳೆಯರ ವಿರುದ್ಧ ಅಪರಾಧಗಳು",
    "Economic Offences": "ಆರ್ಥಿಕ ಅಪರಾಧಗಳು",
    "Cyber Crime": "ಸೈಬರ್ ಅಪರಾಧ",
    "Crimes Against Public Order": "ಸಾರ್ವಜನಿಕ ಸುವ್ಯವಸ್ಥೆಯ ವಿರುದ್ಧ ಅಪರಾಧಗಳು",
    "Special & Local Laws": "ವಿಶೇಷ ಮತ್ತು ಸ್ಥಳೀಯ ಕಾಯ್ದೆಗಳು",
    Others: "ಇತರೆ",
  },

  // ---------------------------------------------------------- CrimeSubHead ----
  crimeSubHead: {
    Murder: "ಕೊಲೆ",
    "Attempt to Murder": "ಕೊಲೆ ಯತ್ನ",
    "Assault / Grievous Hurt": "ಹಲ್ಲೆ / ಗಂಭೀರ ಗಾಯ",
    "Kidnapping / Abduction": "ಅಪಹರಣ",
    "Rash & Negligent Driving": "ಅಜಾಗರೂಕ ಮತ್ತು ನಿರ್ಲಕ್ಷ್ಯ ಚಾಲನೆ",
    Theft: "ಕಳ್ಳತನ",
    "House Burglary": "ಮನೆ ಕನ್ನ",
    Robbery: "ದರೋಡೆ",
    Dacoity: "ಡಕಾಯಿತಿ",
    "Chain Snatching": "ಸರಗಳ್ಳತನ",
    "Vehicle Theft": "ವಾಹನ ಕಳ್ಳತನ",
    "Outraging Modesty of Women": "ಮಹಿಳೆಯ ಮಾನಭಂಗ",
    "Cruelty / Dowry Harassment": "ಕ್ರೌರ್ಯ / ವರದಕ್ಷಿಣೆ ಕಿರುಕುಳ",
    "Cheating / Fraud": "ವಂಚನೆ / ಮೋಸ",
    "Criminal Breach of Trust": "ಕ್ರಿಮಿನಲ್ ನಂಬಿಕೆ ದ್ರೋಹ",
    Extortion: "ಸುಲಿಗೆ",
    "Online Financial Fraud": "ಆನ್‌ಲೈನ್ ಆರ್ಥಿಕ ವಂಚನೆ",
    "Identity Theft / Impersonation": "ಗುರುತು ಕಳ್ಳತನ / ಸೋಗು",
    "Obscene Electronic Content": "ಅಶ್ಲೀಲ ಎಲೆಕ್ಟ್ರಾನಿಕ್ ವಿಷಯ",
    "Rioting / Unlawful Assembly": "ಗಲಭೆ / ಕಾನೂನುಬಾಹಿರ ಸಭೆ",
    "Drunken / Riotous Behaviour": "ಕುಡಿದು ಗಲಾಟೆ ಮಾಡುವ ವರ್ತನೆ",
    "NDPS - Drug Offence": "ಎನ್‌ಡಿಪಿಎಸ್ — ಮಾದಕ ವಸ್ತು ಅಪರಾಧ",
    "Arms Act Violation": "ಶಸ್ತ್ರಾಸ್ತ್ರ ಕಾಯ್ದೆ ಉಲ್ಲಂಘನೆ",
    "Gambling (KP Act)": "ಜೂಜಾಟ (ಕೆ.ಪಿ. ಕಾಯ್ದೆ)",
    "Unnatural Death (UDR)": "ಅಸಹಜ ಸಾವು (ಯು.ಡಿ.ಆರ್.)",
    "Public Nuisance (Petty Case)": "ಸಾರ್ವಜನಿಕ ಕಿರಿಕಿರಿ (ಸಣ್ಣ ಪ್ರಕರಣ)",
  },

  // ------------------------------------------------------ CaseStatusMaster ----
  caseStatus: {
    "Under Investigation": "ತನಿಖೆಯಲ್ಲಿದೆ",
    "Charge Sheeted": "ದೋಷಾರೋಪ ಪಟ್ಟಿ ಸಲ್ಲಿಕೆ",
    "Pending Trial": "ವಿಚಾರಣೆ ಬಾಕಿ",
    Convicted: "ಶಿಕ್ಷೆಯಾಗಿದೆ",
    Acquitted: "ಖುಲಾಸೆ",
    "Closed - False Case": "ಮುಕ್ತಾಯ — ಸುಳ್ಳು ಪ್ರಕರಣ",
    "Closed - Undetected": "ಮುಕ್ತಾಯ — ಪತ್ತೆಯಾಗಿಲ್ಲ",
    "Closed - Others": "ಮುಕ್ತಾಯ — ಇತರೆ",
    Transferred: "ವರ್ಗಾವಣೆ",
  },

  gravity: {
    Heinous: "ಘೋರ",
    "Non-Heinous": "ಘೋರವಲ್ಲದ",
  },

  category: {
    FIR: "ಎಫ್‌ಐಆರ್",
    UDR: "ಯು.ಡಿ.ಆರ್.",
    "Zero FIR": "ಶೂನ್ಯ ಎಫ್‌ಐಆರ್",
    PAR: "ಪಿ.ಎ.ಆರ್.",
  },

  gender: {
    Male: "ಪುರುಷ",
    Female: "ಮಹಿಳೆ",
    Other: "ಇತರೆ",
    Unknown: "ತಿಳಿದಿಲ್ಲ",
    "Not Stated": "ನಮೂದಿಸಿಲ್ಲ",
  },

  caste: {
    General: "ಸಾಮಾನ್ಯ",
    OBC: "ಒ.ಬಿ.ಸಿ.",
    SC: "ಎಸ್.ಸಿ.",
    ST: "ಎಸ್.ಟಿ.",
    Others: "ಇತರೆ",
    "Not Stated": "ನಮೂದಿಸಿಲ್ಲ",
  },

  religion: {
    Hindu: "ಹಿಂದೂ",
    Muslim: "ಮುಸ್ಲಿಂ",
    Christian: "ಕ್ರಿಶ್ಚಿಯನ್",
    Jain: "ಜೈನ",
    Sikh: "ಸಿಖ್",
    Buddhist: "ಬೌದ್ಧ",
    Others: "ಇತರೆ",
    "Not Stated": "ನಮೂದಿಸಿಲ್ಲ",
  },

  occupation: {
    Farmer: "ರೈತ",
    "Daily Wage Labourer": "ದಿನಗೂಲಿ ಕಾರ್ಮಿಕ",
    "Private Employee": "ಖಾಸಗಿ ಉದ್ಯೋಗಿ",
    "Government Employee": "ಸರ್ಕಾರಿ ಉದ್ಯೋಗಿ",
    "Business / Trader": "ವ್ಯಾಪಾರ / ವರ್ತಕ",
    Student: "ವಿದ್ಯಾರ್ಥಿ",
    Homemaker: "ಗೃಹಿಣಿ",
    Driver: "ಚಾಲಕ",
    "IT Professional": "ಐ.ಟಿ. ವೃತ್ತಿಪರ",
    Unemployed: "ನಿರುದ್ಯೋಗಿ",
    Retired: "ನಿವೃತ್ತ",
    Others: "ಇತರೆ",
  },

  /** Also covers the risk tiers, which share the High / Medium / Low vocabulary. */
  severity: {
    Critical: "ಗಂಭೀರ",
    Elevated: "ಏರಿಕೆ",
    High: "ಹೆಚ್ಚು",
    Medium: "ಮಧ್ಯಮ",
    Low: "ಕಡಿಮೆ",
  },

  rank: {
    "Director General of Police": "ಪೊಲೀಸ್ ಮಹಾನಿರ್ದೇಶಕರು",
    "Inspector General of Police": "ಪೊಲೀಸ್ ಮಹಾನಿರೀಕ್ಷಕರು",
    "Superintendent of Police": "ಪೊಲೀಸ್ ವರಿಷ್ಠಾಧಿಕಾರಿ",
    "Deputy Superintendent of Police": "ಪೊಲೀಸ್ ಉಪಾಧೀಕ್ಷಕರು",
    "Police Inspector": "ಪೊಲೀಸ್ ನಿರೀಕ್ಷಕರು",
    "Police Sub-Inspector": "ಪೊಲೀಸ್ ಉಪ-ನಿರೀಕ್ಷಕರು",
    "Assistant Sub-Inspector": "ಸಹಾಯಕ ಉಪ-ನಿರೀಕ್ಷಕರು",
    "Head Constable": "ಮುಖ್ಯ ಪೇದೆ",
    "Police Constable": "ಪೊಲೀಸ್ ಪೇದೆ",
    "Commissioner of Police": "ಪೊಲೀಸ್ ಆಯುಕ್ತರು",
    "Deputy Commissioner of Police": "ಪೊಲೀಸ್ ಉಪ ಆಯುಕ್ತರು",
    "Assistant Commissioner of Police": "ಸಹಾಯಕ ಪೊಲೀಸ್ ಆಯುಕ್ತರು",
  },

  designation: {
    "Station House Officer": "ಠಾಣಾ ಮುಖ್ಯಾಧಿಕಾರಿ",
    "Investigating Officer": "ತನಿಖಾಧಿಕಾರಿ",
    "Circle Inspector": "ವೃತ್ತ ನಿರೀಕ್ಷಕರು",
    "Superintendent of Police": "ಪೊಲೀಸ್ ವರಿಷ್ಠಾಧಿಕಾರಿ",
    "Station Writer": "ಠಾಣಾ ಬರಹಗಾರ",
    "Beat Constable": "ಬೀಟ್ ಪೇದೆ",
    "Commissioner of Police": "ಪೊಲೀಸ್ ಆಯುಕ್ತರು",
    "Deputy Commissioner of Police": "ಪೊಲೀಸ್ ಉಪ ಆಯುಕ್ತರು",
    "Sub-Divisional Police Officer": "ಉಪ-ವಿಭಾಗೀಯ ಪೊಲೀಸ್ ಅಧಿಕಾರಿ",
  },

  urbanisation: {
    metro: "ಮಹಾನಗರ",
    urban: "ನಗರ",
    semiurban: "ಅರೆ-ನಗರ",
    rural: "ಗ್ರಾಮೀಣ",
    border: "ಗಡಿ ಪ್ರದೇಶ",
  },

  // Investigation-funnel stage and leakage labels (routers/analytics.py case_funnel).
  // Fixed enum-like values, so they belong here rather than in the UI catalog.
  funnelStage: {
    "Cases registered": "ದಾಖಲಾದ ಪ್ರಕರಣಗಳು",
    "Final report filed": "ಅಂತಿಮ ವರದಿ ಸಲ್ಲಿಕೆ",
    "Chargesheeted (A)": "ದೋಷಾರೋಪ ಪಟ್ಟಿ (ಎ)",
    "In trial": "ವಿಚಾರಣೆಯಲ್ಲಿ",
    "Disposed by court": "ನ್ಯಾಯಾಲಯದಿಂದ ಇತ್ಯರ್ಥ",
    Convicted: "ಶಿಕ್ಷೆಯಾಗಿದೆ",
  },

  funnelLeakage: {
    "Under investigation": "ತನಿಖೆಯಲ್ಲಿದೆ",
    "False case (B report)": "ಸುಳ್ಳು ಪ್ರಕರಣ (ಬಿ ವರದಿ)",
    "Undetected (C report)": "ಪತ್ತೆಯಾಗಿಲ್ಲ (ಸಿ ವರದಿ)",
    Acquitted: "ಖುಲಾಸೆ",
    "Transferred / others": "ವರ್ಗಾವಣೆ / ಇತರೆ",
  },

  /** Modus-operandi time-of-day buckets (services/mo.py TIME_BUCKETS). */
  timeBucket: {
    Night: "ರಾತ್ರಿ",
    Morning: "ಬೆಳಿಗ್ಗೆ",
    Afternoon: "ಮಧ್ಯಾಹ್ನ",
    Evening: "ಸಂಜೆ",
  },

  arrestType: {
    Arrest: "ಬಂಧನ",
    Surrender: "ಶರಣಾಗತಿ",
  },
};

export type DataLabelFn = (kind: LabelKind, value: string | null | undefined) => string;

/**
 * `const d = useDataLabel();` then `d("district", row.district)`.
 *
 * Falls back to the raw English value when a key is missing, never to a placeholder —
 * the synthetic generator and real SCRB extracts can both emit values this map does not
 * cover, and an untranslated crime head reading in English beats one reading as a key.
 */
export function useDataLabel(): DataLabelFn {
  const { lang } = useLang();
  return useCallback(
    (kind: LabelKind, value: string | null | undefined) => {
      if (!value) return "";
      if (lang === "en") return value;
      return KN[kind][value] ?? value;
    },
    [lang]
  );
}

/**
 * Which `LabelKind` each backend template parameter name refers to. Anything not listed
 * (counts, percentages, months, z-scores) is interpolated verbatim.
 */
const PARAM_KINDS: Record<string, LabelKind> = {
  district: "district",
  sub_head: "crimeSubHead",
  subHead: "crimeSubHead",
  crime_head: "crimeHead",
  status: "caseStatus",
  severity: "severity",
};

/**
 * Translate the *values* inside a backend `params` object before interpolating them
 * into a template — otherwise a Kannada anomaly sentence would still name its district
 * in English. Numbers and unrecognised keys pass through untouched.
 */
export function translateParams(
  params: Record<string, string | number> | undefined,
  d: DataLabelFn
): Record<string, string | number> | undefined {
  if (!params) return params;
  const out: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(params)) {
    const kind = PARAM_KINDS[key];
    out[key] = kind && typeof value === "string" ? d(kind, value) : value;
  }
  return out;
}
