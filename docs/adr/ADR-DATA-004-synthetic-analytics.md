# ADR-DATA-004 Synthetic data through shared dbt models

**Status:** Accepted · **Date:** 2026-11-12

## Context
Dashboards and ML need realistic volumes, but simulated data must never be mistaken for real data.

## Decision
P3 writes envelope-shaped events to `synthetic.events`. The same dbt models build `analytics_synthetic` from that source (selected by a dbt variable). Demo seed: 7 days × 10 orders/day; ML set: 90 days × 30 orders/day. TEST dishes only.

## Consequences
- Real and synthetic data never share a table; tests assert zero leakage into real marts.
- Every UI showing synthetic data labels it "Simulated data".

## References
DDR-56, DDR-74; `DATA_PIPELINE_DESIGN.md` §2.4.
