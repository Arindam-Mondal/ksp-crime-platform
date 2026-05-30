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
    """Catalyst Data Store via ZCQL. Wired during Phase 0 deployment.

    Remember the hard limit: max 300 rows per ZCQL query -> paginate, and prefer
    SELECTing precomputed aggregate tables over scanning `incidents`.
    """

    def rows(self, table: str) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "CatalystStore is not wired yet. Use DATA_MODE=local for now, "
            "or implement the zcatalyst-sdk ZCQL query here in Phase 0 deploy."
        )


@lru_cache
def get_store() -> DataStore:
    settings = get_settings()
    if settings.data_mode == "catalyst":
        return CatalystStore()
    return LocalCsvStore(settings.data_dir)
