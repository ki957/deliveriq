# DeliverIQ — Kitchen Portal Requirements

**Document type:** Business and functional requirements  
**Project:** DeliverIQ  
**Portal:** Kitchen  
**Status:** Approved discovery baseline  
**Scope:** Single centralized cloud kitchen, initially Chennai

---

## 1. Purpose and business context

The Kitchen Portal manages incoming customer orders, kitchen acceptance, food preparation, ingredient availability, operational exceptions and delivery handover.

DeliverIQ is a single centralized cloud-kitchen product, not a multi-restaurant marketplace. The Kitchen Portal must integrate with the shared DeliverIQ identity, order, menu, inventory, delivery, notification and AI modules.

The portal is an operational workspace for kitchen staff and the Kitchen Manager. It must prioritize speed, clarity, reliable status updates and low-friction interaction.

## 2. Roles and permissions

### 2.1 Kitchen roles

- **Kitchen Manager**
- **Kitchen Staff**

Regional Manager and Central Administrator remain separate platform roles. Regional Manager retains approval authority for dish unavailability requests and oversight responsibilities defined elsewhere in DeliverIQ.

### 2.2 Permission matrix

| Capability | Kitchen Manager | Kitchen Staff |
|---|---:|---:|
| View incoming and active orders | Yes | Yes |
| Accept or reject incoming orders | Yes | Yes |
| Update order preparation status | Yes | Yes |
| Update individual item status | Yes | Yes |
| View recipe and preparation details | Yes | Yes |
| Request dish unavailability | Yes | Yes |
| Approve dish unavailability | No | No |
| Create or edit recipes | Yes | No |
| Manage ingredient records | Yes | No |
| Adjust ingredient stock | Yes | No |
| View low-stock alerts | Yes | Yes |
| Change kitchen operating mode | Yes | No |
| Configure maximum concurrent order capacity | Yes | No |
| Update delayed-order ETA | Yes | No |
| Manage kitchen staff access | No | No |

All permissions must be enforced by the backend. Hiding a control in the frontend is not authorization.

## 3. Kitchen operating modes and capacity

The Kitchen Manager can set one of three operating modes:

| Mode | Behaviour |
|---|---|
| Normal | Accept orders subject to configured capacity |
| Busy | Apply a lower/configured capacity to limit incoming work |
| Paused | Stop accepting new orders temporarily |

- Maximum concurrent order capacity is configurable.
- Capacity counts accepted orders that have not reached a terminal state (completed/handed over, cancelled or rejected).
- When capacity is reached, the system must stop accepting additional orders and expose a kitchen-busy/serviceability message to the customer experience.
- Capacity becomes available when an active order reaches a terminal state.
- The Kitchen Manager can change capacity.
- Pausing the kitchen overrides normal order intake.
- Existing accepted orders continue to be prepared during Busy or Paused mode.
- Capacity and operating-mode changes must be recorded with actor and timestamp.

**Implementation clarification:** Incoming orders may be visible in the kitchen's incoming queue while the kitchen is at capacity, but they must not be accepted beyond the configured limit. The customer-facing order-placement flow should use the authoritative backend capacity check to avoid accepting orders that cannot enter the kitchen.

## 4. Incoming order management

- New eligible orders appear automatically in one live incoming queue without manual refresh.
- Any authorized Kitchen Manager or Kitchen Staff member may accept or reject an incoming order.
- Acceptance moves the order into the preparation workflow.
- Rejection requires a mandatory reason.
- An order that remains unaccepted beyond a configurable timeout triggers a Kitchen Manager alert.
- The kitchen must receive the relevant order details, payment state, customer instructions and item customizations.
- Payment state and fulfilment state remain separate.
- Prepaid orders must have successful simulated payment before kitchen processing.
- COD orders may enter kitchen processing without online payment.

## 5. Order prioritization

- Default preparation sequence is **FIFO (First In, First Out)**, based on kitchen acceptance time.
- The system must visibly show queue position or accepted time.
- No automatic priority jumping is permitted.
- Approaching-deadline and delayed orders receive visual warnings without changing FIFO sequence.
- Any future override capability must be separately specified and audited; it is not part of this approved baseline.

## 6. Preparation workflow

### 6.1 Order-level statuses

`Accepted → Preparing → Ready for Pickup → Handed Over`

Terminal exception statuses are governed by the shared order lifecycle, including cancellation and rejection. The Kitchen Portal must not invent conflicting global order statuses.

