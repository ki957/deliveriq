# DeliverIQ POC — Phase 1 Planning & Architecture Validation

**Document:** Phase 1 Master Planning Specification  
**Project:** DeliverIQ — AI-enabled single cloud kitchen delivery platform  
**Phase:** 1 — Technical Discovery and Architecture Validation  
**Version:** 1.0  
**Status:** Planning baseline  
**Prepared:** 11 November 2026

---

# 1. Executive summary

DeliverIQ is a proof of concept for an AI-enabled, centralized cloud kitchen delivery platform. The POC begins with one cloud kitchen in Chennai, while keeping the domain model and application boundaries capable of supporting additional kitchens and regions later.

The objective of Phase 1 is **not to start implementing another architecture from scratch**. It is to establish a verified picture of the current POC, compare it with the product and AI architecture already agreed, identify technical gaps and conflicts, and produce an implementation-ready architecture baseline.

DeliverIQ's AI work is a major purpose of the POC, but AI must remain an optional intelligence layer. The core application must continue to accept, prepare, manage and deliver orders if an LLM, embedding provider, vector search service or AI feature is unavailable.

Phase 1 must therefore validate two connected systems:

1. **The operational product foundation:** portals, identity, roles, APIs, database, order lifecycle, kitchen operations, delivery, payments, reporting and deployment.
2. **The AI foundation:** three isolated portal-specific harnesses and RAG pipelines, connected through shared provider-independent AI infrastructure.

The phase ends with approved architecture decisions, system diagrams, environment strategy, a gap register and a prioritized implementation backlog. It does not authorize unreviewed rewrites or automatically begin implementation.

---

# 2. Product context and POC boundaries

## 2.1 Product definition

DeliverIQ is a centralized cloud kitchen delivery system, not a multi-restaurant marketplace.

Initial POC:
- One city: Chennai.
- One cloud kitchen initially.
- Architecture should allow multiple kitchens and regions later.
- Five user-facing portals/views are represented through four application experiences:
  1. Customer Dashboard.
  2. Delivery Agent Portal.
  3. Kitchen Portal.
  4. Unified Management Dashboard, with separate Regional Manager and Central Administrator permissions.
- The system uses a modular monolith with selective serverless functions and event-driven integration where useful.
- Microservices are a future option, not the initial architecture.
- The POC is designed for a constrained local environment, with approximately 14 GB usable RAM and 2 GB reserved headroom as the planning envelope.

## 2.2 Product engineering status entering Phase 1

The product requirements and portal-level decisions have already been developed. Phase 1 should validate how those requirements map to the actual repository and technical implementation.

### Customer Dashboard

The approved product behaviour includes:
- Browse menu and serviceability before login.
- Mobile OTP authentication for order placement.
- Customer profile and saved delivery addresses.
- Serviceability validation using the agreed straight-line and road-distance rules.
- Menu catalogue, dish details, customization and cart.
- ₹500 minimum food subtotal.
- Price protection and stock/price revalidation at checkout.
- Simulated payment and COD for the POC; no real-money processing.
- Kitchen acceptance and explicit order lifecycle.
- Customer cancellation before kitchen acceptance under the agreed rules.
- Delivery tracking, order history, reorder, reviews and support.
- No scheduled orders, loyalty points, tipping or post-placement order modification in the initial scope.

### Delivery Agent Portal

Approved product behaviour includes:
- Hybrid system-recommended and manager-controlled assignment.
- Agent online/offline status and one active delivery at a time.
- GPS permission and location updates during active delivery.
- OpenStreetMap, Leaflet and OSRM; no Google Maps dependency.
- Pickup and delivery lifecycle with six-digit customer OTP.
- Defined timeout, rejection, customer-unavailable and delivery-failure escalation.
- COD handling is simulated; agents do not collect prepaid payments.
- No earnings/payroll, advanced shift management, in-app chat or AI chatbot in the initial scope.

### Kitchen Portal

