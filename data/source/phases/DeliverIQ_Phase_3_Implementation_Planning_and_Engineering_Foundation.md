# DeliverIQ POC — Phase 3 Implementation Planning & Engineering Foundation

**Document:** Phase 3 Master Planning Specification  
**Project:** DeliverIQ — AI-enabled single cloud kitchen delivery platform  
**Phase:** 3 — Implementation Planning and Engineering Foundation  
**Version:** 1.0  
**Status:** Planning baseline; implementation gated by Phase 1 and Phase 2 approvals  
**Prepared:** 11 November 2026

---

# 1. Executive summary

Phase 3 converts the approved architecture and backend contracts into a controlled, dependency-aware implementation programme.

DeliverIQ is an AI-enabled centralized cloud kitchen delivery POC. Its core product includes Customer, Delivery Agent, Kitchen and Unified Management experiences. Its AI architecture includes three independent portal-specific harnesses and RAG pipelines—Customer, Kitchen and Management—supported by shared AI infrastructure.

The purpose of Phase 3 is to decide **what gets implemented first, in what order, in which module, with which dependencies, and how we prove each increment is correct**.

This is not permission to begin a large, uncontrolled coding effort. The actual implementation backlog must be generated from:
- Verified Phase 1 repository findings.
- Accepted Phase 1 Architecture Decision Records.
- Approved Phase 2 domain ownership and data contracts.
- Existing product requirements and portal specifications.
- Explicitly approved unresolved business decisions.

If Phase 1 and Phase 2 are not yet validated against the repository, this document remains the target implementation-planning framework. Do not treat illustrative modules, tables or APIs as existing facts.

**Core execution principle:** build and verify the operational foundation first, then shared AI infrastructure, then integrate each portal AI harness independently. AI must never become a dependency of the core order-to-delivery workflow.

---

# 2. Product and implementation scope

## 2.1 POC product

Initial deployment:
- One cloud kitchen.
- One initial region/city: Chennai.
- Architecture capable of supporting multiple kitchens and regions later.
- Simulated payment only; no real-money processing in the initial POC.
- OpenStreetMap, Leaflet and OSRM for maps/routing.
- Modular monolith with selective background workers and event-driven integration where justified.
- Local development constrained by the agreed approximate 14 GB usable RAM envelope with reserved headroom.

## 2.2 Portal scope

| Portal | Main responsibilities | Initial AI scope |
|---|---|---|
| Customer Dashboard | Browse menu, cart, checkout, orders, delivery tracking, support | Customer harness + Customer RAG |
| Delivery Agent Portal | Availability, assignments, pickup, delivery, OTP, failure handling | No AI chatbot initially |
| Kitchen Portal | Live queue, preparation, recipes, inventory and kitchen mode | Kitchen harness + Kitchen RAG |
| Unified Management Dashboard | Regional and global operations, staff, reports, configuration, audit | Management harness + Management RAG |

Regional Manager and Central Administrator remain distinct roles within one Management application.

## 2.3 Explicit non-goals for the initial implementation

- Microservices migration.
- Kubernetes deployment.
- Multi-city production rollout.
- Real payment gateway integration.
- Autonomous AI mutations.
- Model-generated SQL or arbitrary code execution.
- Cross-portal RAG retrieval.
- Advanced multi-agent orchestration without a demonstrated use case.
- Full data warehouse or complex streaming platform unless justified by measured need.

---

# 3. Entry gates and prerequisites

Phase 3 implementation planning is only actionable when the following inputs are available.

| Prerequisite | Required evidence | Gate |
|---|---|---|
| Phase 1 repository audit | Actual repository map, dependencies and implementation findings | Required |
| Phase 1 gap analysis | Prioritized gaps and conflicts | Required |
| Phase 1 ADRs | Accepted decisions or visible unresolved items | Required |
| Phase 1 system diagrams | Verified current and target architecture | Required |
| Phase 2 domain ownership | Approved entity/module/source-of-truth map | Required |
| Phase 2 database contracts | Reviewed logical/physical schema design | Required before migrations |
| Phase 2 RBAC matrix | Approved role/resource/scope permissions | Required before protected APIs |
| Phase 2 API contracts | Endpoint and request/response specifications | Required before integration |
| Phase 2 event contracts | Event catalogue and reliability semantics | Required before event consumers |
| Phase 2 data lifecycle | Privacy, audit, retention and deletion rules | Required before production data |
| AI portal specifications | Three RAG specs and shared infrastructure spec | Required before AI integration |

