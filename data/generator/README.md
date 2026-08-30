# Synthetic data generator

Generates a realistic-but-fake Police FIR dataset for development and the demo, **strictly
following the official ER diagram** (`Police_FIR_ER_Diagram.pdf`, transcribed in
`../../ERD_SCHEMA.md`). Standard library only — no dependencies.

```powershell
python data/generator/generate_synthetic.py --cases 20000 --pool 4000 --seed 42
```

The history window ends at **today** by default and runs back `--days` (default 1095).
Pass `--end-date YYYY-MM-DD` to pin it — without that the window slides with the wall
clock, so the same seed produces different dates on a different day.

Outputs **one CSV per ERD table** into `data/output/` (gitignored) — 26 files with the exact
ERD column names, e.g. `CaseMaster.csv`, `Accused.csv`, `ArrestSurrender.csv`,
`ChargesheetDetails.csv`, `ActSectionAssociation.csv`, plus all masters (`District.csv`,
`Unit.csv`, `Employee.csv`, `Court.csv`, `Act.csv`, `Section.csv`, …).

### What's deliberately seeded (so features have signal to find)
- **CrimeNo format** — 1-digit category + 4-digit district + 4-digit unit + year + 5-digit
  serial, with a separate running serial per station/category/year (as documented in the ERD).
  `BriefFacts` additionally quotes the short form a station actually writes ("FIR No. 42/2026").
- **Real organisation** — the 350 police stations carry their real KSP names and locations
  (`KA_STATIONS`), each with a load weight so a city-market station books many times what a
  peri-urban one does. Courts are numbered JMFC/ACMM benches plus NDPS and POCSO special courts.
- **Dual-era statute layer** — the BNS/BNSS replaced the IPC/CrPC on **01-07-2024**, and an
  offence is charged under the law in force on the date it was *committed*. `SUB_HEADS`
  declare IPC/CrPC sections and `era_act_section()` maps them forward for post-cutover
  incidents, so the dataset carries a genuine IPC tail (~20%) alongside BNS cases.
- **Spatiotemporal hotspots** — each police station has 1–3 hot cells; ~65% of cases cluster there.
- **Time-of-day patterns** — burglaries peak at night, chain-snatching in the evening, etc.
- **An emerging spike** — one district + sub-head surges in the last 30 days (drives the
  trend-alert demo). The chosen combo is printed at the end of a run.
- **Case lifecycle realism** — reporting delay, arrest probability & lag, chargesheet rate &
  lag, and A/B/C final-report mix all vary by crime sub-head and gravity; case status is
  consistent with the chargesheet and court linkage.
- **Network structure** — ~12% of the accused identity pool is habitual and clusters into
  small gangs that co-offend across FIRs, so name-based entity resolution yields a real
  co-accused graph. Offenders have a home district and mostly offend there, so a cluster
  reads as a local crew rather than a statewide phantom.
- **Party demographics** — victim/accused age & gender profiles per crime; complainant
  occupation is conditioned on age, gender and urbanisation, and caste on religion.
- **Names** — drawn community-first then region-first (`NAMES` / `SURNAMES`), so a given name
  and surname always come from the same tradition and surname geography matches the district.

> **Name uniqueness is load-bearing, not cosmetic.** Analytics resolve an accused across
> FIRs by `(AccusedName, GenderID)` alone (`services/firdata.offenders()`). Two distinct
> people sharing a name would silently merge into one offender and fabricate cross-district
> links; one identity emitted under two genders would split in half and lose its links.
> `make_name(..., used=...)` guarantees the former and the pool's gender is authoritative at
> emit time for the latter — keep both if you touch this.

`graph_edges`, `hotspot_cells`, `risk_scores`, etc. are **not** produced here — they are
computed by the Cron/Event jobs under `functions/` (the precompute-and-serve pattern).