Approved product behaviour includes:
- Kitchen Manager and Kitchen Staff roles.
- Live order queue, acceptance/rejection and preparation lifecycle.
- Normal, Busy and Paused kitchen modes with backend-enforced capacity.
- Recipe and ingredient-level inventory workflows.
- Ingredient reservation on order acceptance, deduction on handover and release on cancellation/rejection.
- Recipe version pinned to an accepted order.
- Kitchen Manager owns recipe/ingredient/stock administration.
- Regional Manager approves dish-unavailability requests.
- Large kitchen display and tablet-friendly workflows.

### Unified Management Dashboard

Approved product behaviour includes:
- One dashboard experience with distinct Regional Manager (RM) and Central Administrator (CA) permissions.
- RM limited to assigned regions.
- CA has global authority and can perform authorized RM actions.
- Staff, kitchen, delivery, orders, exceptions, payments/refunds, promotions, support, reviews, reports, configuration and audit views.
- Configuration changes are audited.
- YAML configuration is schema-validated; arbitrary code execution is prohibited.
- Management AI is read-only in the initial MVP.

## 2.3 POC exclusions and guardrails

Phase 1 must preserve these constraints:
- No real payment processing unless separately approved.
- No marketplace or multi-vendor scope.
- No autonomous AI actions that mutate operational state.
- No direct model access to unrestricted database queries.
- No unrestricted cross-portal data access.
- No premature microservices or Kubernetes.
- No assumption that every AI capability requires an agent.
- No AI dependency in the critical order, kitchen or delivery path.

---

# 3. Approved high-level architecture baseline

## 3.1 Application architecture

Use a **modular monolith** as the default application architecture:
- Clear domain modules and service boundaries.
- Explicit API contracts.
- Shared database where appropriate, with domain ownership and least-privilege access.
- Event-driven integration for asynchronous or decoupled workflows where justified.
- Selective serverless functions only for suitable isolated workloads.
- No service extraction until measured scaling, deployment or ownership needs justify it.

## 3.2 Technology baseline to verify

| Layer | Current planning baseline | Phase 1 validation |
|---|---|---|
| Frontend | React | Inspect actual app structure, routing and state management |
| Backend | Python + FastAPI | Inspect modules, dependencies and API conventions |
| Relational database | PostgreSQL | Verify schema, constraints, transactions and migrations |
| Document database | MongoDB | Verify actual use cases; do not retain merely because it is in the proposed stack |
| Vector search | pgvector | Validate extension availability, version and expected workload |
| Lexical search | PostgreSQL full-text search | Validate suitability for the initial corpus |
| Cache/state | Redis where justified | Verify existing use and memory footprint |
| Object storage | MinIO if required | Verify document/file use case and local resource cost |
| LLM provider | Groq through provider-independent gateway | Verify SDK, model capability, limits and configuration |
| Model gateway | OpenRouter/provider-independent abstraction as previously planned | Decide whether OpenRouter is the routing layer, a provider adapter, or both; avoid duplicate gateways |
| Embeddings | Separate provider-independent abstraction | Select only after benchmark |
| Maps | OSM + Leaflet + OSRM | Verify map tile/routing assumptions and local/network dependency |
| Local deployment | Docker Compose initially | Verify RAM and startup footprint |
| Migrations | Alembic for SQL schema | Verify existing migration discipline |

**Important architecture question:** The POC has referenced both Groq and OpenRouter. Phase 1 must clarify the intended relationship. A clean design has one internal DeliverIQ LLM gateway, with provider adapters behind it. OpenRouter may be one adapter/route and Groq another; portal code should not call both independently.

## 3.3 Shared AI architecture

Three separate portal-specific AI harnesses:

1. Customer harness + Customer RAG.
2. Kitchen harness + Kitchen RAG.
3. Unified Management harness + Management RAG.

Shared AI infrastructure:
- Provider-independent LLM gateway.
- Provider-independent embedding service.
- Shared ingestion primitives.
- Shared retrieval primitives.
- Shared observability and evaluation.
- Shared configuration and secrets-management patterns.

The shared layer provides reusable capabilities, not shared authority.

## 3.4 AI isolation rules

