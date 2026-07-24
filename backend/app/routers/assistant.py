"""
Pillar 4 — natural-language query + AI report.

All model access goes through services/llm.py (the gate). Local mode uses naive
keyword retrieval over FIR BriefFacts + the mock provider; Phase 4 swaps in QuickML
RAG + SmartBrowz PDF export.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import firdata
from app.services.llm import get_llm

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class AskRequest(BaseModel):
    question: str
    top_k: int = 5


def _retrieve(question: str, top_k: int) -> list[str]:
    """Naive keyword retrieval over FIR BriefFacts (placeholder for QuickML RAG)."""
    terms = {t.lower() for t in question.split() if len(t) > 3}
    scored = []
    for c in firdata.cases():
        text = (c["brief_facts"] + " " + c["sub_head"] + " " + c["district"]).lower()
        score = sum(text.count(t) for t in terms)
        if score:
            scored.append((score, f"{c['crime_no']}: {c['brief_facts']}"))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [s for _, s in scored[:top_k]]


@router.post("/ask")
def ask(req: AskRequest):
    context = _retrieve(req.question, req.top_k)
    result = get_llm().complete(req.question, context=context)
    return {
        "question": req.question,
        "answer": result.text,
        "provider": result.provider,
        "model": result.model,
        "grounded_on": result.grounded_on,
    }
