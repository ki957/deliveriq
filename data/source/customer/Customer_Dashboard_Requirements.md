# DeliverIQ --- Customer Dashboard Requirements

**Scope:** Customer Dashboard POC\
**Status:** Business requirements approved; UI/UX discovery in progress\
**Business model:** One centralized cloud kitchen, initially in Chennai.
Not a multi-restaurant marketplace.

## 1. Product objective

Allow customers to discover the menu, check delivery availability,
customize dishes, order, pay using POC simulators, track delivery,
review orders and contact support.

## 2. Approved visual direction

-   Primary: `#A8C9CB`
-   Base/background: `#FFFFFF`
-   Accent: `#F45B0B`
-   Premium food photography + clean, minimal layouts.
-   Desktop-first, fully responsive on laptop, tablet and mobile.
-   Ubuntu-inspired left navigation concept; do not copy Ubuntu branding
    or exact UI.
-   Desktop sidebar expanded by default with icons and labels;
    collapsible.
-   Laptop: collapsible sidebar. Tablet: compact sidebar/drawer. Mobile:
    hamburger drawer + bottom navigation.
-   Maintain accessible contrast. Use readable dark text where needed.

## 3. Navigation

1.  Home
2.  Menu
3.  My Orders
4.  Support
5.  Profile
6.  Settings

Keep cart access easy to find, with item count. Customer AI/chatbot
design and implementation are deferred until all five dashboards are
completed.

## 4. Home dashboard

Show selected sections, not the entire catalogue: 1. Welcome message and
delivery location. 2. Active order card only when an active order
exists. 3. Menu search entry point. 4. Food categories. 5. Popular
dishes. 6. Featured dishes/promotions. 7. Reorder previous meals when
history exists.

Full catalogue belongs on the separate Menu page.

### Food cards

Responsive grid cards with image, dish name, short description, price,
vegetarian/non-vegetarian indicator and Add action. Selecting a card
opens dish details and customization.

**Open interaction decision:** Add action is not yet selected: - A. Add
directly; customization later. - B. Always open customization first. -
C. Add directly if no customization is required; otherwise open
customization.

## 5. Access and authentication

-   Visitors can browse after selecting a delivery location without
    login.
-   OTP authentication is mandatory before placing an order.
-   New mobile number becomes a customer account after successful OTP
    verification.
-   Existing access follows assigned roles.
-   Staff users receive customer access only if customer role is
    separately assigned.
-   Lost mobile number recovery is intended to use email verification;
    detailed recovery safeguards remain open.

## 6. Location and delivery

-   Support browser GPS and manual address entry.
-   Multiple saved addresses and one default address.
-   Validate full address and GPS coordinates against configured
    delivery zones.
-   Delivery eligibility requires BOTH: straight-line distance \<= 4 km
    AND road distance \<= 6 km from the kitchen.
-   Outside area: show unavailable message, nearby serviceable areas and
    allow location change.
-   Revalidate when address changes and before order placement.
-   Do not show a misleading orderable menu for an unserviceable
    location.

## 7. Menu and dish details

-   Separate Menu page contains full catalogue.
-   Categories, search and filters: price, vegetarian/non-vegetarian,
    spice level, popularity/bestseller.
-   Hide unavailable dishes.
-   Dish details show description, ingredients, base price and
    customization choices.
-   Kitchen configures customization per dish.
-   Examples: spice level, portion size, add-ons.
-   All customization included in base price; no surcharge.
-   Free-text special instructions; proposed 250-character limit,
    pending confirmation.
-   Kitchen controls customization availability.

## 8. Cart and pricing

-   One unified cart for the single kitchen.
-   Persist cart for authenticated customers.
-   No fixed per-dish quantity cap; stock availability is the limit.
-   Minimum order: ₹500 food subtotal before taxes and delivery.
-   Cart item price protection: 30 minutes after adding.
-   If item becomes unavailable before checkout, remove it, notify
    customer and require confirmation.
-   No order modification after placement. If cancellation remains
    eligible, customer can cancel and reorder.
-   Reorder previous meals subject to current menu and stock.
-   Delivery fee configurable; free delivery above configurable
    threshold.
-   Displayed dish prices include taxes; show tax details in bill.
-   Management-configured coupons.
-   No delivery tips.

### Price protection

Never silently charge a changed price. At checkout, validate the
30-minute protection. If expired and price changed, show revised price
and require explicit confirmation before payment. Preserve accepted
price in the order.

## 9. Checkout and payment