- Each portal has its own harness, prompt, context builder, tool registry, RAG collection, retrieval configuration and evaluation dataset.
- Customer RAG cannot access Kitchen or Management knowledge.
- Kitchen RAG cannot access Customer or Management knowledge.
- Management RAG cannot directly access Customer or Kitchen RAG.
- Regional Manager retrieval and tools are restricted to assigned regions.
- Central Administrator has approved global scope.
- Backend authorization is authoritative.
- No model/client-supplied role, customer ID, region ID or permission is trusted.
- Separate least-privilege service/database identities are preferred.
- AI is read-only for the initial POC.
- Current operational facts come from authorized APIs, not stale RAG chunks.
- System prompts are not security boundaries.

---

# 4. Phase 1 objectives

At the end of Phase 1, the team must be able to answer:

1. What is actually implemented in the repository today?
2. Which approved product requirements are implemented, incomplete, missing or contradicted?
3. Are the application modules aligned with the modular monolith architecture?
4. Are PostgreSQL and MongoDB responsibilities clearly justified?
5. Are authentication, RBAC and region scope enforced by the backend?
6. Are core order, kitchen, inventory and delivery transitions consistent and transaction-safe?
7. Are events, retries and idempotency designed for the workflows that need them?
8. Can three independent AI harnesses be implemented without cross-portal access?
9. Is the LLM gateway/provider setup unambiguous and replaceable?
10. Can the POC run within the available RAM and local development constraints?
11. What must be fixed before AI integration?
12. What can safely be deferred until after the POC?

---

# 5. Phase 1 workstreams and execution order

## Workstream 1 — Repository and implementation audit

**Purpose:** Establish facts about the current codebase before proposing changes.

### Inspect

**Frontend**
- Portal/application structure.
- Route boundaries and role-aware navigation.
- Component organization and shared UI.
- API client and authentication flow.
- State management and data fetching.
- Environment/configuration usage.
- Responsive behaviour and error/loading states.

**Backend**
- FastAPI application entry points.
- Domain/module boundaries.
- Routers, services, repositories and schemas.
- Dependency injection and authentication middleware.
- Authorization checks and resource ownership validation.
- Background tasks/workers.
- Event publishing/consumption.
- Error handling and API versioning.

**Data**
- PostgreSQL schemas, tables, constraints and indexes.
- Alembic migrations and migration history.
- MongoDB collections and concrete business use cases.
- Transaction boundaries and concurrent updates.
- pgvector extension and vector schema if present.
- Redis keys, TTLs and actual responsibilities.
- MinIO buckets and file lifecycle if present.

**AI**
- Existing Groq/OpenRouter SDK usage.
- Provider calls and hard-coded model names.
- Prompt locations and prompt versioning.
- Embedding implementation.
- RAG ingestion and retrieval code.
- Tool/function calling and permission checks.
- Conversation history and retention.
- AI logs, traces, token/cost tracking and evaluation.
- Any shared code currently used across portals.

**Infrastructure**
- Dockerfiles and Compose services.
- Environment variables and sample configuration.
- Secrets handling.
- Health checks and startup dependencies.
- Volume and network configuration.
- Resource limits and observed RAM usage.
- CI/CD and test execution.
- Backup/restore scripts, if any.

### Audit outputs

- Repository map.
- Dependency inventory.
- Existing architecture diagram.
- Existing database and API inventory.
- AI implementation inventory.
- Security findings.
- Test and deployment inventory.

### Audit rule

Do not infer implementation from a requirements document. Mark a capability as implemented only when code, tests or runtime evidence supports it.

---

## Workstream 2 — Requirements-to-code gap analysis

Compare actual repository evidence against:
- Customer portal requirements.
- Delivery Agent portal requirements.
- Kitchen portal requirements.
- Unified Management requirements.
- Customer RAG master specification.
- Kitchen RAG master specification.
- Management RAG master specification.
- Shared AI infrastructure specification.

### Classification

| Status | Meaning |
|---|---|
| Implemented | Verified in code/tests |
| Partial | Exists but incomplete or weakly enforced |
| Missing | No implementation found |
| Conflict | Implementation contradicts an approved requirement |
| Unverified | Evidence is insufficient |
| Decision required | Product/architecture owner must decide |

### Severity

