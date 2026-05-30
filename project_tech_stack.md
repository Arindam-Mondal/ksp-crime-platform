# KSP Crime Intelligence Platform — Tech Stack & Architecture

> Reference document for our hackathon submission: an **AI-Driven Crime Analytics & Visualization Platform** for the Karnataka State Police (KSP) / State Crime Records Bureau (SCRB). See `challange.md` for the problem statement and `zoho_resources.md` for the full Catalyst service mapping.

---

## 1. Guiding constraints

1. **Zoho Catalyst deployment is mandatory.** Where a Catalyst service matches a capability, we use it — a 3rd-party substitute "may affect validity." (Exception: capabilities Catalyst has **no** service for — maps, graph rendering — are done client-side.)
2. **Budget = the one-time $250 Catalyst credit** (valid ~60 days from claim) on top of the monthly free tier. No spend outside Catalyst (no external Claude API at runtime).
3. **Not overkill.** Pick the smallest stack that cleanly delivers the four hero features and is easy to build, deploy, and debug live.

---

## 2. Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| AI/LLM runtime | **Catalyst QuickML** (LLM Serving + RAG, Qwen 2.5) | Compliant + inside credits; no external Claude API at runtime |
| Hero features | Geospatial hotspots · Network/link analysis · Predictive & anomaly AI · NL query + AI reports | Covers all 6 challenge capabilities through 4 demoable pillars |
| Data | **Synthetic Karnataka dataset** we generate | No privacy issues, full control of demo patterns |
| Backend | **AppSail — single Python FastAPI app** | Normal web server handles heavy ML libs natively; no serverless package/timeout friction |
| Frontend | **React + Vite + TypeScript + Tailwind** on Catalyst Slate | Modern, fast, Git auto-deploy + free SSL |
| Maps / Graph | **MapLibre GL JS** + **Cytoscape.js** | Best visual + analytical fit; Catalyst has no native map/graph service |

---

## 3. Architecture & service mapping

| Layer | Technology | Catalyst service |
|---|---|---|
| Frontend | React + Vite + TS, Tailwind; MapLibre GL JS (OSM tiles), Cytoscape.js, Recharts, TanStack Query | **Slate** |
| API | Python **FastAPI** (single service) | **AppSail** (managed Python runtime) |
| Heavy compute | Python jobs: spatiotemporal clustering, graph build, risk scoring, spike detection | **Serverless Functions** — Cron + Event |
| Auth | Role-based: SCRB admin / district officer / investigator | **Catalyst Authentication** |
| API routing | Throttling / keys in front of AppSail | **API Gateway** |
| Relational data | Crime records + precomputed aggregates (ZCQL) | **Data Store** |
| Object storage | CSV uploads, GeoJSON, generated PDFs | **Stratus** |
| Cache | Hot aggregates (district stats, hotspot grids) | **Cache** |
| LLM / RAG | NL query, report narratives, knowledge base | **QuickML** (LLM Serving + RAG) |
| Predictive ML | Tabular risk scoring & emerging-typology forecast | **Zia AutoML** |
| Text analytics | NER / keyword extraction from FIR narratives | **Zia Services** |
| PDF reports | HTML → PDF intelligence report | **SmartBrowz** |
| Email / alerts | Report delivery + trend-spike alerts | **Mail** + **Push Notifications** |
| Orchestration *(optional)* | ingest → enrich → score → index | **Circuits** |
| CI/CD *(optional)* | auto-deploy | **Pipelines** |

### Core architectural pattern: precompute-and-serve

Heavy math (DBSCAN/KDE hotspots, networkx centrality, AutoML scoring, anomaly/spike detection) runs in **Cron/Event functions** (15-min timeout) and writes compact results to aggregate tables. The **FastAPI request path only reads precomputed aggregates** — this sidesteps Data Store's 300-rows-per-query cap and the 30s request timeout, and keeps the UI fast.

**Client-side rendering** of maps (MapLibre + free OpenStreetMap tiles) and the network graph (Cytoscape.js) is the correct choice because Catalyst offers no geospatial or graph service — it is not a banned 3rd-party substitution.

---

## 4. Catalyst constraints (verified from docs)

