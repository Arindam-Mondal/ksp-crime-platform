"""
AI intelligence report builder (Pillar 4).

Assembles a structured briefing from the ERD-backed aggregates and writes the
narrative through the single LLM gate (`services/llm.py`). Local mode returns JSON
(the frontend renders + prints to PDF). In catalyst mode `render_pdf()` is the hook
for SmartBrowz HTML→PDF + Stratus storage (wired at deploy; see CLAUDE.md budget rule).
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from app.services import aggregations, derived, firdata
from app.services.llm import get_llm


def _top_offenders(case_ids: set[int] | None, limit: int = 8) -> list[dict]:
    out = []
    for oid, g in firdata.offenders()["by_id"].items():
        if case_ids is not None and not (set(g["case_ids"]) & case_ids):
            continue
        n = g["n_cases"] if case_ids is None else len(set(g["case_ids"]) & case_ids)
        out.append({"person_id": oid, "name": g["name"], "cases": n})
        if case_ids is None and len(out) >= limit:
            break
    out.sort(key=lambda x: -x["cases"])
    return out[:limit]


def build_report(scope: str = "state", subject_id: str | None = None) -> dict:
    cases_all = firdata.cases()

    if scope == "district" and subject_id:
        rows = [c for c in cases_all if c["district"] == subject_id]
        subject = subject_id
    elif scope == "person" and subject_id:
        g = firdata.offenders()["by_id"].get(subject_id)
        ids = set(g["case_ids"]) if g else set()
        rows = [c for c in cases_all if c["id"] in ids]
        subject = g["name"] if g else subject_id
    else:
        scope = "state"
        rows = cases_all
        subject = "Karnataka (State-wide)"

    total = len(rows)
    finals = [c for c in rows if c["cstype"]]
    charged = sum(1 for c in finals if c["cstype"] == "A")
    cs_rate = round(charged / len(finals) * 100, 1) if finals else 0
    subs = Counter(c["sub_head"] for c in rows)
    districts = Counter(c["district"] for c in rows)
    heinous = round(sum(1 for c in rows if c["heinous"]) / total * 100, 1) if total else 0
    cyber = round(sum(1 for c in rows if c["head"] == "Cyber Crime") / total * 100, 1) if total else 0
    arrests = sum(c["n_arrests"] for c in rows)

    alerts = aggregations.spike_alerts(cases_all)
    anoms = derived.anomalies()
    if scope == "district" and subject_id:
        alerts = [a for a in alerts if a["district"] == subject_id]
        anoms = [a for a in anoms if a["subject"] == subject_id]
    dstats = aggregations.district_stats(rows)
    case_ids = {c["id"] for c in rows} if scope != "state" else None
    offenders = _top_offenders(case_ids)

    top_alert = alerts[0] if alerts else None
    prompt = (
        f"Write a concise 4-5 sentence crime-intelligence briefing for {subject}. "
        f"Registered cases: {total}. Chargesheet rate: {cs_rate}%. "
        f"Heinous share: {heinous}%. "
        f"Top crime: {subs.most_common(1)[0][0] if subs else 'n/a'}. "
        f"Cyber-crime share: {cyber}%. Arrests: {arrests}. Active spike alerts: {len(alerts)}"
        + (f" (notably {top_alert['sub_head']} up {top_alert['ratio']}x in {top_alert['district']})" if top_alert else "")
        + f". Statistical anomalies flagged: {len(anoms)}. "
        "Highlight emerging risks and recommend where to focus resources."
    )
    context = [a["description"] for a in anoms[:3]] + (
        [f"{a['sub_head']} surging {a['ratio']}x in {a['district']}" for a in alerts[:3]]
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
            {"label": "Registered cases", "value": f"{total:,}"},
            {"label": "Chargesheet rate", "value": f"{cs_rate}%"},
            {"label": "Heinous share", "value": f"{heinous}%"},
            {"label": "Arrests", "value": f"{arrests:,}"},
            {"label": "Districts", "value": str(len(districts))},
            {"label": "Active alerts", "value": str(len(alerts))},
        ],
        "hotspots": [
            {"district": d["district"], "cases": d["cases"], "risk_score": d["risk_score"]}
            for d in dstats[:6]
        ],
        "offenders": offenders,
        "alerts": alerts[:8],
        "anomalies": anoms[:8],
    }


def render_pdf(html: str) -> bytes:  # pragma: no cover - Catalyst-only
    """SmartBrowz HTML→PDF (wired at deploy). Locally the client prints to PDF instead.

    Deploy note: validate the SmartBrowz request shape against your endpoint; the caller
    should upload the returned bytes to Stratus and hand the URL back to the client.
    """
    from app.config import get_settings

    s = get_settings()
    if not s.smartbrowz_endpoint:
        raise NotImplementedError(
            "SMARTBROWZ_ENDPOINT not set — local mode returns JSON and the frontend uses "
            "window.print(). Set it (and DATA_MODE=catalyst) to enable server-side PDF."
        )
    import httpx

    payload = {"html": html, "output": "pdf", "page": {"format": "A4", "margin": "16mm"}}
    headers = {"Authorization": f"Bearer {s.smartbrowz_api_key}"}
    with httpx.Client(timeout=40) as client:
        resp = client.post(s.smartbrowz_endpoint, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.content