- **P0 — Critical:** Security boundary, data loss, incorrect payment/order state, cross-portal/region leakage.
- **P1 — High:** Core workflow or data integrity failure.
- **P2 — Medium:** Important functionality, operability or maintainability gap.
- **P3 — Low:** UX polish, optimization or later enhancement.

Every gap must include:
- Requirement/reference.
- Repository evidence or missing evidence.
- Classification.
- Severity.
- Impact.
- Recommended resolution.
- Dependencies.
- Whether approval is required.

---

## Workstream 3 — Architecture decision records (ADRs)

Create concise, version-controlled ADRs. Each ADR includes:
- Title and decision ID.
- Status: proposed, accepted, rejected or superseded.
- Context and problem.
- Options considered.
- Decision and rationale.
- Consequences/trade-offs.
- Security and resource impact.
- Validation required.
- Owner and date.

### Required ADR topics

| ADR | Decision |
|---|---|
| ADR-001 | Modular monolith boundaries and domain ownership |
| ADR-002 | PostgreSQL versus MongoDB responsibilities |
| ADR-003 | API conventions and internal module communication |
| ADR-004 | Event-driven workflow boundaries |
| ADR-005 | Transaction and idempotency strategy |
| ADR-006 | Authentication, RBAC and region authorization |
| ADR-007 | LLM gateway and Groq/OpenRouter relationship |
| ADR-008 | Embedding provider/model selection process |
| ADR-009 | Portal-specific RAG isolation and database access |
| ADR-010 | Background worker and ingestion job execution |
| ADR-011 | Logging, observability and evaluation |
| ADR-012 | Local POC deployment and resource limits |
| ADR-013 | File/object storage decision |
| ADR-014 | AI data retention and conversation context policy |

Do not create an ADR merely to document an obvious implementation detail. Use ADRs for consequential choices and trade-offs.

---

## Workstream 4 — System architecture and diagrams

Produce diagrams that agree with actual code and accepted ADRs.

### Required diagrams

1. **System context:** users, portals, external providers and core platform.
2. **Application architecture:** portal frontend, API layer, domain modules and shared infrastructure.
3. **Backend module architecture:** ownership and dependency direction.
4. **Data architecture:** PostgreSQL, MongoDB if justified, Redis, MinIO and pgvector.
5. **Order lifecycle:** order, payment, kitchen and delivery state transitions.
6. **Event architecture:** events, producers, consumers, retries and idempotency.
7. **AI architecture:** three isolated harnesses, three RAG collections and shared AI infrastructure.
8. **Security boundaries:** identity, roles, regions, portal service identities and database permissions.
9. **Deployment architecture:** local POC and future production topology.

### Diagram quality rules

- Show trust boundaries and data ownership.
- Distinguish synchronous API calls from asynchronous events.
- Show source of truth for important data.
- Mark proposed versus implemented components.
- Do not draw speculative microservices as current components.
- Include failure boundaries for external AI providers.

---

## Workstream 5 — Environment and resource strategy

### Environments

| Environment | Purpose | Data |
|---|---|---|
| Local development | Daily engineering | Synthetic/local data |
| Automated test | Unit and integration tests | Fixtures and isolated test DB |
| Staging | Production-like end-to-end validation | Synthetic or approved masked data |
| Production | Live operation, if/when launched | Authorized production data |

The POC may not need four independently provisioned environments immediately. Define the strategy now; provision only what is justified.

### Configuration and secrets

- Use `.env.example` with placeholders only.
- Keep real `.env` files out of version control.
- Validate required settings at startup.
- Separate non-secret configuration from secrets.
- Never place provider keys in frontend code.
- Never expose secrets through AI tools, RAG, prompts or logs.
- Define key rotation and environment-specific credentials.
- Validate YAML configuration against a schema.
- Do not allow arbitrary code execution from configuration.

### Resource budget

The planning envelope is approximately 14 GB usable RAM with 2 GB reserved headroom. Confirm actual host and container usage before locking limits.

Measure:
- Frontend development server.
- FastAPI application/workers.
- PostgreSQL.
- MongoDB, if retained.
- Redis, if retained.
- MinIO, if retained.
- Ingestion worker.
- Vector search and embedding workload.
- Browser and test tooling.

