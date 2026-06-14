"""
AI intelligence report builder (Pillar 4).

Assembles a structured briefing from the precomputed aggregates and writes the
narrative through the single LLM gate (`services/llm.py`). Local mode returns JSON
(the frontend renders + prints to PDF). In catalyst mode `render_pdf()` is the hook
for SmartBrowz HTML→PDF + Stratus storage (wired at deploy; see CLAUDE.md budget rule).
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from app.services import aggregations
from app.services.datastore import get_store
from app.services.llm import get_llm

CLEARED = {"Charge-sheeted", "Closed"}


def _top_offenders(incidents_ids: set[str] | None, limit: int = 8) -> list[dict]:
    links = get_store().rows("incident_persons")
    persons = {p["id"]: p for p in get_store().rows("persons")}
    counts: Counter = Counter()
    for l in links:
        if l.get("role") != "offender":
            continue
        if incidents_ids is not None and l.get("incident_id") not in incidents_ids:
            continue
        counts[l["person_id"]] += 1
    return [
        {"person_id": pid, "name": persons.get(pid, {}).get("name", pid), "incidents": n}
        for pid, n in counts.most_common(limit)
    ]


def build_report(scope: str = "state", subject_id: str | None = None) -> dict:
    incidents_all = get_store().rows("incidents")
    locations = get_store().rows("locations")

    # Scope the incident set.
    if scope == "district" and subject_id:
        incidents = [r for r in incidents_all if r.get("district") == subject_id]
        subject = subject_id
    elif scope == "person" and subject_id:
        link_ids = {
            l["incident_id"] for l in get_store().rows("incident_persons")
            if l.get("person_id") == subject_id and l.get("role") == "offender"
        }
        incidents = [r for r in incidents_all if r.get("id") in link_ids]
        persons = {p["id"]: p for p in get_store().rows("persons")}
        subject = persons.get(subject_id, {}).get("name", subject_id)
    else:
        scope = "state"
        incidents = incidents_all
        subject = "Karnataka (State-wide)"

    total = len(incidents)
    cleared = sum(1 for r in incidents if r.get("status") in CLEARED)
    crimes = Counter(r.get("crime_type", "") for r in incidents)
    districts = Counter(r.get("district", "") for r in incidents)
    clearance = round(cleared / total * 100, 1) if total else 0
    cyber = round(sum(1 for r in incidents if r.get("crime_type") == "Cybercrime") / total * 100, 1) if total else 0

    # Aggregates (alerts/anomalies are computed on the full set, then filtered for scope).
    alerts = aggregations.spike_alerts(incidents_all, locations)
    anoms = aggregations.anomalies(incidents_all)
    if scope == "district" and subject_id:
        alerts = [a for a in alerts if a["district"] == subject_id]
        anoms = [a for a in anoms if a["subject"] == subject_id]
    dstats = aggregations.district_stats(incidents, locations)
    inc_ids = {r["id"] for r in incidents} if scope != "state" else None
    offenders = _top_offenders(inc_ids)

    # Narrative via the LLM gate (mock locally; QuickML in production).
    top_alert = alerts[0] if alerts else None
    prompt = (
        f"Write a concise 4-5 sentence crime-intelligence briefing for {subject}. "
        f"Reported incidents: {total}. Clearance rate: {clearance}%. "
        f"Top crime: {crimes.most_common(1)[0][0] if crimes else 'n/a'}. "
        f"Cybercrime share: {cyber}%. Active spike alerts: {len(alerts)}"
        + (f" (notably {top_alert['crime_type']} up {top_alert['ratio']}x in {top_alert['district']})" if top_alert else "")
        + f". Statistical anomalies flagged: {len(anoms)}. "
        "Highlight emerging risks and recommend where to focus resources."
    )
    context = [a["description"] for a in anoms[:3]] + (
        [f"{a['crime_type']} surging {a['ratio']}x in {a['district']}" for a in alerts[:3]]
    )
    llm = get_llm().complete(prompt, context=context)

    return {
        "scope": scope,
        "subject": subject,
        "subject_id": subject_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "narrative": llm.text,
        "provider": llm.provider,
        "model": llm.model,
        "kpis": [
            {"label": "Total incidents", "value": f"{total:,}"},
            {"label": "Clearance rate", "value": f"{clearance}%"},
            {"label": "Districts", "value": str(len(districts))},
            {"label": "Cyber share", "value": f"{cyber}%"},
            {"label": "Active alerts", "value": str(len(alerts))},
            {"label": "Anomalies", "value": str(len(anoms))},
        ],
        "hotspots": [
            {"district": d["district"], "incidents": d["incidents"], "risk_score": d["risk_score"]}
            for d in dstats[:6]
        ],
        "offenders": offenders,
        "alerts": alerts[:8],
        "anomalies": anoms[:8],
    }


def render_pdf(html: str) -> bytes:  # pragma: no cover - Catalyst-only
    """SmartBrowz HTML→PDF hook (wired at deploy). Locally the client prints to PDF."""
    raise NotImplementedError(
        "render_pdf uses Catalyst SmartBrowz; set DATA_MODE=catalyst and wire the "
        "SmartBrowz call at deploy. Locally the frontend uses window.print()."
    )
