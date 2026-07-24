# Design: Rebuild the platform on the official Police FIR ERD

Date: 2026-07-24 · Status: approved-by-directive (user instructed the rewrite; session is autonomous)

## Goal

The challenge organisers provided `Police_FIR_ER_Diagram.pdf` — the real CCTNS-style FIR
schema. The platform must (a) **strictly follow that ERD** as its data model, (b) generate
rich synthetic data for every ERD table, and (c) use the extra entities the ERD unlocks
(arrests, chargesheets, acts/sections, courts, officers, complainant demographics) to make the
analytics genuinely data-intensive rather than cosmetic.

Full transcription of the ERD lives in `ERD_SCHEMA.md` (26 tables).

## What changes vs. the old model

Old synthetic model (4 flat tables: `incidents`, `persons`, `incident_persons`, `locations`)
is replaced by the 26-table ERD. Everything downstream is rebuilt on it.

## Architecture decision

Keep the existing precompute-and-serve shape and the local/catalyst dual mode. Add one new
backend service, `app/services/firdata.py`, which:

1. loads every ERD CSV via the existing `datastore.get_store().rows(<TableName>)`;
2. builds lookup dicts (district, unit, status, category, gravity, head, subhead, court,
   employee, rank, occupation, religion, act/section);
3. materialises a **denormalised case view** (one dict per `CaseMaster` row with resolved
   names, party counts, arrest/chargesheet facts, derived fields: report-delay days,
   days-to-first-arrest, days-to-chargesheet, month, hour) — cached with `lru_cache`;
4. builds a **resolved-offender index**: `Accused` rows are per-case, so the same physical
   person is identified across cases by exact (AccusedName, GenderID) match — the generator
   draws repeat offenders from a fixed identity pool to make this resolvable, mirroring
   real-world name-based entity resolution on FIR data.

Routers read the case view / indexes only. On Catalyst the same view rows become an aggregate
table written by the Cron functions (precompute-and-serve unchanged).

## Synthetic data generator (rewrite)

`data/generator/generate_synthetic.py` emits one CSV per ERD table, column names exactly per
`ERD_SCHEMA.md`. Realism/enrichment kept from the old generator and extended:

- Geography: 31 Karnataka districts (+ neighbouring states for out-of-state arrests), with
  archetypes (metro/urban/semiurban/rural/border) driving per-district crime mix and volume;
  station coordinates jittered around district centroids; case lat/lon clustered around
  per-district hotspot cells.
- Legal layer: real acts (IPC, IT Act, NDPS, Arms Act, POCSO, JJ Act, KP Act, MV Act, Dowry
  Prohibition Act…) with real section numbers; ~24 crime sub-heads under 7 crime heads;
  `CrimeHeadActSection` mapping; each case gets 1–4 `ActSectionAssociation` rows driven by
  its sub-head.
- Case lifecycle: IncidentFromDate → InfoReceivedPSDate (reporting delay, crime-dependent) →
  CrimeRegisteredDate → arrests (probability and lag depend on gravity/sub-head) →
  chargesheet (`ChargesheetDetails` with A/B/C final-report types) → court assignment; case
  status consistent with these events.
- Temporal structure: growth + seasonality + weekend uplift, rising cyber/fraud trend, one
  emerging spike (district × sub-head) in the last 30 days.
- Parties: complainants (occupation/religion/caste/gender/age), victims and accused with
  crime-specific age/gender profiles; repeat-offender identity pool (~12%) that recurs across
  cases and co-offends → real network structure; occasional victim-is-police flag.
- Organisation: units per district (PS under Circle under District HQ via `ParentUnit`),
  employees with rank/designation, courts per district; FIRs registered by SHO-side
  employees; arrests by IOs.

Scale defaults: ~20k cases, ~900 units/employees, all masters. Stdlib only, seeded.

## Backend rewrite

- `services/firdata.py` (new) as above; `services/datastore.py` unchanged.
- `routers/incidents.py` → `/api/cases` semantics (paths kept: list, meta) serving case-view
  rows (CrimeNo, category, gravity, head/subhead, status, unit, district, dates, sections).
- `routers/analytics.py` — enriched: summary KPIs (cases, detection/chargesheet rates, mean
  report delay, mean days-to-chargesheet, arrests); by-crime-head/sub-head; case-category
  mix; gravity split; status funnel (registered → under investigation → chargesheeted /
  false / undetected → in court); by-month stacked by head; top act-sections; demographics
  (victim/accused age-gender, complainant occupation/religion); officer/court load
  (FIRs per IO rank band, court caseload).
- `routers/hotspots.py` — district choropleth + grid cells from CaseMaster lat/lon; station
  drill-down (unit stats, top sub-heads, hourly profile); by-hour.
- `routers/network.py` — co-accused graph over resolved offenders; person profile (cases,
  timeline, sections invoked, arrest history, associates, threat heuristic); relationship
  detail.
- `routers/predictive.py` + `alerts.py` — same statistical methods re-keyed to
  (district, sub-head); risk score uses volume + heinous share + detection rate.
- `routers/assistant.py` / `report.py` — retrieval over `BriefFacts`; report KPIs from the
  new summary.
- `services/aggregations.py` and `functions/common/aggregations.py` mirrors updated to the
  new field names.

## Frontend rewrite

`lib/api.ts` types re-generated for the new payloads. Pages updated: Dashboard (KPIs +
funnel + category/gravity + acts), Hotspots (unchanged UX, new fields), Network (resolved
offenders), PersonProfile (adds arrest/section history), Predictive, Demographics (adds
complainant occupation/religion + victim/accused panels), Reports, Assistant. New panels only
where the ERD adds real analytical value (funnel, acts/sections, arrests, officer/court load).

## Docs

- `ERD_SCHEMA.md` (new, authoritative transcription).
- `CLAUDE.md` + `project_tech_stack.md` §5 data-model sections updated to point at it.
- `challange.md`, `zoho_resources.md` untouched (hard rule).

## Verification

Regenerate data; `uvicorn` backend serves all endpoints without error; `npm run build`
passes; spot-check numbers (counts, funnel consistency: chargesheeted ≤ cases with FIR
category, arrests only for cases with accused, CrimeNo format round-trips).
