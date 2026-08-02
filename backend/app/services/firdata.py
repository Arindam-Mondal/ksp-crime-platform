"""
FIR-schema data views.

The Data Store holds the tables of the official Police FIR ERD (see ERD_SCHEMA.md).
This module joins them into cached, denormalised in-memory views the routers read:

  * lookups()   -> id -> name maps for every master table
  * cases()     -> one dict per CaseMaster row with resolved names + derived fields
                   (month, hour, report delay, arrest/chargesheet facts, party counts)
  * offenders() -> accused entity-resolution index: the same physical person across
                   cases is identified by (AccusedName, GenderID) — mirrors real-world
                   name-based resolution on FIR data (Accused rows are per-case)
  * arrests(), sections_by_case(), parties() -> child-table indexes

Local mode reads the generator CSVs; catalyst mode reads Data Store tables of the
same names. On Catalyst the heavy rollups derived from these views are precomputed
by the Cron functions (precompute-and-serve, see CLAUDE.md).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from app.services.cache import cached
from app.services.datastore import get_store

GENDER = {1: "M", 2: "F", 3: "T"}
# Case statuses that mean a chargesheet was filed and the case moved to court.
COURT_STAGE = {2, 3, 4, 5}


def _int(v: Any) -> int | None:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _float(v: Any) -> float | None:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _dt(v: str) -> datetime | None:
    s = str(v or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


@cached()
def lookups() -> dict[str, Any]:
    store = get_store()
    states = {_int(r["StateID"]): r["StateName"] for r in store.rows("State")}
    districts, district_state = {}, {}
    for r in store.rows("District"):
        did = _int(r["DistrictID"])
        districts[did] = r["DistrictName"]
        district_state[did] = _int(r["StateID"])
    unit_types = {_int(r["UnitTypeID"]): r["UnitTypeName"] for r in store.rows("UnitType")}
    units = {}
    for r in store.rows("Unit"):
        units[_int(r["UnitID"])] = {
            "name": r["UnitName"], "type_id": _int(r["TypeID"]),
            "district_id": _int(r["DistrictID"]), "parent": _int(r["ParentUnit"]),
        }
    ranks = {_int(r["RankID"]): r["RankName"] for r in store.rows("Rank")}
    designations = {_int(r["DesignationID"]): r["DesignationName"] for r in store.rows("Designation")}
    employees = {}
    for r in store.rows("Employee"):
        employees[_int(r["EmployeeID"])] = {
            "name": r["FirstName"], "kgid": r.get("KGID", ""),
            "rank_id": _int(r["RankID"]), "rank": ranks.get(_int(r["RankID"]), ""),
            "designation": designations.get(_int(r["DesignationID"]), ""),
            "unit_id": _int(r["UnitID"]), "district_id": _int(r["DistrictID"]),
        }
    courts = {}
    for r in store.rows("Court"):
        courts[_int(r["CourtID"])] = {
            "name": r["CourtName"], "district_id": _int(r["DistrictID"]),
        }
    acts = {r["ActCode"]: r["ShortName"] for r in store.rows("Act")}
    act_desc = {r["ActCode"]: r["ActDescription"] for r in store.rows("Act")}
    sections = {(r["ActCode"], r["SectionCode"]): r["SectionDescription"]
                for r in store.rows("Section")}
    heads = {_int(r["CrimeHeadID"]): r["CrimeGroupName"] for r in store.rows("CrimeHead")}
    sub_heads = {}
    for r in store.rows("CrimeSubHead"):
        sub_heads[_int(r["CrimeSubHeadID"])] = {
            "name": r["CrimeHeadName"], "head_id": _int(r["CrimeHeadID"]),
            "head": heads.get(_int(r["CrimeHeadID"]), ""),
        }
    categories = {_int(r["CaseCategoryID"]): r["LookupValue"] for r in store.rows("CaseCategory")}
    gravity = {_int(r["GravityOffenceID"]): r["LookupValue"] for r in store.rows("GravityOffence")}
    statuses = {_int(r["CaseStatusID"]): r["CaseStatusName"] for r in store.rows("CaseStatusMaster")}
    occupations = {_int(r["OccupationID"]): r["OccupationName"] for r in store.rows("OccupationMaster")}
    religions = {_int(r["ReligionID"]): r["ReligionName"] for r in store.rows("ReligionMaster")}
    castes = {_int(r["caste_master_id"]): r["caste_master_name"] for r in store.rows("CasteMaster")}
    return {
        "states": states, "districts": districts, "district_state": district_state,
        "unit_types": unit_types, "units": units, "ranks": ranks,
        "designations": designations, "employees": employees, "courts": courts,
        "acts": acts, "act_desc": act_desc, "sections": sections,
        "heads": heads, "sub_heads": sub_heads, "categories": categories,
        "gravity": gravity, "statuses": statuses, "occupations": occupations,
        "religions": religions, "castes": castes,
    }


@cached()
def sections_by_case() -> dict[int, list[dict]]:
    lk = lookups()
    out: dict[int, list[dict]] = defaultdict(list)
    for r in get_store().rows("ActSectionAssociation"):
        cid = _int(r["CaseMasterID"])
        act = r["ActID"]
        out[cid].append({
            "act": lk["acts"].get(act, act), "act_code": act,
            "section": r["SectionID"],
            "description": lk["sections"].get((act, r["SectionID"]), ""),
            "label": f"{lk['acts'].get(act, act)} {r['SectionID']}",
        })
    return out


@cached()
def parties() -> dict[str, dict[int, list[dict]]]:
    lk = lookups()
    victims: dict[int, list[dict]] = defaultdict(list)
    for r in get_store().rows("Victim"):
        victims[_int(r["CaseMasterID"])].append({
            "id": _int(r["VictimMasterID"]), "name": r["VictimName"],
            "age": _int(r["AgeYear"]), "gender": GENDER.get(_int(r["GenderID"]), "M"),
            "police": str(r.get("VictimPolice", "0")).strip() == "1",
        })
    accused: dict[int, list[dict]] = defaultdict(list)
    for r in get_store().rows("Accused"):
        accused[_int(r["CaseMasterID"])].append({
            "id": _int(r["AccusedMasterID"]), "name": r["AccusedName"],
            "age": _int(r["AgeYear"]), "gender": GENDER.get(_int(r["GenderID"]), "M"),
            "person_no": r.get("PersonID", ""),
        })
    complainants: dict[int, list[dict]] = defaultdict(list)
    for r in get_store().rows("ComplainantDetails"):
        complainants[_int(r["CaseMasterID"])].append({
            "id": _int(r["ComplainantID"]), "name": r["ComplainantName"],
            "age": _int(r["AgeYear"]), "gender": GENDER.get(_int(r["GenderID"]), "M"),
            "occupation": lk["occupations"].get(_int(r["OccupationID"]), ""),
            "religion": lk["religions"].get(_int(r["ReligionID"]), ""),
            "caste": lk["castes"].get(_int(r["CasteID"]), ""),
        })
    return {"victims": victims, "accused": accused, "complainants": complainants}


@cached()
def arrests() -> dict[str, Any]:
    """All arrest/surrender rows (resolved) + per-case and per-accused indexes."""
    lk = lookups()
    rows = []
    by_case: dict[int, list[dict]] = defaultdict(list)
    by_accused: dict[int, dict] = {}
    for r in get_store().rows("ArrestSurrender"):
        cid = _int(r["CaseMasterID"])
        did = _int(r["ArrestSurrenderDistrictId"])
        sid = _int(r["ArrestSurrenderStateId"])
        row = {
            "id": _int(r["ArrestSurrenderID"]), "case_id": cid,
            "type": "Surrender" if _int(r["ArrestSurrenderTypeID"]) == 2 else "Arrest",
            "date": str(r["ArrestSurrenderDate"]).strip(),
            "district": lk["districts"].get(did, ""), "district_id": did,
            "state": lk["states"].get(sid, ""), "state_id": sid,
            "io_id": _int(r["IOID"]),
            "accused_id": _int(r["AccusedMasterID"]),
            "is_primary": str(r.get("IsAccused", "0")).strip() == "1",
        }
        rows.append(row)
        by_case[cid].append(row)
        if row["accused_id"] is not None:
            by_accused[row["accused_id"]] = row
    return {"rows": rows, "by_case": by_case, "by_accused": by_accused}


@cached()
def chargesheets_by_case() -> dict[int, dict]:
    out = {}
    for r in get_store().rows("ChargesheetDetails"):
        out[_int(r["CaseMasterID"])] = {
            "csid": _int(r["CSID"]), "date": str(r["csdate"]).strip(),
            "cstype": str(r["cstype"]).strip().upper(), "officer_id": _int(r["PolicePersonID"]),
        }
    return out


@cached()
def cases() -> list[dict]:
    """Denormalised case view — one dict per CaseMaster row."""
    lk = lookups()
    secs = sections_by_case()
    pts = parties()
    arr = arrests()["by_case"]
    css = chargesheets_by_case()

    out = []
    for r in get_store().rows("CaseMaster"):
        cid = _int(r["CaseMasterID"])
        station_id = _int(r["PoliceStationID"])
        unit = lk["units"].get(station_id, {})
        did = unit.get("district_id")
        sub_id = _int(r["CrimeMinorHeadID"])
        sub = lk["sub_heads"].get(sub_id, {})
        status_id = _int(r["CaseStatusID"])
        inc_from = _dt(r["IncidentFromDate"])
        info = _dt(r["InfoReceivedPSDate"])
        reg = _dt(r["CrimeRegisteredDate"])
        court_id = _int(r["CourtID"])
        cs = css.get(cid)
        arrs = arr.get(cid, [])
        first_arrest_days = None
        if arrs and reg:
            adates = [_dt(a["date"]) for a in arrs]
            adates = [d for d in adates if d]
            if adates:
                first_arrest_days = max(0, (min(adates) - reg).days)
        cs_days = None
        if cs and reg:
            cd = _dt(cs["date"])
            if cd:
                cs_days = max(0, (cd - reg).days)
        report_delay = None
        if inc_from and info:
            report_delay = max(0.0, round((info - inc_from).total_seconds() / 86400, 2))
        out.append({
            "id": cid,
            "crime_no": r["CrimeNo"],
            "case_no": r["CaseNo"],
            "category": lk["categories"].get(_int(r["CaseCategoryID"]), ""),
            "gravity": lk["gravity"].get(_int(r["GravityOffenceID"]), ""),
            "heinous": _int(r["GravityOffenceID"]) == 1,
            "head": sub.get("head", ""),
            "head_id": sub.get("head_id"),
            "sub_head": sub.get("name", ""),
            "sub_head_id": sub_id,
            "status": lk["statuses"].get(status_id, ""),
            "status_id": status_id,
            "in_court": status_id in COURT_STAGE,
            "district": lk["districts"].get(did, ""),
            "district_id": did,
            "station": unit.get("name", ""),
            "station_id": station_id,
            "court": lk["courts"].get(court_id, {}).get("name", ""),
            "court_id": court_id,
            "officer_id": _int(r["PolicePersonID"]),
            "lat": _float(r["latitude"]),
            "lon": _float(r["longitude"]),
            "registered": r["CrimeRegisteredDate"],
            "incident": r["IncidentFromDate"],
            "month": (r["IncidentFromDate"] or "")[:7],
            "hour": inc_from.hour if inc_from else None,
            "report_delay_days": report_delay,
            "n_victims": len(pts["victims"].get(cid, [])),
            "n_accused": len(pts["accused"].get(cid, [])),
            "n_complainants": len(pts["complainants"].get(cid, [])),
            "n_arrests": len(arrs),
            "first_arrest_days": first_arrest_days,
            "cstype": cs["cstype"] if cs else "",
            "cs_days": cs_days,
            "sections": [s["label"] for s in secs.get(cid, [])],
            "brief_facts": r.get("BriefFacts", ""),
        })
    return out


@cached()
def case_index() -> dict[int, dict]:
    return {c["id"]: c for c in cases()}


@cached()
def offenders() -> dict[str, Any]:
    """Entity-resolved accused index.

    Key = (AccusedName, GenderID): Accused rows are per-case, so recurring names with
    matching gender are treated as the same physical person (name-based resolution).
    Returns stable ids ("O00001"...) ordered by case count for deterministic URLs.
    """
    pts = parties()
    arr = arrests()["by_accused"]
    cidx = case_index()

    groups: dict[tuple, dict] = {}
    for cid, rows in pts["accused"].items():
        for a in rows:
            key = (a["name"], a["gender"])
            g = groups.setdefault(key, {
                "name": a["name"], "gender": a["gender"], "ages": [],
                "case_ids": [], "accused_row_ids": [], "arrests": 0, "surrenders": 0,
            })
            g["case_ids"].append(cid)
            g["accused_row_ids"].append(a["id"])
            if a["age"] is not None:
                g["ages"].append(a["age"])
            ev = arr.get(a["id"])
            if ev:
                if ev["type"] == "Surrender":
                    g["surrenders"] += 1
                else:
                    g["arrests"] += 1

    ordered = sorted(groups.values(),
                     key=lambda g: (-len(g["case_ids"]), g["name"]))
    by_id: dict[str, dict] = {}
    by_case: dict[int, list[str]] = defaultdict(list)
    for i, g in enumerate(ordered, start=1):
        oid = f"O{i:05d}"
        g["id"] = oid
        g["n_cases"] = len(g["case_ids"])
        g["districts"] = sorted({cidx[c]["district"] for c in g["case_ids"] if c in cidx})
        by_id[oid] = g
        for cid in g["case_ids"]:
            by_case[cid].append(oid)
    return {"by_id": by_id, "by_case": by_case}


@cached()
def co_accused_adjacency() -> dict[str, dict]:
    """offender_id -> {co_offender_id: shared case count}. Cheap over the resolved index,
    but called from 7 sites (including inside communities()) — uncached, every network /
    person / MO request rebuilt the whole adjacency map from scratch."""
    off = offenders()
    adj: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    for oids in off["by_case"].values():
        uniq = sorted(set(oids))
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                a, b = uniq[i], uniq[j]
                adj[a][b] += 1
                adj[b][a] += 1
    return adj


@cached()
def communities() -> dict[str, Any]:
    """Organized-crime-structure detection: Louvain community detection over the full
    co-accused graph (networkx.community.louvain_communities), not just direct/ego
    pairwise links.

    The ego graphs in /api/network/ego only ever show a hand-picked offender's
    immediate neighborhood. This groups every resolved offender with 2+ linked FIRs
    into modularity-optimal clusters — the actual "reveal organized crime structures"
    ask — and is cached for the process lifetime since the underlying case data doesn't
    change at runtime in local mode."""
    import networkx as nx

    adj = co_accused_adjacency()
    off = offenders()["by_id"]
    g = nx.Graph()
    for a, neighbors in adj.items():
        for b, weight in neighbors.items():
            g.add_edge(a, b, weight=weight)
    if g.number_of_nodes() == 0:
        return {"by_person": {}, "clusters": []}

    # resolution > 1 biases Louvain toward smaller, tighter groups — at resolution=1 the
    # whole graph collapses into a handful of 100+-member mega-components (everyone is
    # weakly reachable from everyone else through a long chain of one-off co-accused
    # links), which reads as noise, not "organized crime structures". resolution=12 was
    # tuned against this dataset to produce cohesive cells (~10-30 members, median ~15).
    raw = nx.community.louvain_communities(g, weight="weight", seed=42, resolution=12.0)
    by_person: dict[str, int] = {}
    clusters = []
    for cid, members in enumerate(raw):
        if len(members) < 3:
            continue  # pairs/singletons aren't a "structure" worth surfacing
        for m in members:
            by_person[m] = cid
        districts = Counter(d for m in members for d in off.get(m, {}).get("districts", []))
        total_cases = sum(off.get(m, {}).get("n_cases", 0) for m in members)
        clusters.append({
            "id": cid,
            "size": len(members),
            "members": sorted(members, key=lambda m: -off.get(m, {}).get("n_cases", 0))[:25],
            "districts": [d for d, _ in districts.most_common(5)],
            "total_cases": total_cases,
        })
    clusters.sort(key=lambda c: c["size"], reverse=True)
    return {"by_person": by_person, "clusters": clusters}
