# Synthetic data generator

Generates a realistic-but-fake Karnataka crime dataset for development and the demo. Standard library only — no dependencies.

```powershell
python data/generator/generate_synthetic.py --incidents 20000 --persons 6000 --seed 42
```

Outputs four CSVs into `data/output/` (gitignored), matching the Data Store model in `project_tech_stack.md` §5:
`locations.csv`, `persons.csv`, `incidents.csv`, `incident_persons.csv`.

### What's deliberately seeded (so features have signal to find)
- **Spatiotemporal hotspots** — each district has 2–3 hot cells; ~65% of incidents cluster there.
- **Time-of-day patterns** — e.g. burglaries peak at night, chain-snatching in the evening.
- **An emerging spike** — one district + crime category surges in the last 30 days (drives the trend-alert demo). The chosen combo is printed at the end of a run.
- **Network structure** — ~12% of offenders are habitual/repeat, plus co-offenders per incident, creating graph edges for link analysis.

`graph_edges`, `hotspot_cells`, `risk_scores`, etc. are **not** produced here — they are computed by the Cron/Event jobs under `functions/` (the precompute-and-serve pattern).