If a prerequisite is incomplete, plan that work as a dependency. Do not invent a decision to make the backlog appear complete.

---

# 4. Implementation strategy

## 4.1 Build in dependency order

Recommended implementation sequence:

1. Repository baseline and engineering workflow.
2. Configuration, secrets and environment validation.
3. Database migration and testing foundation.
4. Identity, sessions, RBAC and resource authorization.
5. Core domain services and API conventions.
6. Critical order/payment/kitchen/inventory/delivery transactions.
7. Event/outbox and background worker foundation where required.
8. Audit, observability and reporting read contracts.
9. Shared AI infrastructure.
10. Customer AI/RAG integration.
11. Kitchen AI/RAG integration.
12. Management AI/RAG integration.
13. Cross-portal security, quality and operational validation.
14. Controlled POC release.

This is a dependency order, not a requirement to complete every feature in one long branch. Use small, testable vertical slices.

## 4.2 Vertical-slice delivery

For each capability, deliver:
- Data model and migration.
- Domain/service logic.
- API contract and authorization.
- Frontend integration where applicable.
- Events/background work if needed.
- Audit/observability.
- Automated tests.
- Documentation.
- Acceptance evidence.

Avoid implementing all database tables first, then all APIs, then all frontend pages without an end-to-end working slice.

## 4.3 Definition of an implementation unit

Every backlog item must include:
- ID and title.
- Business outcome.
- Scope and exclusions.
- Owning module.
- Dependencies.
- Data/API/event contracts.
- Security and privacy considerations.
- Implementation tasks.
- Unit/integration/security tests.
- Acceptance criteria.
- Rollback or recovery consideration.
- Estimated effort after repository audit.
- Priority and owner.
- Status and evidence link.

---

# 5. Workstream A — Engineering foundation

## A1. Repository and branch baseline

- Confirm repository layout and ownership.
- Define branch and pull-request conventions.
- Define commit message conventions.
- Protect the main branch.
- Require review for authorization, payment, inventory and AI security changes.
- Define code ownership for critical modules.
- Remove committed secrets and add secret scanning where available.
- Record baseline dependency versions.
- Avoid mass formatting or refactoring unrelated to the work item.

**Deliverables:** contribution guide, branch policy, ownership map and clean baseline.

## A2. Local development environment

- Validate Ubuntu/Linux setup instructions.
- Define supported Python and Node versions based on actual dependencies.
- Define reproducible dependency installation.
- Define Docker Compose profiles.
- Separate required services from optional services.
- Add health checks and startup dependencies.
- Document seed/reset commands.
- Measure RAM and startup time.
- Keep actual `.env` files out of source control.
- Provide `.env.example` with placeholders only.

**Deliverables:** local setup guide, Compose profiles, environment template and resource baseline.

## A3. Quality gates and CI

Establish automated checks appropriate to the repository:
- Formatting.
- Linting.
- Type checks where adopted.
- Unit tests.
- Integration tests.
- Migration checks.
- API schema validation.
- Dependency/security scanning.
- Secret scanning.
- Build checks.
- AI evaluation/security tests when those modules are introduced.

Do not add tools solely for appearance. Select tools compatible with the current stack and team workflow.

**Deliverables:** CI pipeline, test commands and quality-gate policy.

## A4. Configuration and secrets

- Typed settings and startup validation.
- Environment-specific configuration.
- Secret injection through environment/approved secret storage.
- No frontend secrets.
- No credentials in prompts, RAG content, logs or test fixtures.
- Rotation procedure.
- Safe configuration redaction.
- Schema validation for administrative YAML.

**Deliverables:** configuration design, secrets policy and validation tests.

---

# 6. Workstream B — Database and persistence foundation

This workstream uses approved Phase 2 data contracts.

## B1. Database foundation

- Verify PostgreSQL version and required extensions.
- Configure local database roles and least privilege.
- Establish Alembic migration conventions.
- Add migration validation to CI.
- Define development/test database reset.
- Define transaction isolation and connection pool settings from workload evidence.
- Establish backup/restore procedure appropriate to the POC.
- Add indexes from documented query patterns.

## B2. Domain schema implementation order

