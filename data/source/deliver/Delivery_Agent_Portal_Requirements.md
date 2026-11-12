# DeliverIQ — Delivery Agent Portal Requirements

**Status:** Working baseline for the POC  
**Product:** Single centralized cloud kitchen; not a multi-restaurant marketplace.

## 1. Objective
Build a credible, real-world delivery-agent workflow that demonstrates strong product thinking and engineering. Keep the scope focused. Core business rules should be real; expensive external integrations and UI interactions may be simulated when the simulation demonstrates the workflow adequately.

## 2. Agent capabilities
- Switch Online/Offline manually.
- Receive, accept or reject delivery assignments.
- View assigned order summary, delivery instructions and customer destination.
- Navigate using open-source mapping.
- Confirm kitchen pickup.
- Share live GPS after assignment; customer sees agent location only after pickup.
- Complete delivery using customer OTP.
- Report delivery exceptions and contact the manager.
- View basic delivery history and profile.

No delivery-agent AI chatbot in this phase.

## 3. Assignment and availability
- Hybrid assignment: system recommends an available agent; manager can override or assign manually.
- One active delivery per agent.
- Agent receives an in-app assignment notification and has 60 seconds to respond.
- Timeout returns assignment to the pool.
- Rejection requires a reason and returns assignment to the pool.
- Agent cannot independently cancel an accepted assignment; manager intervention is required.
- Agent and manager can control availability.
- Manager can force an agent offline, but must first reassign or explicitly handle any active delivery. Never silently abandon an order.
- Reassignment immediately revokes the previous agent's access to that assignment.

## 4. Order details and privacy
After accepting an assignment, the agent sees:
- Order ID, item summary/quantities and delivery instructions.
- Full delivery address and destination on the map.
- Masked customer phone number.
- Full phone number only when needed for delivery coordination, and only for the active assigned order.

Customer live tracking begins only after pickup.

## 5. Pickup and delivery
1. Agent accepts assignment.
2. Agent views order details and destination.
3. Agent navigates to the kitchen.
4. Agent taps **Picked up** after collecting the order.
5. Backend validates the state transition.
6. Customer live tracking becomes available after pickup.
7. Agent navigates to the customer.
8. Agent enters the customer's six-digit delivery OTP.
9. Backend verifies the OTP.
10. Only successful verification permits Delivered status.
11. Tracking stops and assignment closes after delivery.

Payment state and delivery state are separate. Prepaid orders never require cash collection. COD is simulated; agent confirms collection and escalates any amount mismatch.

## 6. Maps and GPS
- Open-source mapping only: OpenStreetMap data, Leaflet interactive map, OSRM-compatible road routing.
- Browser Geolocation API for real GPS.
- Support real GPS and simulated GPS modes.
- GPS starts when an order is assigned; proposed update interval is every 3–5 seconds while active and configurable.
- Customer live location sharing starts only after pickup.
- Store active-delivery location history in PostgreSQL/PostGIS.
- Redis + WebSockets may distribute live location/status updates.
- Show permission, accuracy and connectivity warnings honestly. Never fabricate a real location.
- On network loss, show a warning, retry and synchronize only safe queued updates. Backend validates event order and stale updates.
- Route recalculation where practical.
- Do not use Google Maps or proprietary mapping SDKs.
- Public OSM tiles/routing services have usage policies; do not treat community endpoints as unrestricted production infrastructure. Document compliant/self-hosted options.

## 7. Exceptions
- Customer unavailable: agent calls, waits five minutes, then contacts manager.
- Incorrect OTP: three attempts, then manager escalation.
- Customer refuses order: agent submits refusal with mandatory reason; manager handles outcome.
- Delivery failure: agent submits request with mandatory reason; manager approves final failure status.
- GPS unavailable: show warning; do not invent coordinates.
- Network loss: show connection state and retry/synchronize permitted updates.
- Prominent contact-manager action for emergencies.
- Agent cannot silently abandon an accepted delivery.

