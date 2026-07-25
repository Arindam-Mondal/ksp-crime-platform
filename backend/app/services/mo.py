"""
Modus Operandi (MO) analysis — Pillar 2 behavioural fingerprinting.

The challenge asks us to highlight an offender's *specific MO across different
jurisdictions* and to detect *recurring MO*. The ERD carries no "MO" column, so we
derive a behavioural signature per resolved offender from their linked FIRs:

  * crime-type mix   (CrimeSubHead distribution)  — what they do
  * time-of-day mix  (IncidentFromDate hour bucket) — when they do it
  * section set      (ActSectionAssociation labels) — the legal fingerprint
  * gravity + jurisdiction spread                   — how serious / how wide

Two offenders are compared by a transparent weighted similarity (cosine on the crime
and time vectors + Jaccard on the section sets). "Same MO" matches operating in a
*different* district are the ones the challenge cares about — the same method surfacing
across jurisdictions. Computed over the bounded repeat-offender pool (like the ego
graph), so it stays off the heavy path.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache

from app.services import firdata

# Weights for the composite MO similarity (sum to 1.0). Crime-type dominates, the legal
# section fingerprint and timing refine it.
W_CRIME, W_SECTION, W_TIME = 0.55, 0.30, 0.15

TIME_BUCKETS = [
    ("Night", range(0, 6)),      # 00:00–05:59
    ("Morning", range(6, 12)),   # 06:00–11:59
    ("Afternoon", range(12, 18)),
    ("Evening", range(18, 24)),
]


def _bucket(hour: int | None) -> str | None:
    if hour is None:
        return None
    for name, hrs in TIME_BUCKETS:
        if hour in hrs:
            return name
    return None


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = sum(v * v for v in a.values()) ** 0.5
    nb = sum(v * v for v in b.values()) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b) if (a | b) else 0.0


def _raw_signature(case_ids: list[int], cidx: dict) -> dict:
    """Internal vectors used for matching (Counters + sets, not display-shaped)."""
    crimes: Counter = Counter()
    times: Counter = Counter()
    sections: set = set()
    districts: set = set()
    heinous = 0
    n = 0
    for cid in case_ids:
        c = cidx.get(cid)
        if not c:
            continue
        n += 1
        if c["sub_head"]:
            crimes[c["sub_head"]] += 1
        tb = _bucket(c["hour"])
        if tb:
            times[tb] += 1
        sections.update(c["sections"])
        if c["district"]:
            districts.add(c["district"])
        if c["heinous"]:
            heinous += 1
    return {"crimes": crimes, "times": times, "sections": sections,
            "districts": districts, "heinous": heinous, "n": n}


def similarity(a: dict, b: dict) -> float:
    """Composite MO similarity in [0,1] between two raw signatures."""
    return round(
        W_CRIME * _cosine(a["crimes"], b["crimes"])
        + W_SECTION * _jaccard(a["sections"], b["sections"])
        + W_TIME * _cosine(a["times"], b["times"]),
        3,
    )


def public_signature(sig: dict) -> dict:
    """Display-shaped MO fingerprint from a raw signature."""
    n = sig["n"] or 1
    top_crimes = [{"name": k, "share": round(v / n * 100, 1)}
                  for k, v in sig["crimes"].most_common(3)]
    time_profile = [{"bucket": name, "count": sig["times"].get(name, 0)}
                    for name, _ in TIME_BUCKETS]
    dominant_time = sig["times"].most_common(1)[0][0] if sig["times"] else None
    return {
        "n_cases": sig["n"],
        "top_crimes": top_crimes,
        "time_profile": time_profile,
        "dominant_time": dominant_time,
        "top_sections": sorted(sig["sections"])[:6],
        "heinous_share": round(sig["heinous"] / n * 100, 1),
        "jurisdictions": sorted(sig["districts"]),
    }


@lru_cache(maxsize=1)
def _repeat_signatures() -> dict[str, dict]:
    """Raw MO signature for every repeat offender (n_cases >= 2). Cached — the underlying
    synthetic data is static in local mode; the Cron rebuild handles catalyst mode."""
    off = firdata.offenders()["by_id"]
    cidx = firdata.case_index()
    out: dict[str, dict] = {}
    for oid, g in off.items():
        if g["n_cases"] < 2:
            break  # by_id is ordered by case count desc
        out[oid] = _raw_signature(g["case_ids"], cidx)
    return out


def profile(person_id: str, limit: int = 8) -> dict:
    """MO signature for one offender + ranked 'same MO' matches across jurisdictions."""
    off = firdata.offenders()["by_id"]
    g = off.get(person_id)
    if not g:
        return {}
    cidx = firdata.case_index()
    sig = _raw_signature(g["case_ids"], cidx)

    pool = _repeat_signatures()
    adj = firdata.co_accused_adjacency().get(person_id, {})
    matches = []
    for oid, other in pool.items():
        if oid == person_id:
            continue
        score = similarity(sig, other)
        if score <= 0:
            continue
        shared_crimes = sorted((set(sig["crimes"]) & set(other["crimes"])),
                               key=lambda k: -(sig["crimes"][k] + other["crimes"][k]))
        matches.append({
            "person_id": oid,
            "name": off[oid]["name"],
            "gender": off[oid]["gender"],
            "cases": off[oid]["n_cases"],
            "similarity": score,
            "shared_crimes": shared_crimes[:3],
            "shared_sections": len(sig["sections"] & other["sections"]),
            "districts": sorted(other["districts"]),
            "different_jurisdiction": bool(other["districts"] - sig["districts"]),
            "is_associate": oid in adj,
        })
    matches.sort(key=lambda m: -m["similarity"])
    return {"signature": public_signature(sig), "matches": matches[:limit]}
