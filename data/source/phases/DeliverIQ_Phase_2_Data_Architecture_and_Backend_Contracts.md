# DeliverIQ POC — Phase 2 Data Architecture & Backend Contracts

**Document:** Phase 2 Master Planning Specification  
**Project:** DeliverIQ — AI-enabled single cloud kitchen delivery platform  
**Phase:** 2 — Data Architecture and Backend Contracts  
**Version:** 1.0  
**Status:** Planning baseline; subject to Phase 1 architecture validation  
**Prepared:** 11 November 2026

---

# 1. Executive summary

Phase 2 translates the verified architecture baseline from Phase 1 into precise data and backend contracts.

The goal is to define **who owns each piece of data, where it is stored, how it changes, how modules communicate, and how access is enforced** before implementing or expanding the application and its AI capabilities.

DeliverIQ is a single-cloud-kitchen POC in Chennai, designed with a path to multiple kitchens and regions. It uses a modular monolith as the initial application architecture, with selective asynchronous/event-driven workflows where they improve reliability. The AI layer consists of three independent portal-specific harnesses and RAG pipelines over shared AI infrastructure.

Phase 2 must not assume that the existing repository matches the proposed design. Phase 1 findings and accepted Architecture Decision Records (ADRs) are authoritative. Any unresolved Phase 1 decision must remain explicitly marked as unresolved rather than being hidden inside a schema or API design.

**Phase 2 is a design and contract phase.** It produces database specifications, authorization matrices, API contracts, event contracts and data lifecycle policies. Implementation begins only after these contracts are reviewed and approved.

---

# 2. Objectives

At the end of Phase 2, the team must be able to answer:

1. Which module owns each business entity and field?
2. Which database is authoritative for each entity?
3. Which relationships, constraints and indexes are required?
4. Which operations must be atomic?
5. How are concurrent requests and duplicate events handled?
6. How are roles, permissions, region scope and resource ownership enforced?
7. What API contracts connect the frontend, backend modules and external integrations?
8. Which workflows use synchronous APIs and which use asynchronous events?
9. How are event delivery, retries, ordering and idempotency guaranteed?
10. How are data retention, deletion, audit and privacy handled?
11. How do the three AI/RAG pipelines access only approved, role-scoped data?
12. What contracts must exist before implementation can proceed safely?

---

# 3. Inputs and dependencies

Phase 2 depends on the following Phase 1 outputs:

- Verified repository audit.
- Requirements-to-code traceability matrix.
- Architecture gap register.
- Accepted or explicitly proposed ADRs.
- Verified system and module architecture.
- Data ownership recommendations.
- Order/payment/kitchen/delivery state diagrams.
- AI trust-boundary diagram.
- Environment and resource specification.
- Risk register.

### Dependency rule

If Phase 1 has not yet verified the repository, Phase 2 can define logical contracts and proposed target models, but it cannot claim that a particular table, endpoint, module or database already exists.

For each design item, label it:
- **Existing and verified**
- **Target design**
- **Proposed**
- **Unresolved**
- **Requires product approval**

Do not silently replace existing implementation.

---

# 4. Phase 2 workstreams and execution order

| Order | Workstream | Main output |
|---:|---|---|
| 1 | Domain and data ownership | Domain map and source-of-truth matrix |
| 2 | Relational data model | ERD, entity definitions and constraints |
| 3 | Transaction and consistency design | Transaction boundaries and concurrency rules |
| 4 | RBAC and authorization | Role-permission-resource-scope matrix |
| 5 | API contract design | OpenAPI specification and endpoint catalogue |
| 6 | Event and asynchronous contracts | Event catalogue, schemas and delivery rules |
| 7 | Data lifecycle and audit | Retention, deletion, history and audit policy |
| 8 | AI data access contracts | Portal-specific projections, ingestion contracts and tool schemas |
| 9 | Contract validation | Schema validation, test cases and implementation backlog |

The order matters. API and event contracts must be derived from domain ownership and state transitions, not designed independently.

---

# 5. Workstream 1 — Domain and data ownership

## 5.1 Domain ownership principles

- Every business entity has one authoritative owner.
- Other modules access an entity through an explicit service/API or an approved read projection.
- A module must not write directly into another module's tables merely for convenience.
- Cross-module workflows must define transaction boundaries or eventual-consistency behaviour.
- Avoid duplicating the same business fact across PostgreSQL and MongoDB.
- Reporting projections may duplicate data for read performance, but their source and refresh semantics must be documented.
- AI/RAG content is derived knowledge, not an alternative transactional source of truth.

