# DeliverIQ --- Unified Management Dashboard Requirements

**Status:** Approved discovery baseline\
**Initial deployment:** One centralized cloud kitchen in Chennai, India\
**Application:** One dashboard with role-based Central Administrator and
Regional Manager experiences.

## 1. Purpose and scope

Combine the former Regional Manager and Central Administrator dashboards
into one application without merging their authority. The initial POC
has one Chennai region and one kitchen; model Region and Kitchen
separately to support future expansion. This is not a multi-restaurant
marketplace. Backend authorization is authoritative.

## 2. Roles and permissions

### Central Administrator

-   Platform-wide access to all regions and kitchens.
-   Create, assign, update and deactivate Regional Managers.
-   Perform authorized Regional Manager operations in any region.
-   Configure global policies, providers, integrations, AI settings and
    YAML configuration.
-   Manage global or regional promotions.
-   View global reports and audit logs.

### Regional Manager

-   Access only assigned regions.
-   Manage Kitchen Managers, Kitchen Staff and Delivery Agents in
    assigned regions.
-   Monitor/intervene in kitchen, delivery and order operations.
-   Assign/reassign agents; change kitchen mode/capacity within regional
    limits.
-   Approve/reject dish unavailability requests.
-   Handle escalations and approve exceptional refunds within assigned
    regions.
-   Manage regional promotions, support, review moderation and regional
    settings.
-   View regional reports and audit logs.

Regional Managers cannot create Regional Managers, change global
policies/providers, access other regions or edit global YAML
configuration. Central Administrator access is additive and includes
regional operations.

  Capability                      Regional Manager   Central Administrator
  ------------------------------- ------------------ -----------------------
  View operations                 Assigned regions   All regions
  Create Regional Managers        No                 Yes
  Manage kitchen/delivery staff   Assigned regions   All regions
  Assign/reassign agents          Assigned regions   All regions
  Change kitchen mode/capacity    Assigned regions   All regions
  Approve dish unavailability     Assigned regions   All regions
  Exceptional refund approval     Assigned regions   All regions
  Override refund decisions       No                 Yes
  Regional settings               Yes                Yes
  Global settings/providers       No                 Yes
  Regional audit logs             Yes                Yes
  Global audit logs/YAML          No                 Yes

## 3. Organization model

-   Region contains one or more kitchens.
-   Regional Manager may be assigned to one or more regions.
-   Initial data: Chennai region, one centralized kitchen.
-   Enforce region scope on every backend request, query, export,
    WebSocket and AI retrieval.
-   Avoid unnecessary multi-tenant billing/marketplace functionality.

## 4. Staff and access

-   Management provisions Kitchen Managers, Kitchen Staff and Delivery
    Agents.
-   Only Central Administrator provisions Regional Managers and changes
    their region assignments.
-   Support explicitly assigned multiple roles; Customer role is not
    implicit.
-   Reuse shared mobile OTP authentication and
    trusted-device/account-recovery rules from other DeliverIQ portals.
-   Role changes take effect immediately; removal revokes relevant
    active access/sessions.
-   Regional Managers can manage only staff in assigned regions.
-   Prevent self-escalation of permissions.
-   Staff deactivation must first handle active orders/deliveries
    safely.
-   Audit creation, role/region assignment, changes and deactivation.

## 5. Kitchen operations

-   Management can inspect kitchen mode (Normal/Busy/Paused), capacity,
    orders, delays, exceptions, inventory alerts and dish unavailability
    requests.
-   Regional Manager/Central Administrator may change mode/capacity
    within authority; backend enforces capacity and records overrides
    with reasons.
-   Regional Manager approves/rejects dish unavailability; kitchen staff
    cannot approve their own request.
-   Preserve Kitchen Portal ownership: Kitchen Manager edits
    recipes/ingredient records, manages stock and normal kitchen
    operations.
-   Accepted orders retain their recipe version.
-   Ingredient stock is reserved atomically on acceptance, deducted on
    handover and released on cancellation/rejection.
-   Stock adjustments require reason/audit.
-   Ingredient shortage does not automatically hide a dish; management
    approval controls customer-facing availability.
-   No procurement, supplier, purchase order, accounting or wastage
    module.

## 6. Delivery operations

-   View agent availability, active assignments and live locations for
    active deliveries.
-   Assign/reassign agents and handle timeouts, rejection,
    delivery-failure requests, customer-unavailable cases and COD
    discrepancies.
-   One active delivery per agent.
-   Assignment response timeout: 60 seconds; unanswered assignments
    return to pool.
-   Rejection requires reason; reassignment immediately revokes previous
    agent access.
