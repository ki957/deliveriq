# Database migrations

Alembic revisions in `versions/`, run by the one-off `migrate` service as `app_migrator` (DDL only). The API never migrates on startup (DOCKER_DEPLOYMENT_DESIGN §8).

| Revision | Contents |
|---|---|
| 0001 | 11 schemas (DDR-25); status-transition engine (`app.status_transitions`, `app.status_initial`, `app.status_history`, trigger function); regions, kitchens, config, users, role assignments |
| 0002 | Ingredients, recipes, recipe versions, recipe ingredients, five sign-offs, menu categories and items, readiness checklist, publication audit |
| 0003 | Transition data for six machines; orders, order items, payments, delivery assignments |
| 0004 | Outbox, `raw.events`, `synthetic.events`, pipeline-runs framework tables, `audit.events`, append-only triggers |
| 0005 | Production-safe seeds (region, synthetic kitchen fixture, config, pipeline registry) and least-privilege grants |
| 0006 | Identity: OTP challenges, sessions, trusted devices, revocation trigger (DDR-96–DDR-99) |
| 0007 | Worker grants, `ops.workers`, `ops.cancel_run()`, run report and failure class, P1 staging tables, SOP lineage columns, recipe review queue and its submit block (DDR-102–DDR-105). Needs the `worker` role: `make up` runs `make db-roles` first |
| 0008 | Order placement (DDR-109): price and fee snapshots, checkout idempotency key, one payment per order with amount and `SIM-` reference, `app.create_order()` (derives kitchen, region and fixture flag from the dishes; refuses mixed TEST/real orders), order items and payments inherit their order's fixture flag |

## How rules are enforced

- **Status machines (DDR-17, DDR-10, DDR-11):** every status column has a trigger that checks `app.status_transitions`, requires actor context and records `app.status_history`. Services set it per transaction:
  `set_config('app.actor_role', …, true)`, `app.actor_user_id`, `app.reason`, `app.correlation_id`.
  Python `domain.py` modules define the same machines; a test asserts both are identical.
- **Authority in the database:** only `KITCHEN_MANAGER` activates recipes (DDR-30); only `REGIONAL_MANAGER`/`CENTRAL_ADMIN` publish (DDR-31). Region scope for RM is checked by the backend service (Task 4/10), not here.
- **Leak controls (plan §5.2):** `is_test_fixture` on the five tables, never writable by runtime roles (column grants); fixture and real rows cannot reference each other (composite FKs); `TEST – ` prefix must match the flag; no SOP recipe can become ACTIVE (DDR-50).
- **Append-only:** audit tables, status history, sign-offs and `raw.events` reject UPDATE and DELETE for everyone.

## Downgrade / forward-fix policy

1. **Every revision has a working `downgrade()`.** The full chain is tested: each step down to base, then up to head, then base and head again, on a throwaway stack.
2. **Downgrades are for local and test only.** They drop data (0001's downgrade drops every schema). Never run them against a database whose data matters. Below 0005 they need a database without runtime rows: 0005 removes its seeds, which pipeline runs, imported recipes and fixture users reference. 0007 downgrades with data in place.
3. **Applied revisions are never edited.** A mistake found after a revision is merged to `main` is fixed by a **new forward revision**. The one exception is a revision not yet merged (still on its task branch).
4. **Seeds hold no fixture rows.** TEST dishes, users, opening stock and test orders are loaded by the fixture loader (local/test only, Task 5), never by migrations.

## Commands

```bash
make migrate                                         # upgrade head (core stack)
docker compose --project-directory . -f infra/compose.yaml --profile core \
  run --rm migrate alembic downgrade -1              # local/test only
make test-integration                                # schema, grants and state-machine tests
```
