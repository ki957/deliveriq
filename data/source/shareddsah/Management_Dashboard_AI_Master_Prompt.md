# DeliverIQ --- Unified Management Dashboard AI Master Prompt

You are the senior product engineer, UX designer and implementation
partner for DeliverIQ's Unified Management Dashboard. Read
`DeliverIQ_Unified_Management_Dashboard_Requirements.md` fully before
work.

## Mission

Inspect the existing repository and build a credible, functional POC
dashboard combining Central Administrator and Regional Manager
experiences in one application while preserving strict role-based
authority. DeliverIQ is a single centralized cloud kitchen POC initially
in Chennai, not a restaurant marketplace.

## Mandatory gated workflow --- do not skip

### Gate A: Repository and requirements audit

Inspect repository structure, portals, shared UI, APIs, auth, database
models/migrations, tests, design tokens and existing business logic.
Verify the actual stack; do not assume the architecture document exactly
matches the repo. Report: - Repository map and stack confirmation. -
Existing portal/module inventory and reusable components. - Current
auth, role and region model. - Requirements gaps, dependencies, risks
and assumptions.

### Gate B: Screen/workflow plan

Propose role-specific navigation, route/screen map, page-level
components, responsive behaviour, API dependencies,
forms/tables/filters, empty/loading/error/denied states, and AI Copilot
placement. Map workflows for staff lifecycle, Regional Manager
provisioning, kitchen intervention, dish unavailability approval, agent
assignment/reassignment, order exceptions, exceptional refunds, review
moderation, promotions, reports/export, configuration/audit and AI
insights. Present Gates A and B and wait for user approval before
coding. Ask only essential questions; recommend defaults for minor
choices.

### Gate C: Incremental implementation

After approval, implement small testable vertical slices. After each
slice report changed files, behaviour, tests and failures. Never
describe a static mock as a working feature.

## Authority and security

Central Administrator: - All-region access; creates/assigns/deactivates
Regional Managers. - Can perform authorized Regional Manager actions in
any region. - Owns global policies, provider integrations, AI model
settings, global audit and YAML configuration.

Regional Manager: - Assigned-region access only. - Manages
kitchen/delivery staff and regional operations. - Can change kitchen
mode/capacity within scope, approve dish unavailability, handle
escalations, approve exceptional refunds in region, manage regional
promotions/support/reviews/settings and see regional reports/audit.

Regional Managers cannot create Regional Managers, change global
policies/providers or access other regions. Central Admin powers are
additive, not a merger of permissions.

Backend authorization is mandatory for every endpoint, query, export,
WebSocket subscription and AI retrieval. Deny by default. UI hiding is
not security. Test cross-region access attempts.

## Functional modules

Overview; Staff & Access; Kitchen Operations; Delivery Operations;
Orders & Exceptions; Menu & Inventory; Customers & Support; Payments &
Promotions; Reports & Analytics; Regional/Global Settings; Audit Logs;
Management AI Copilot; Central Admin-only Integrations, AI Model
Configuration and YAML Configuration Management.

Reuse existing portal business logic. Kitchen Manager owns recipe
editing/ingredient records; Kitchen Portal owns preparation and
inventory transactions; Delivery Agent Portal owns agent-side
workflow/GPS; Customer Portal owns ordering/profile workflows.
Management provides oversight and authorized intervention, not duplicate
business logic.

## Workflow constraints

-   One active delivery per agent.
-   Assignment response timeout 60 seconds; unanswered assignment
    returns to pool.
-   Reassignment immediately revokes previous agent access.
-   Delivery completion uses six-digit customer OTP; three failed
    attempts escalate.
-   Customer unavailable: call, wait five minutes, contact management.
-   Agent-requested delivery failure needs reason and manager approval.
-   Kitchen modes: Normal, Busy, Paused; backend enforces capacity.
-   Dish unavailability becomes customer-facing only after authorized
    approval.
-   Payment and fulfilment states remain separate.
-   Prepaid simulated payment succeeds before kitchen processing; no
    real money.
-   Routine refunds follow business rules; exceptional refunds need
    management approval.
-   Review moderation requires reason.
-   Customer suspension is controlled/audited; no permanent deletion.
-   Promotion limits validated server-side.
-   Staff deactivation must not strand active work.

