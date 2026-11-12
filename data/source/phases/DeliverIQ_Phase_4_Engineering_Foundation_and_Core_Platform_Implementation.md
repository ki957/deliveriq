# DeliverIQ POC — Phase 4 Engineering Foundation and Core Platform Implementation

**Document:** Phase 4 Master Implementation Specification  
**Project:** DeliverIQ — AI-enabled single cloud kitchen delivery platform  
**Phase:** 4 — Engineering Foundation and Core Platform Implementation  
**Version:** 1.0  
**Status:** Execution specification; gated by approved Phase 1, Phase 2 and Phase 3 outputs  
**Prepared:** 11 November 2026

---

# 1. Executive summary

Phase 4 begins controlled engineering implementation of DeliverIQ.

The objective is to establish a reproducible development environment, safe configuration and secrets handling, database migration/testing foundations, identity and authorization, and the first reliable core operational workflows.

The implementation target is a working application foundation—not a collection of disconnected modules.

**Primary outcome:** DeliverIQ can execute the core order-to-delivery workflow without depending on AI.

AI infrastructure and the three portal-specific AI/RAG integrations are deliberately deferred to the next dedicated implementation phase, after identity, data ownership, API contracts and operational boundaries are stable.

This document is an implementation playbook. It does not prove that any task has been implemented. Every completed item must be supported by code review, automated tests and acceptance evidence.

---

# 2. Phase 4 objectives

1. Establish a reproducible repository and local development workflow.
2. Establish CI quality gates.
3. Validate configuration and secret handling.
4. Establish PostgreSQL migration and integration-test foundations.
5. Implement authentication, sessions and authorization.
6. Implement shared API conventions and error handling.
7. Implement audit and request-correlation foundations.
8. Deliver a vertical slice of the core order-to-delivery workflow.
9. Prove transaction correctness for payment, inventory and delivery transitions.
10. Keep the application within the POC resource envelope.

## 2.1 In scope

- Repository and environment baseline.
- Configuration and secret management.
- CI and code-quality automation.
- Database migrations and test fixtures.
- Identity and role/scope authorization.
- Domain service foundations.
- API conventions and OpenAPI.
- Audit and observability foundations.
- Customer, menu, cart and checkout.
- Simulated payments and order lifecycle.
- Kitchen queue and preparation.
- Ingredient inventory and reservations.
- Delivery assignment, tracking and completion.
- Essential Management workflows.
- Core end-to-end and security tests.

## 2.2 Out of scope

- Shared LLM gateway implementation.
- Embedding service implementation.
- RAG ingestion/retrieval implementation.
- Customer, Kitchen or Management AI Copilots.
- Real payment processing.
- Microservices extraction.
- Kubernetes.
- Multi-city production deployment.
- Advanced analytics warehouse.
- Autonomous AI actions.

---

# 3. Mandatory entry gates

Do not begin broad implementation until these inputs are reviewed.

| Gate | Required approved input |
|---|---|
| G1 | Phase 1 repository audit and actual current-state architecture |
| G2 | Phase 1 accepted ADRs or explicitly tracked open decisions |
| G3 | Phase 2 entity ownership and approved data model |
| G4 | Phase 2 API and event contracts |
| G5 | Phase 2 RBAC and resource-scope matrix |
| G6 | Phase 3 dependency-aware backlog and acceptance criteria |
| G7 | Repository backup/version-control baseline |
| G8 | Product approval for any unresolved business rule |

If the actual repository differs from the plan, stop the affected task and update the architecture/backlog. Never fabricate repository structure or assume a technology is installed.

---

# 4. Execution rules

## 4.1 Repository-first implementation

Before changing code:
- Inspect the actual repository tree.
- Read package manifests and lockfiles.
- Inspect current application entry points.
- Inspect existing migrations and database models.
- Inspect authentication and authorization code.
- Inspect existing tests and CI.
- Identify reusable modules and known defects.
- Record the exact files expected to change.

Do not replace an existing working implementation simply because a proposed folder structure looks cleaner.

## 4.2 Small vertical slices

Each implementation increment must be:
- Small enough to review.
- Independently testable.
- Consistent with approved contracts.
- Reversible where practical.
- Documented with evidence.

Avoid giant rewrites, unrelated refactoring and speculative abstractions.

## 4.3 Approval boundaries

