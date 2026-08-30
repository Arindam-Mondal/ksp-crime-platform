"""
Pillar 4 — natural-language query + AI report.

All model access goes through services/llm.py (the gate). Retrieval is our own —
keyword-scored locally, or swappable for QuickML RAG once QUICKML_* env vars are set —
rather than QuickML's Knowledge Base, which is a static document-upload store and
doesn't fit our live/queryable case data. Generation always goes through the same
get_llm() gate either way.
"""
from __future__ import annotations

import re

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import derived, firdata
from app.services.llm import get_llm

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

# Per-case keyword retrieval (below) only ever matches literal words inside a FIR's
# BriefFacts narrative — it has no way to answer "top hotspots" or "most connected
# offenders" style questions, since those terms don't appear in any individual case's
# text; the answer lives in the precomputed aggregates instead (district_stats,
# firdata.communities()). Route those intents to the aggregates directly rather than
# silently handing the model empty context.
_HOTSPOT_TERMS = {"hotspot", "hotspots", "quarter", "trend", "trending", "summarise",
                   "summarize", "district", "districts", "top"}
_NETWORK_TERMS = {"offender", "offenders", "connected", "network", "cluster", "clusters",
                   "organized", "organised", "gang", "repeat", "associate", "associates"}


def _hotspot_context(top_n: int = 5) -> list[str]:
    stats = derived.district_stats(with_socio=False)[:top_n]
    return [
        f"{d['district']}: {d['cases']} cases, {d['heinous_share']}% heinous, "
        f"{d['recent_90d']} in the last 90 days, risk score {d['risk_score']}."
        for d in stats
    ]


def _network_context(top_n: int = 5) -> list[str]:
    off = firdata.offenders()["by_id"]
    adj = firdata.co_accused_adjacency()
    lines = []
    for c in firdata.communities()["clusters"][:top_n]:
        names = ", ".join(off.get(m, {}).get("name", m) for m in c["members"][:3])
        districts = ", ".join(c["districts"][:3]) or "multiple districts"
        lines.append(
            f"Cluster #{c['id']}: {c['size']} linked offenders across {districts}, "
            f"{c['total_cases']} total cases. Notable members: {names}."
        )
    most_connected = sorted(off.values(), key=lambda g: -len(adj.get(g["id"], {})))[:top_n]
    for g in most_connected:
        assoc = len(adj.get(g["id"], {}))
        if assoc == 0:
            continue
        lines.append(f"{g['name']}: {g['n_cases']} cases, linked to {assoc} co-accused associates.")
    return lines


def _aggregate_context(question: str) -> list[str]:
    q = question.lower()
    ctx: list[str] = []
    if any(t in q for t in _HOTSPOT_TERMS):
        ctx += _hotspot_context()
    if any(t in q for t in _NETWORK_TERMS):
        ctx += _network_context()
    return ctx

# BriefFacts is machine-generated (see data/generator/generate_synthetic.py) and always
# renders victim/accused identity as " Victim: <name> (<age>/<gender>)." and
# " Accused: <name(s)>." — strip those spans before any FIR narrative leaves the server as
# LLM context or a UI-visible answer. Even on synthetic data, a policing tool echoing names
# verbatim into an ungated "ask anything" endpoint is a habit not worth normalizing.
#
# These anchor on the *structure* around the name rather than on the name itself: Karnataka
# names legitimately contain full stops ("C. R. Yusuf", "Nagendra P."), so the earlier
# "[^.]+" form stopped at the first initial and leaked the rest of the name.
_VICTIM_RE = re.compile(r"Victim: .*?\(\d{1,3}/[MFT]\)\.")
_ACCUSED_RE = re.compile(r"Accused: .*?(?=\s+Case registered as\b|$)", re.S)


def _redact(text: str) -> str:
    text = _VICTIM_RE.sub("Victim: [redacted].", text)
    text = _ACCUSED_RE.sub("Accused: [redacted].", text)
    return text


class AskRequest(BaseModel):
    question: str
    top_k: int = 5
    lang: str = "en"  # output language only; retrieval stays over the English case text


def _retrieve(question: str, top_k: int) -> list[str]:
    """Naive keyword retrieval over FIR BriefFacts (placeholder for QuickML RAG)."""
    terms = {t.lower() for t in question.split() if len(t) > 3}
    scored = []
    for c in firdata.cases():
        text = (c["brief_facts"] + " " + c["sub_head"] + " " + c["district"]).lower()
        score = sum(text.count(t) for t in terms)
        if score:
            scored.append((score, f"{c['crime_no']}: {_redact(c['brief_facts'])}"))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [s for _, s in scored[:top_k]]


@router.post("/ask")
def ask(req: AskRequest):
    # Aggregate context first — it's the direct answer for hotspot/network-style
    # questions and the LLM only ever grounds on the first 5 items (see llm.py).
    context = _aggregate_context(req.question) + _retrieve(req.question, req.top_k)
    result = get_llm().complete(req.question, context=context, lang=req.lang)
    return {
        "question": req.question,
        "answer": result.text,
        "provider": result.provider,
        "model": result.model,
        "grounded_on": result.grounded_on,
    }