Implement schemas in dependency order, adjusted to the verified ERD:

1. Identity and authorization.
2. Region and kitchen.
3. Customer and addresses.
4. Menu and customization.
5. Cart and checkout support.
6. Orders and status history.
7. Payments and simulated refunds.
8. Kitchen operations.
9. Recipes and recipe versions.
10. Inventory, reservations and movements.
11. Delivery and assignment history.
12. Promotions.
13. Support and reviews.
14. Reporting projections, if needed.
15. Audit.
16. Portal-specific RAG schemas.

Do not create a table simply because it appears in a planning list. Follow the approved physical schema.

## B3. Persistence acceptance

- Migrations apply cleanly to a fresh database.
- Constraints prevent invalid states.
- Critical transaction tests pass.
- Concurrent stock reservation tests pass.
- Duplicate command tests pass.
- Migration upgrade path is documented.
- Test data is deterministic and synthetic.

---

# 7. Workstream C — Identity, authentication and authorization foundation

This is a P0 security dependency for every portal and every AI tool.

## C1. Authentication

Implement or validate:
- Mobile OTP authentication.
- OTP expiry and attempt limits.
- Rate limiting and abuse protection.
- New customer registration after verified OTP.
- Staff role provisioning through authorized management workflows.
- Session and refresh lifecycle.
- Trusted-device behaviour with the approved seven-day policy.
- Logout and device revocation.
- Lost-number recovery workflow.
- Account deactivation and session revocation.

Never store plaintext OTPs or secrets. Do not expose whether an account exists where that creates account enumeration risk.

## C2. Authorization

- Central permission evaluation service/dependency.
- Multiple explicit roles where approved.
- Resource ownership validation.
- Region and kitchen scope resolution.
- RM assigned-region restriction.
- CA global permissions.
- Kitchen Staff/Manager distinctions.
- Delivery Agent assignment-specific access.
- Customer own-resource access.
- Prompt-independent authorization.
- Permission refresh and cache invalidation on role/scope changes.

## C3. Security acceptance

- Direct API requests cannot bypass UI restrictions.
- Role removal revokes access promptly.
- Region reassignment invalidates old scope.
- Customer cannot access another customer.
- Agent cannot access another agent's assignment.
- RM cannot access unassigned region data.
- Kitchen Staff cannot invoke Manager-only operations.
- AI tools use the same authorization services.

---

# 8. Workstream D — Core operational product foundation

Implement the minimum reliable order-to-delivery workflow before advanced AI integration.

## D1. Customer and menu vertical slice

- Public menu discovery.
- Serviceability check.
- Dish details and customization.
- Customer OTP and profile.
- Address selection.
- Cart and price snapshot.
- Stock and price revalidation.
- Minimum subtotal validation.
- Simulated payment/COD selection.
- Checkout idempotency.
- Clear customer-facing errors.

**Acceptance:** A customer can place a valid POC order without relying on AI.

## D2. Order and payment lifecycle

- Order creation.
- Payment attempt/result.
- Separate payment and fulfilment state.
- Idempotent simulated payment.
- Kitchen acceptance/rejection.
- Cancellation before kitchen acceptance under approved rules.
- Rejection/refund simulation.
- Status history.
- Customer order tracking.

**Acceptance:** Duplicate requests cannot create duplicate orders or payment effects; invalid state transitions are rejected.

## D3. Kitchen workflow

- Live queue.
- Accept/reject with mandatory reason on rejection.
- Preparation state.
- Item-level preparation.
- Ready-for-pickup gate.
- Kitchen mode and capacity.
- Recipe version snapshot at acceptance.
- Manager-only recipe and inventory administration.
- Escalation and delay handling.

**Acceptance:** Kitchen cannot exceed enforced capacity or mark an order ready before all required items are prepared.

## D4. Inventory correctness

- Ingredient master and units.
- Recipe ingredient mapping.
- Stock balance and movement history.
- Atomic reservation on kitchen acceptance.
- Release on valid cancellation/rejection.
- Deduction on handover.
- Adjustment with reason and actor.
- Low-stock calculation.
- Concurrency and duplicate-event protection.

**Acceptance:** No overselling, duplicate deduction or unexplained stock change in tested concurrent workflows.

## D5. Delivery workflow