## 5.2 Proposed domain ownership matrix

Validate this against the actual Phase 1 findings.

| Domain | Owns | Proposed source of truth |
|---|---|---|
| Identity and Access | Users, credentials references, roles, grants, sessions, trusted devices | PostgreSQL |
| Region and Kitchen | Regions, kitchens, assignments, operating configuration | PostgreSQL |
| Customer | Customer profile, addresses, preferences | PostgreSQL |
| Menu | Categories, dishes, customization options, visibility | PostgreSQL |
| Cart | Cart and cart items | PostgreSQL or existing approved session design |
| Orders | Orders, order items, status history, cancellation/rejection | PostgreSQL |
| Payments | Simulated payment attempts, payment state, refund records | PostgreSQL |
| Kitchen Operations | Kitchen mode, capacity, queue and preparation state | PostgreSQL |
| Recipes | Recipe definitions, versions, ingredient mappings | PostgreSQL |
| Inventory | Ingredients, stock balances, reservations, movements | PostgreSQL |
| Delivery | Agent state, assignments, delivery state, OTP verification attempts | PostgreSQL |
| Location | Recent agent coordinates and location timestamps | Evaluate PostgreSQL/Redis from update rate and retention |
| Promotions | Coupon rules, promotions, eligibility and redemption | PostgreSQL |
| Support and Reviews | Tickets, reviews, moderation state | PostgreSQL |
| Reporting | KPI definitions and persisted read models where needed | PostgreSQL initially |
| Audit | Append-only audit events | PostgreSQL initially |
| RAG | Portal-specific documents, chunks, embeddings and ingestion jobs | Separate logical schemas in PostgreSQL/pgvector |
| Source Files | Approved source document binaries | MinIO or existing storage if justified |

Do not create one database per domain for this modular-monolith POC.

## 5.3 Entity inventory

Create an entity catalogue with:
- Entity name and purpose.
- Owning module.
- Primary identifier.
- Important attributes.
- Relationships.
- Data classification.
- Source of truth.
- Write permissions.
- Read permissions.
- Retention requirement.
- Audit requirement.
- Events emitted.
- APIs exposing the entity.

The catalogue must cover at least:
- User, Role, Permission, RoleAssignment, RegionAssignment, Session, TrustedDevice.
- Region, Kitchen.
- Customer, Address, CustomerPreference.
- MenuCategory, Dish, CustomizationOption.
- Cart, CartItem.
- Order, OrderItem, OrderStatusHistory.
- PaymentAttempt, PaymentTransaction, Refund.
- KitchenConfiguration, KitchenOrder, PreparationItem.
- Recipe, RecipeVersion, RecipeIngredient.
- Ingredient, StockBalance, StockReservation, StockMovement.
- DeliveryAgentProfile, AgentAvailability, DeliveryAssignment, DeliveryStatusHistory, DeliveryLocation.
- Promotion, Coupon, CouponRedemption.
- SupportTicket, Review, ReviewModeration.
- AuditEvent.
- KnowledgeDocument, KnowledgeChunk, IngestionJob, IngestionEvent for each portal's RAG boundary.

This is a discovery checklist, not a command to create every entity as a separate table. Normalize or combine only where the domain semantics justify it.

---

# 6. Workstream 2 — Relational data model and ERD

## 6.1 Database baseline

PostgreSQL is the proposed primary transactional source of truth. Confirm this against Phase 1.

MongoDB must be retained only if a concrete document-oriented use case is demonstrated and its ownership/consistency model is documented. Do not use MongoDB simply because it appears in an earlier stack proposal.

pgvector is a PostgreSQL extension for embeddings; it does not require a separate database server for this POC.

## 6.2 Schema organization

Possible logical schemas, subject to repository validation:

```text
identity
regions
customers
menu
orders
payments
kitchen
recipes
inventory
delivery
promotions
support
reporting
audit
customer_rag
kitchen_rag
management_rag
```

Schema separation is an organizational and access-control aid. It does not automatically create complete security isolation. Combine it with least-privilege database roles, backend authorization and service boundaries.

## 6.3 Common data modelling rules

