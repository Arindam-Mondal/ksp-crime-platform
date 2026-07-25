"""
Static socio-economic reference for Karnataka's districts (Pillar 3 — the "why"
behind the "where").

The official FIR ERD has no population / urbanisation columns, so crime volume alone
cannot separate a genuinely high-crime district from a merely populous one. This module
supplies public Census 2011 / Karnataka figures keyed by DistrictName, letting the
analytics layer compute true per-capita crime rates and correlate crime against
urbanisation, literacy and population density.

The data is bundled with the backend (app/data/karnataka_socioeconomic.csv) so it works
identically in local and Catalyst modes — it is stable reference data, not synthetic FIR
data, and never needs Data Store seeding. Non-Karnataka districts simply have no row and
are excluded from per-capita / correlation views.
"""
from __future__ import annotations

import csv
import os
from functools import lru_cache
from typing import Any

_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "karnataka_socioeconomic.csv")


@lru_cache(maxsize=1)
def socioeconomic() -> dict[str, dict[str, Any]]:
    """district name -> {population, area_km2, urban_pct, literacy_pct, pop_density, source}."""
    path = os.path.abspath(_CSV)
    if not os.path.exists(path):
        return {}
    out: dict[str, dict[str, Any]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            name = (r.get("district") or "").strip()
            if not name:
                continue
            try:
                pop = int(r["population"])
                area = float(r["area_km2"])
                urban = float(r["urban_pct"])
                lit = float(r["literacy_pct"])
            except (KeyError, TypeError, ValueError):
                continue
            out[name] = {
                "population": pop,
                "area_km2": area,
                "urban_pct": urban,
                "literacy_pct": lit,
                "pop_density": round(pop / area, 1) if area else None,
                "source": (r.get("source") or "").strip(),
            }
    return out