- Agent availability and GPS permission.
- Assignment recommendation and manager override.
- One active assignment per agent.
- 60-second response timeout.
- Rejection reason.
- Reassignment and access revocation.
- Pickup after Ready for Pickup.
- Live location during active delivery.
- Six-digit customer OTP.
- Three failed attempts and escalation.
- Customer-unavailable and failure workflows.
- COD simulation handling.

**Acceptance:** Assignment, pickup and completion transitions are server-authoritative and auditable.

## D6. Unified Management foundation

- RM/CA navigation and permissions.
- Region-scoped operations.
- Staff provisioning boundaries.
- Kitchen and delivery operational views.
- Order exceptions.
- Payment/refund read and approved management workflows.
- Dish-unavailability approvals.
- Promotions and support/review controls.
- Reports and audit read views.
- Configuration metadata and validated configuration workflows.

**Acceptance:** RM scope is enforced on every protected API; CA global actions require explicit permission and audit.

---

# 9. Workstream E — API and event implementation foundation

## E1. API implementation

- Implement approved Phase 2 API contracts.
- Maintain OpenAPI.
- Use typed schemas.
- Standardize error responses.
- Implement pagination and filtering.
- Enforce authentication and authorization centrally.
- Apply idempotency to retryable commands.
- Add request/correlation IDs.
- Avoid leaking internal database models.

## E2. Event and worker implementation

Implement only the events approved in Phase 2.

Where required:
- Transactional outbox.
- Background worker.
- Idempotent consumers.
- Bounded retries.
- Dead-letter/reconciliation handling.
- Event versioning.
- Structured event tracing.

Do not introduce Kafka/RabbitMQ unless the Phase 1/2 evidence justifies it. PostgreSQL outbox plus a worker may be sufficient for the POC.

## E3. Critical event tests

- Duplicate delivery.
- Worker restart.
- Retry exhaustion.
- Out-of-order event.
- Consumer idempotency.
- Outbox recovery.
- Event schema compatibility.

---

# 10. Workstream F — Shared AI infrastructure implementation

This workstream implements the shared AI infrastructure specification. It begins after the core identity, data ownership and API boundaries are stable.

## F1. LLM gateway

- Internal DeliverIQ gateway interface.
- Provider adapters.
- Groq adapter for the approved POC route.
- OpenRouter adapter only if its role is approved.
- Model profiles and allowlists.
- Typed response/error normalization.
- Timeout, retry, rate and concurrency controls.
- Usage metadata and per-portal accounting.
- Streaming only where a portal requires it.
- No provider credentials or model endpoints in frontend code.

**Acceptance:** Portal harnesses call the internal gateway, not provider SDKs directly.

## F2. Embedding service

- Provider-independent interface.
- Benchmark candidate embedding models.
- Select model using representative portal datasets.
- Validate vector dimensions.
- Track model/version.
- Batch document embedding.
- Retry and queue failed ingestion.
- Re-embedding migration procedure.

**Acceptance:** Document and query vectors are compatible and model identity is traceable.

## F3. Shared ingestion framework

- Source adapter interface.
- Extraction and normalization.
- Portal approval gates.
- Content hashing and versioning.
- Chunking primitives.
- Metadata validation.
- Embedding batch client.
- Atomic publish.
- Withdrawal and expiry.
- Job retries and reconciliation.

**Acceptance:** Shared code supports portal ingestion without merging portal approval or authorization policies.

## F4. Shared retrieval primitives

- Vector search.
- PostgreSQL lexical search.
- Candidate fusion.
- Optional reranker interface.
- Provenance formatting.
- Safe empty-result handling.

**Acceptance:** Portal-specific retrieval wrappers enforce filters before candidates reach the model. No all-portal retrieval endpoint exists.

## F5. Observability and evaluation

- Request tracing.
- Provider/model/version tracking.
- Token usage and cost.
- Retrieval metrics.
- Ingestion freshness.
- Prompt/version tracking.
- Error/fallback metrics.
- Redaction and retention.
- Common evaluation runner.
- Portal-specific evaluation datasets.

**Acceptance:** Quality, latency, cost and security behaviour can be measured without logging secrets or unnecessary personal data.

---

# 11. Workstream G — Portal AI/RAG integrations

Implement each portal independently. Do not activate all three simultaneously before each one passes its own gates.

## G1. Customer AI/RAG

Knowledge:
- Approved customer-visible menu information.
- Customer policies.
- FAQs.
- Ordering and delivery guidance.