Request product-owner approval before:
- Changing order/payment/cancellation rules.
- Changing stock reservation or deduction semantics.
- Changing role permissions or regional scope.
- Changing recipe-version behaviour.
- Changing delivery completion or failure rules.
- Adding a new database or message broker.
- Introducing a new external paid service.
- Enabling any AI mutation capability.

Routine implementation details that preserve approved contracts may proceed under normal code review.

---

# 5. Workstream A — Repository and engineering baseline

## A1. Establish baseline

- Capture repository commit and branch.
- Confirm clean/known working-tree state.
- Record runtime and dependency versions.
- Identify frontend, backend, database and infrastructure entry points.
- Record existing test commands.
- Record known failures before making changes.
- Create a baseline repository map.

## A2. Engineering conventions

Adopt conventions consistent with the repository:
- Naming and module boundaries.
- Formatting and linting.
- Type checking where supported.
- Error handling.
- Logging.
- Test naming and fixtures.
- Migration naming.
- API schema conventions.
- Pull-request review checklist.

Do not enforce a new convention by mass-editing unrelated files.

## A3. Branch and review policy

- Keep the main branch protected where repository hosting supports it.
- Use focused feature branches.
- Require review for auth, payment, inventory, role and data-access changes.
- Require automated tests for merge.
- Keep commits logically scoped.
- Never commit credentials, tokens, private keys or real customer data.

**Exit evidence:** clean baseline, repository map, working development instructions and review policy.

---

# 6. Workstream B — Local environment, configuration and secrets

## B1. Environment setup

Document and verify:
- Supported OS and runtime versions.
- Dependency installation.
- Environment variable setup.
- Database startup.
- Optional service startup.
- Migration command.
- Seed command.
- Test command.
- Application startup and shutdown.
- Reset procedure.

Use the actual dependency versions found in the repository and approved by Phase 1.

## B2. Docker Compose

If Phase 1 confirms Docker Compose:
- Separate core-required services from optional profiles.
- Add health checks.
- Avoid unnecessary always-on services.
- Use persistent volumes where needed.
- Document port allocation.
- Document safe reset behaviour.
- Measure memory usage.

Do not add MongoDB, Redis, MinIO or a broker unless an approved use case requires it.

## B3. Configuration

- Centralize typed configuration.
- Validate required settings at startup.
- Separate local, test and deployment configuration.
- Use safe defaults only for non-secret development settings.
- Fail clearly when required configuration is missing.
- Redact secrets in logs and diagnostics.
- Validate administrative YAML against an approved schema.
- Never permit arbitrary code execution through configuration editing.

## B4. Secrets

- Keep `.env` and secret files out of Git.
- Provide placeholder-only `.env.example`.
- Rotate any credential found committed or exposed.
- Keep provider credentials server-side.
- Never place credentials in frontend bundles, prompts, RAG documents or logs.

**Exit evidence:** a new developer can reproduce the environment using documented steps, without access to another developer's secrets.

---

# 7. Workstream C — CI and quality gates

Configure CI based on the actual stack.

Minimum checks:
1. Dependency installation/build.
2. Formatting check.
3. Lint.
4. Type checks if adopted.
5. Unit tests.
6. Database integration tests.
7. Migration validation.
8. API/OpenAPI validation.
9. Secret scanning.
10. Dependency/security scanning.

Add later:
- End-to-end tests.
- Event/worker tests.
- Load tests.
- AI evaluation and prompt-injection tests.

CI must fail on required checks. Do not make security or test jobs decorative or permanently non-blocking without an explicit reason.

**Exit evidence:** a pull request runs repeatable checks and reports failures clearly.

---

# 8. Workstream D — Database and migration foundation

## D1. Database decision

Use the approved Phase 1/2 database decision. PostgreSQL is the planned transactional source of truth. Retain MongoDB only if a concrete, approved workload justifies it.

Do not duplicate ownership of orders, payments, stock, recipes or users across databases.

## D2. Migration foundation

- Configure Alembic if approved for the Python/FastAPI stack.
- Establish migration naming and review.
- Test clean database creation.
- Test upgrade from the current baseline.
- Document rollback limitations and forward-fix policy.
- Ensure migrations are deterministic.
- Prevent application startup from silently applying unreviewed production migrations.

## D3. Database roles and constraints