### 6.2 Item-level statuses

`Pending → Preparing → Prepared`

- Authorized kitchen staff can update item statuses.
- Order-level preparation status must reflect item progress.
- An order can become **Ready for Pickup** only when every item is marked **Prepared**.
- The system should transition the order to Ready for Pickup automatically once this condition is met.
- The portal must preserve the identity and timestamp of status changes.
- Staff may continue an order started by another authorized staff member; assigning every order to one individual is not required.

### 6.3 Preparation information

For each order and item, staff can view:
- Order ID and accepted time.
- Dish name and quantity.
- Selected spice level and portion.
- Add-ons and customizations.
- Customer special instructions.
- Relevant recipe, ingredient quantities and preparation steps.
- Current item and order status.
- Estimated preparation time and delay warnings.

Customer customizations and add-ons are included in the base price; the kitchen must not add customization charges.

### 6.4 Recipe versioning

- Kitchen Manager creates and edits recipes.
- A recipe includes ingredients, quantities, units, preparation steps and estimated preparation time.
- Recipe changes apply to new orders only.
- The recipe version used when an order is accepted must be preserved for that order.
- Ingredient substitutions are not automatic.
- Substitution requires Kitchen Manager approval. If it changes the dish or what the customer receives, customer consent is required before proceeding.

## 7. Ingredient inventory

The initial inventory capability is ingredient-level tracking, not a full warehouse or procurement system.

### 7.1 Ingredient records

Each ingredient record should include:
- Ingredient name.
- Unit of measure.
- Available quantity.
- Reserved quantity.
- Low-stock threshold.
- Active/inactive state.

### 7.2 Recipe mapping and stock lifecycle

- Each dish recipe maps to its required ingredients and quantities.
- When an order is accepted, required ingredient quantities are reserved.
- When the order is handed over, reserved quantities are deducted from stock.
- If an order is cancelled or rejected before handover, its reservations are released.
- Reservation must be atomic and concurrency-safe to prevent overselling.
- Stock adjustments require a reason and an audit record.
- Low-stock alerts notify the Kitchen Manager.

### 7.3 Ingredient shortage and dish availability

- When stock is insufficient, the system identifies every dish whose recipe depends on the affected ingredient.
- The affected dishes are flagged for review.
- Kitchen Manager is notified.
- Kitchen staff or Kitchen Manager may submit a temporary dish-unavailability request.
- Regional Manager approves or rejects that request.
- A dish must not be removed from the customer menu solely because an AI recommendation or an unapproved kitchen request exists.
- Approved unavailability updates the customer-facing menu.

### 7.4 Inventory exclusions

Not included in the initial POC:
- Supplier management.
- Purchase orders and procurement workflows.
- Accounting.
- Advanced wastage management.
- Expiry/batch tracking.
- Automatic purchasing.

Inventory intelligence based on predictive forecasting is a later AI enhancement and requires sufficient historical data.

## 8. Delays and operational exceptions

| Scenario | Required behaviour |
|---|---|
| Acceptance timeout | Alert Kitchen Manager after configurable timeout |
| Order rejection | Mandatory reason; update shared order lifecycle |
| Preparation delay | Highlight order and alert Kitchen Manager |
| ETA change | Kitchen Manager can update ETA; notify customer |
| Equipment failure | Kitchen Manager can switch to Paused mode |
| Ingredient shortage | Identify affected dishes and raise stock warning |
| Incorrect preparation | Staff reports issue; Kitchen Manager handles resolution |
| Agent arrives before order is ready | Keep order in preparation; do not permit pickup confirmation prematurely |
| Agent arrives late | Keep ready order visible and notify Kitchen Manager |
| Kitchen cannot fulfil accepted order | Escalate to Regional Manager for resolution |
| Customer cancellation before kitchen acceptance | Remove from incoming queue and release any applicable reservation |
| Customer cancellation after kitchen acceptance | Normal customer cancellation is not permitted under Customer Portal policy |

- Delay records retain original ETA, revised ETA, reason where supplied, actor and timestamps.
- Kitchen staff must not fabricate completion or pickup events.
- The Kitchen Portal must clearly distinguish an operational warning from a status transition.

## 9. Delivery handover

- The kitchen can see the delivery assignment and relevant agent identity.
- When the agent arrives, the order remains Ready for Pickup until the agent confirms collection.
- The delivery agent's **Picked Up** action is authoritative.
- That action automatically transitions the kitchen order to **Handed Over**.
- The kitchen does not perform a second confirmation.
- Pickup must be blocked if the order is not Ready for Pickup.
- The handover event records order, agent, timestamp and relevant audit information.