Live tools:
- Current price.
- Availability.
- Serviceability.
- Delivery quote.
- Authenticated customer's own orders/status.
- Support options.

Guardrails:
- No kitchen recipes/internal procedures.
- No internal stock quantities or management data.
- No invented ingredients, allergens, nutrition, prices or ETA.
- No order/payment/cancellation mutation tools.
- Customer ownership checked server-side.

## G2. Kitchen AI/RAG

Knowledge:
- Recipe knowledge and version history.
- Kitchen SOPs.
- Approved food-handling guidance.
- Troubleshooting.

Live tools:
- Order preparation context.
- Order-pinned recipe version.
- Kitchen queue and preparation state.
- Authorized inventory/capacity insights.

Guardrails:
- Recipe version for accepted order must be preserved.
- Staff/Manager permissions remain distinct.
- No order, stock, recipe, capacity, mode or ETA mutations.
- No Customer or Management RAG access.

## G3. Management AI/RAG

Knowledge:
- Operational SOPs.
- Business policies.
- Management documentation.
- Analytics definitions.

Live tools:
- Role-scoped operations summaries.
- Exceptions.
- Reports and KPI values.
- Authorized audit/configuration read views.

Guardrails:
- RM assigned regions only.
- CA approved global/regional scope.
- No Customer or Kitchen RAG access.
- No staff, refund, promotion, approval, configuration or YAML mutations.

## G4. Portal rollout gates

For each portal:
1. Ingestion quality verified.
2. Retrieval relevance evaluated.
3. Tool authorization tests passed.
4. Prompt-injection tests passed.
5. No cross-portal leakage.
6. Grounded answer and abstention behaviour validated.
7. Latency/cost acceptable.
8. Feature flag and failure handling tested.
9. Product owner accepts the portal.

---

# 12. Workstream H — Testing, security and performance

## H1. Test pyramid

- Unit tests for domain logic, validators and utilities.
- Database integration tests for constraints and transactions.
- API integration tests for contracts and authorization.
- Event/worker tests for retries and idempotency.
- Frontend component and workflow tests.
- End-to-end order-to-delivery tests.
- AI retrieval and grounded-answer evaluations.
- Security and privacy negative tests.
- Load and resource tests.

## H2. Critical end-to-end scenarios

1. Customer places COD order; kitchen accepts; agent delivers; customer OTP completes.
2. Customer prepaid simulation succeeds; order becomes eligible for kitchen.
3. Simulated payment fails; kitchen processing does not begin.
4. Kitchen rejects; order and payment/refund states remain consistent.
5. Inventory reservation prevents concurrent overselling.
6. Duplicate acceptance does not reserve stock twice.
7. Kitchen marks all items prepared; order becomes Ready for Pickup.
8. Agent cannot pick up before Ready for Pickup.
9. Assignment timeout returns work safely to the pool.
10. Reassignment revokes previous agent access.
11. OTP failure limit escalates.
12. Customer cannot view another customer's order.
13. RM cannot view an unassigned region.
14. Kitchen Staff cannot use Manager-only tools.
15. AI provider outage does not interrupt core order processing.
16. Each AI harness cannot retrieve another portal's knowledge.
17. RAG withdrawal removes content from active retrieval.
18. Current operational facts are obtained from APIs, not stale chunks.

## H3. Performance and resource validation

Measure on the actual POC host:
- Baseline idle RAM.
- Peak RAM during normal workflows.
- Database and worker memory.
- Ingestion and embedding workload.
- Concurrent API requests.
- AI request concurrency.
- P50/P95 API and AI latency.
- CPU, disk and network usage.
- Startup and recovery time.

Do not set artificial performance targets before establishing the baseline and product expectations. Record target, measurement method and observed result.

---

# 13. Workstream I — Deployment and operational readiness

## I1. Deployment progression

1. Local development.
2. Automated test environment.
3. Staging/production-like validation.
4. Controlled POC deployment.

Use Docker Compose initially if confirmed by Phase 1. Kubernetes is not a POC prerequisite.

## I2. Operational requirements

- Health/readiness checks.
- Structured logs and correlation IDs.
- Metrics and alert thresholds.
- Database backup and restore tests.
- Migration runbook.
- Secret rotation.
- Provider outage handling.
- AI feature flags per portal.
- Incident and rollback procedures.
- Operational ownership and escalation.