- Use stable primary keys; UUID is a candidate where distributed/event references are useful.
- Use foreign keys for relational integrity.
- Use explicit `NOT NULL`, `UNIQUE`, `CHECK` and appropriate FK constraints.
- Store timestamps in UTC; convert to local time for presentation and reporting.
- Use timezone-aware timestamp types.
- Store currency amounts using fixed-precision decimal or integer minor units; never floating point.
- Store currency code explicitly where future multi-currency support is possible.
- Use explicit status columns with constrained values or reference tables.
- Use `created_at` and `updated_at` where appropriate.
- Use optimistic concurrency/version fields for contested updates where justified.
- Keep immutable history for important state transitions.
- Avoid generic EAV designs for core transactional entities.
- Avoid storing derived values if they can be reliably calculated, unless a documented snapshot is required.
- Add indexes based on query patterns and explain plans, not speculation.
- Never store plaintext OTPs, passwords or provider secrets.

## 6.4 Key modelling topics to resolve

### Identity and access
- User identity and verified mobile number.
- Multiple roles per user.
- Role grants and region assignments.
- Central Administrator global permission.
- Session lifecycle and trusted devices.
- Revocation and permission refresh semantics.

### Customer and address
- Verified mobile ownership.
- Multiple addresses and default address.
- Customer preferences and declared ingredients to avoid.
- Data minimization and retention.

### Menu and recipes
- Customer-visible dish data versus internal recipe data.
- Recipe version snapshots.
- Customization options and price inclusion.
- Dish visibility and approval history.
- Menu data projection for Customer RAG.

### Orders and payments
- Order and item snapshots at placement.
- Price/tax/delivery-fee snapshots.
- Payment attempts separate from order fulfilment.
- Idempotency keys for checkout and payment simulation.
- Cancellation/rejection/refund history.

### Kitchen and inventory
- Ingredient unit consistency.
- Recipe-to-ingredient quantities.
- Reservation ledger.
- Stock movement ledger.
- Available, reserved and on-hand quantities.
- Atomic reservation and release.

### Delivery
- Assignment history.
- One-active-delivery constraint.
- OTP verification attempt history.
- Delivery failure and escalation history.
- Location retention and access.

### RAG
- Independent portal collections/schemas.
- Source identity, approval, version and scope metadata.
- Embedding model/version/dimension.
- Withdrawal and effective-date support.

## 6.5 ERD deliverables

Produce:
1. Logical domain ERD.
2. Physical PostgreSQL ERD.
3. Identity/RBAC ERD.
4. Order/payment ERD.
5. Kitchen/recipe/inventory ERD.
6. Delivery ERD.
7. RAG metadata ERDs for Customer, Kitchen and Management.

Do not force all domains into one unreadable diagram. Use bounded domain diagrams and a system-level relationship overview.

---

# 7. Workstream 3 — Transactions, consistency and concurrency

This workstream is critical. Correct state transitions matter more than adding AI features.

## 7.1 Transaction principles

- A business operation must have a clear transaction owner.
- Related writes that must succeed together belong in one database transaction where possible.
- External provider calls must not be performed while holding long database transactions.
- Use an outbox pattern when a committed state change must reliably publish an event.
- Consumers must be idempotent.
- Never assume an event is delivered exactly once.
- Use database constraints to protect invariants against concurrent requests.
- Use row locking or optimistic concurrency where necessary.
- Define retryable versus permanent failures.

## 7.2 Critical transaction contracts

| Operation | Required consistency |
|---|---|
| Checkout | Validate price, stock, serviceability and minimum subtotal; create order/payment intent consistently |
| Simulated prepaid payment | Idempotent payment result; kitchen processing only after success |
| Kitchen acceptance | Atomic order transition and ingredient reservation |
| Inventory reservation | Prevent concurrent overselling |
| Cancellation before acceptance | Atomic order cancellation and reservation release where applicable |
| Kitchen rejection | Record reason, terminal state and payment/refund consequence |
| Handover | Deduct reserved ingredients exactly once and move order/delivery workflow consistently |
| Delivery assignment | Enforce one active delivery per agent |
| Assignment timeout | Expire only the matching active assignment attempt |
| Delivery completion | Validate OTP attempts and completion transition atomically |
| Refund | Prevent duplicate refund execution and preserve payment/order state separation |
| Promotion redemption | Enforce usage limits and eligibility atomically |

Exact transaction boundaries depend on the verified module/data architecture.

## 7.3 Inventory ledger model

Recommended conceptual distinction:
- `on_hand`: physical stock recorded.
- `reserved`: quantity committed to accepted orders but not yet deducted.
- `available`: derived as on-hand minus reserved, subject to unit and adjustment rules.

