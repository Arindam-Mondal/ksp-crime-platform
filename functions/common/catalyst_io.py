"""
Catalyst Data Store I/O helpers for the Cron/Event jobs.

NOTE (deploy): the exact `zcatalyst_sdk` method names/signatures must be validated
against the installed SDK version — this is written to the documented API but is not
runnable locally (no Catalyst context). Heavy full-table reads should ideally use the
Data Store **bulk read** job; ZCQL paging below is the simplest portable fallback and
respects the 300-rows-per-query cap.
"""
from __future__ import annotations

from typing import Any

try:  # only present in the Catalyst runtime
    import zcatalyst_sdk
except ImportError:  # pragma: no cover
    zcatalyst_sdk = None

PAGE = 300  # Data Store hard cap per ZCQL query


def _app():
    if zcatalyst_sdk is None:
        raise RuntimeError("zcatalyst_sdk unavailable — run inside a Catalyst Function.")
    return zcatalyst_sdk.initialize()


def read_all(table: str) -> list[dict[str, Any]]:
    """Page through a whole table via ZCQL using ROWID as a cursor."""
    app = _app()
    zcql = app.zcql()
    rows: list[dict] = []
    last = 0
    while True:
        q = f"SELECT * FROM {table} WHERE ROWID > {last} ORDER BY ROWID LIMIT {PAGE}"
        page = zcql.execute_query(q)
        if not page:
            break
        for r in page:
            row = r.get(table, r)            # ZCQL nests under the table name
            rows.append(row)
            last = max(last, int(row.get("ROWID", last) or last))
        if len(page) < PAGE:
            break
    return rows


def replace_table(table: str, rows: list[dict[str, Any]], chunk: int = 200) -> int:
    """Clear a table and insert fresh aggregate rows (idempotent job output)."""
    app = _app()
    ds = app.datastore()
    t = ds.table(table)

    # delete existing rows (paged select of ROWIDs -> bulk delete)
    zcql = app.zcql()
    while True:
        page = zcql.execute_query(f"SELECT ROWID FROM {table} ORDER BY ROWID LIMIT {PAGE}")
        if not page:
            break
        ids = [int(r.get(table, r)["ROWID"]) for r in page]
        t.delete_rows(ids)
        if len(page) < PAGE:
            break

    # insert in chunks
    written = 0
    for i in range(0, len(rows), chunk):
        t.insert_rows(rows[i:i + chunk])
        written += len(rows[i:i + chunk])
    return written