Do not run every optional service continuously if it is not needed. Prefer a minimal Compose profile for daily development and optional profiles for ingestion/testing.

### Environment deliverables

- Environment variable inventory.
- `.env.example` requirements.
- Docker Compose service map.
- Resource budget and measured baseline.
- Startup/health-check order.
- Local reset/seed instructions.
- Backup/restore approach for POC data.

---

# 6. Cross-cutting technical validation

Phase 1 must specifically validate the following high-risk areas.

## 6.1 Identity and authorization

- One authenticated identity can have multiple explicitly assigned roles.
- Customer role is not implicitly granted to staff unless product rules say so.
- RM assignments are region-scoped.
- Only CA can provision/manage RM roles.
- Permission changes and role removal take effect promptly.
- Resource ownership is validated server-side.
- Trusted device and session behaviour is consistent.
- No authorization depends only on frontend hiding or system prompts.

**Required output:** role/permission matrix and authorization flow diagram for Phase 2.

## 6.2 Order, payment and kitchen consistency

Validate:
- Payment state is separate from fulfilment state.
- Simulated prepaid payment succeeds before kitchen processing.
- Kitchen acceptance is an explicit transition.
- Cancellation/rejection behaviour is consistent.
- Inventory reservation is atomic on acceptance.
- Inventory deduction occurs at handover.
- Reservation is released on permitted cancellation/rejection.
- Duplicate requests/events cannot double-reserve or double-deduct stock.
- Ready-for-pickup and agent pickup transitions are authoritative.
- Customer-facing status is derived from trusted order state.

**Required output:** state-transition matrix, transaction boundary notes and idempotency requirements.

## 6.3 Delivery consistency

Validate:
- One active delivery per agent.
- Assignment timeout and rejection are race-safe.
- Reassignment revokes old assignment access.
- GPS permission is required before Online.
- Real GPS coordinates are never fabricated.
- OTP attempts and escalation are server-enforced.
- Customer-unavailable and delivery-failure flows are auditable.
- Prepaid orders never request COD collection.

**Required output:** delivery state diagram and concurrency/security findings.

## 6.4 Data ownership and database choice

PostgreSQL should be evaluated as the primary transactional source of truth.

MongoDB must have a documented, concrete POC use case before it is retained. Do not duplicate transactional entities across PostgreSQL and MongoDB without an explicit ownership and consistency model.

For every domain, identify:
- Owning module/service.
- Authoritative database.
- Read/write owner.
- Cross-domain access method.
- Transaction boundary.
- Event emitted after commit, if needed.
- Retention and audit requirements.

**Required output:** data ownership matrix and database decision recommendation.

## 6.5 AI isolation and data boundaries

Validate:
- Three separate portal harnesses.
- Three separate RAG collections/logical schemas.
- Portal-specific service identities and least privilege.
- Trusted role/region/customer scope.
- No direct cross-portal RAG access.
- Current facts through authorized APIs.
- AI tools read-only for initial POC.
- Prompt injection cannot change permissions.
- AI failure cannot interrupt core workflows.

**Required output:** AI trust-boundary diagram and isolation test plan.

---

# 7. Proposed domain ownership map to validate

This is a planning proposal, not a claim about existing repository structure.

| Domain | Primary responsibility | Authoritative data |
|---|---|---|
| Identity and access | Users, roles, sessions, permissions, region assignments | PostgreSQL |
| Customer | Profile, addresses, preferences | PostgreSQL |
| Menu | Dishes, categories, customization, visibility | PostgreSQL |
| Orders | Cart conversion, order lifecycle, order items | PostgreSQL |
| Payments | Simulated transactions, payment state, refunds | PostgreSQL |
| Kitchen | Queue, prep state, kitchen mode/capacity | PostgreSQL |
| Recipes | Recipe versions and ingredient mappings | PostgreSQL |
| Inventory | Ingredients, reservations, stock movements | PostgreSQL |
| Delivery | Assignments, agent state, delivery lifecycle | PostgreSQL |
| Location | Current/short-lived agent location | Evaluate PostgreSQL/Redis based on update rate and retention |
| Promotions | Coupons, promotion rules and redemption | PostgreSQL |
| Support/reviews | Tickets, reviews and moderation state | PostgreSQL |
| Reporting | Persisted reporting queries/projections | PostgreSQL initially |
| Audit | Append-only audit records | PostgreSQL initially |
| RAG knowledge | Portal-specific documents/chunks/embeddings | Separate logical PostgreSQL schemas with pgvector |
| Source files | Approved document binaries where needed | MinIO or existing storage |

