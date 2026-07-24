# Synthetic data generator

Generates a realistic-but-fake Police FIR dataset for development and the demo, **strictly
following the official ER diagram** (`Police_FIR_ER_Diagram.pdf`, transcribed in
`../../ERD_SCHEMA.md`). Standard library only — no dependencies.

```powershell
python data/generator/generate_synthetic.py --cases 20000 --pool 4000 --seed 42
```

Outputs **one CSV per ERD table** into `data/output/` (gitignored) — 26 files with the exact
ERD column names, e.g. `CaseMaster.csv`, `Accused.csv`, `ArrestSurrender.csv`,
`ChargesheetDetails.csv`, `ActSectionAssociation.csv`, plus all masters (`District.csv`,
`Unit.csv`, `Employee.csv`, `Court.csv`, `Act.csv`, `Section.csv`, …).

### What's deliberately seeded (so features have signal to find)
- **CrimeNo format** — 1-digit category + 4-digit district + 4-digit unit + year + 5-digit
  serial, with a separate running serial per station/category/year (as documented in the ERD).
- **Spatiotemporal hotspots** — each police station has 1–2 hot cells; ~65% of cases cluster there.
- **Time-of-day patterns** — burglaries peak at night, chain-snatching in the evening, etc.
- **An emerging spike** — one district + sub-head surges in the last 30 days (drives the
  trend-alert demo). The chosen combo is printed at the end of a run.
- **Case lifecycle realism** — reporting delay, arrest probability & lag, chargesheet rate &
  lag, and A/B/C final-report mix all vary by crime sub-head and gravity; case status is
  consistent with the chargesheet and court linkage.
- **Network structure** — ~12% of the accused identity pool is habitual and clusters into
  small gangs that co-offend across FIRs, so name-based entity resolution yields a real
  co-accused graph.
- **Party demographics** — victim/accused age & gender profiles per crime; complainants carry
  occupation / religion / caste lookups.

`graph_edges`, `hotspot_cells`, `risk_scores`, etc. are **not** produced here — they are
computed by the Cron/Event jobs under `functions/` (the precompute-and-serve pattern).