-   Customer delivery confirmation uses six-digit OTP; three failed
    attempts trigger management escalation.
-   Customer unavailable: agent calls, waits five minutes, then contacts
    management.
-   Agent-requested delivery failure requires reason and manager
    approval.
-   Force agent offline only after active work is reassigned or
    explicitly handled.
-   GPS uses browser geolocation with permission; never fabricate real
    coordinates.
-   Maps/routing: OpenStreetMap, Leaflet and OSRM only.

## 7. Orders and exceptions

-   Monitor orders by status, date, kitchen, agent and exception.
-   Keep payment state separate from fulfilment state.
-   Handle kitchen rejection, prep delays, assignment failures, delivery
    failures and customer-unavailable cases.
-   Preserve existing lifecycle: customer cancellation before kitchen
    acceptance; no normal cancellation after acceptance; kitchen
    rejection cancels; kitchen acceptance precedes preparation.
-   Kitchen: Accepted → Preparing → Ready for Pickup → Handed Over.
-   Agent pickup is authoritative and blocked until Ready for Pickup.
-   No post-placement customer modification.
-   Overrides require permission and mandatory reason.

## 8. Menu, inventory and customer support

-   Inspect menu availability, unavailability requests, ingredient
    stock, reservations, thresholds and stock history.
-   Kitchen Manager owns recipe editing and ingredient records.
-   View customer profiles/orders within scope; handle support tickets.
-   Hide inappropriate reviews only with reason and audit.
-   Customer suspension is controlled and audited; Regional Manager may
    initiate/recommend within scope, Central Administrator has final
    global authority.
-   No permanent customer deletion through dashboard.
-   Customer-declared allergies/preferences are not a food-safety
    guarantee.

## 9. Payments and promotions

-   POC uses simulated payments only; no real money.
-   Regional Manager views regional transactions, failed payments and
    COD discrepancies; may approve exceptional refunds within region.
-   Central Administrator views all, overrides refund decisions and
    configures payment simulator.
-   Routine refunds follow existing automated rules; exceptional refunds
    require review.
-   Prepaid simulated payment succeeds before kitchen processing; COD is
    simulated.
-   Agents never collect payment for prepaid orders.
-   Record refund actor, amount, reason, transaction/order and outcome.
-   Regional Managers create regional promotions; Central Administrator
    creates global or regional promotions and configures global coupon
    rules.
-   Validate eligibility, dates, usage limits and discounts server-side;
    audit changes.

## 10. Reporting and analytics

Metrics: orders (total/completed/cancelled/rejected), revenue (gross
sales/refunds/AOV), kitchen (acceptance/preparation time/delays),
delivery (assignment/delivery time/failures), inventory (low
stock/consumption/shortages), customers (new/repeat/ratings), staff
(active agents/workload), promotions (usage/discount/resulting
orders). - Regional view is limited to assigned regions; Central
Administrator gets global view and drill-down. - Date filters, period
comparisons and CSV export. - Metrics derive from persisted records;
label simulated/demo data and never invent values. - Exports enforce
same authorization as UI.

## 11. Management AI Copilot

Read-only contextual decision support: - Operational bottlenecks/delayed
orders. - Revenue, order and customer trends. - Inventory shortage
risk. - Staffing workload imbalance. - Prioritized recommendations with
evidence. Example questions: "Why are orders delayed?", "Which
ingredients may run out?", "Which agents are overloaded?", "Summarize
today's operations." - AI cannot approve refunds, change
permissions/settings, modify orders, approve dish unavailability or
execute overrides. - Enforce current user's region scope on every
retrieval. - Groq via provider-independent LLM gateway; PostgreSQL
source of truth; pgvector/RAG only where useful. - Live data through
permission-checked APIs. - Explain evidence, time window and
uncertainty; do not present predictions as facts. - AI outage must not
interrupt dashboard operations.

## 12. Configuration and audit

  Configuration                                      Regional Manager   Central Administrator
  -------------------------------------------------- ------------------ -----------------------
  Regional hours/delivery limits/capacity defaults   Yes                Yes
  Global business rules                              No                 Yes
  SMS/OTP provider                                   No                 Yes
  AI provider/model                                  No                 Yes
  Integrations                                       No                 Yes
  Regional audit logs                                Yes                Yes
  Global audit logs/YAML                             No                 Yes

Validate configuration before saving; confirm sensitive changes; mask
secrets; maintain append-only audit records; support rollback where
eligible. YAML must be schema-validated, permission-controlled,
versioned and audited; never execute arbitrary code. Audit actor, role,
timestamp, target, action, scope, reason, result, correlation ID and
safe before/after values. Never log passwords, OTPs, tokens or secrets.

