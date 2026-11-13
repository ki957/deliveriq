# Pricing module (price protection, coupons, bill)

**Purpose and scope:** the checkout amounts: 30-minute price protection, coupon rules, the ₹500 minimum and the ₹30 delivery fee (CU-12–CU-16; DDR-38, DDR-53, DDR-110). Called by the orders service inside its transaction; no routes of its own.

| Item | Value |
| --- | --- |
| UI screens | Cart and checkout bill (Task 6B); coupon management (Management, Task 10) |
| API endpoints | None directly; used by `GET /api/v1/cart` and `POST /api/v1/orders` |
| Service functions | `protection_minutes`, `minimum_paise`, `delivery_fee_paise`, `coupon`, `redeem`, `now` |
| Tables | `app.coupons` (migration 0009), `app.config_settings` (`PRICE_PROTECTION_MINUTES`, `MINIMUM_FOOD_SUBTOTAL`, `DELIVERY_FEE_FLAT`) |
| Tests | `tests/test_domain.py`; `orders/tests/test_checkout_integration.py` (₹499/₹500, coupon below ₹500, usage limit under concurrency, price protection) |

## Rules implemented

- **Price protection (DDR-110 (5)):** a cart line's price is charged for 30 minutes after it was added; afterwards the current published price applies, and a difference from the price the customer stated returns 409 `price_changed` until the customer confirms (`accept-price`). The order stores the price charged.
- **Minimum (DDR-53):** checked on the food subtotal before any coupon; ₹499 refused, ₹500 accepted. A coupon may then take the payable total below ₹500, never below zero.
- **Delivery fee (DDR-38):** ₹30 at every subtotal, no waiver path.
- **Coupons (DDR-110 (3)):** active, inside its validity window, under its usage limit (atomic, race-safe), food subtotal at or above its own minimum, one per order. TEST coupons only on TEST orders and never in production. No production coupon exists; `POCWELCOME` (#15 §11) is not loaded until the owner approves its terms.
- **Tax (DDR-110 (4)):** the bill states "Prices include applicable taxes."; no breakdown until DDR-32.
