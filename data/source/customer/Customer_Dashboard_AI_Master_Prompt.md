# DeliverIQ Customer Dashboard --- AI Master Generation Prompt

You are a senior product designer and frontend engineer. Design and
implement the **Customer Dashboard** for DeliverIQ, a
single-centralized-cloud-kitchen ordering and delivery POC.

Treat the accompanying `DeliverIQ_Customer_Dashboard_Requirements.md` as
the source of truth. Do not invent scope or silently change approved
business rules.

## 1. Before implementation: collect missing inputs

Inspect the available project context first. Ask only for information
not already supplied. Ask concise, grouped questions and accept partial
answers.

1.  **Logo:** Request DeliverIQ logo. Prefer SVG; transparent PNG is
    acceptable. Ask whether light/dark variants exist.
2.  **Brand wording:** Confirm exact capitalization/spelling and
    tagline, if any.
3.  **Food imagery:** Ask whether user will provide dish photos, an
    image folder, or authorize temporary clearly-labelled placeholders.
4.  **Typography:** Ask for font preference or permission to choose.
5.  **References:** Ask for websites, screenshots or apps to use as
    design inspiration (do not copy).
6.  **Implementation target:** Confirm static HTML/CSS prototype or
    integration into existing frontend. Do not assume a framework.
7.  **Existing project:** If integrating into a repository, inspect
    structure/conventions before editing. Ask for files/repository if
    unavailable.
8.  **Food-card Add action:** User has not decided: A) add directly and
    customize later; B) always open customization first; C) add directly
    if no customization is needed, otherwise open customization. Ask
    before deciding. If user explicitly authorizes a sensible default,
    use C.
9.  **Special instructions:** Confirm proposed 250-character limit.
10. **Viewport/browser constraints:** Ask if specific targets are
    required.

Do not block on optional assets if the user authorizes placeholders.
Never fabricate an official logo or present placeholder imagery as final
brand photography.

## 2. Product context

-   Product: DeliverIQ.
-   Scope: Customer Dashboard only.
-   One centralized cloud kitchen, initially in Chennai.
-   Not a multi-restaurant marketplace.
-   POC: prioritize simple, dependable end-to-end customer ordering.
-   Business requirements are approved; UI/UX discovery is still in
    progress.
-   Other portals (Delivery Agent, Kitchen, Regional Manager, Central
    Administrator) are outside this task.
-   Customer AI chatbot design and implementation are deferred until all
    five dashboards are completed. Do not add chatbot widgets, floating
    AI buttons, AI panels or chatbot flows.

## 3. Brand palette

Use the exact supplied colours: - Primary: `#A8C9CB` - Base/background:
`#FFFFFF` - Accent: `#F45B0B`

Suggested tokens: - `--color-primary: #A8C9CB` -
`--color-background: #FFFFFF` - `--color-accent: #F45B0B`

You may add neutral text, border, muted-surface and status colours for
accessible hierarchy. Do not replace the supplied colours. Check
contrast; use readable dark text where needed. Do not assume white text
is accessible on every teal/orange surface.

## 4. Visual direction and responsive layout

-   Desktop-first, fully responsive on laptop, tablet and mobile.
-   Premium food photography + clean, minimal layout.
-   Ubuntu-inspired left-sidebar navigation concept; do not copy Ubuntu
    branding, artwork, icons or exact interface.
-   Desktop sidebar expanded by default with icon + label; collapsible.
-   Laptop: collapsible sidebar.
-   Tablet: compact sidebar or drawer.
-   Mobile: hamburger drawer + bottom navigation for primary sections.
-   Generous whitespace, clear hierarchy, consistent spacing, readable
    typography, restrained shadows and borders.
-   Avoid excessive gradients, glassmorphism, decorative animations and
    clutter.
-   Prominent, consistently cropped food photography.
-   Accessible focus states, keyboard navigation, semantic markup and
    adequate contrast.
-   Deliberately design desktop, tablet and mobile layouts; do not
    merely shrink desktop.

## 5. Navigation

1.  Home
2.  Menu
3.  My Orders
4.  Support
5.  Profile
6.  Settings

Keep cart access convenient and visible, with item-count indicator when
relevant.

## 6. Home dashboard

Selected sections only: 1. Welcome message and current delivery
location. 2. Active order card only when an active order exists. 3. Menu
search entry point. 4. Food categories. 5. Popular dishes. 6. Featured
dishes/promotions. 7. Reorder previous meals when history exists.

Full catalogue is on separate Menu page.

Food cards use a responsive grid and include image, name, short
description, price, veg/non-veg indicator and Add action. Selecting a
dish opens details/customization.

Do not guess the Add-button interaction; ask the user first (see section
1). If explicitly asked to proceed with a default, use option C.

## 7. Location and delivery

-   Visitors browse without login after selecting location.
-   Support GPS and manual address entry.
-   Multiple saved addresses and one default address for authenticated
    customers.
-   Validate address and GPS coordinates against configured delivery
    zones.
-   Eligibility requires BOTH: straight-line distance \<= 4 km AND road
    distance \<= 6 km from kitchen.
-   Outside area: clear unavailable message, nearby serviceable areas,
    allow location change.
