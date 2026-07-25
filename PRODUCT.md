# Product

## Register

product

## Users

Analysts and senior officers at the Karnataka State Police / State Crime Records Bureau
(SCRB), plus district-level investigators. They work at desks in operations rooms on
large monitors, often for long sessions, scanning for exceptions (spikes, anomalies,
repeat offenders) and drilling from state → district → station → person. Secondary
audience: hackathon judges evaluating the platform against the official challenge
statement (`challange.md`).

## Product Purpose

An AI-driven crime intelligence & analytics platform that replaces Excel silos with
interactive geospatial dashboards, criminological network/link analysis, and
predictive/anomaly intelligence — moving SCRB from reactive reporting to a "Strategic
Intelligence Hub". Success = every capability in the challenge statement demonstrably
working on the official Police FIR ERD, deployed on Zoho Catalyst.

## Brand Personality

Authoritative, precise, operational. A dark "command surface" — calm layered navy
surfaces, one indigo accent, semantic signal colors (danger/warning/success) reserved
for actual signals. Numbers are first-class citizens (tabular mono figures). The tool
should feel like professional intelligence software, not a marketing dashboard.

## Anti-references

- Consumer BI template look (bootstrap admin themes, gradient-heavy SaaS heroes).
- Decorative color: red/amber must always mean severity, never decoration.
- Static-chart "Excel replacement" feel — the thing this platform exists to replace.

## Design Principles

1. **Exceptions first** — spikes, anomalies and high-risk entities surface at the top
   of every relevant view; healthy states stay quiet.
2. **Drill-down is the story** — state → district → station → person → relationship;
   every aggregate is a door, not a dead end.
3. **Explain the model** — every AI/statistical output states its method (z-scores,
   risk formula, provider/model) so officers can defend it in court and judges can
   verify it.
4. **Precompute-and-serve** — the UI reads compact aggregates; nothing heavy on the
   request path (Catalyst 300-row / 30s limits).
5. **Consistent vocabulary** — one Panel/StatCard/Badge/chart-theme system across all
   pages; same affordance means the same thing everywhere.

## Accessibility & Inclusion

- Dark theme is the single committed theme (ops-room context); maintain ≥4.5:1 body
  text contrast on layered navy surfaces.
- Respect `prefers-reduced-motion` for pulsing/shimmer/entrance animations.
- Never encode meaning in color alone: severity badges carry text, charts carry
  legends + tooltips + tabular fallbacks.
