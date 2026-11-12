# ADR-004 Outbox + worker; no message broker

**Status:** Accepted · **Date:** 2026-11-12

## Context
Business events must reach analytics without being lost or duplicated. Kafka or a broker would cost RAM and operations effort on the laptop (ETL spec, #17).

## Decision
Business changes write an event to `app.outbox` in the same transaction. A single worker lands outbox events to `raw` continuously and runs jobs from a PostgreSQL job queue (`SELECT … FOR UPDATE SKIP LOCKED`). Redis is used only for pub/sub and caching, not as a durable queue.

## Consequences
- No event loss on crash after commit; idempotent landing by `event_id`.
- One extra container (worker); no broker to run.
- Throughput is sized for a POC, not high volume.

## References
DDR-63, DDR-66; `DATA_PIPELINE_DESIGN.md` §2.2, §11; `DOCKER_DEPLOYMENT_DESIGN.md` §14.