- Least-privilege application roles.
- Separate migration privileges from runtime privileges where practical.
- Foreign keys for ownership relationships.
- Unique constraints for natural business uniqueness.
- Check constraints for valid values.
- Indexes from known access patterns.
- Explicit timestamp and timezone handling.
- Fixed-precision monetary representation.
- Avoid storing derived values as authoritative state unless the contract defines a snapshot.

## D4. Test fixtures

- Synthetic customers and staff.
- Synthetic regions and kitchen.
- Synthetic menu and recipe data.
- Synthetic orders and payment attempts.
- Synthetic inventory and delivery agents.
- Repeatable fixture reset.
- No real personal data in tests.

**Exit evidence:** fresh database setup, migrations and core persistence tests pass.

---

# 9. Workstream E — Identity, sessions and authorization

This is a security-critical foundation. Complete it before exposing protected business APIs.

## E1. Authentication

Implement the approved mobile OTP flow:
- Request OTP.
- Rate-limit requests.
- Store OTP securely using an appropriate hash/verification approach.
- Enforce expiry and attempt limits.
- Verify OTP.
- Register new customer after successful verification.
- Create staff sessions only through approved provisioning.
- Issue and rotate sessions/tokens according to the approved design.
- Support logout and device revocation.
- Apply the seven-day trusted-device policy if retained in approved contracts.
- Implement the approved lost-number recovery path.

Use an SMS provider abstraction or a clearly isolated development OTP adapter. Never expose development OTP shortcuts in a deployed environment.

## E2. Authorization service

Implement centralized authorization for:
- Customer ownership.
- Delivery agent's active assignment.
- Kitchen Staff permissions.
- Kitchen Manager permissions.
- Regional Manager assigned-region scope.
- Central Administrator global scope.

Authorization must be checked in backend services/API dependencies, not merely by hiding frontend controls.

## E3. Permission change lifecycle

- Role removal revokes access.
- Region reassignment refreshes effective permissions.
- Deactivation does not strand an active delivery.
- Old delivery assignment loses access after reassignment.
- Session and permission caches are invalidated safely.

## E4. Security tests

Required negative tests:
- Anonymous user calls protected endpoint.
- Customer accesses another customer's order.
- Agent accesses another agent's assignment.
- RM accesses unassigned region.
- Kitchen Staff invokes Manager-only operation.
- Removed role continues using an old session.
- Reassigned agent uses old assignment URL.
- CA-only role administration is invoked by RM.

**Exit evidence:** positive and negative authorization tests pass for every protected module.

---

# 10. Workstream F — Shared API and application foundations

## F1. API conventions

- Implement approved Phase 2 API contracts.
- Maintain OpenAPI.
- Use request/response schemas.
- Standardize error envelope and stable error codes.
- Validate all input server-side.
- Add pagination and filtering where required.
- Add request/correlation IDs.
- Avoid exposing internal ORM objects directly.
- Apply rate limits to sensitive endpoints.
- Use idempotency keys for critical commands.

## F2. Domain service boundaries

Use the approved modular-monolith boundaries. Candidate domains include:
- Identity and access.
- Customer and profile.
- Region and kitchen.
- Menu and pricing.
- Cart and checkout.
- Orders.
- Payments.
- Kitchen operations.
- Recipes.
- Inventory.
- Delivery.
- Promotions.
- Support and reviews.
- Management and audit.

These are logical boundaries; actual package/module placement must follow repository findings.

## F3. Dependency direction

- API layer validates and delegates.
- Domain/application services own business decisions.
- Persistence adapters implement data access.
- External providers are isolated behind interfaces.
- Frontend never connects directly to the database.
- AI is not called from critical transaction logic.

**Exit evidence:** representative APIs follow consistent validation, authorization, errors and OpenAPI conventions.

---

# 11. Workstream G — Audit and observability foundation

Implement:
- Structured logs.
- Request and correlation IDs.
- Actor identity where known.
- Domain entity and action references.
- Audit records for sensitive management actions.
- Error reporting without secret/PII leakage.
- Health and readiness endpoints.
- Basic metrics for API and worker behaviour.

Audit records should capture who did what, to which resource, when, and the outcome. Do not store OTPs, credentials, full payment secrets or unnecessary personal data.

Audit must not be editable through ordinary business APIs.