Do not create a separate database for every domain in the modular monolith. Logical ownership and permissions matter more than database count.

---

# 8. Event architecture discovery

Do not assume every state change needs a message broker. Identify events that improve reliability or decouple work.

Candidate domain events to validate:
- `OrderPlaced`
- `PaymentSucceeded`
- `PaymentFailed`
- `OrderAcceptedByKitchen`
- `OrderRejectedByKitchen`
- `PreparationStarted`
- `OrderReadyForPickup`
- `DeliveryAssigned`
- `DeliveryAssignmentExpired`
- `DeliveryPickedUp`
- `DeliveryCompleted`
- `DeliveryFailed`
- `IngredientReservationCreated`
- `IngredientReservationReleased`
- `StockDeducted`
- `DishAvailabilityApproved`
- `KnowledgeSourceApproved`
- `KnowledgeSourceWithdrawn`
- `RoleAssignmentChanged`

For each event, document:
- Producer and owning domain.
- Event payload schema.
- Event ID and idempotency key.
- Occurrence timestamp.
- Aggregate/resource ID.
- Region/kitchen scope where relevant.
- Consumer(s).
- Retry policy.
- Duplicate handling.
- Failure/dead-letter handling.
- Whether an outbox pattern is needed.

For the POC, a PostgreSQL-backed outbox plus a background worker may be sufficient. Decide after examining actual reliability needs and existing infrastructure.

---

# 9. AI-specific architecture validation

## 9.1 LLM gateway: Groq and OpenRouter

The existing planning references both Groq and OpenRouter. Resolve this explicitly.

Recommended target:
- One internal DeliverIQ LLM gateway.
- Provider adapters behind the gateway.
- Groq adapter for the intended POC model route.
- OpenRouter adapter/route only if its model routing and fallback capabilities are actually required.
- Portal harnesses call only the internal gateway.
- Provider/model allowlists are server-controlled.
- No provider key or provider endpoint in frontend code.

Phase 1 must decide whether OpenRouter is:
1. The primary gateway provider,
2. One adapter among multiple providers, or
3. Not needed for the first POC milestone.

Do not build two overlapping gateway abstractions.

## 9.2 Embeddings

- Keep embeddings independent from LLM selection.
- Benchmark against representative Customer, Kitchen and Management queries.
- Track model, version and vector dimension.
- Use a controlled re-embedding migration when changing models.
- Keep portal collections separate even if one embedding model is shared.

Exact embedding model selection belongs to the evidence-based AI infrastructure decision, not guesswork.

## 9.3 RAG data ownership

| Portal | Knowledge owner | Retrieval boundary |
|---|---|---|
| Customer | Approved customer-visible menu/policy/FAQ content | Public customer knowledge plus authenticated customer's permitted context |
| Kitchen | Approved recipes/SOPs/food handling/troubleshooting | Kitchen role and order-specific recipe version |
| Management | Approved operational SOPs/business policies/management docs/KPI definitions | RM assigned regions; CA approved global/regional scope |

Live operational values are retrieved through role-aware APIs, not embedded as static facts.

## 9.4 AI capability and tool boundaries

Validate the tool inventory for each harness:
- Customer: menu, price, availability, serviceability, delivery quote, own orders and support options.
- Kitchen: recipe/order context and authorized live kitchen/inventory views; manager-only operational insights where specified.
- Management: role-scoped operational summaries, exceptions, reports and audit read views.

Initial AI tools are read-only. No model-generated SQL, arbitrary shell, unrestricted network access or operational mutation tools.

---

# 10. Architecture decisions: proposed baseline versus validation status

