# DeliverIQ — Portal Requirements Matrix

**Status:** Consolidated from verified source documents. Source references use file numbers from `SOURCE_DOCUMENT_INVENTORY.md` §2–3.
**Legend — Status:** `Approved` (stated as approved in source) · `Decided` (owner decision in this session) · `Open` (needs owner decision; see Design Decision Register) · `Conflict` (sources disagree)

Source key: **#1** Customer_Dashboard_Requirements · **#2** Customer_Dashboard_AI_Master_Prompt · **#3** Customer_RAG · **#4** Kitchen_Portal_Requirements · **#5** Kitchen_Portal_AI_Master_Prompt · **#6** Kitchen_RAG · **#7** Delivery_Agent_Portal_Requirements · **#8** Delivery_Agent_AI_Master_Prompt · **#9** Management_RAG · **#10** Management_Dashboard_Requirements · **#11** Management_Dashboard_AI_Master_Prompt · **#12** Shared_AI_Infrastructure · **#13** Kitchen SOP · **#14/#15** data · **#16–#21** phases

---

## 1. Cross-cutting platform requirements

| ID | Requirement | Source | Status |
|---|---|---|---|
| PL-01 | Single centralized cloud kitchen, Chennai; not a marketplace; Region and Kitchen modelled separately | #1, #4, #10 | Approved |
| PL-02 | Mobile OTP authentication shared across portals; hashed OTP; expiry; attempt limits; rate limit; never logged | #1, #10, #19 | Approved |
| PL-03 | Users may hold multiple explicit roles; Customer role not implicit for staff | #1, #10 | Approved |
| PL-04 | Role changes take effect immediately; removal revokes sessions | #10, #19 | Approved |
| PL-05 | Trusted devices: seven-day policy, revocable | #19, Harness blueprint §4.2 | Approved |
| PL-06 | Backend authorization authoritative on every endpoint, query, export, WebSocket, AI retrieval; deny by default | All | Approved |
| PL-07 | Payment state separate from fulfilment state | #1, #4, #7, #10 | Approved |
| PL-08 | Simulated UPI/card/COD only; transaction IDs, timestamps, audit history | #1, #7, #10, #15 | Approved |
| PL-09 | Canonical backend order statuses with portal display mappings (§7) | Owner decision | Decided |
| PL-10 | Unavailable-customer wait: configurable, default 5 minutes | Owner decision; #7, #10, #15 | Decided |
| PL-11 | UTC storage; `Asia/Kolkata` display; decimal-safe money | Requirements spec, #17 | Approved |
| PL-12 | Append-only audit: actor, role, timestamp, target, action, scope, reason, result, correlation ID, safe before/after | #10, #17 | Approved |
| PL-13 | No secrets/OTPs/tokens in logs, events, prompts or RAG | All | Approved |
| PL-14 | Realtime via Redis + WebSockets; refetch canonical REST state on reconnect | #4, #7, Requirements spec | Approved |
| PL-15 | Maps: OpenStreetMap, Leaflet, OSRM only; no Google Maps; respect public endpoint policies | #7, #8, #10 | Approved |
| PL-16 | Simulated data, GPS, payments and notifications clearly labelled | #1, #2, #7, #8, #10 | Approved |
| PL-17 | Every screen has loading, empty, error, permission-denied and success states | #2, #8, #10 | Approved |
| PL-18 | Status never communicated by colour alone; accessible contrast, keyboard focus, visible focus, touch targets | #1, #4, #7, #10 | Approved |
| PL-19 | Core workflows work when AI is unavailable; AI independently feature-flagged per portal | #3, #6, #9, #12 | Approved |
| PL-20 | Responsive web / PWA only; no native apps | Owner decision; #10 §15 | Decided |

---

## 2. Customer Portal

### 2.1 Workflows and functional requirements