The authoritative stock movement ledger should explain every change:
- Receipt/opening balance.
- Reservation.
- Reservation release.
- Consumption/deduction.
- Adjustment with reason and actor.
- Reversal/correction.

Do not allow independent updates to `available` without a corresponding ledger/reservation operation.

## 7.4 Idempotency

Define idempotency for:
- Checkout submission.
- Payment simulation callback/result.
- Kitchen accept/reject.
- Inventory reservation/release/deduction.
- Delivery assignment and reassignment.
- OTP verification.
- Delivery completion.
- Refund processing.
- Promotion redemption.
- Event consumption.
- RAG ingestion and source publication.

For each operation document:
- Idempotency key source.
- Uniqueness scope.
- Persistence period.
- Duplicate response behaviour.
- Conflict behaviour.

---

# 8. Workstream 4 — RBAC and authorization matrix

## 8.1 Authorization model

Use role-based permissions plus resource/region scope checks.

Authentication answers: **Who is the user?**

Authorization answers:
- What role grants do they have?
- Which region/kitchen/customer/order resources may they access?
- What action may they perform?
- Is the resource in their assigned scope?
- Is the current account/session active?

The backend is authoritative. Frontend visibility is not a security control.

## 8.2 Roles to model

At minimum:
- Customer.
- Delivery Agent.
- Kitchen Staff.
- Kitchen Manager.
- Regional Manager.
- Central Administrator.

A user may hold multiple explicitly assigned roles where allowed. Role assignment must not automatically imply unrelated permissions.

## 8.3 Authorization matrix deliverable

Create a matrix with columns:
- Role.
- Domain/resource.
- Action: create/read/update/delete/approve/override/export.
- Scope: own/customer, assigned kitchen, assigned region, global.
- Conditions.
- Approval requirements.
- Audit requirement.
- API/tool enforcement location.

### Important approved boundaries

**Customer**
- Can access own profile, addresses, orders and support data.
- Cannot access another customer's records.
- Public menu knowledge can be retrieved without authentication where approved.

**Delivery Agent**
- Can access assigned active delivery information.
- One active delivery at a time.
- Full delivery address and necessary customer contact information only for an authorized active assignment.
- Cannot change prepaid payment state.
- Cannot independently finalize failure outside approved workflow.

**Kitchen Staff**
- Can view and process authorized kitchen queue and recipe context.
- Cannot manage staff access, approve dish unavailability or change manager-only settings.

**Kitchen Manager**
- Can manage recipes, ingredient records, stock adjustments, kitchen mode/capacity and authorized kitchen operations.
- Cannot approve dish unavailability if that remains Regional Manager authority.

**Regional Manager**
- Assigned regions only.
- Can perform authorized regional management actions.
- Cannot create/manage Regional Manager roles or access global-only configuration.

**Central Administrator**
- Approved global authority and authorized RM actions.
- Can manage RM roles and global configuration.
- Must still respect privacy, purpose limitation and explicit tool/API permissions.

## 8.4 Authorization implementation requirements

- Resolve identity and grants server-side.
- Validate resource ownership and region on every protected request.
- Derive scope from trusted session/authorization services.
- Never trust user-supplied role, region or customer ID.
- Deny by default.
- Revoke access promptly on role removal.
- Refresh permissions on role/region changes.
- Invalidate relevant caches and conversation context.
- Apply the same checks to AI tools and normal APIs.
- Log sensitive administrative actions.
- Test direct API calls, not only frontend navigation.

## 8.5 Required security tests

- Customer cannot access another customer.
- Agent cannot access an unassigned delivery.
- Agent cannot access a previous assignment after reassignment.
- Kitchen user cannot access another kitchen.
- Kitchen Staff cannot use Manager-only operations.
- RM cannot access an unassigned region.
- RM cannot create another RM or change global configuration.
- CA global access works only for explicitly authorized endpoints.
- Role revocation takes effect.
- AI tool calls enforce the same authorization as application APIs.

---

# 9. Workstream 5 — API contract design

## 9.1 API design principles

- Define contracts before implementation.
- Use consistent resource naming and HTTP semantics.
- Use typed request and response schemas.
- Validate input at the API boundary.
- Return stable error codes.
- Include pagination and filtering for collection endpoints.
- Use idempotency keys for retryable business commands.
- Do not expose internal database models directly.
- Keep authorization checks in backend services.
- Generate/maintain OpenAPI from FastAPI schemas.
- Version APIs deliberately; avoid versioning every internal module unnecessarily.

## 9.2 API contract template

