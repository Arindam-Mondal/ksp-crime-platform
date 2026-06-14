"""
Pillar 4 — one-click AI intelligence report.

Returns a structured briefing (narrative via the LLM gate + aggregates). The frontend
renders it print-optimised and exports to PDF. In production the catalyst path renders
the HTML to PDF via SmartBrowz and stores it in Stratus (see services/report.py).
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import report as report_service

router = APIRouter(prefix="/api/report", tags=["report"])


class ReportRequest(BaseModel):
    scope: str = "state"  # state | district | person
    id: str | None = None


@router.post("")
def generate(req: ReportRequest):
    return report_service.build_report(scope=req.scope, subject_id=req.id)