- **Free tier (monthly, account-wide):** Data Store 2 GB + 10K SELECT / 5K INSERT / 1K UPDATE / 1K DELETE; Functions 25K GB-s; AppSail 15 GB-hr; Stratus 5 GB; API Gateway 100K req; Mail 100; Push 500. **$5/project/month** minimum billing once a project exceeds free tier.
- **Data Store:** relational, ZCQL; **max 300 rows/query** (paginate), 100 cols/table, 10K-char text fields.
- **Functions:** Python / Node / Java; AdvancedIO request timeout **30s**; Cron/Event up to **15 min**; 128 MB–1 GB.
- **AppSail:** managed Node/Java/Python or custom Docker; ~$0.08/GB-hr; warm ~5 min; max 5 instances.
- **QuickML LLM Serving + RAG:** early-access; models = Qwen 2.5 (14B Instruct / 7B Coder / 7B Vision); **pricing undisclosed → the one budget unknown.**
- **$250 credit valid ~60 days** from claim.

### Budget strategy ($250)
- AppSail + functions stay within free tier at demo scale; static frontend negligible.
- Keep the synthetic dataset modest (~50–150K rows) to stay inside the 2 GB / free-tier limits.
- **Biggest risk = QuickML LLM/RAG endpoints.** Gate all LLM calls behind one interface, keep prompts small, spin endpoints up only during dev/demo and tear them down after, and confirm early-access is enabled on day 1.
- Train Zia AutoML a handful of times (not in a loop). Cache aggregates to cut DB/function calls.

---

## 5. Data model (Data Store, synthetic)

**Core tables**
- `incidents` (id, crime_type, ipc_section, district, station, lat, lon, datetime, mo_tags, narrative, status)
- `persons` (id, role = offender | victim, name, age, gender, address_district)
- `incident_persons` (incident_id, person_id, role) — link table
- `locations` (district, station, lat, lon, population, socio_economic_index)

**Precomputed (written by Cron/Event jobs)**
- `graph_edges` (src_person, dst_person, edge_type, weight, incident_id)
- `hotspot_cells`, `district_stats`, `risk_scores`, `trend_baselines`, `anomalies`, `alerts`

---

## 6. Build phases

- **Phase 0 — Foundation:** Catalyst project + CLI; Auth (roles); AppSail FastAPI skeleton + health route deployed; Slate React skeleton deployed; confirm QuickML early-access. Synthetic data generator → Data Store seeded.
- **Phase 1 — Geospatial hotspots:** Cron job → clusters (DBSCAN/KDE) + Getis-Ord-style hotspot cells + trend baselines. API serves GeoJSON. UI: MapLibre district drill-down choropleth + heat layer + red-zone pulsing spike alerts; Recharts time-series.
- **Phase 2 — Network/link analysis:** Event/Cron job builds `graph_edges` (networkx centrality, components); Zia extracts entities/MO from narratives. UI: Cytoscape.js suspect↔victim↔location graph, repeat-offender profiles, MO match, shortest-path association detection.
- **Phase 3 — Predictive & anomaly AI:** Zia AutoML → `risk_scores` + emerging-typology forecast; anomaly job → `anomalies`. UI: risk dashboard, socio-economic map overlay, anomaly call-outs.
- **Phase 4 — NL query + AI reports:** QuickML RAG over records/MO; plain-English Q&A endpoint; LLM-written report narrative; SmartBrowz HTML→PDF in Stratus; Mail delivery; Cron + Push trend-spike alerts.
- **Phase 5 — Polish:** demo storyline, custom domain (Domain Mappings), cost check vs credits, record demo.

---

## 7. Verification

- **Deploy smoke test:** after Phase 0, hit the AppSail FastAPI health route via API Gateway, load the Slate URL over HTTPS, confirm Auth login.
- **Data:** query Data Store via ZCQL/console to confirm seeded rows and that aggregate tables populate after each Cron run.
- **Per feature:** map renders districts + hotspot heat + pulsing alert; graph renders with working shortest-path/centrality highlight; risk dashboard shows AutoML scores + anomaly call-outs; NL query returns a grounded answer and a PDF report downloads from Stratus.
- **Budget:** check the Catalyst billing/usage console after each phase; confirm the QuickML endpoint is torn down when idle; verify total stays well under $250 within the 60-day window.