Every endpoint specification must contain:

| Field | Required detail |
|---|---|
| Name | Stable operation name |
| Method/path | HTTP method and route |
| Owner | Domain/module |
| Purpose | Business capability |
| Authentication | Required or public |
| Authorization | Role, scope and resource checks |
| Request | Path/query/body schema |
| Response | Success schema |
| Errors | Stable error codes and HTTP status |
| Idempotency | Required/optional/not applicable |
| Side effects | Database writes/events |
| Audit | Required event and actor |
| Rate limit | If applicable |
| Tests | Positive, negative and boundary cases |

## 9.3 API groups to inventory and specify

1. Authentication and sessions.
2. Customer profile and addresses.
3. Menu and serviceability.
4. Cart and checkout.
5. Orders and order history.
6. Payments and refunds.
7. Kitchen queue and preparation.
8. Recipes and inventory.
9. Delivery assignment and tracking.
10. Promotions and coupons.
11. Support and reviews.
12. Staff and role management.
13. Region and kitchen configuration.
14. Management reports and audit.
15. AI assistant and AI tool backend endpoints.
16. RAG ingestion/admin endpoints.

Do not create public endpoints for internal-only operations. Internal AI tools should call approved service functions or protected internal APIs.

## 9.4 Standard response and error conventions

Define a consistent response shape appropriate to the existing project. A conceptual success response:

```json
{
  "data": {},
  "meta": {
    "request_id": "request-id"
  }
}
```

A conceptual error response:

```json
{
  "error": {
    "code": "RESOURCE_NOT_AUTHORIZED",
    "message": "The requested resource is not available.",
    "request_id": "request-id"
  }
}
```

These are examples, not a requirement to wrap every endpoint if the existing API has a sound consistent convention.

Error categories should distinguish:
- Validation failure.
- Authentication required.
- Authorization denied.
- Resource not found.
- State transition conflict.
- Idempotency conflict.
- Rate limit.
- Dependency unavailable.
- Internal error.

Do not leak whether a protected resource exists when that would expose private information.

## 9.5 API contract outputs

- Endpoint inventory.
- OpenAPI specification.
- Request/response schemas.
- Error catalogue.
- Authentication/authorization requirements.
- Idempotency requirements.
- API contract tests.
- Frontend/backend integration map.

---

# 10. Workstream 6 — Event and asynchronous contracts

## 10.1 Event design principles

Use events only when asynchronous decoupling, reliable side effects or independent processing provide clear value.

A modular monolith can use internal domain events and a background worker. A broker is not automatically required.

## 10.2 Candidate event catalogue

Validate and finalize events such as:
- `OrderPlaced`
- `PaymentSucceeded`
- `PaymentFailed`
- `KitchenOrderAccepted`
- `KitchenOrderRejected`
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
- `DishAvailabilityRequested`
- `DishAvailabilityApproved`
- `KnowledgeSourceApproved`
- `KnowledgeSourceWithdrawn`
- `RoleAssignmentChanged`
- `RegionAssignmentChanged`

Do not publish an event merely because a CRUD operation occurred. Events should describe meaningful domain facts.

## 10.3 Event envelope

Conceptual schema:

```json
{
  "event_id": "uuid",
  "event_type": "OrderPlaced",
  "event_version": 1,
  "occurred_at": "2026-11-11T08:00:00Z",
  "producer": "orders",
  "aggregate_type": "order",
  "aggregate_id": "order-id",
  "region_id": "region-id",
  "kitchen_id": "kitchen-id",
  "correlation_id": "request-or-workflow-id",
  "idempotency_key": "stable-key",
  "data": {}
}
```

Include only fields needed by consumers. Do not place secrets or unnecessary customer PII in event payloads.

## 10.4 Delivery guarantees

Define:
- At-least-once delivery expectations.
- Consumer idempotency.
- Retry schedule and maximum attempts.
- Poison-message handling.
- Dead-letter/reconciliation process.
- Event schema version compatibility.
- Ordering requirements per aggregate.
- Event replay policy.
- Observability and alerting.

Never claim exactly-once processing merely because a queue is used.

## 10.5 Outbox pattern

Where a database transaction must both update business state and publish an event:
- Write business state and outbox row in the same transaction.
- Background worker publishes pending outbox events.
- Mark delivery state only after successful publication.
- Consumer records processed event IDs or equivalent idempotency state.
- Reconcile stuck events.
- Keep payloads minimal.

For the POC, a PostgreSQL outbox and worker may be sufficient. Decide after Phase 1 repository and workload review.