## I3. Release controls

- Feature flags for AI capabilities.
- Independent enable/disable per portal.
- Database migration review.
- Backward-compatible API changes where possible.
- Security test pass.
- Regression test pass.
- Backup before risky migration.
- Staged rollout and rollback plan.

---

# 14. Implementation backlog structure

Create a single prioritized backlog with these fields:

| Field | Description |
|---|---|
| ID | Stable task identifier |
| Epic | Domain/workstream |
| Title | Clear implementation outcome |
| Business value | Why the work is needed |
| Priority | P0, P1, P2, P3 |
| Status | Proposed, ready, in progress, blocked, review, done |
| Owner | Responsible engineer |
| Dependencies | Required tasks/decisions |
| Module | Owning code/domain module |
| Data contract | Schema/migration references |
| API contract | OpenAPI operation references |
| Event contract | Event schema references |
| Security | Authorization/privacy requirements |
| Tests | Required automated evidence |
| Acceptance criteria | Observable completion conditions |
| Estimate | Added after repository review |
| Risk | Technical/product risk |
| Evidence | PR, test report, diagram or decision |

## Suggested epics

- E01 — Engineering foundation.
- E02 — Configuration and environments.
- E03 — Database and migrations.
- E04 — Identity and authorization.
- E05 — Customer and menu.
- E06 — Orders and payments.
- E07 — Kitchen and recipes.
- E08 — Inventory.
- E09 — Delivery.
- E10 — Management operations.
- E11 — API and events.
- E12 — Audit and reporting.
- E13 — Shared AI infrastructure.
- E14 — Customer AI/RAG.
- E15 — Kitchen AI/RAG.
- E16 — Management AI/RAG.
- E17 — Security and evaluation.
- E18 — Deployment and release.

---

# 15. Recommended milestone plan

These are dependency-based milestones, not calendar estimates. Estimate duration only after repository audit, team capacity and scope are known.

| Milestone | Scope | Exit evidence |
|---|---|---|
| M0 — Baseline ready | Repo, CI, environments, decisions | Reproducible build and approved backlog |
| M1 — Identity foundation | OTP/session/RBAC/scope | Authorization tests pass |
| M2 — Core order flow | Customer/menu/cart/checkout/payment/order | End-to-end order test passes |
| M3 — Kitchen/inventory | Queue, recipes, reservation and preparation | Transaction/concurrency tests pass |
| M4 — Delivery/management | Assignment, tracking, OTP, management permissions | End-to-end delivery and scope tests pass |
| M5 — AI platform | Gateway, embeddings, ingestion, retrieval, observability | Shared AI infrastructure tests pass |
| M6 — Customer AI | Customer RAG and tools | Customer acceptance/security gates pass |
| M7 — Kitchen AI | Kitchen RAG and tools | Kitchen acceptance/security gates pass |
| M8 — Management AI | Management RAG and tools | Management acceptance/security gates pass |
| M9 — POC release | Regression, load, security, backup and runbooks | Release checklist approved |

Do not force parallel delivery where it creates unresolved data or authorization dependencies.

---

# 16. Prioritization rules

## P0 — Must precede dependent work

- Verified architecture and approved contracts.
- Identity and authorization.
- Source-of-truth ownership.
- Order/payment state integrity.
- Inventory reservation/deduction correctness.
- Delivery assignment ownership and completion security.
- Portal and region isolation.
- Secret management.
- AI read-only tool boundaries.

## P1 — Required for reliable POC

- API consistency.
- Event/outbox reliability where needed.
- Audit and observability.
- RAG ingestion/versioning/withdrawal.
- Hybrid retrieval and evaluation.
- Graceful AI degradation.
- Backup/restore and deployment runbooks.

## P2 — Optimization and expansion

- Advanced reranking.
- Sophisticated caching.
- Advanced analytics.
- Additional provider routing.
- Multi-city readiness work beyond necessary domain support.
- Selective service extraction based on measured bottlenecks.

---

# 17. Phase 3 deliverables

