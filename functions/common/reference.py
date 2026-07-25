"""
Static socio-economic reference for the Cron jobs (framework-free mirror of
backend/app/services/reference.py). Bundled CSV so district_stats / risk_scores can
fold a per-capita term into the risk score on Catalyst too. Keep in sync with the
backend copy and app/data/karnataka_socioeconomic.csv.
"""
from __future__ import annotations

import csv
import os

_CSV = os.path.join(os.path.dirname(__file__), "data", "karnataka_socioeconomic.csv")


def socioeconomic():
    """district name -> {population, area_km2, urban_pct, literacy_pct, pop_density}."""
    if not os.path.exists(_CSV):
        return {}
    out = {}
    with open(_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            name = (r.get("district") or "").strip()
            if not name:
                continue
            try:
                pop = int(r["population"])
                area = float(r["area_km2"])
                out[name] = {
                    "population": pop,
                    "area_km2": area,
                    "urban_pct": float(r["urban_pct"]),
                    "literacy_pct": float(r["literacy_pct"]),
                    "pop_density": round(pop / area, 1) if area else None,
                }
            except (KeyError, TypeError, ValueError):
                continue
    return out