## 10.6 Event contract outputs

- Event catalogue.
- JSON schemas or typed event definitions.
- Producer/consumer matrix.
- Retry and dead-letter policy.
- Ordering and idempotency matrix.
- Outbox/inbox design.
- Event contract tests.

---

# 11. Workstream 7 — Data lifecycle, audit and privacy

## 11.1 Data classification

Classify data into:
- Public.
- Internal.
- Confidential operational.
- Personal/customer data.
- Sensitive security/credential data.

Classification must determine:
- Who can read it.
- Where it can be stored.
- Whether it can be indexed in RAG.
- Whether it can appear in AI context.
- Logging/redaction rules.
- Retention and deletion behaviour.

## 11.2 Retention matrix

Create a policy table for:
- Customer profiles and addresses.
- Orders and payment simulation records.
- Refund records.
- Delivery assignments and GPS history.
- OTP verification attempts.
- Staff and role history.
- Support tickets and reviews.
- Audit records.
- RAG source documents and chunks.
- AI conversation history.
- AI traces and evaluation records.
- Ingestion job logs.

Do not invent legal retention periods. Identify product requirements, operational needs and applicable legal obligations for review by the responsible owner.

## 11.3 Audit events

Audit important operations including:
- Role/permission changes.
- Region assignment changes.
- Staff provisioning/deactivation.
- Refund approval/override.
- Dish availability approval.
- Kitchen mode/capacity changes.
- Stock adjustments.
- Promotion changes.
- Customer suspension.
- Review moderation.
- Configuration/YAML changes.
- AI provider/model configuration changes.
- Sensitive data access where required.

Audit fields should include:
- Event ID.
- Actor identity and role at action time.
- Action.
- Target type and ID.
- Scope/region.
- Timestamp.
- Outcome.
- Reason where required.
- Correlation/request ID.
- Before/after summary where safe and necessary.

Audit records should be append-only for application users. Do not store passwords, tokens or full secret values in audit payloads.

## 11.4 Deletion and correction

Define:
- Which records can be deleted.
- Which records must be retained for financial/operational audit.
- How personal data is corrected.
- How deactivation differs from deletion.
- How source document withdrawal propagates to RAG.
- How embeddings and caches are invalidated.
- How backups age out under the approved retention policy.

---

# 12. Workstream 8 — AI data access and backend tool contracts

This workstream connects Phase 2 data/API contracts to the three AI specifications.

## 12.1 Non-negotiable architecture

- Three independent harnesses.
- Three independent RAG collections/logical schemas.
- Shared provider-independent infrastructure.
- Backend authorization on every retrieval and tool call.
- No direct cross-portal RAG search.
- No unrestricted SQL.
- No model-generated authorization scope.
- Read-only AI tools in the initial POC.

## 12.2 AI source-of-truth matrix

| AI capability | Knowledge source | Live/current source |
|---|---|---|
| Customer menu/policy help | Approved Customer RAG | Menu, price, stock, serviceability and order APIs |
| Kitchen recipe/SOP help | Approved Kitchen RAG | Order, kitchen, inventory and preparation APIs |
| Management policy/SOP help | Approved Management RAG | Region-scoped operations, reports, audit and configuration APIs |

RAG explains approved knowledge. APIs provide current facts.

## 12.3 Customer tool contracts

Potential read-only tools:
- Search customer-visible menu.
- Get dish details and approved customizations.
- Get current price and availability.
- Check delivery serviceability.
- Get delivery quote.
- Get authenticated customer's orders/status.
- Get support options.

Authorization:
- Anonymous users receive public menu/serviceability capabilities only.
- Authenticated customer ID comes from trusted session.
- Order ownership is validated server-side.
- Never accept a model-supplied customer ID as authority.
- Do not expose kitchen recipes, internal stock quantities, staff data or management metrics.

## 12.4 Kitchen tool contracts

Potential read-only tools:
- Get order preparation context.
- Get order-pinned recipe version.
- Get authorized kitchen queue/status.
- Get approved recipe and SOP content.
- Get ingredient/stock insights for Kitchen Manager only where approved.
- Get authorized capacity/mode/delay context.

Authorization:
- Kitchen scope is derived from trusted staff assignment.
- Staff and Manager permissions remain distinct.
- Accepted orders retain their recipe version.
- No AI mutation of order, recipe, stock, kitchen mode, capacity or ETA.

## 12.5 Management tool contracts

