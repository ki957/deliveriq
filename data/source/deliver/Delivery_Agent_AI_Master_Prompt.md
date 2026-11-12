# DeliverIQ — Delivery Agent Portal AI Master Prompt
## UI/UX design and complete dashboard implementation

You are a senior product designer, UX architect and frontend engineer. Design and build the complete DeliverIQ Delivery Agent Portal as a polished, mobile-first, responsive application.

**First read `DeliverIQ_Delivery_Agent_Portal_Requirements.md` completely.** It is the source of truth. Do not invent features, silently alter business rules or expand scope.

## 1. Product goal
DeliverIQ is a POC for one centralized cloud kitchen. Build a credible operational product, not a static mockup. It must have meaningful navigation, working interactions, realistic states, validation, responsive layouts and clearly identified demo data. Prefer a small number of complete workflows over many shallow screens.

## 2. Before implementation: inspect and ask
Inspect the repository first. Report its structure, current frontend stack, entry point, package manager and run commands. Do not assume a framework or replace existing conventions.

Then ask the user, in one concise batch, only for missing information:
1. DeliverIQ logo (SVG preferred; transparent PNG acceptable). If unavailable, ask permission for a text wordmark.
2. Exact brand spelling/tagline. Default: `DeliverIQ`, no tagline.
3. Confirm palette: `#FFF21A`, `#171717`, `#A66BFF`.
4. Font preference. Recommend a legible sans-serif/system stack; do not depend on remote font services without approval.
5. Reference websites/screenshots, if any. Do not copy another product's exact UI.
6. Is this a standalone frontend or integration into an existing DeliverIQ frontend?
7. Implementation target if not evident: static HTML/CSS/JavaScript prototype or existing frontend stack. Do not introduce a framework without approval.
8. Target browsers/device constraints if not evident. Default: modern mobile and desktop browsers.
9. Permission to create clearly fictional mock orders/agents if no sample data exists. Default: yes.
10. Confirm mobile-first with responsive desktop/tablet layouts.
11. Confirm simulated GPS/map mode for local demos while keeping interfaces ready for real browser GPS and open-source map services.

Do not ask for details already established in the repository or requirements. Do not ask the user to paste API keys/secrets into chat. Explain safe local environment-variable configuration if credentials become necessary.

## 3. Design system
Use the exact portal palette:
- `#FFF21A` — yellow
- `#171717` — near-black
- `#A66BFF` — purple

Recommended usage:
- Near-black: main shell, navigation, strong surfaces and text.
- Yellow: primary actions, key operational emphasis and active state.
- Purple: secondary actions, selected states and supporting accents.
- Use neutral supporting colours only when needed for hierarchy and readability.
- Ensure accessible contrast, keyboard focus and large touch targets.
- Never communicate status through colour alone; include text and/or icons.

Visual direction: premium, modern, operational and minimal. Avoid generic admin-template styling, excessive gradients, excessive rounded cards, clutter, decorative charts and unnecessary animations.

## 4. UX principles
- Mobile-first for agents using smartphones during deliveries.
- Responsive on tablet and desktop.
- Current assignment and next action are immediately obvious.
- Large touch targets, minimal typing and clear confirmations.
- Map/navigation is easy to access.
- Explicit loading, empty, error, offline, GPS-denied, GPS-unavailable and success states.
- Destructive actions need confirmation and clear consequences.
- Every visible control must work.
- Do not copy the Customer Portal sidebar without a clear operational reason.

## 5. Screens to implement
Implement only screens supported by the requirements:
1. Agent home: Online/Offline control, current assignment, next action, GPS/network status, relevant notification and useful empty state.
2. Assignment: notification, order summary, 60-second countdown, Accept/Reject, mandatory rejection reason, timeout state.
3. Active delivery: order ID, item summary, instructions, destination, masked phone and permitted phone-reveal action.
4. Map/route: OpenStreetMap-compatible map using Leaflet and OSRM-compatible routing; real/simulated GPS distinction; permission, accuracy and network states.
5. Pickup: explicit `Picked up` action and confirmation; customer tracking becomes available only after pickup.
6. Delivery completion: six-digit OTP entry, backend-verification-ready flow, three-attempt limit, escalation and success state only after verification.
7. Exceptions: customer unavailable, refusal, failure request, pending manager decision and contact-manager action.
8. Notifications: assignment, reassignment, manager instructions and important events; latest 30 days.
9. Delivery history: order ID, date/time, status and reliable duration. No earnings.
10. Profile: name, photo, verified mobile and account status; only permitted fields editable.
11. Manager oversight only if this task/repository includes it. If Manager Portal is a separate deliverable, do not build its complete dashboard here; expose only agent-facing states and integration points.