Checkout sequence: review cart → validate stock/prices → confirm
address/eligibility → enforce ₹500 minimum → apply coupon → calculate
taxes/delivery → select payment → place order → simulate payment or COD
→ send to kitchen.

Payment methods: UPI simulator, card simulator, COD. No real money is
processed.

Track payment and fulfilment separately: - Prepaid orders require
successful simulated payment before kitchen processing. - COD does not
require online payment. - Kitchen acceptance is required for fulfilment
confirmation.

## 10. Order lifecycle and tracking

Customer-visible statuses: 1. Order placed 2. Awaiting kitchen
acceptance 3. Accepted 4. Preparing 5. Ready for pickup 6. Delivery
agent assigned 7. Picked up 8. Out for delivery 9. Delivered

Additional terminal states: Cancelled, Rejected, Delivery failed.

Rules: - Cancellation allowed until kitchen acceptance. - No normal
customer cancellation after acceptance. - Kitchen rejection cancels
order. - Simulated refund for prepaid rejected orders; no refund for
COD. - Show estimated delivery time/range. - Show live delivery agent
location on map after pickup, alongside status. - If customer
unavailable: agent calls, waits a configured period, then follows
retry/escalation. - Immediate orders only; no scheduled orders. - No
post-placement modification.

## 11. Orders, reviews and profile

Orders: view history/details, reorder, download invoices.

Reviews: food rating, delivery rating, written review. Regional manager
can hide inappropriate reviews with reason and audit record.

Profile: name (required), verified mobile (required), email (required),
multiple saved addresses, default address, food preferences, spice
preference, customer-declared allergies/ingredients to avoid, favourite
dishes.

Allergy data is customer-provided preference information, not a
guarantee of allergen-free food.

## 12. Notifications and support

SMS and in-app notifications for order placed, accepted/rejected,
preparation started, ready for pickup, agent assigned, out for delivery,
delivered and cancellation/refund updates. Browser push is optional and
permission-based.

Support: phone support and support tickets. Customer AI is deferred
until all five dashboards are completed. Do not include chatbot UI or
flows now.

## 13. Explicitly excluded from POC

-   Scheduled orders
-   Loyalty points
-   Delivery tips
-   Real payment processing
-   Multi-restaurant marketplace
-   Post-placement order modification
-   Paid customization
-   Customer AI chatbot in this phase

## 14. Acceptance criteria

  -----------------------------------------------------------------------
  ID                                  Acceptance criterion
  ----------------------------------- -----------------------------------
  CD-01                               Visitor can browse after selecting
                                      location without login.

  CD-02                               Out-of-zone customers see
                                      serviceability information and can
                                      change location.

  CD-03                               Only OTP-authenticated customers
                                      with customer access can order.

  CD-04                               Categories, search and all four
                                      menu filters work.

  CD-05                               Unavailable dishes are hidden and
                                      cannot be ordered.

  CD-06                               Customization follows
                                      kitchen-configured options without
                                      extra charges.

  CD-07                               Cart persists for authenticated
                                      customers.

  CD-08                               ₹500 minimum food subtotal is
                                      enforced.

  CD-09                               Stock, price and delivery
                                      eligibility are validated before
                                      order placement.

  CD-10                               Customer confirms changes when an
                                      item becomes unavailable.

  CD-11                               UPI, card and COD simulators work.

  CD-12                               Kitchen acceptance controls
                                      fulfilment confirmation.

  CD-13                               Cancellation follows agreed policy.

  CD-14                               Customer sees order status and live
                                      delivery location after pickup.

  CD-15                               Customers can view history, reorder
                                      and download invoices.

  CD-16                               Reviews and support tickets can be
                                      submitted.

  CD-17                               Responsive layout works on desktop,
                                      laptop, tablet and mobile.

  CD-18                               AI chatbot is not included in this
                                      phase.
  -----------------------------------------------------------------------

## 15. Open product-owner inputs

1.  DeliverIQ logo (SVG preferred; transparent PNG acceptable;
    light/dark variants if available).
2.  Exact brand wording and tagline, if any.
3.  Food photos, image folder, or permission to use clearly-labelled
    placeholders.
4.  Font preference or permission to choose.
5.  Reference websites/screenshots, if any.
6.  Target: static HTML/CSS prototype or integration into an existing
    frontend. Do not assume a framework.
7.  Existing repository structure/assets, if integrating into an
    existing project.
8.  Food-card Add interaction (A/B/C above).
9.  Confirm 250-character special-instructions limit.
10. Any required viewport/browser targets.

**Approval boundary:** Business requirements are approved. UI/UX
discovery is in progress; not every visual detail or interaction has
been approved.