## 10. Notifications and real-time updates

The Kitchen Portal requires real-time updates for:
- New incoming orders.
- Order acceptance/rejection.
- Capacity reached.
- Kitchen mode changes.
- Approaching preparation deadlines and delays.
- ETA updates.
- Low ingredient stock.
- Dish-unavailability request decisions.
- Delivery agent arrival and pickup.

Use the existing DeliverIQ notification and real-time architecture. A temporary connection loss must not cause duplicate order actions or silently lose persisted state changes.

## 11. Kitchen AI requirements

The Kitchen Portal includes a contextual **Kitchen AI Copilot**. It is an assistant embedded in operational screens, not a separate AI dashboard.

### 11.1 Priority features

**A. Recipe Preparation Copilot — High priority**
- Answers questions about approved recipes, ingredient quantities and preparation steps.
- Explains order-specific customization and special instructions.
- Uses the recipe version associated with the accepted order.
- Grounds answers in approved recipe data and identifies the relevant source.
- Must say when recipe information is missing rather than inventing instructions.

**B. Kitchen Operations Assistant — High priority**
- Answers authorized questions about active orders, FIFO queue, delays, workload and pickup readiness.
- Uses live backend data through permission-checked tools/API calls.
- Shows the relevant order identifiers and data freshness where appropriate.
- Must not rely on stale LLM conversation context for live order status.

**C. Preparation-time prediction — Medium priority**
- Estimates preparation-time ranges using historical preparation durations, dish types, item quantities and current workload.
- Clearly labels estimates and communicates uncertainty.
- Falls back to configured/manual estimates when historical data is insufficient.
- Predictions must not silently reorder the FIFO queue.

**D. Inventory intelligence — Later**
- Analyses historical ingredient consumption and recurring shortages.
- May recommend replenishment quantities.
- Requires adequate historical data and must be presented as advisory only.
- Must not create purchases or change inventory automatically.

### 11.2 AI architecture and safety

- Inference provider: Groq through DeliverIQ's provider-independent LLM gateway.
- PostgreSQL is the source of truth for recipes, orders and inventory.
- Use pgvector/RAG where semantic retrieval is useful; do not force vector search for simple structured lookups.
- Live operational information must be fetched through backend tools/API calls.
- Backend enforces role and record-level authorization on every tool call.
- AI can read, explain, summarize and recommend.
- AI cannot autonomously accept/reject orders, change order status, modify stock, edit recipes, approve dish unavailability, alter capacity or change kitchen operating mode.
- AI must not expose customer personal data beyond what the signed-in kitchen role is authorized to see.
- AI outages must not interrupt normal kitchen operations.
- Display a clear fallback when AI is unavailable.
- Log AI tool usage and relevant audit metadata without unnecessarily retaining sensitive prompts or data.

### 11.3 AI exclusions

- No autonomous kitchen decisions.
- No autonomous inventory changes or purchases.
- No AI-generated recipe substitutions without approval.
- No separate AI analytics dashboard.
- No generic chatbot features unrelated to kitchen work.

## 12. UI/UX requirements

### 12.1 Device strategy

- Primary: large kitchen monitor / Kitchen Display System (KDS).
- Secondary: tablet for touch-based order and item updates.
- Also responsive on desktop, laptop and mobile.

### 12.2 Navigation and screens

| Screen | Purpose |
|---|---|
| Kitchen Overview | Operating mode, active workload and capacity |
| Live Orders | Incoming orders and FIFO queue |
| Preparation Board | Order and item-level preparation controls |
| Recipes | Ingredients and preparation instructions |
| Inventory | Ingredient quantities, reservations and alerts |
| Exceptions | Delays, rejection and operational issues |
| Settings | Capacity and kitchen configuration |

Kitchen Manager sees manager-only controls. Kitchen Staff sees only authorized actions.

### 12.3 Visual design

Approved Kitchen Portal palette:

| Role | Colour |
|---|---|
| Primary / action | `#D5360C` |
| Secondary / warm highlight | `#E6D58D` |
| Dark surface / text | `#101010` |

Use white or neutral light surfaces where needed for readability, and accessible contrast. Status colours must remain distinguishable from the brand palette:
- Preparing: blue informational treatment.
- Ready: green success treatment.
- Delayed: red warning treatment, with clear text/icon in addition to colour.
- Pending: neutral treatment.