**Exit evidence:** sensitive actions are traceable and logs can correlate a request across application layers.

---

# 12. Workstream H — Core customer-to-order vertical slice

Build the first end-to-end slice before broadening the feature set.

## H1. Public menu and serviceability

- Public menu discovery.
- Dish detail and customization.
- Serviceability check using approved distance rules.
- Revalidate serviceability at checkout.
- Clear unavailable/out-of-area response.

## H2. Customer identity and address

- OTP login.
- New customer registration.
- Profile basics.
- Multiple saved addresses.
- Default address selection.
- Ownership enforcement.

## H3. Cart and checkout

- Add/update/remove items.
- Customization validation.
- Price snapshot and 30-minute protection policy where approved.
- Revalidate price and stock at checkout.
- ₹500 minimum food subtotal.
- Handle out-of-stock items with clear customer confirmation.
- Checkout idempotency.

## H4. Acceptance criteria

- Public browsing works without login.
- Protected customer actions require verified identity.
- Customer cannot access another customer's cart/address.
- Invalid customization is rejected server-side.
- Price and stock are revalidated before order placement.
- Duplicate checkout submission does not create duplicate orders.
- AI outage has no impact on this workflow.

---

# 13. Workstream I — Simulated payment and order lifecycle

## I1. Payment simulation

- Simulate UPI/card success and failure.
- Support COD selection.
- Persist payment attempts and results.
- Keep payment state separate from fulfilment state.
- Make simulated payment idempotent.
- Never represent the POC simulator as a real payment gateway.

## I2. Order lifecycle

Implement approved transitions:
- Order created/placed.
- Awaiting kitchen decision.
- Kitchen accepted or rejected.
- Preparing.
- Ready for pickup.
- Handed over.
- In transit.
- Delivered.
- Cancelled or failed through approved paths.

The exact state names and transition graph must follow Phase 2 contracts.

## I3. Critical invariants

- Prepaid payment success precedes kitchen processing.
- COD may proceed according to approved rules.
- Kitchen rejection produces the correct cancellation/refund simulation.
- Customer cancellation follows the approved acceptance boundary.
- Payment and fulfilment states never overwrite each other.
- Every transition is validated server-side.
- Duplicate commands cannot repeat financial or fulfilment effects.

## I4. Acceptance tests

- Successful simulated prepaid order.
- Failed simulated payment.
- COD order.
- Duplicate payment callback/command.
- Kitchen rejection.
- Eligible cancellation.
- Ineligible cancellation.
- Refund simulation consistency.

---

# 14. Workstream J — Kitchen and inventory workflow

## J1. Kitchen queue

- Eligible orders appear in the queue.
- FIFO ordering by approved acceptance timestamp.
- Capacity is enforced server-side.
- Normal, Busy and Paused modes.
- Existing accepted orders continue under approved rules.
- Authorized staff can accept/reject.
- Rejection requires a reason.
- Unaccepted timeout and escalation.
- Preparation and item-level progress.
- Ready state only when all items are prepared.

## J2. Recipe versioning

- Recipe and ingredient records.
- Recipe version history.
- Pin recipe version to accepted order.
- Recipe edits affect new orders only.
- Preserve historical recipe reference for older orders.
- Manager-only recipe administration.

## J3. Inventory

- Ingredient stock records and units.
- Recipe ingredient mapping.
- Atomic stock reservation on acceptance.
- Reservation release on valid cancellation/rejection.
- Deduction at handover.
- Adjustment reason and actor.
- Stock movement ledger.
- Low-stock alerts.
- Manager-only adjustment.

## J4. Concurrency and integrity

Test:
- Two orders competing for the last available ingredient.
- Duplicate acceptance.
- Duplicate cancellation/rejection event.
- Handover retried after timeout.
- Worker restart during reservation processing.
- Recipe changed after an order is accepted.

**Exit evidence:** inventory cannot be oversold or deducted twice in tested concurrent/retry scenarios.

---

# 15. Workstream K — Delivery workflow

Implement:
- Agent Online/Offline state.
- Assignment recommendation and manager override.
- One active delivery per agent.
- Assignment response timeout of 60 seconds.
- Rejection reason.
- Safe reassignment.
- Assignment-specific access.
- GPS permission and location updates.
- Real and simulated GPS modes clearly distinguished.
- OpenStreetMap/Leaflet/OSRM integration according to approved design.
- Pickup only after Ready for Pickup.
- Customer OTP completion.
- Three failed OTP attempts escalate.
- Customer unavailable workflow with five-minute wait.
- Delivery failure reason and manager resolution.
- COD simulation handling.