| ID | Deliverable | Contents |
|---|---|---|
| P3-D01 | Implementation Roadmap | Dependency-ordered milestones |
| P3-D02 | Master Engineering Backlog | Epics, tasks, priorities and acceptance |
| P3-D03 | Module Ownership Map | Code/domain owners and dependency direction |
| P3-D04 | Engineering Workflow | Branches, reviews, CI and quality gates |
| P3-D05 | Environment Build Plan | Local/test/staging setup and resource profiles |
| P3-D06 | Database Implementation Plan | Migrations, seed data and test strategy |
| P3-D07 | Identity/RBAC Build Plan | Auth, roles, scopes and negative tests |
| P3-D08 | Core Workflow Build Plan | Order, payment, kitchen, inventory and delivery |
| P3-D09 | API/Event Build Plan | Contract-to-code implementation sequence |
| P3-D10 | Shared AI Build Plan | Gateway, embeddings, ingestion, retrieval |
| P3-D11 | Portal AI Integration Plans | Three independent harness rollout plans |
| P3-D12 | Test and Security Plan | Automated coverage and release gates |
| P3-D13 | Deployment/Operations Plan | Monitoring, backup, rollback and runbooks |
| P3-D14 | Risk and Decision Register | Open decisions, risks, owners and due gates |

---

# 18. Phase 3 exit criteria

Phase 3 is complete when:

- [ ] Phase 1 and Phase 2 entry gates are satisfied or remaining gaps are explicitly tracked.
- [ ] Every implementation epic has a defined outcome and owner.
- [ ] Dependencies are sequenced.
- [ ] Critical P0 tasks are identified.
- [ ] Module ownership and dependency direction are documented.
- [ ] Database, API and event contracts are linked to backlog items.
- [ ] Authentication and authorization are scheduled before protected features.
- [ ] Order/payment/inventory/delivery correctness has explicit acceptance tests.
- [ ] Shared AI infrastructure is sequenced before portal AI integrations.
- [ ] Each portal AI rollout has independent security and quality gates.
- [ ] Resource constraints and deployment plan are included.
- [ ] CI, testing and code-review gates are defined.
- [ ] Risks and unresolved decisions have owners.
- [ ] No unapproved mutation capability is planned for AI.
- [ ] Product owner approves the implementation roadmap.

---

# 19. Handoff to Phase 4

Phase 4 should be **Engineering Foundation and Core Platform Implementation**.

It should begin with:
1. Repository baseline and CI.
2. Environment/configuration/secrets.
3. Database migrations and test fixtures.
4. Identity, sessions and authorization.
5. Shared API/error conventions.
6. Audit and correlation foundations.
7. Core order-to-delivery vertical slice.

The exact work sequence must be generated from the approved backlog and repository evidence. Do not start the LLM gateway before the required identity, data and API boundaries are stable.

---

# 20. Execution protocol

## Step 1 — Verify inputs

Read Phase 1 findings and Phase 2 contracts. Identify any missing approval or unresolved decision.

## Step 2 — Map work to actual repository

For each epic, identify:
- Existing module/file locations.
- Reusable code.
- Required changes.
- Missing modules.
- Migration impact.
- Test impact.

Do not assume the suggested architecture folders already exist.

## Step 3 — Build dependency graph

Identify critical path and independent work. Keep authorization and data ownership ahead of AI integration.

## Step 4 — Create implementation tickets

Each ticket must be small enough to review, test and revert independently where practical.

## Step 5 — Review acceptance criteria

Product rules and security boundaries must be observable in tests. “Works” is not an acceptance criterion.

## Step 6 — Approve implementation roadmap

Obtain approval before broad implementation. Implement one vertical slice at a time and update the backlog with evidence.

---

# 21. Final instruction to the engineering agent

Act as DeliverIQ's technical programme architect and implementation lead.

Convert the verified architecture, data model, API contracts, authorization rules and AI specifications into a realistic engineering execution plan.

Prioritize core transactional correctness and authorization before AI integration. Keep the modular monolith maintainable. Reuse existing infrastructure. Do not add services, databases, queues or agent frameworks without a clear requirement and measured benefit.

Build the shared AI platform only after the application has stable identity, data ownership and API boundaries. Integrate Customer, Kitchen and Management AI independently. Preserve read-only AI permissions for the initial POC and make every AI capability independently disableable.

Do not claim implementation is complete because a plan exists. Track code, tests, reviews, decisions and acceptance evidence separately.

The Phase 3 result must be a dependency-aware, testable and approved implementation roadmap that engineering can execute incrementally without conflicting assumptions.