Do not use colour alone to communicate status.

### 12.4 Interaction principles

- New orders appear without manual refresh.
- FIFO position is always visible.
- Order cards expand to show individual items and instructions.
- Touch targets are large enough for kitchen tablet use.
- Status updates are quick, clear and confirmed.
- Delayed orders are highlighted without changing queue order.
- Manager controls are separated from routine staff actions.
- Contextual AI assistant must not obstruct order operations.
- Layout adapts to monitor, desktop, tablet and mobile.

## 13. Technical and architecture alignment

Follow the established DeliverIQ architecture:
- Python + FastAPI backend.
- PostgreSQL as source of truth; Alembic migrations.
- Redis and WebSockets for real-time updates.
- Shared identity and role-based access control.
- Existing order, menu, inventory, notification and delivery modules.
- Groq behind provider-independent LLM gateway.
- pgvector for RAG when appropriate.
- Modular monolith with selective serverless functions and event-driven integration.
- Docker Compose for local POC development.

Do not introduce microservices, new databases or infrastructure without a demonstrated requirement. Keep business rules in the backend, not only in frontend logic or prompts.

## 14. POC simulation policy

Simulation is acceptable for expensive external integrations and complex UI interactions where appropriate. However:
- Authentication and authorization must be real.
- Order lifecycle and backend validation must be real.
- Inventory reservation and stock calculations must be real.
- Recipe versioning and audit records must be real.
- AI integration must be real through the selected provider gateway.
- Clearly label simulated external integrations and seeded/demo data.
- Never simulate success for a core operation while presenting it as a real persisted action.

## 15. Explicit exclusions

- Multi-restaurant marketplace functionality.
- Supplier management and procurement.
- Purchase orders and accounting.
- Advanced wastage and expiry tracking.
- Autonomous AI decisions or mutations.
- Automatic recipe substitutions.
- Automatic priority jumping outside FIFO.
- Separate AI dashboard.
- Microservices as the initial architecture.
- Unnecessary analytics dashboards and unrelated features.

## 16. Acceptance criteria

| ID | Acceptance criterion |
|---|---|
| KP-01 | Incoming eligible orders appear automatically |
| KP-02 | Authorized staff can accept/reject; rejection requires a reason |
| KP-03 | FIFO preparation queue is maintained |
| KP-04 | Order and item statuses remain consistent |
| KP-05 | Order becomes Ready only when every item is Prepared |
| KP-06 | Configurable maximum concurrent capacity is enforced |
| KP-07 | Normal, Busy and Paused modes behave correctly |
| KP-08 | Existing accepted orders continue during Busy/Paused mode |
| KP-09 | Accepted orders preserve the recipe version used |
| KP-10 | Ingredient reservations are concurrency-safe |
| KP-11 | Stock is deducted on handover and reservations released on cancellation/rejection |
| KP-12 | Ingredient shortage identifies all dependent dishes |
| KP-13 | Dish unavailability requires Regional Manager approval |
| KP-14 | Low-stock alerts reach Kitchen Manager |
| KP-15 | Manager can update delayed-order ETA and customer is notified |
| KP-16 | Agent pickup automatically marks kitchen order Handed Over |
| KP-17 | Pickup is blocked until the order is Ready |
| KP-18 | Exceptions and important changes retain actor, reason where applicable and timestamps |
| KP-19 | Recipe Copilot answers from approved recipe data |
| KP-20 | Operations Assistant retrieves permission-checked live data |
| KP-21 | AI cannot perform prohibited autonomous mutations |
| KP-22 | AI failure does not interrupt kitchen operations |
| KP-23 | Monitor, desktop, tablet and mobile layouts are usable |
| KP-24 | Approved Kitchen Portal palette is applied accessibly |

## 17. Open implementation details

These are implementation-level values to configure or validate during development, not reasons to reopen the approved business model:
- Default maximum concurrent order capacity.
- Default Busy-mode capacity.
- Order acceptance timeout.
- Preparation deadline thresholds.
- Low-stock thresholds per ingredient.
- Exact notification delivery channels.
- Historical data threshold required before enabling predictive ETA.
- Detailed staff account provisioning workflow, governed by shared identity and access requirements.

---

**Approval baseline:** This document records the Kitchen Portal decisions approved during discovery. Any material change to business behaviour, permissions, inventory rules, AI authority or order lifecycle must be proposed explicitly before implementation.