-   Revalidate when address changes and before order placement.
-   Do not show an orderable menu for an unserviceable location.
-   Do not fake live GPS/routes. For visual prototype, label sample data
    illustrative.

## 8. Menu and customization

Menu page: full catalogue, categories, search, filters for price,
veg/non-veg, spice level and popularity/bestseller. Hide unavailable
dishes. Dish details show description, ingredients, base price and
kitchen-configured options.

Customization: - Configured per dish by kitchen. - Examples: spice
level, portion size, add-ons. - All customization included in base
price; no surcharge. - Free-text special instructions; proposed
250-character limit pending confirmation. - Kitchen controls
availability. - Do not claim allergy safety. Allergy data is
customer-provided preference information.

## 9. Cart and checkout

-   One unified cart for the single kitchen.
-   Persist for authenticated customers.
-   No fixed per-dish quantity cap; stock availability controls
    quantity.
-   Minimum order: ₹500 food subtotal before taxes and delivery.
-   Price protection: 30 minutes after adding an item.
-   If item unavailable before checkout, remove it, notify customer and
    require confirmation.
-   No order modifications after placement.
-   Reorder allowed subject to current availability/prices.
-   Delivery fee configurable; free delivery above configurable
    threshold.
-   Dish prices displayed inclusive of taxes; tax details in bill.
-   Management-configured coupons.
-   No tips.

Never silently charge a changed price. Validate at checkout. If
protection expired and price changed, show revised price and require
explicit confirmation before payment. Preserve accepted price in order.

Checkout sequence: review cart → validate availability/prices → confirm
address/eligibility → enforce ₹500 minimum → apply coupon → calculate
taxes/delivery → select payment → place order → simulate payment or COD
→ send to kitchen.

Payment methods: UPI simulator, card simulator, COD. No real payments.
Track payment and fulfilment separately. Prepaid orders require
successful simulated payment before kitchen processing. COD requires no
online payment. Kitchen acceptance is required for fulfilment
confirmation.

## 10. Order lifecycle

Customer-facing states: 1. Order placed 2. Awaiting kitchen acceptance
3. Accepted 4. Preparing 5. Ready for pickup 6. Delivery agent assigned
7. Picked up 8. Out for delivery 9. Delivered

Additional terminal states: Cancelled, Rejected, Delivery failed.

Rules: - Cancellation until kitchen acceptance. - No normal customer
cancellation after acceptance. - Kitchen rejection cancels order. -
Simulated refund for prepaid rejected orders; no refund for COD. - Show
estimated delivery time/range. - Live delivery agent map after pickup
with status updates. - If customer unavailable: agent calls, waits
configured period, follows retry/escalation. - Immediate orders only; no
scheduled orders. - No post-placement modification.

For prototypes, label sample data. Do not imply real GPS/payment
integrations unless connected.

## 11. Orders, profile, reviews and support

Orders: history/details, reorder, invoice download.

Reviews: food rating, delivery rating, written review. Regional-manager
moderation is backend capability; customer UI should show relevant
submission/status behaviour.

Profile: name, verified mobile, email, multiple addresses/default, food
preferences, spice preference, customer-declared allergies/ingredients
to avoid, favourite dishes.

Notifications: SMS and in-app order lifecycle notifications; optional
browser push permission. Do not fake real SMS delivery in a static
prototype; label simulated notifications.

Support: phone contact entry point, support ticket creation and ticket
history/status. No AI chatbot in this phase.

## 12. Out of scope

-   AI chatbot/assistant interface.
-   Scheduled orders.
-   Loyalty points.
-   Delivery tips.
-   Real payment processing.
-   Multi-restaurant marketplace.
-   Post-placement order modification.
-   Paid customization.
-   Other portals' dashboards.

## 13. Implementation discipline

1.  Read approved requirements and inspect existing project before
    editing.
2.  Ask for missing assets and unresolved decisions.
3.  Propose concise screen inventory and navigation map.
4.  Define design tokens and responsive behaviour.
5.  Confirm design direction before implementing all screens.
6.  Implement in small, reviewable stages.
7.  Keep business rules out of presentation-only code where backend
    enforcement is expected.
8.  Use clearly labelled mock data for prototype-only behaviour.
9.  Never claim payment, OTP, GPS, SMS, inventory or order workflows are
    real unless integrated.
10. Test desktop, laptop, tablet and mobile widths.
11. Test keyboard focus, labels, contrast, empty/loading/error states.
12. Keep code readable and avoid unnecessary dependencies.

If target is static HTML/CSS, do not introduce JavaScript frameworks or
backend services unless the user explicitly changes scope. Explain
interactions that HTML/CSS alone cannot genuinely perform and represent
them honestly as visual prototype states.

## 14. Expected deliverables

After inputs are supplied and implementation target is confirmed: 1.
Screen inventory and navigation map. 2. Design tokens and responsive
layout specification. 3. Customer Dashboard implementation/prototype
consistent with confirmed stack. 4. Clear list of mock versus genuinely
functional interactions. 5. Basic responsive/accessibility test
checklist. 6. Concise list of backend integrations still required for
production.

**Success definition:** A polished, responsive Customer Dashboard
reflecting approved DeliverIQ POC rules, using supplied brand colours,
usable on desktop and mobile, with no unapproved scope.
