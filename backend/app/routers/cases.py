"""FIR/case lookups over the ERD-backed case view. Paginated (300-row Catalyst cap)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import firdata

router = APIRouter(prefix="/api/cases", tags=["cases"])

PAGE_MAX = 300  # Catalyst Data Store hard cap.

# Fields served in list rows (the full view row also carries brief_facts etc.).
LIST_FIELDS = ("id", "crime_no", "case_no", "category", "gravity", "head", "sub_head",
               "status", "district", "station", "registered", "incident", "sections",
               "n_victims", "n_accused", "n_arrests", "cstype", "lat", "lon")


@router.get("")
def list_cases(
    district: str | None = None,
    head: str | None = None,
    sub_head: str | None = None,
    category: str | None = None,
    status: str | None = None,
    limit: int = Query(100, le=PAGE_MAX),
    offset: int = 0,
):
    rows = firdata.cases()
    if district:
        rows = [r for r in rows if r["district"] == district]
    if head:
        rows = [r for r in rows if r["head"] == head]
    if sub_head:
        rows = [r for r in rows if r["sub_head"] == sub_head]
    if category:
        rows = [r for r in rows if r["category"] == category]
    if status:
        rows = [r for r in rows if r["status"] == status]
    rows = sorted(rows, key=lambda r: r["registered"], reverse=True)
    total = len(rows)
    items = [{k: r[k] for k in LIST_FIELDS} for r in rows[offset:offset + limit]]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/meta")
def meta():
    """Distinct values for filter dropdowns."""
    lk = firdata.lookups()
    rows = firdata.cases()
    return {
        "districts": sorted({r["district"] for r in rows if r["district"]}),
        "heads": sorted({r["head"] for r in rows if r["head"]}),
        "sub_heads": sorted({r["sub_head"] for r in rows if r["sub_head"]}),
        "categories": [v for _, v in sorted(lk["categories"].items())],
        "statuses": [v for _, v in sorted(lk["statuses"].items())],
    }


@router.get("/{case_id}")
def case_detail(case_id: int):
    """Full FIR dossier: case, sections, parties, arrests, chargesheet, officer."""
    c = firdata.case_index().get(case_id)
    if not c:
        raise HTTPException(status_code=404, detail="case not found")
    lk = firdata.lookups()
    pts = firdata.parties()
    secs = firdata.sections_by_case().get(case_id, [])
    arrs = firdata.arrests()["by_case"].get(case_id, [])
    cs = firdata.chargesheets_by_case().get(case_id)
    officer = lk["employees"].get(c["officer_id"], {})
    return {
        "case": c,
        "sections": secs,
        "complainants": pts["complainants"].get(case_id, []),
        "victims": pts["victims"].get(case_id, []),
        "accused": pts["accused"].get(case_id, []),
        "arrests": arrs,
        "chargesheet": cs,
        "registered_by": {"name": officer.get("name", ""), "rank": officer.get("rank", ""),
                          "designation": officer.get("designation", "")},
    }