## 8. Payment simulation
- UPI, card, refund and COD are simulated through Python/FastAPI.
- No real payment gateway and no real money.
- Simulated transactions still have transaction IDs, timestamps, statuses and auditable history.
- Prepaid orders never request cash from agent.
- COD collection confirmation is simulated; amount mismatch escalates to manager.
- Payment and fulfilment statuses remain separate.

## 9. Notifications, profile and history
- In-app notifications: new assignment, reassignment/cancellation, manager instructions and important delivery exceptions.
- Retain latest 30 days of notification history.
- Profile: name, photo, verified mobile and account status.
- Agent can edit name/photo. Mobile change follows account recovery; it is not a simple unverified edit.
- Basic history: order ID, date/time, delivery status and duration where reliable.

## 10. Manager oversight
- View online/offline agents and active assignments.
- View live locations of agents with active assignments.
- Manually assign/reassign orders.
- Force agents offline subject to active-delivery safeguards.
- Review delivery-failure requests.
- Handle COD mismatch escalations.
- Respect manager authorization scope.

## 11. UI/UX direction
**Mobile-first**, with responsive tablet and desktop layouts. Prioritize the current assignment and next action. Use large touch targets, minimal typing, clear status labels, accessible contrast and visible focus states. Map/navigation must be easy to reach. Avoid dense analytics, decorative charts, excessive animation and unnecessary controls.

### Portal colour palette
- Yellow: `#FFF21A`
- Near-black: `#171717`
- Purple: `#A66BFF`

Suggested use: near-black for primary surfaces and text; yellow for primary actions and high-priority emphasis; purple for secondary emphasis and selected states. Use neutral supporting shades only as needed. Never rely on colour alone to communicate status.

## 12. Explicit exclusions
- Delivery-agent AI chatbot.
- Earnings, payroll and incentives.
- Shift scheduling.
- Advanced performance analytics.
- In-app chat/messaging.
- Real payment processing.
- Google Maps/proprietary map services.
- Multiple concurrent deliveries per agent.
- Agent-initiated cancellation of accepted assignments.
- Unnecessary animation or complex UI interactions.

## 13. Acceptance criteria
- DA-01 Agent manually switches Online/Offline subject to location permission and manager controls.
- DA-02 Manager can force offline without silently abandoning an active delivery.
- DA-03 System recommends available agents; manager can override.
- DA-04 Assignment notification and 60-second response timeout work.
- DA-05 Timeout returns assignment to pool.
- DA-06 Rejection requires reason and returns assignment to pool.
- DA-07 Agent has at most one active delivery.
- DA-08 Accepted agent sees order summary, instructions, destination and masked phone.
- DA-09 Full phone access is restricted to coordination for the active assignment.
- DA-10 Pickup is agent-confirmed and backend-validated.
- DA-11 Customer live tracking starts only after pickup.
- DA-12 OpenStreetMap/Leaflet/OSRM-compatible map and routing are used.
- DA-13 Real and simulated GPS modes are distinguishable.
- DA-14 GPS/network failures are represented honestly.
- DA-15 Six-digit OTP is backend-verified; three failed attempts trigger escalation.
- DA-16 Delivered status requires successful OTP verification.
- DA-17 Customer-unavailable flow includes call, five-minute wait and manager escalation.
- DA-18 Delivery failure requires agent reason and manager approval.
- DA-19 COD/prepaid remain distinct; COD is simulated.
- DA-20 Reassignment immediately revokes previous agent access.
- DA-21 Manager can view agents and active deliveries within authorized scope.
- DA-22 Agent can view basic delivery history and permitted profile fields.
- DA-23 In-app notifications cover assignments and important updates.
- DA-24 UI is mobile-first and responsive.
- DA-25 No chatbot, earnings, shift scheduling, advanced analytics or real payment gateway is included.

## 14. Validate during implementation planning
Confirm SMS provider and OTP policy (shared authentication decision), GPS retention period, exact sampling interval, OSM tile/routing deployment, browser background-geolocation limits, PWA requirement, typography/assets and network-recovery conflict handling. These are not permission to expand product scope.