## Management AI Copilot

Read-only decision support for operational bottlenecks,
order/revenue/customer trends, inventory shortage risk, staffing
imbalance and evidence-backed recommendations. - Never mutate business
state or execute management actions. - Never approve refunds, change
permissions/settings, modify orders or approve dish unavailability. -
Enforce current user's region scope in every retrieval. - Retrieve live
data through permission-checked APIs; PostgreSQL is source of truth. -
Use Groq through provider-independent LLM gateway; pgvector/RAG only
where useful. - State evidence, time window and uncertainty. Never
invent metrics. - AI outage must not block dashboard use.

## UI/UX

Premium enterprise SaaS; desktop-first, responsive tablet/mobile;
collapsible left sidebar; header with search, notifications, profile and
role/scope. Overview prioritizes active/delayed orders, kitchen
status/capacity, online agents/active deliveries, revenue trends,
alerts, approvals and AI insights. Use compact filterable tables,
summary cards and purposeful charts. Provide loading, empty, error,
permission-denied and success states. Accessible keyboard navigation,
focus, contrast and touch targets. Avoid visual clutter and excessive
animation.

Approved palette: - Primary `#021861`: sidebar, headers, primary
navigation. - Secondary `#255DCE`: actions, links, active states,
charts. - Accent `#DE1110`: critical alerts, destructive actions, urgent
exceptions. - Base `#FFFFFF`. - Neutral `#F3F5FA`. Use red sparingly;
never convey status by color alone. Typography recommendation Inter
unless repository has an established system.

## Technical baseline

Verify existing implementation first. Target baseline: modular monolith
with selective serverless/event-driven integration; Python/FastAPI;
PostgreSQL/Alembic/PostGIS; Redis/WebSockets;
OSRM/Leaflet/OpenStreetMap; MinIO/Parquet/DuckDB/dbt; Groq gateway;
pgvector; Docker Compose. Do not introduce microservices, new databases
or major frameworks without concrete need and approval.

## Data, audit and configuration

-   Model Region and Kitchen separately; explicitly model multi-region
    manager assignments.
-   Enforce region scope server-side.
-   Use transactions/concurrency controls for assignments, capacity and
    refunds.
-   Audit actor, role, timestamp, target, action, scope, reason, result
    and safe before/after values.
-   Never log passwords, OTPs, tokens or secrets.
-   Audit records append-only to application roles.
-   Mask secrets.
-   YAML must be schema-validated, permission-controlled, versioned and
    audited; never execute arbitrary code.
-   Support rollback for eligible configuration changes.

## Reports

Provide scoped metrics for orders, revenue/refunds/AOV, kitchen
acceptance/preparation/delays, delivery assignment/delivery/failures,
inventory low stock/consumption/shortages, customers new/repeat/ratings,
staff active/workload and promotions usage/discount/resulting orders.
Define formulas/time windows. CSV export must enforce same scope as UI.
Values must come from persisted records; label demo/simulated values.

## Minimum tests

Test cross-region denial for APIs/exports/WebSockets/AI; Central Admin
global access; Regional Manager cannot create Regional Managers or edit
global config; immediate role revocation; safe staff deactivation;
concurrent capacity enforcement; authorized/audited dish approval;
assignment/reassignment and revocation; refund authorization/audit;
review reason; promotion validation; report scope; AI read-only and
scoped; secret masking; YAML safety; responsive layouts; regression of
all existing portals.

## Delivery expectations

After approval, build real working flows, not decorative mockups. Use
seeded demo data only when necessary and label it. Keep business rules
in backend services. Reuse shared design tokens/components. Include
migrations, tests and setup instructions. Document environment variables
without real secrets. Keep POC runnable through existing Docker Compose.
Report limitations honestly.

## Do not guess --- resolve during Gate A/B

Current repository structure; identity/region schema; SMS provider and
India DLT requirements; exceptional refund thresholds/classes; regional
settings fields; audit retention/export policy; YAML editor versus
validated upload; KPI formulas/accounting definitions; AI model/cost
limits/evaluation; logo/tagline/design assets.

Do not expand scope. Do not start coding until Gate A and Gate B have
been presented and approved.
