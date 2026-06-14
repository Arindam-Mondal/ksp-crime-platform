"""
Data access layer.

Keeps two modes interchangeable so the same routers work locally and on Catalyst:
  * DATA_MODE=local    -> reads data/output/*.csv (the synthetic dataset).
  * DATA_MODE=catalyst -> reads Catalyst Data Store via ZCQL (TODO: wire SDK in Phase 0 deploy).

IMPORTANT (see CLAUDE.md): the API must only read *precomputed aggregates* in production.
The CSV reader here is a dev convenience; on Catalyst, heavy aggregation is done by the
Cron/Event functions and this layer just SELECTs the resulting aggregate tables.
"""
from __future__ import annotations

import csv
import os
from functools import lru_cache
from typing import Any

from app.config import get_settings


class DataStore:
    """Abstract data access. Subclasses implement a single `rows(table)` primitive."""

    def rows(self, table: str) -> list[dict[str, Any]]:  # pragma: no cover - interface
        raise NotImplementedError


class LocalCsvStore(DataStore):
    """Reads CSVs produced by data/generator/generate_synthetic.py."""

    def __init__(self, data_dir: str):
        # Resolve relative to the backend working directory.
        self.data_dir = os.path.abspath(data_dir)

    @lru_cache(maxsize=32)
    def rows(self, table: str) -> list[dict[str, Any]]:
        path = os.path.join(self.data_dir, f"{table}.csv")
        if not os.path.exists(path):
            return []
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))


class CatalystStore(DataStore):
    """Catalyst Data Store via ZCQL.

    Respects the 300-rows-per-query cap by paging on ROWID. In production this reads
    the small *aggregate* tables the Cron jobs write (hotspot_cells, district_stats,
    risk_scores, anomalies, alerts, graph_edges) — never a full scan of `incidents`
    on the request path.

    Deploy note: validated against the documented zcatalyst-sdk API; not runnable
    locally (needs a Catalyst context). Use DATA_MODE=local for dev.
    """

    PAGE = 300

    def __init__(self):
        try:
            import zcatalyst_sdk  # noqa: F401
            self._sdk = zcatalyst_sdk
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "zcatalyst-sdk not installed. Add it to pyproject and run inside AppSail, "
                "or set DATA_MODE=local."
            ) from e

    def rows(self, table: str) -> list[dict[str, Any]]:
        app = self._sdk.initialize()
        zcql = app.zcql()
        out: list[dict[str, Any]] = []
        last = 0
        while True:
            page = zcql.execute_query(
                f"SELECT * FROM {table} WHERE ROWID > {last} ORDER BY ROWID LIMIT {self.PAGE}"
            )
            if not page:
                break
            for r in page:
                row = r.get(table, r)  # ZCQL nests columns under the table name
                out.append(row)
                try:
                    last = max(last, int(row.get("ROWID", last) or last))
                except (TypeError, ValueError):
                    pass
            if len(page) < self.PAGE:
                break
        return out


@lru_cache
def get_store() -> DataStore:
    settings = get_settings()
    if settings.data_mode == "catalyst":
        return CatalystStore()
    return LocalCsvStore(settings.data_dir)