## Acceptance criteria

- An agent cannot accept a second active assignment.
- A previous agent cannot access a reassigned order.
- Pickup is rejected before kitchen readiness.
- Delivery completion requires valid OTP.
- Failed OTP attempts trigger escalation.
- GPS denial is handled without fabricating coordinates.
- Manager overrides are authorized and audited.

---

# 16. Workstream L — Unified Management foundation

Implement the approved RM/CA role separation:
- Shared Management application.
- RM limited to assigned regions.
- CA global authority within approved controls.
- Staff role provisioning boundaries.
- Region and kitchen management.
- Kitchen/delivery operational views.
- Order exception handling.
- Dish-unavailability approval.
- Refund simulation workflows.
- Promotion management.
- Support and review workflows.
- Persisted-data reporting.
- Audit views.
- Validated configuration editor.

Never rely on frontend navigation to enforce regional access. Scope every backend query and mutation.

**Acceptance criteria:** every management API has positive and negative tests for role and region scope.

---

# 17. Workstream M — Event and background processing foundation

Only implement events approved in Phase 2.

If the POC requirements can be met with PostgreSQL outbox and a worker, do not add a separate broker without evidence.

Where needed:
- Transactional outbox.
- Worker lifecycle.
- Idempotent consumers.
- Retry policy.
- Dead-letter/failure visibility.
- Reconciliation.
- Event versioning.
- Correlation IDs.

Test duplicate delivery, process restart, retry exhaustion, out-of-order messages and replay safety.

Do not claim exactly-once delivery. Design for at-least-once delivery and idempotent effects.

---

# 18. Workstream N — Frontend integration

Use the actual frontend framework and repository conventions confirmed in Phase 1.

For each completed backend vertical slice:
- Integrate the corresponding portal screens.
- Handle loading, empty, success and error states.
- Hide unavailable actions for usability, but enforce permissions in backend.
- Prevent duplicate submissions.
- Handle expired sessions.
- Display state transitions from server responses.
- Make responsive layouts consistent with the approved portal design.
- Avoid hardcoded operational facts.

Frontend integration must not create an alternate source of truth for prices, permissions, order state or inventory.

---

# 19. Testing and verification strategy

## 19.1 Required test layers

| Layer | What it proves |
|---|---|
| Unit | Business rules and state transitions |
| Database integration | Constraints, transactions and locking |
| API integration | Contracts, validation and authorization |
| Worker/event | Retry and idempotency |
| Frontend | Interaction and error handling |
| End-to-end | Full customer-to-delivery workflow |
| Security | Unauthorized access is denied |
| Resource | POC host remains stable |

## 19.2 Minimum end-to-end scenarios

1. Customer places COD order and completes delivery.
2. Customer places prepaid simulation order and completes delivery.
3. Payment failure blocks kitchen processing.
4. Kitchen rejection triggers correct order/payment handling.
5. Concurrent reservations cannot oversell stock.
6. Duplicate acceptance cannot reserve twice.
7. Order cannot be ready before all items are prepared.
8. Agent cannot pick up before readiness.
9. Assignment timeout safely returns work to the pool.
10. Reassignment removes old agent access.
11. OTP completion and failed-attempt escalation work.
12. Customer cannot read another customer's data.
13. RM cannot read an unassigned region.
14. Kitchen Staff cannot perform Manager-only actions.
15. Provider/AI services are not required for core order processing.

## 19.3 Test data policy

- Use synthetic records.
- Never copy production personal data into local fixtures.
- Keep secrets out of fixtures.
- Make test setup repeatable.
- Test both successful and denied access paths.

---

# 20. Resource and performance validation

The POC resource envelope is approximately 14 GB usable RAM with 2 GB reserved headroom, subject to Phase 1 confirmation.

Measure:
- Idle application memory.
- Peak memory during end-to-end workflow.
- Database memory.
- Worker memory.
- Frontend development server memory.
- Concurrent request behaviour.
- Database connection usage.
- Startup and recovery.
- CPU and disk usage.