## 13. UI/UX

-   Premium enterprise SaaS; desktop-first, responsive tablet/mobile.
-   Collapsible left sidebar; header with search, notifications, profile
    and role/scope.
-   Mobile compact navigation/cards; tablet compact sidebar.
-   Overview prioritizes active/delayed orders, kitchen status/capacity,
    online agents/active deliveries, revenue trends, critical alerts,
    pending approvals and AI insights.
-   Use compact filterable/paginated tables, summary cards and
    purposeful charts.
-   Provide loading, empty, error, permission-denied and success states.
-   Accessible contrast, keyboard focus/navigation and touch targets.
-   Avoid excessive gradients, animations and clutter.
-   Typography recommendation: Inter unless repo has an established font
    system.

### Approved color palette

  -----------------------------------------------------------------------
  Token                   Hex                     Use
  ----------------------- ----------------------- -----------------------
  Primary                 `#021861`               Sidebar, headers,
                                                  primary navigation

  Secondary               `#255DCE`               Actions, links, active
                                                  states, charts

  Accent                  `#DE1110`               Critical alerts,
                                                  destructive actions,
                                                  urgent exceptions

  Base                    `#FFFFFF`               Main workspace

  Neutral                 `#F3F5FA`               Page/secondary
                                                  backgrounds
  -----------------------------------------------------------------------

Use red sparingly and never rely on color alone for status.

### Navigation

Shared: Overview, Kitchen Operations, Delivery Operations, Orders &
Exceptions, Menu & Inventory, Customers & Support, Payments &
Promotions, Reports & Analytics, Management AI Copilot. Regional
Manager: Staff & Access, Regional Settings, Regional Audit Logs. Central
Administrator: Global Staff & Regional Manager Access, Global
Configuration, Integrations & Providers, AI Model Configuration, Global
Audit Logs, YAML Configuration Management. Navigation is
permission-derived; frontend hiding is not authorization.

## 14. Architecture and non-functional requirements

Existing baseline: modular monolith with selective
serverless/event-driven integration; Python/FastAPI; PostgreSQL/Alembic
and PostGIS; Redis/WebSockets; OSRM/Leaflet/OSM; MinIO, Parquet, DuckDB,
dbt; Groq gateway; pgvector; Docker Compose first. Verify repository
before assuming stack. - Reuse shared identity, order, payment,
inventory, kitchen and delivery services. - Server-side role/region
checks for every endpoint, query, export, WebSocket and AI retrieval. -
Transactions/concurrency controls for assignment, capacity and
refunds. - Pagination and bounded date ranges. - Safe retry for read
operations. - No secrets in logs/UI. - AI optional/non-blocking. - Do
not introduce microservices or major infrastructure without demonstrated
need and approval.

## 15. Exclusions

No marketplace, real payments, payroll/incentives/shifts, procurement,
permanent customer deletion, autonomous AI actions, arbitrary YAML code
execution, mandatory microservices migration or native mobile app.

## 16. Acceptance criteria

1.  Regional Manager cannot access other regions through UI, API,
    export, WebSocket or AI.
2.  Central Administrator accesses all regions and manages Regional
    Managers.
3.  Role changes take effect immediately.
4.  Backend rejects unauthorized actions even if manually invoked.
5.  Staff deactivation cannot strand active deliveries.
6.  Kitchen capacity is enforced under concurrent requests and overrides
    audited.
7.  Dish unavailability requires authorized approval and audit.
8.  Agent assignment/reassignment respects one-active-delivery and
    revocation.
9.  Payment and fulfilment states remain separate.
10. Exceptional refund approval/override is permission-checked and
    audited.
11. Review moderation requires reason and audit.
12. Promotions validated server-side.
13. Reports/exports respect region scope.
14. AI uses authorized current data and cannot mutate business state.
15. Provider/configuration access is Central Administrator-only; secrets
    masked.
16. YAML is validated, versioned and audited.
17. Responsive navigation works desktop/tablet/mobile.
18. Critical states are not color-only.
19. All screens have loading, empty, error and denied states.
20. Existing Customer, Kitchen and Delivery Agent flows pass regression
    tests.

## 17. Open implementation decisions

Resolve during repository inspection; do not guess: current repo
structure; identity/region schema; SMS provider and India DLT
requirements; refund thresholds/classes; regional configuration fields;
audit retention/export; YAML editor versus validated upload; KPI
formulas/accounting definitions; AI model/cost limits/evaluation;
logo/tagline/design assets.