## 6. Non-negotiable business rules
- One active delivery per agent.
- Hybrid assignment: system recommends; manager can override.
- Assignment response timeout is 60 seconds.
- Timeout returns assignment to pool.
- Rejection requires reason and returns assignment to pool.
- Agent cannot independently cancel accepted delivery.
- Manager force-offline must not abandon active work.
- Accepted agent sees destination and masked phone.
- Customer live tracking begins only after pickup.
- GPS starts on assignment; update interval 3–5 seconds, configurable.
- Real and simulated GPS modes must be clearly distinguished.
- Six-digit delivery OTP is verified by backend; three failed attempts trigger escalation.
- UI alone must never mark delivery successful.
- Customer unavailable: call, wait five minutes, contact manager.
- Delivery failure is requested with reason and approved by manager.
- Prepaid orders never require agent cash collection.
- COD is simulated; payment status is separate from delivery status.
- Reassignment immediately revokes previous agent access.
- Delivery completion stops tracking and closes assignment.
- Backend authorization is authoritative.

## 7. Open-source and simulation rules
- Mapping: OpenStreetMap data, Leaflet and OSRM-compatible routing.
- No Google Maps, Google Maps SDK or proprietary mapping services.
- Keep map/routing behind replaceable adapters so open-source self-hosted services can be used.
- Respect tile/routing service usage policies; public community endpoints are not unrestricted production infrastructure.
- Payment (UPI/card/refund/COD) is simulated through Python/FastAPI. No real money or payment gateway.
- GPS may be simulated for local demos, but never label simulated coordinates as real GPS.
- In-app notifications may be simulated.
- Do not simulate backend authorization or security checks in frontend-only code.

## 8. Technical constraints
- Preserve the existing repository and conventions.
- Do not assume React, Vue, Angular, Tailwind, Bootstrap or another framework without evidence and approval.
- Do not add dependencies without justification.
- Separate UI state from business logic and service adapters.
- Use realistic fictional mock data only where backend endpoints do not exist; label demo data.
- Do not hardcode secrets.
- Do not claim an integration is live if it is only simulated.
- Use semantic accessible markup, keyboard support and visible focus.
- Optimize for mobile performance.
- If the user requires HTML and CSS only, do not add a framework. Explain that meaningful interactions require at least minimal JavaScript and obtain approval before adding it.

## 9. Suggested delivery sequence
1. Inspect repository and report findings.
2. Ask for missing inputs.
3. Propose concise screen map and interaction flow.
4. Confirm visual direction and unresolved decisions.
5. Establish design tokens and responsive shell.
6. Implement dashboard, assignment and active-delivery flow.
7. Implement map/GPS demo and service boundaries.
8. Implement pickup, OTP, exception, notifications, history and profile.
9. Add loading, empty, error, offline and permission-denied states.
10. Test responsive behaviour and every interactive control.
11. Run the app and report exact commands, completed features, simulated features and limitations.

Pause for user approval at design/architecture checkpoints. Do not skip directly to coding.

## 10. Definition of done
- All in-scope screens are navigable.
- All visible actions work.
- Assignment, pickup, OTP, exception and delivery states follow the requirements.
- Previous agents cannot control reassigned orders.
- Mobile touch workflows are usable; tablet/desktop layouts remain coherent.
- GPS, map, network and simulation states are clear and honest.
- No out-of-scope features or dead buttons.
- No misleading live-data claims or frontend-only security checks.
- User receives run instructions and a clear real-versus-simulated feature list.

## Final instruction
Build a focused, production-minded POC. Make every included feature meaningful, functional and demonstrable. Do not optimize for feature count.
