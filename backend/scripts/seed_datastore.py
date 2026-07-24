"""
Seed the Catalyst Data Store from the synthetic CSVs, then (optionally) trigger the
Cron jobs to populate the aggregate tables.

This is an admin/maintenance script — run it with Catalyst admin credentials, not on
the request path. It is NOT runnable locally without a Catalyst context; for local dev
the API reads the CSVs directly (DATA_MODE=local).

Usage (after `catalyst login` and tables created in the console / via schema import):
    python backend/scripts/seed_datastore.py --data data/output

Tables expected: the 26 ERD tables (see ERD_SCHEMA.md) + the aggregate tables the
jobs write (hotspot_cells, district_stats, trend_baselines, alerts, risk_scores,
anomalies, graph_edges).
"""
from __future__ import annotations

import argparse
import csv
import os

# Masters first (FK targets), then case data — one CSV per ERD table.
CORE_TABLES = [
    "State", "District", "UnitType", "Unit", "Rank", "Designation", "Employee",
    "Court", "CaseCategory", "GravityOffence", "CaseStatusMaster", "CasteMaster",
    "ReligionMaster", "OccupationMaster", "CrimeHead", "CrimeSubHead",
    "Act", "Section", "CrimeHeadActSection",
    "CaseMaster", "ComplainantDetails", "Victim", "Accused",
    "ActSectionAssociation", "ArrestSurrender", "ChargesheetDetails",
]
CHUNK = 200  # insert_rows batch size


def read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description="Seed Catalyst Data Store from CSVs.")
    ap.add_argument("--data", default=os.path.join("data", "output"))
    ap.add_argument("--tables", nargs="*", default=CORE_TABLES)
    args = ap.parse_args()

    try:
        import zcatalyst_sdk
    except ImportError:
        raise SystemExit("zcatalyst-sdk not installed. `uv add zcatalyst-sdk` and run with admin creds.")

    app = zcatalyst_sdk.initialize()
    ds = app.datastore()

    for table in args.tables:
        path = os.path.join(args.data, f"{table}.csv")
        if not os.path.exists(path):
            print(f"  skip {table}: {path} not found")
            continue
        rows = read_csv(path)
        t = ds.table(table)
        written = 0
        for i in range(0, len(rows), CHUNK):
            t.insert_rows(rows[i:i + CHUNK])
            written += len(rows[i:i + CHUNK])
        print(f"  seeded {table}: {written} rows")

    print("Done. Now run the Cron jobs (hotspot_job, risk_job, graph_job) from the "
          "Catalyst console to populate the aggregate tables, or wait for their schedule.")


if __name__ == "__main__":
    main()