Potential read-only tools:
- Regional operations summary.
- Regional order exceptions.
- Regional kitchen/delivery status.
- Regional staff and inventory summaries.
- Regional payment/refund status.
- Regional reports and audit read views.
- Global operations and region comparison for CA only.
- Global configuration metadata for CA only.

Authorization:
- RM assigned regions only.
- CA approved global/regional scope.
- No Customer or Kitchen RAG access.
- No staff, refund, promotion, approval, configuration or YAML mutation tools.

## 12.6 Tool schema requirements

Every tool contract must specify:
- Tool name and purpose.
- Portal owner.
- Allowed roles.
- Required scope.
- Typed input schema.
- Typed output schema.
- Data minimization.
- Backend authorization.
- Error categories.
- Timeout and rate limit.
- Audit/trace requirements.
- Test cases.

The model selects from a server-controlled allowlist; it does not create new tools.

---

# 13. Workstream 9 — Contract validation and test strategy

## 13.1 Database tests

- Foreign key and uniqueness constraints.
- Check constraints and valid statuses.
- Transaction rollback.
- Concurrent stock reservation.
- Duplicate checkout/payment requests.
- One-active-delivery constraint.
- Recipe version immutability for accepted orders.
- Audit append-only behaviour.
- Migration upgrade and rollback strategy where safe.

## 13.2 Authorization tests

- Positive and negative tests for every role.
- Cross-customer ownership.
- Cross-kitchen access.
- RM cross-region access denial.
- CA global access.
- Role revocation and region reassignment.
- AI tool calls use the same backend checks.

## 13.3 API contract tests

- Request schema validation.
- Response schema stability.
- Error code consistency.
- Pagination and filtering.
- Idempotency behaviour.
- State transition conflicts.
- Authentication and authorization.
- OpenAPI consistency.

## 13.4 Event contract tests

- Schema validation.
- Duplicate delivery.
- Consumer idempotency.
- Retry and dead-letter handling.
- Out-of-order event behaviour.
- Outbox recovery after worker interruption.
- Event version compatibility.

## 13.5 AI contract tests

- Portal collection isolation.
- RM region filters.
- Customer ownership filters.
- Kitchen Staff/Manager permission differences.
- Live values are retrieved through APIs.
- No mutation tools registered.
- Prompt injection cannot alter scope.
- Source withdrawal invalidates retrieval eligibility.

## 13.6 Test environments and data

- Use synthetic fixtures for customer, staff, order and payment data.
- Never use production credentials in tests.
- Do not copy unmasked production PII into local or staging environments.
- Ensure tests can reset their own database state.
- Keep test data deterministic.

---

# 14. Phase 2 deliverables

| ID | Deliverable | Required contents |
|---|---|---|
| P2-D01 | Domain Ownership Catalogue | Domain, entities, owner, source of truth |
| P2-D02 | Data Classification Matrix | Sensitivity, access, retention and AI eligibility |
| P2-D03 | Logical ERD Pack | Domain relationships |
| P2-D04 | Physical Schema Specification | Tables, columns, constraints and indexes |
| P2-D05 | Transaction Design | Atomic operations, locking and idempotency |
| P2-D06 | RBAC Matrix | Role, action, resource, scope and conditions |
| P2-D07 | Authorization Flow Specification | Trusted identity and scope resolution |
| P2-D08 | API Endpoint Catalogue | Endpoint owner, method, purpose and permissions |
| P2-D09 | OpenAPI Contracts | Request, response and error schemas |
| P2-D10 | Event Catalogue | Producers, consumers and domain facts |
| P2-D11 | Event Schemas | Versioned payload contracts |
| P2-D12 | Reliability Specification | Outbox, retries, ordering and deduplication |
| P2-D13 | Data Lifecycle Policy | Retention, deletion, correction and archival |
| P2-D14 | Audit Specification | Events, fields and access controls |
| P2-D15 | AI Tool Contract Catalogue | Portal-specific read-only tool schemas |
| P2-D16 | AI Data Access Matrix | RAG/API source, role and scope |
| P2-D17 | Contract Test Plan | DB, API, authorization, event and AI tests |
| P2-D18 | Phase 3 Implementation Backlog | Sequenced work with dependencies and acceptance criteria |

---

# 15. Priority and implementation dependency

## P0 — Must be resolved before implementation

- Source-of-truth ownership for transactional entities.
- Identity, role and region authorization.
- Order/payment state separation.
- Atomic inventory reservation and release.
- One active delivery per agent.
- API ownership and protected resource access.
- AI portal and region isolation.
- No AI mutation tools in initial POC.
- Secrets and personal-data boundaries.