Keep optional services off by default. Record measurements instead of assuming resource consumption.

---

# 21. Phase 4 implementation sequence and exit gates

| Gate | Work | Exit evidence |
|---|---|---|
| P4.0 | Repository baseline | Current state and clean baseline documented |
| P4.1 | Environment/config/CI | Reproducible setup and passing CI |
| P4.2 | Database foundation | Migrations and integration tests pass |
| P4.3 | Identity/RBAC | Authorization negative tests pass |
| P4.4 | Customer/menu/checkout | Customer can place valid order |
| P4.5 | Payment/order lifecycle | Payment and fulfilment invariants pass |
| P4.6 | Kitchen/inventory | Preparation and concurrency tests pass |
| P4.7 | Delivery | Assignment and OTP workflow passes |
| P4.8 | Management | Role/region boundaries pass |
| P4.9 | Integrated POC core | Full end-to-end workflow passes |
| P4.10 | Operational handoff | Runbooks, known gaps and release evidence complete |

Do not advance a dependent gate while its critical predecessor is failing.

---

# 22. Required implementation evidence

For each completed task, retain:
- Task ID.
- Commit/PR reference.
- Files changed.
- Migration reference, if applicable.
- API/OpenAPI change, if applicable.
- Tests executed.
- Test results.
- Security review evidence where relevant.
- Screenshots or workflow evidence where useful.
- Known limitations.
- Rollback/recovery notes.
- Reviewer and approval.

Update the master backlog. A checked box without evidence is not completion.

---

# 23. Phase 4 exit criteria

- [ ] Repository baseline and environment are reproducible.
- [ ] CI runs required quality gates.
- [ ] Configuration and secrets are handled safely.
- [ ] Database migrations and test fixtures are reliable.
- [ ] Authentication and session lifecycle work.
- [ ] Backend authorization enforces role, ownership and region scope.
- [ ] Customer can place an order without AI.
- [ ] Simulated payment and fulfilment states remain separate.
- [ ] Kitchen queue and preparation workflow work.
- [ ] Inventory reservation and deduction are concurrency-safe.
- [ ] Delivery assignment and OTP completion work.
- [ ] Management role/scope boundaries are enforced.
- [ ] Critical APIs and events follow approved contracts.
- [ ] Audit and correlation foundations exist.
- [ ] End-to-end and negative security tests pass.
- [ ] Resource use has been measured against the POC envelope.
- [ ] Known gaps and operational runbooks are documented.
- [ ] Product owner accepts the core platform milestone.

---

# 24. Handoff to Phase 5

**Recommended Phase 5: Shared AI Infrastructure Implementation.**

Begin only after Phase 4 has stable:
- Identity and authorization.
- Domain ownership.
- API contracts.
- Audit and observability.
- Core application runtime.
- Database and migration practices.

Phase 5 should implement:
1. Provider-independent LLM gateway.
2. Provider-independent embedding service.
3. Shared ingestion framework.
4. Shared retrieval primitives.
5. AI observability and evaluation.
6. Security identities and portal-isolation foundations.

Then Phase 6 can integrate Customer, Kitchen and Management AI/RAG independently.

---

# 25. Engineering agent execution prompt

Act as the DeliverIQ engineering implementation lead.

Start by auditing the actual repository and comparing it with the approved Phase 1 architecture, Phase 2 contracts and Phase 3 backlog. Report existing components, missing components, conflicts and proposed file changes before editing.

Implement one approved vertical slice at a time. Preserve working code. Follow existing repository conventions unless an approved ADR says otherwise. Do not invent files, dependencies, environment values or completed features.

Enforce backend authorization on every protected operation. Treat order, payment, inventory and delivery transitions as critical transactions. Add tests for retries, duplicate commands, concurrency and unauthorized access.

Keep the core order-to-delivery workflow independent of AI. Do not implement the LLM gateway, embeddings or RAG pipelines in Phase 4.

Do not add infrastructure or dependencies without a documented need. Do not make unapproved business-rule changes. Stop and ask for approval when implementation requires a new product or architecture decision.

For every completed increment, report:
- What changed.
- Why it changed.
- Files/modules affected.
- Tests executed and results.
- Remaining gaps.
- Risks or decisions requiring approval.

Phase 4 is complete only when the core operational workflow is demonstrably reliable and its security and acceptance tests pass.