| Topic | Proposed baseline | Phase 1 action |
|---|---|---|
| Application style | Modular monolith | Validate current module boundaries |
| Service extraction | Avoid initially | Require measured justification |
| API | FastAPI | Inspect conventions and contracts |
| Transactional store | PostgreSQL | Validate schema and transaction design |
| MongoDB | Conditional | Retain only with concrete use case |
| Vector store | pgvector | Validate extension and query performance |
| Lexical search | PostgreSQL FTS | Benchmark representative queries |
| Cache | Redis where justified | Audit current use and RAM |
| Object storage | MinIO if required | Validate document/file need |
| LLM | Internal gateway, Groq route | Resolve OpenRouter relationship |
| Embeddings | Separate abstraction | Benchmark before choosing model |
| Ingestion | Background worker | Reuse current worker if suitable |
| Events | Domain events/outbox where useful | Avoid unnecessary broker |
| Deployment | Docker Compose | Measure local resource footprint |
| Orchestration | No complex agent framework initially | Add only for clear use case |
| Kubernetes | Not for initial POC | Revisit only after deployment needs justify it |

---

# 11. Phase 1 deliverables

The phase is complete only when these artifacts exist.

| ID | Deliverable | Contents |
|---|---|---|
| P1-D01 | Repository Audit Report | Repository map, dependencies, existing implementation evidence |
| P1-D02 | Requirements Traceability Matrix | Requirement-to-code status and evidence |
| P1-D03 | Architecture Gap Register | Severity, impact, resolution and dependencies |
| P1-D04 | ADR Pack | Accepted/proposed decisions with rationale |
| P1-D05 | System Context Diagram | Users, portals, platform and external providers |
| P1-D06 | Application Architecture Diagram | Frontend, backend modules and service boundaries |
| P1-D07 | Data Ownership Matrix | Domain, source of truth, owner and access |
| P1-D08 | State and Event Diagrams | Order/payment/kitchen/delivery transitions and events |
| P1-D09 | AI Trust-Boundary Diagram | Three harnesses, RAG collections, APIs and shared layer |
| P1-D10 | Environment Specification | Local/test/staging/production, secrets and resource plan |
| P1-D11 | Risk Register | Technical, security, operational and delivery risks |
| P1-D12 | Prioritized Implementation Backlog | Sequenced work, dependencies, acceptance criteria |

---

# 12. Prioritization and decision rules

## 12.1 Priority order

1. Identity, authorization and data isolation.
2. Transactional correctness for orders, payments and inventory.
3. Core delivery/kitchen state consistency.
4. Data ownership and API contracts.
5. AI provider and RAG isolation boundaries.
6. Reliability, observability and evaluation.
7. Performance and resource optimization.
8. UX polish and future enhancements.

## 12.2 Decision rules

- Preserve working code if it meets requirements and has adequate tests.
- Do not rewrite modules merely to make folder structures look cleaner.
- Resolve architectural conflicts before adding more AI features.
- Use the simplest technology that satisfies the POC requirements.
- Every new dependency must have a concrete purpose and resource cost.
- Every cross-module write must have an explicit owner and consistency strategy.
- Every AI data path must have an explicit authorization boundary.
- Every critical state transition must be transaction-safe and idempotent.
- Unknown behaviour must be marked unverified, not assumed.
- Product-rule changes require explicit product approval.

---

# 13. Risk register — initial hypotheses to verify

These are risks to investigate, not findings about the current code.

| Risk | Impact | Initial mitigation |
|---|---|---|
| Groq/OpenRouter responsibilities unclear | Duplicate abstractions and provider lock-in | One internal gateway with explicit adapters |
| PostgreSQL/MongoDB ownership unclear | Data duplication and consistency defects | Domain source-of-truth matrix |
| Portal RAG collections share permissions | Cross-portal data leakage | Separate schemas/roles and negative tests |
| RM region filtering performed only in prompts | Cross-region disclosure | Server-side scope enforcement |
| AI tools can mutate operations | Unintended business actions | Read-only allowlists |
| Inventory reservation is not atomic | Overselling or incorrect stock | Transactional reservation and idempotency |
| Event consumer handles duplicates incorrectly | Duplicate side effects | Event IDs, idempotency and outbox |
| Current facts are stored only in RAG | Stale answers | Authorized live APIs |
| Local stack exceeds memory budget | Unstable development environment | Measure RAM and optional Compose profiles |
| Provider outage blocks core workflow | Operational failure | AI optionality and graceful degradation |
| Secrets enter prompts/logs | Credential/data exposure | Redaction and secret boundaries |
| No evaluation baseline | Undetected quality regressions | Labeled datasets and release gates |