## P1 — Required for reliable POC operation

- API error conventions.
- Event/outbox strategy for critical workflows.
- Idempotency and retry policies.
- Audit coverage.
- Data retention and source withdrawal.
- Reporting definitions and read contracts.
- Ingestion job contracts.
- Contract and integration tests.

## P2 — Can follow after the foundational contracts

- Advanced reporting projections.
- Additional cache design.
- High-volume event broker.
- Advanced analytics data warehouse.
- More complex multi-region data partitioning.
- Advanced event replay tooling.

---

# 16. Phase 2 exit criteria

Phase 2 is complete only when:

- [ ] Every core entity has an owning domain and source of truth.
- [ ] PostgreSQL/MongoDB responsibilities are explicitly decided.
- [ ] Logical and physical ERDs are reviewed.
- [ ] Constraints, indexes and timestamp/currency conventions are defined.
- [ ] Critical transaction boundaries are documented.
- [ ] Concurrency and idempotency rules are documented.
- [ ] Role/action/resource/scope matrix is approved.
- [ ] API endpoint ownership and contracts are documented.
- [ ] Error and pagination conventions are consistent.
- [ ] Event catalogue and schemas are versioned.
- [ ] Outbox, retry and consumer idempotency strategy is approved.
- [ ] Data classification and retention policy is reviewed.
- [ ] Audit events and append-only rules are defined.
- [ ] Customer/Kitchen/Management AI tool contracts are documented.
- [ ] Live API versus RAG boundaries are explicit.
- [ ] Cross-customer, cross-kitchen, cross-region and cross-portal tests are specified.
- [ ] Phase 3 implementation backlog is prioritized.
- [ ] Product-owner approval is recorded for consequential business decisions.

---

# 17. Handoff to Phase 3

Phase 3 should be **Implementation Planning and Foundation Build**, subject to the project's overall execution plan.

It should begin with:
1. Approved schema and migrations.
2. Identity/RBAC enforcement foundation.
3. API contracts and common error handling.
4. Transaction and idempotency primitives.
5. Outbox/worker foundation where required.
6. Audit and observability foundation.
7. AI tool authorization adapters.

Do not implement all business domains simultaneously. Sequence implementation around dependency order and protect the core order-to-delivery workflow.

---

# 18. Execution instructions

## Step 1 — Use Phase 1 as the authority

Read the Phase 1 audit and accepted ADRs. If the repository audit is not complete, keep Phase 2 designs provisional.

## Step 2 — Build the domain ownership catalogue

Identify entities, owners, authoritative stores and cross-domain access. Resolve PostgreSQL versus MongoDB before creating duplicate models.

## Step 3 — Design the state and transaction contracts

Start with checkout, payment, kitchen acceptance, inventory reservation, handover and delivery completion. These define the most important consistency requirements.

## Step 4 — Define authorization before endpoints

Write the role/resource/scope matrix before finalizing protected API contracts.

## Step 5 — Define APIs and events from domain ownership

Specify request/response and event contracts only after the owning module and state transitions are clear.

## Step 6 — Define data lifecycle and AI access

Specify retention, audit, source withdrawal and portal-specific AI projections. Ensure AI never bypasses normal backend authorization.

## Step 7 — Validate contracts

Review with product and engineering stakeholders, add contract tests and produce the Phase 3 backlog.

### Scope control

Do not:
- Start coding before critical contracts are approved.
- Create tables simply because they appear in this planning document.
- Duplicate the same entity in PostgreSQL and MongoDB without a clear reason.
- Introduce a message broker without a demonstrated need.
- expose raw database rows to frontend or AI models.
- Let the model supply authorization scope.
- Store live operational facts as the sole source in RAG.
- implement write-capable AI tools in the initial POC.

---

# 19. Final instruction

Act as DeliverIQ's data architect and backend contract designer.

Translate the verified Phase 1 architecture into explicit, testable contracts for data ownership, schema design, transactions, authorization, APIs, events, lifecycle and AI access.

Preserve the approved product rules. Distinguish verified implementation from proposed target design. Do not invent fields, endpoints, event payloads or policies as if they already exist. Surface unresolved business decisions and request approval when they affect permissions, money, order state, inventory or privacy.

The result of Phase 2 must be a coherent contract set that backend, frontend, data and AI engineers can implement independently without conflicting assumptions.
