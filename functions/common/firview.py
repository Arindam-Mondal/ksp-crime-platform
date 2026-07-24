"""
Minimal case-view builder for the Cron/Event jobs (mirror of the join logic in
`backend/app/services/firdata.py`, trimmed to the fields the aggregations need).

Takes a `read_all(table)` callable (see catalyst_io.read_all) so it is testable and
independent of the Catalyst SDK.
"""
from __future__ import annotations


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _float(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def build_case_view(read_all) -> list[dict]:
    districts = {_int(r["DistrictID"]): r["DistrictName"] for r in read_all("District")}
    units = {_int(r["UnitID"]): {"name": r["UnitName"], "district_id": _int(r["DistrictID"])}
             for r in read_all("Unit")}
    heads = {_int(r["CrimeHeadID"]): r["CrimeGroupName"] for r in read_all("CrimeHead")}
    subs = {_int(r["CrimeSubHeadID"]): {"name": r["CrimeHeadName"],
                                        "head": heads.get(_int(r["CrimeHeadID"]), "")}
            for r in read_all("CrimeSubHead")}
    cs_by_case = {_int(r["CaseMasterID"]): str(r["cstype"]).strip().upper()
                  for r in read_all("ChargesheetDetails")}

    out = []
    for r in read_all("CaseMaster"):
        cid = _int(r["CaseMasterID"])
        unit = units.get(_int(r["PoliceStationID"]), {})
        sub = subs.get(_int(r["CrimeMinorHeadID"]), {})
        incident = str(r.get("IncidentFromDate", "") or "")
        hour = None
        if len(incident) >= 13:
            try:
                hour = int(incident[11:13])
            except ValueError:
                hour = None
        out.append({
            "id": cid,
            "district": districts.get(unit.get("district_id"), ""),
            "station": unit.get("name", ""),
            "head": sub.get("head", ""),
            "sub_head": sub.get("name", ""),
            "heinous": _int(r.get("GravityOffenceID")) == 1,
            "status_id": _int(r.get("CaseStatusID")),
            "cstype": cs_by_case.get(cid, ""),
            "incident": incident,
            "hour": hour,
            "lat": _float(r.get("latitude")),
            "lon": _float(r.get("longitude")),
        })
    return out