---

# 14. Phase 1 exit criteria

Phase 1 may be marked complete only when:

- [ ] Actual repository structure and dependencies are documented.
- [ ] All major implementation claims have evidence or are marked unverified.
- [ ] Portal requirements have been mapped to implementation status.
- [ ] Critical gaps and conflicts are prioritized.
- [ ] PostgreSQL/MongoDB responsibilities are decided.
- [ ] Modular monolith boundaries are documented.
- [ ] Identity, RBAC and region-scope design is validated.
- [ ] Order/payment/inventory/delivery state transitions are documented.
- [ ] Event and idempotency requirements are documented.
- [ ] Groq/OpenRouter gateway relationship is decided.
- [ ] Embedding model selection process is defined.
- [ ] Three portal AI/RAG isolation boundaries are documented.
- [ ] Local environment and RAM budget are measured or have a measurement plan.
- [ ] Required ADRs are accepted or clearly marked proposed.
- [ ] System diagrams reflect the verified architecture.
- [ ] Risks and unresolved decisions have owners.
- [ ] Phase 2 backlog is prioritized and ready.

---

# 15. Handoff to Phase 2

Phase 2 is **Data and Backend Contracts**. It should begin only after Phase 1 has established the verified architecture baseline.

Phase 2 will define:
1. Database architecture and schema ownership.
2. RBAC and authorization matrix.
3. API contracts.
4. Event schemas and delivery guarantees.
5. Data lifecycle, audit, retention and deletion.

Phase 2 must use the evidence and accepted decisions from this phase. It must not independently redesign the architecture.

---

# 16. How to execute this plan

## Step 1 — Make the repository available

Provide the current DeliverIQ repository as a ZIP or make the repository files available in the project workspace.

Before packaging, exclude:
- `node_modules/`
- `.venv/`, `venv/`
- `__pycache__/`
- `.git/`
- build output and caches
- actual `.env` files
- credentials, API keys, certificates and private keys
- production database dumps containing personal data

Keep:
- Source code.
- Package manifests and lockfiles.
- `requirements.txt` / `pyproject.toml`.
- Dockerfiles and Compose files.
- Alembic migrations.
- Safe configuration examples.
- Tests.
- Architecture and product documentation.

## Step 2 — Audit without changing code

Inspect and report. Do not modify files, install packages, migrate databases or refactor during the initial audit.

## Step 3 — Review findings

Present:
- Verified facts.
- Unverified assumptions.
- Critical gaps.
- Conflicts with approved requirements.
- Decisions that need product-owner approval.

## Step 4 — Approve architecture baseline

Record accepted ADRs and update diagrams. Keep unresolved decisions visible.

## Step 5 — Produce Phase 2 backlog

Create sequenced tasks with dependencies, acceptance criteria and risk.

---

# 17. Final instruction to the engineering agent

Act as the technical architect and senior engineering reviewer for DeliverIQ's AI-enabled cloud kitchen POC.

Your first responsibility is to establish the truth about the current implementation. Do not assume that the repository matches the architecture specifications. Do not invent completed functionality. Do not start implementation during the discovery-only audit.

Evaluate the product foundation and AI architecture together. Pay particular attention to:
- Transactional correctness.
- Identity and region authorization.
- Customer/Kitchen/Management isolation.
- Provider independence.
- Live API versus RAG boundaries.
- Resource usage within the POC hardware envelope.
- Operational resilience when AI is unavailable.

Preserve working implementation, surface conflicts, recommend the simplest sound architecture and request approval for consequential changes.

The Phase 1 output must be a verified, prioritized and implementation-ready architecture baseline—not merely a description of the intended system.