| ID | Requirement | Source | Acceptance ref | Status |
|---|---|---|---|---|
| CU-01 | Browse after selecting location, without login | #1 §5 | CD-01 | Approved |
| CU-02 | GPS and manual address; multiple saved addresses; one default | #1 §6 | — | Approved |
| CU-03 | Serviceability: straight-line ≤ 4 km **and** road ≤ 6 km; revalidate on address change and before placement | #1 §6 | CD-02, CD-09 | Approved |
| CU-04 | Out of area: unavailable message, nearby serviceable areas, change location; no orderable menu | #1 §6 | CD-02 | Approved |
| CU-05 | OTP required before ordering; new number auto-registers as customer | #1 §5 | CD-03 | Approved |
| CU-06 | Menu page: categories, search, filters (price, veg/non-veg, spice level, popularity/bestseller) | #1 §7 | CD-04 | Approved |
| CU-07 | Unavailable dishes hidden and not orderable | #1 §7 | CD-05 | Approved |
| CU-08 | Dish details: description, ingredients, base price, kitchen-configured customization; no surcharge | #1 §7 | CD-06 | Approved |
| CU-09 | Special instructions free text; 250-character limit enforced in UI and backend | #1 §7, #2; DDR-07 | — | Decided |
| CU-10 | Food-card Add behaviour A/B/C | #1 §4, #2 | — | Open (DDR-06) |
| CU-11 | One unified cart; persisted for authenticated customers; no per-dish cap (stock limits) | #1 §8 | CD-07 | Approved |
| CU-12 | ₹500 minimum food subtotal (before tax and delivery); checked before coupon; a coupon may reduce the payable total below ₹500 (DDR-53) | #1 §8–9; DDR-53 | CD-08 | Approved |
| CU-13 | 30-min price protection; expired + changed price requires explicit confirmation; accepted price preserved | #1 §8 | CD-09 | Approved |
| CU-14 | Item unavailable before checkout: remove, notify, require confirmation | #1 §8 | CD-10 | Approved |
| CU-15 | Prices tax-inclusive; tax detail in bill; delivery fee ₹30 flat per order; **no** free-delivery threshold (supersedes "free above threshold" in #1 §8) | #1 §8; DDR-38 | — | Decided (prices/tax Open, DDR-32) |
| CU-16 | Management-configured coupons; no tips; coupon vs minimum per DDR-53 | #1 §8; DDR-53 | — | Approved |
| CU-17 | Checkout sequence: review → validate → address → ₹500 → coupon → tax/delivery → payment → place → simulate/COD → kitchen | #1 §9 | CD-11, CD-12 | Approved |
| CU-18 | Prepaid requires simulated success before kitchen; COD proceeds | #1 §9 | CD-11 | Approved |
| CU-19 | Cancellation only before kitchen acceptance; kitchen rejection cancels; simulated refund for prepaid only | #1 §10 | CD-13 | Approved |
| CU-20 | Estimated delivery range; live agent map only after pickup | #1 §10 | CD-14 | Approved |
| CU-21 | Order history, details, reorder (current price/stock), invoice download | #1 §11 | CD-15 | Approved |
| CU-22 | Reviews: food rating, delivery rating, written review | #1 §11 | CD-16 | Approved |
| CU-23 | Profile: name, verified mobile, email (all required), preferences, spice preference, declared allergies, favourites | #1 §11 | — | Approved |
| CU-24 | Allergy data is preference only; never a safety guarantee | #1 §11, #3 | — | Approved |
| CU-25 | SMS + in-app notifications for lifecycle events; browser push optional | #1 §12 | — | Approved (SMS provider Open, DDR-40) |
| CU-26 | Support: phone contact, ticket creation, ticket history/status | #1 §12 | CD-16 | Approved |
| CU-27 | Lost-mobile recovery via email verification; safeguards undefined | #1 §5 | — | Open (DDR-41) |
| CU-28 | No chatbot UI until all dashboards complete | #1 §12, #2 | CD-18 | Approved |
| CU-29 | Exclusions: scheduled orders, loyalty, tips, real payments, post-placement modification, paid customization | #1 §13 | — | Approved |

### 2.2 Dashboard structure and navigation

| ID | Requirement | Source |
|---|---|---|
| CU-N1 | Navigation: Home, Menu, My Orders, Support, Profile, Settings; cart visible with item count | #1 §3 |
| CU-N2 | Home sections: welcome + location, active order card (only if active), search entry, categories, popular, featured/promotions, reorder (if history) | #1 §4 |
| CU-N3 | Food card: image, name, short description, price, veg indicator, Add | #1 §4 |

### 2.3 UI and responsive requirements

| ID | Requirement | Source |
|---|---|---|
| CU-U1 | Palette B: primary `#A8C9CB`, background `#FFFFFF`, accent `#F45B0B`; extra neutrals allowed; check contrast | #1 §2, #2 §3; owner decision DDR-01 |
| CU-U2 | Desktop-first, fully responsive; premium food photography; minimal | #1 §2 |
| CU-U3 | Ubuntu-inspired left sidebar (not copied); desktop expanded + collapsible; laptop collapsible; tablet compact/drawer; mobile hamburger + bottom nav | #1 §2, #2 §4 |
| CU-U4 | Deliberate layouts per breakpoint; no simple shrinking | #2 §4 |
| CU-U5 | Never present placeholder imagery or logo as final | #2 §1 |

---

## 3. Kitchen Portal

### 3.1 Role permissions

| Capability | Kitchen Manager | Kitchen Staff | Source |
|---|:-:|:-:|---|
| View incoming/active orders | Yes | Yes | #4 §2.2 |
| Accept/reject (reason required for reject) | Yes | Yes | #4 §2.2, §4 |
| Update order and item status | Yes | Yes | #4 §2.2 |
| View recipes and preparation details | Yes | Yes | #4 §2.2 |
| Request dish unavailability | Yes | Yes | #4 §2.2 |
| Approve dish unavailability | No | No | #4 §2.2 (RM approves) |
| Create/edit recipes | Yes | No | #4 §2.2 |
| Manage ingredient records | Yes | No | #4 §2.2 |
| Adjust stock (reason + audit) | Yes | No | #4 §2.2, §7.2 |
| View low-stock alerts | Yes | **Yes** | #4 §2.2 |
| Change mode / configure capacity | Yes | No | #4 §2.2 |
| Update delayed-order ETA | Yes | No | #4 §2.2 |
| Manage kitchen staff access | No | No | #4 §2.2 |
| Submit recipe for chef validation | Yes (proposed) | No | Owner decision (DDR-10) |
| Activate recipe version (after recorded five SOP sign-offs) | **Yes** | No | Owner decision DDR-30; #13 release checklist |

Note: #4 grants Kitchen Staff "view low-stock alerts", while #6 §15.1 lists `get_low_stock_alerts` as a **Manager-only AI tool**. Both can hold: the UI shows alerts to Staff, and the AI tool is restricted to the Manager. Record as intended, not a conflict.

### 3.2 Order queue and preparation

| ID | Requirement | Source | Acceptance |
|---|---|---|---|
| KI-01 | Eligible orders appear automatically in one live queue | #4 §4 | KP-01 |
| KI-02 | Configurable unaccepted-order timeout alerts Kitchen Manager | #4 §4 | — |
| KI-03 | FIFO by acceptance time; warnings never reorder | #4 §5 | KP-03 |
| KI-04 | Order: Accepted → Preparing → Ready for Pickup → Handed Over | #4 §6.1 | KP-04 |
| KI-05 | Item: Pending → Preparing → Prepared; order auto-Ready when all Prepared | #4 §6.2 | KP-05 |
| KI-06 | Staff may continue another staff member's order; actor + timestamp kept | #4 §6.2 | KP-18 |
| KI-07 | Card shows order ID, accepted time, dish, qty, spice, portion, add-ons, instructions, recipe, status, ETA, delay | #4 §6.3 | — |
| KI-08 | Agent "Picked Up" is authoritative → Handed Over; no second kitchen confirmation; blocked until Ready | #4 §9 | KP-16, KP-17 |
| KI-09 | Early agent does not make order ready; late agent alerts Manager | #4 §8 | — |
| KI-10 | Delay records keep original ETA, revised ETA, reason, actor, timestamps; customer notified | #4 §8 | KP-15 |
| KI-11 | Inability to fulfil an accepted order escalates to RM; KM, RM or CA may reject it after acceptance with a reason (DDR-111 (5)) | #4 §8; DDR-111 | — |

### 3.3 Modes and capacity

| ID | Requirement | Source | Acceptance |
|---|---|---|---|
| KI-12 | Normal / Busy (lower configured capacity) / Paused (no new acceptance) | #4 §3 | KP-07 |
| KI-13 | Capacity = accepted non-terminal orders; enforced by backend; customer placement checks capacity | #4 §3 | KP-06 |
| KI-14 | Accepted orders continue in Busy/Paused | #4 §3 | KP-08 |
| KI-15 | Mode/capacity changes audited; RM/CA may also change within scope with reason | #4 §3, #10 §5 | — |
| KI-16 | Equipment failure can trigger Paused | #4 §8 | — |

### 3.4 Recipes and inventory

| ID | Requirement | Source | Acceptance |
|---|---|---|---|
| KI-17 | Recipe: ingredients, quantities, units, steps, estimated prep time; versioned | #4 §6.4 | — |
| KI-18 | Accepted order pins recipe version; edits affect new orders only | #4 §6.4 | KP-09 |
| KI-19 | Substitution never automatic; KM approval; customer consent if dish changes | #4 §6.4 | — |
| KI-20 | Imported recipes remain DRAFT until chef validation and explicit activation | Owner decision | — |
| KI-21 | Ingredient record: name, unit, available, reserved, low-stock threshold, active | #4 §7.1 | — |
| KI-22 | Reserve on acceptance; deduct on handover; release on cancel/reject; atomic; concurrency-safe | #4 §7.2 | KP-10, KP-11 |
| KI-23 | Shortage identifies all dependent dishes; flagged; KM notified | #4 §7.3 | KP-12 |
| KI-24 | Dish unavailability: kitchen requests, RM approves; only approved changes reach customer menu; AI cannot remove dishes | #4 §7.3 | KP-13 |
| KI-25 | Exclusions: suppliers, procurement, POs, accounting, advanced wastage, expiry/batch tracking | #4 §7.4 | — |
| KI-26 | SOP AI stock-deduction command excluded from MVP | Owner decision; #13 | — |

### 3.5 Kitchen UI

| ID | Requirement | Source |
|---|---|---|
| KI-U1 | Primary device: large KDS monitor; secondary: tablet; responsive to desktop/laptop/mobile | #4 §12.1 |
| KI-U2 | Screens: Overview, Live Orders, Preparation Board, Recipes, Inventory, Exceptions, Settings | #4 §12.2 |
| KI-U3 | Palette: primary `#D5360C`, secondary `#E6D58D`, dark `#101010`; neutral light surfaces allowed | #4 §12.3 |
| KI-U4 | Status treatments: Preparing blue, Ready green, Delayed red + text/icon, Pending neutral | #4 §12.3 |
| KI-U5 | Large touch targets; low-typing status changes; manager controls separated; AI must not obstruct | #4 §12.4 |
| KI-U6 | No decorative controls; every control functional or labelled preview | #5 §7 |

---

## 4. Delivery Agent Portal

### 4.1 Agent workflows

| ID | Requirement | Source | Acceptance |
|---|---|---|---|
| DL-01 | Manual Online/Offline, subject to location permission and manager controls | #7 §3 | DA-01 |
| DL-02 | Hybrid assignment: system recommends; manager overrides | #7 §3 | DA-03 |
| DL-03 | One active delivery per agent | #7 §3 | DA-07 |
| DL-04 | 60-second response; timeout → pool; rejection requires reason → pool | #7 §3 | DA-04–06 |
| DL-05 | Agent cannot cancel accepted assignment; manager intervention required | #7 §3 | — |
| DL-06 | Manager force-offline only after active work reassigned/handled | #7 §3 | DA-02 |
| DL-07 | Reassignment immediately revokes previous agent access | #7 §3 | DA-20 |
| DL-08 | After accept: order ID, items, instructions, full address, map destination, masked phone; full phone only for active coordination | #7 §4 | DA-08, DA-09 |
| DL-09 | Pickup: agent taps Picked up → backend validates (order must be Ready) | #7 §5 | DA-10 |
| DL-10 | Customer tracking starts only after pickup | #7 §4–6 | DA-11 |
| DL-11 | Six-digit OTP, backend-verified; 3 failures → manager escalation; UI alone cannot mark Delivered | #7 §5, §7 | DA-15, DA-16 |
| DL-12 | Delivery completion stops tracking and closes assignment | #7 §5 | — |
| DL-13 | Customer unavailable: call, wait (default 5 min, configurable), contact manager | #7 §7; DDR-14 | DA-17 |
| DL-14 | Refusal and failure: mandatory reason; manager approves final failure | #7 §7 | DA-18 |
| DL-15 | Prepaid: no cash collection; COD simulated; amount mismatch escalates | #7 §8 | DA-19 |
| DL-16 | Notifications: assignment, reassignment/cancellation, manager instructions, exceptions; 30-day history | #7 §9 | DA-23 |
| DL-17 | History: order ID, date/time, status, reliable duration; no earnings | #7 §9 | DA-22 |
| DL-18 | Profile: name, photo editable; mobile change via recovery; account status | #7 §9 | DA-22 |
| DL-19 | Exclusions: AI chatbot, earnings, payroll, shifts, analytics, chat, multi-delivery, Google Maps | #7 §12 | DA-25 |

### 4.2 GPS and maps

| ID | Requirement | Source | Acceptance |
|---|---|---|---|
| DL-G1 | GPS starts on assignment; 3–5 s interval, configurable. Assignment occurs at kitchen acceptance (DDR-51) | #7 §6; DDR-51 | — |
| DL-G2 | Real (browser Geolocation) and simulated modes clearly distinguished | #7 §6 | DA-13 |
| DL-G3 | Permission, accuracy, connectivity warnings shown honestly; never fabricate | #7 §6 | DA-14 |
| DL-G4 | Network loss: warn; buffer GPS points in bounded memory and re-send; backend rejects stale/out-of-order; actions blocked offline (DDR-52) | #7 §6; DDR-52 | DA-14 |
| DL-G5 | Location history stored in PostgreSQL/PostGIS; Redis/WebSocket distribution; retained 30 days then deleted or irreversibly anonymised by a retention job (sampling interval Open, DDR-43). GPS points are not exported as events; analytics uses per-delivery summaries (DDR-78) | #7 §6; DDR-43; DDR-78 | — |
| DL-G6 | Map/routing behind replaceable adapters | #8 §7 | DA-12 |

### 4.3 Delivery UI and PWA

| ID | Requirement | Source |
|---|---|---|
| DL-U1 | Mobile-first; responsive tablet/desktop; current assignment and next action obvious | #7 §11, #8 §4 |
| DL-U2 | Palette A: yellow `#FFF21A`, near-black `#171717`, purple `#A66BFF` | #7 §11, #8 §3; owner decision DDR-02 |
| DL-U3 | Large touch targets, minimal typing, confirmations for destructive actions | #8 §4 |
| DL-U4 | Explicit offline, GPS-denied, GPS-unavailable states | #8 §4 |
| DL-U5 | Do not copy Customer sidebar without operational reason | #8 §4 |
| DL-U6 | Screens: Home, Assignment, Active delivery, Map, Pickup, Completion, Exceptions, Notifications, History, Profile | #8 §5 |
| DL-U7 | Installable PWA (Decided). Offline action queue not approved. Background geolocation Open (DDR-15) | #7 §14; DDR-15 |

---

## 5. Unified Management Portal (RM / CA)

### 5.1 Role and scope

| Capability | Regional Manager | Central Administrator | Source |
|---|---|---|---|
| View operations | Assigned regions | All regions | #10 §2 |
| Create/manage Regional Managers, assign regions | No | Yes | #10 §2 |
| Manage KM, KS, Delivery Agents | Assigned regions | All | #10 §2 |
| Assign/reassign agents | Assigned regions | All | #10 §2 |
| Change kitchen mode/capacity (with reason) | Assigned regions | All | #10 §2, §5 |
| Approve dish unavailability | Assigned regions | All | #10 §2 |
| Exceptional refund approval | Assigned regions | All | #10 §2 |
| Override refund decisions | No | Yes | #10 §2 |
| Regional settings | Yes | Yes | #10 §12 |
| Global settings, providers, AI model, integrations, YAML | No | Yes | #10 §12 |
| Regional audit logs | Yes | Yes | #10 §12 |
| Global audit logs | No | Yes | #10 §12 |
| Customer suspension | Initiate/recommend in scope | Final authority | #10 §8 |
| Promotions | Regional | Global + regional; global coupon rules | #10 §9 |
| Publish menu items to customer menu (readiness checklist + ACTIVE recipe; audited) | **Yes** (assigned regions) | **Yes** (all regions) | DDR-11, DDR-31 |

### 5.2 Functional requirements

| ID | Requirement | Source |
|---|---|---|
| MG-01 | Prevent self-escalation; staff deactivation must not strand active work | #10 §4 |
| MG-02 | Ingredient shortage does not auto-hide a dish; approval controls availability | #10 §5 |
| MG-03 | Overrides require permission and mandatory reason | #10 §7 |
| MG-04 | Review hiding requires reason + audit; no permanent customer deletion | #10 §8 |
| MG-05 | Refund records: actor, amount, reason, order, outcome | #10 §9 |
| MG-06 | Promotions validated server-side (eligibility, dates, limits) and audited | #10 §9 |
| MG-07 | Reports: orders, revenue, kitchen, delivery, inventory, customers, staff, promotions; date filters, comparisons, CSV export with same scope | #10 §10 |
| MG-08 | Metrics from persisted records; formulas/time windows defined; simulated data labelled | #10 §10, #11 |
| MG-09 | YAML: schema-validated, permission-controlled, versioned, audited, rollback; no code execution; secrets masked | #10 §12 |
| MG-10 | Navigation: shared modules + RM-only + CA-only sections; permission-derived | #10 §13 |
| MG-11 | Management Copilot: read-only; region-scoped; evidence + time window + uncertainty | #10 §11, #9 |
| MG-12 | Data Pipelines area: groups Data and Knowledge; CA triggers, cancels, retries and views all; RM views own-region runs only; others denied | DDR-63, DDR-64 |
| MG-13 | Management Operational Actions: CA only; typed allowlisted tools with confirmation, same backend RBAC, idempotent, audited | DDR-68, DDR-69 |
| MG-14 | Builder Agent: CA only; sandboxed code changes delivered as PRs; never merges or pushes to `main` | DDR-68, DDR-70, DDR-71 |
| MG-15 | AI settings: CA only; move a harness to a model already in config; capability-checked; audited; applies without restart; reset to default; UI never adds providers or keys. AI health panel (CA only) | #10 §12, DDR-87 |

### 5.3 Management UI

| ID | Requirement | Source |
|---|---|---|
| MG-U1 | Palette: primary `#021861`, secondary `#255DCE`, accent `#DE1110` (sparingly), base `#FFFFFF`, neutral `#F3F5FA` | #10 §13 |
| MG-U2 | Premium enterprise SaaS; desktop-first; collapsible sidebar; header with search, notifications, profile, role/scope | #10 §13 |
| MG-U3 | Typography: Inter unless repo has an established system | #10 §13 |
| MG-U4 | Compact filterable/paginated tables, summary cards, purposeful charts | #10 §13 |

---

## 6. Shared design requirements (`shareddsah/` and cross-portal)

`shareddsah/` contains **no shared design-system document**. The requirements below are the only shared design rules that appear consistently across portal documents. Everything else is Open (DDR-21, DDR-22).

| ID | Requirement | Source | Status |
|---|---|---|---|
| SH-01 | Per-portal palettes as theme tokens; no palette mixing across portals | #1, #4, #7, #10; DDR-01/02 | Decided |
| SH-02 | Shared components (buttons, forms, tables, modals, status badges, nav shell, toasts) themed by tokens; not duplicated per portal | Owner request; Requirements spec §4.6 | Decided |
| SH-03 | Status indicators: text + icon + colour | All portal docs | Approved |
| SH-04 | Keyboard navigation, visible focus, semantic markup, labels | All portal docs | Approved |
| SH-05 | Avoid excessive gradients, glassmorphism, decorative animation, clutter | #1, #4, #8, #10 | Approved |
| SH-06 | Spacing scale, type scale, radius, elevation | None | Decided (DDR-21) |
| SH-07 | Typography family | Inter (Mgmt), system stack (Delivery), undecided (Customer, Kitchen) | Decided: Inter, self-hosted, all portals (DDR-22) |
| SH-08 | Logo and tagline | Requested in #2, #5, #8, #11; none supplied | Open (DDR-08) |
| SH-09 | Breakpoints | Not specified numerically | Decided (DDR-21) |

---

## 7. Canonical order status model (decided) and display mappings

Backend stores **three independent state machines**. Portals derive display labels. No portal invents its own status.

### 7.1 Canonical fulfilment status (`orders.fulfilment_status`)

| Canonical | Meaning | Entered by |
|---|---|---|
| `PLACED` | Order persisted; awaiting payment outcome (prepaid) or immediately eligible (COD) | Checkout |
| `PENDING_KITCHEN` | Eligible for kitchen queue | Payment success or COD |
| `ACCEPTED` | Kitchen accepted; recipe pinned; stock reserved | Kitchen |
| `PREPARING` | At least one item Preparing | Kitchen (auto from items) |
| `READY_FOR_PICKUP` | All items Prepared | Auto |
| `PICKED_UP` | Agent confirmed pickup; stock deducted | Delivery agent |
| `OUT_FOR_DELIVERY` | Agent en route to customer | Automatic after validated pickup (DDR-16) |
| `DELIVERED` | OTP verified | Backend after OTP |
| `CANCELLED` | Terminal: customer cancel before acceptance, or prepaid payment failure | Customer / system |
| `REJECTED` | Terminal: kitchen rejection before acceptance, or "cannot fulfil" after acceptance (from `ACCEPTED`, `PREPARING` or `READY_FOR_PICKUP`; KM, RM or CA; reason required; releases stock, refunds prepaid; DDR-111 (5)) | Kitchen / KM, RM, CA |
| `DELIVERY_FAILED` | Terminal: manager-approved failure | Manager |

Non-terminal flag: `delivery_exception_open` (customer unavailable, OTP escalation, refusal pending) — a flag, not a status, so the main status does not regress.

### 7.2 Other canonical machines

- **Payment** (`payments.status`): `PENDING`, `SUCCEEDED`, `FAILED`, `TIMED_OUT`, `REFUND_PENDING`, `REFUNDED`; COD: `COLLECTION_PENDING`, `COLLECTED`, `MISMATCH`. Values align with simulator scenarios in #15 §9.
- **Delivery assignment** (`delivery_assignments.status`): `OFFERED`, `ACCEPTED`, `REJECTED`, `EXPIRED`, `REVOKED`, `COMPLETED`, `FAILURE_REQUESTED`, `FAILED`.
- **Item** (`order_items.prep_status`): `PENDING`, `PREPARING`, `PREPARED`.

### 7.3 Display mapping

| Canonical fulfilment (+ assignment) | Customer label (#1 §10) | Kitchen label (#4 §6.1) | Delivery label (#7 §5) | Management label |
|---|---|---|---|---|
| `PLACED` | Order placed | — (not visible) | — | Placed |
| `PENDING_KITCHEN` | Awaiting kitchen acceptance | Incoming | — | Awaiting kitchen |
| `ACCEPTED` | Accepted | Accepted | — | Accepted |
| `PREPARING` | Preparing | Preparing | — | Preparing |
| `READY_FOR_PICKUP` (no accepted assignment) | Ready for pickup | Ready for Pickup | — | Ready |
| any of `ACCEPTED…READY_FOR_PICKUP` + assignment `ACCEPTED` | Fulfilment label unchanged (e.g. Preparing) **plus** "Agent Assigned" indicator, shown immediately after assignment | (agent shown on card) | Go to kitchen | Agent assigned |
| `PICKED_UP` | Picked up | Handed Over | Picked up | Picked up |
| `OUT_FOR_DELIVERY` | Out for delivery | Handed Over | In transit | Out for delivery |
| `DELIVERED` | Delivered | Handed Over | Delivered | Delivered |
| `CANCELLED` | Cancelled | Cancelled (if seen) | — | Cancelled |
| `REJECTED` | Rejected | Rejected | — | Rejected |
| `DELIVERY_FAILED` | Delivery failed | Handed Over | Failed | Delivery failed |

**Agent Assigned visibility (decided, DDR-16):** the customer sees "Agent Assigned" immediately after an agent is successfully assigned (assignment status `ACCEPTED`), without waiting for `READY_FOR_PICKUP`. It is derived from the assignment machine and shown alongside the fulfilment label; it never changes `fulfilment_status`, never implies pickup, and never enters `OUT_FOR_DELIVERY`. On reassignment or revocation the indicator reflects the current assignment only. This means the customer may see "Agent Assigned" while the order is still Preparing, which differs from the linear list in #1 §10; the owner decision takes precedence.

**`OUT_FOR_DELIVERY` (decided, DDR-16):** entered automatically after the validated pickup, in the same transaction. It is never entered because of assignment.

Because assignment happens at kitchen acceptance (DDR-51), "Agent Assigned" typically appears while the order is Accepted or Preparing.

---

## 8. AI requirements by portal (summary)

| Portal | Harness | MVP status | Read-only | Source |
|---|---|---|---|---|
| Management | Management Copilot + Management RAG | First in AI order | Yes | #9, #10 §11 |
| Management | Management Operational Actions | With Management (Task 15A) | No — confirmed, audited writes (CA only) | DDR-68, DDR-69 |
| Management | Builder Agent | With Management (Tasks 15B–15C) | No — PRs only, never merges (CA only) | DDR-68, DDR-70, DDR-71 |
| Kitchen | Kitchen Copilot + Kitchen RAG (recipe-version aware) | Second | Yes | #6, #4 §11 |
| Customer | Customer Assistant + Customer RAG | Third; gated on all portals complete | Yes | #3, #1 §12 |
| Delivery | None | Excluded | — | #7 §2 |
| ML | Demand forecasting, then ETA/assignment optimization | Fourth, fifth | Advisory only | Owner decision |

All RAG ingestion, retrieval and evaluation is English only (DDR-58).

---

## 9. Requirements count

| Area | Mapped IDs |
|---|---:|
| Platform (PL) | 20 |
| Customer (CU + CU-N + CU-U) | 29 + 3 + 5 = 37 |
| Kitchen (KI + KI-U) + permission rows | 26 + 6 = 32 (+15 permission rows) |
| Delivery (DL + DL-G + DL-U) | 19 + 6 + 7 = 32 |
| Management (MG + MG-U) + capability rows | 15 + 4 = 19 (+15 capability rows) |
| Shared (SH) | 9 |
| **Total requirement IDs** | **149** |

Of these, 3 have status Open (CU-10, CU-27, SH-08); SH-06, SH-07 and SH-09 were decided on 2026-11-12 (DDR-21, DDR-22). A further 4 are decided in part with open values:
- CU-15 prices/tax (real SOP dishes are out of POC scope, DDR-32);
- CU-25 SMS provider (out of POC scope, DDR-40);
- DL-G5 sampling interval (DDR-43);
- DL-U7 background geolocation (DDR-15).

All are tracked in the Design Decision Register. Owner decisions of 2026-11-11 closed CU-09, recipe activation authority (KM) and menu publication authority (RM and CA, DDR-31). Decisions of 2026-11-12 added MG-12 to MG-15.

---

## 10. AI guardrail matrix

One row per harness. Backend authorization is the security boundary in every case; prompts are behavioural guidance only (#3 §16, #6 §17, #9 §15). Customer, Kitchen and Management Copilot rows consolidate the source specifications; Operational Actions and Builder Agent rows come from DDR-68–DDR-71.

### 10.1 Placement, users and sources

| Harness | Where / UI placement | Permitted users | System prompt source | Knowledge sources | Tools | Write capability |
|---|---|---|---|---|---|---|
| Customer Assistant | Customer portal; UI hidden until all dashboards are complete (CD-18) | Customers; anonymous users get public content only | "DeliverIQ Customer Assistant", #3 §16 | Customer RAG: customer-visible menu content, FAQs, ordering/delivery/cancellation/refund/support policies (#3 §5) | Read-only: menu, dish details, customizations, price, availability, promotions, serviceability, delivery quote, own orders, support options (#3 §14.1) | None |
| Kitchen Copilot | Contextual in kitchen screens; no separate AI dashboard (#4 §11.3) | Kitchen Staff and Kitchen Manager | "DeliverIQ Kitchen Copilot", #6 §17 | Kitchen RAG: versioned recipes, kitchen SOPs, food-handling guidance, troubleshooting (#6 §5.2) | Read-only. Both roles: recipes, recipe version, order kitchen view, prep status, SOPs, troubleshooting, kitchen context. KM only: stock summary, reservations, low-stock alerts, mode/capacity, delays, shortage impact (#6 §15.1) | None |
| Management Copilot | Management portal | RM (assigned regions); CA (global) | "DeliverIQ Management Copilot", #9 §15 | Management RAG: operational SOPs, business policies, management documentation, analytics definitions (#9 §4) | Read-only role-scoped report and operations tools (#9 §13.1) | None |
| Management Operational Actions | Management portal | CA only | "DeliverIQ Operational Actions Assistant" v1, `RAG_AI_DESIGN.md` §13.1 (DDR-93) | None beyond the action contract | Allowlist per DDR-69 | Yes: confirmed, idempotent, audited, via the same backend services as the UI |
| Builder Agent | Management portal; runs in on-demand `agent` sandbox | CA only | "DeliverIQ Builder Agent" v1, `RAG_AI_DESIGN.md` §13.2 (DDR-93) | Throwaway repository copy only; no untrusted content (DDR-71) | Edit files and run unit tests inside the sandbox; open PR | PRs only; never merges or pushes to `main` (DDR-70) |
| Delivery | — | — | — | — | — | No AI (#7 §2) |

### 10.2 Cannot do, guardrails and proving tests

| Harness | Cannot do | Key guardrails | Proving tests |
|---|---|---|---|
| Customer Assistant | Place, modify or cancel orders; pay, refund or apply coupons; change profile or address; change price, stock or menu; read Kitchen or Management RAG, recipes, SOPs, stock, staff data or costs; see other customers' orders; guarantee allergen safety or give medical advice; request OTPs, card numbers or passwords (#3 §2.2, §14.3, §16) | Server-side retrieval filters (#3 §12.4); customer identity from session only; short-lived conversation memory; abstention when evidence is weak; independent feature flag | #3 §17.3 cross-portal and ownership tests |
| Kitchen Copilot | Accept/reject orders; change status; mark Ready or Handed Over; edit or publish recipes; adjust stock or reservations or run the SOP stock command (DDR-18); substitute ingredients; change mode, capacity or ETA; approve unavailability; manage staff; contact customers or refund; override FIFO; read Customer or Management RAG, customer profiles or revenue; invent cook times or temperatures (#6 §2.3, §15.3, §17) | Exact pinned recipe version; no mixed-version chunks; food-safety escalation; kitchen scope from trusted identity; KM-only tools hidden from KS in the backend; TEST recipes indexed in test/demo only; production refuses fixture chunks (DDR-77) | #6 §18.3 cross-portal, role and recipe-version tests; production-profile Kitchen RAG rejects `is_test_fixture` chunks |
| Management Copilot | Any write (writes exist only in the MG-13/MG-14 harnesses); read Customer or Kitchen RAG; let an RM cross regions or see CA-only content; fall back to global data; reveal secrets; run SQL or shell; invent metrics (#9 §2.3, §13.3, §15) | RM region scope enforced server-side; CA-only content excluded for RM; reporting period and definition stated; abstain on policy conflicts | #9 §16.2 region, portal and read-only tests |
| Management Operational Actions | Any excluded action: staff/role changes, RM creation and region assignment, AI provider/model settings, integrations, secrets, global YAML at runtime, customer suspension, refund overrides (DDR-69) | Confirmation dialog showing the exact change; same backend service and RBAC checks as the UI; idempotent; audited; exceptional refund disabled until DDR-44 thresholds exist | Each allowed action requires confirmation and writes an audit record; excluded actions are not registered; RM and all other roles denied; exceptional refund rejected without thresholds |
| Builder Agent | Merge or push to `main`; modify its own prompts, guardrails, permissions, RBAC, secrets or CI workflow files; access the live DB, Redis or `.env`; read untrusted content (reviews, tickets, orders, notes, RAG documents); change global YAML outside the PR path (DDR-70, DDR-71) | Sandbox container destroyed after each task; outbound network limited to GitHub and configured LLM provider hosts (DDR-85); `ai_models.yaml` is a protected path (DDR-87); CPU/memory capped; branch protection on `main`; CA reviews diff before PR | No push to `main`; no merge; cannot edit own prompts/guardrails/RBAC/secrets/CI; no DB/Redis/`.env` access from sandbox; untrusted content excluded from context; egress limited to allowed hosts |
| Delivery | — | No AI registered | Test asserts no AI endpoint is reachable from the Delivery portal |
