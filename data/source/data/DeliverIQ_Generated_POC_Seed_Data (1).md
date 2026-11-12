# DeliverIQ — Generated POC Seed Data

**Version:** 1.0  
**Date:** 11 November 2026  
**Environment:** Local development / automated testing only  
**Purpose:** Ready-to-use minimal synthetic records for DeliverIQ.

> This file contains generated sample data, not real customer or business data. Import only into a local/test database. Do not use the fake phone numbers with an SMS provider.

---

## 1. What this file generates

| Dataset | Generated here? | Reason |
|---|---:|---|
| Region | Yes | One Chennai POC region |
| Kitchen | Yes | One test kitchen |
| User identities | Yes | One account per role |
| Role assignments | Yes | Access testing |
| Customer address | Yes | Checkout testing |
| Delivery configuration | Yes | Serviceability testing |
| Kitchen settings | Yes | Queue/capacity testing |
| Payment simulator cases | Yes | Checkout testing |
| Delivery agent profile | Yes | Dispatch testing |
| Test order scenarios | Yes | End-to-end testing |
| Support categories/sample ticket | Yes | Minimal portal testing |
| Promotion | Yes | One optional test promotion |
| Menu catalogue | No | Import the existing 104 dishes |
| Ingredient catalogue/mappings | No | Import the existing ingredient data |
| Actual recipe quantities | No | Must use approved recipe quantities |
| Opening stock quantities | No | Must be confirmed against actual kitchen stock |
| Actual menu prices/tax | No | Must be approved by product owner |
| RAG policy/SOP content | Starter drafts only | Must be reviewed and approved before publication |

---

# 2. Region seed

| region_id | name | city | state | country | timezone | status |
|---|---|---|---|---|---|---|
| REG-CHN-001 | Chennai | Chennai | Tamil Nadu | India | Asia/Kolkata | ACTIVE |

# 3. Kitchen seed

| kitchen_id | region_id | name | address | latitude | longitude | status |
|---|---|---|---|---:|---:|---|
| KIT-CHN-001 | REG-CHN-001 | DeliverIQ Chennai POC Kitchen | Synthetic Test Address, Chennai, Tamil Nadu, India | 13.0827 | 80.2707 | ACTIVE |

The address and coordinates are synthetic test fixtures. Replace them with the approved POC kitchen address and coordinates before real map/serviceability testing.

# 4. User seed

The phone values below are intentionally invalid placeholders. They are not deliverable telephone numbers.

| user_id | display_name | mobile | status |
|---|---|---|---|
| USR-CUS-001 | Demo Customer | +91-00000-00001 | ACTIVE |
| USR-DEL-001 | Demo Delivery Agent | +91-00000-00002 | ACTIVE |
| USR-KST-001 | Demo Kitchen Staff | +91-00000-00003 | ACTIVE |
| USR-KMG-001 | Demo Kitchen Manager | +91-00000-00004 | ACTIVE |
| USR-RM-001 | Demo Regional Manager | +91-00000-00005 | ACTIVE |
| USR-CA-001 | Demo Central Administrator | +91-00000-00006 | ACTIVE |

## 4.1 Role assignment seed

| assignment_id | user_id | role | region_id | kitchen_id | scope |
|---|---|---|---|---|---|
| RAS-001 | USR-CUS-001 | CUSTOMER | — | — | OWN_ACCOUNT |
| RAS-002 | USR-DEL-001 | DELIVERY_AGENT | REG-CHN-001 | KIT-CHN-001 | ASSIGNED_DELIVERIES |
| RAS-003 | USR-KST-001 | KITCHEN_STAFF | REG-CHN-001 | KIT-CHN-001 | KIT-CHN-001 |
| RAS-004 | USR-KMG-001 | KITCHEN_MANAGER | REG-CHN-001 | KIT-CHN-001 | KIT-CHN-001 |
| RAS-005 | USR-RM-001 | REGIONAL_MANAGER | REG-CHN-001 | — | REG-CHN-001 |
| RAS-006 | USR-CA-001 | CENTRAL_ADMIN | — | — | GLOBAL |

**Security note:** `GLOBAL` is a server-managed authorization scope, not a value accepted from a client request. Regional Managers cannot assign the CENTRAL_ADMIN role.

## 4.2 Development OTP adapter

For local automated tests only:

| Setting | Value |
|---|---|
| Adapter | MOCK_OTP |
| Fixed test OTP | 123456 |
| Enabled outside local/test | false |
| Send real SMS | false |
| Log OTP | false |

The mock adapter must be selected by environment configuration and must fail closed if enabled in staging/production. Do not store OTPs in the user table.

# 5. Customer address seed

| address_id | customer_id | label | address | latitude | longitude | is_default |
|---|---|---|---|---:|---:|---|
| ADR-CUS-001 | USR-CUS-001 | Home | Synthetic Test Address, Chennai, Tamil Nadu, India | 13.0835 | 80.2710 | true |

This address is for application-flow testing only.

# 6. Delivery/serviceability configuration

| config_key | value | unit | scope |
|---|---:|---|---|
| SERVICEABILITY_STRAIGHT_LINE_MAX | 4 | km | KIT-CHN-001 |
| SERVICEABILITY_ROAD_DISTANCE_MAX | 6 | km | KIT-CHN-001 |
| MINIMUM_FOOD_SUBTOTAL | 500 | INR | KIT-CHN-001 |
| CUSTOMER_UNAVAILABLE_WAIT | 5 | minutes | REG-CHN-001 |
| AGENT_ASSIGNMENT_RESPONSE_TIMEOUT | 60 | seconds | REG-CHN-001 |
| GPS_UPDATE_INTERVAL_MIN | 3 | seconds | REG-CHN-001 |
| GPS_UPDATE_INTERVAL_MAX | 5 | seconds | REG-CHN-001 |

These values reflect the current POC rules. Store them in backend configuration/database records; do not hardcode them in the frontend.

**Not generated:** delivery fee. It must be confirmed by the product owner before displaying a final checkout quote.

# 7. Kitchen settings seed

| setting_key | value | unit |
|---|---:|---|
| KITCHEN_MODE | NORMAL | enum |
| MAX_CONCURRENT_ORDERS | 10 | orders |
| ORDER_QUEUE_POLICY | FIFO_ACCEPTED_AT | enum |
| INVENTORY_RESERVE_EVENT | KITCHEN_ACCEPTANCE | enum |
| INVENTORY_DEDUCT_EVENT | HANDOVER | enum |
| RECIPE_VERSION_POLICY | PIN_ON_ACCEPTANCE | enum |

`MAX_CONCURRENT_ORDERS=10` is an initial test value. Confirm actual kitchen capacity before operational use.

The order acceptance timeout remains configurable and is not fixed here because the approved product rule only requires a configurable timeout.

# 8. Delivery agent profile seed

| agent_profile_id | user_id | status | max_active_deliveries | gps_mode |
|---|---|---|---:|---|
| AGP-001 | USR-DEL-001 | OFFLINE | 1 | SIMULATED |

# 9. Payment simulator seed

| method_code | display_name | enabled | simulator_scenarios |
|---|---|---:|---|
| SIM_UPI | UPI (Simulation) | true | SUCCESS, FAILED, TIMEOUT |
| SIM_CARD | Card (Simulation) | true | SUCCESS, FAILED, TIMEOUT |
| COD | Cash on Delivery | true | COLLECTION_PENDING, COLLECTED, MISMATCH |

No real payment gateway, bank account, UPI ID, card number or payment credential is included.

# 10. Test order scenario seed

These are scenario definitions, not complete persisted orders. The application must create real order IDs and calculate totals from the imported menu catalogue.

| scenario_id | customer_id | menu_reference | payment_method | expected_path |
|---|---|---|---|---|
| SCN-ORD-001 | USR-CUS-001 | EXISTING_MENU_ITEM_A | COD | ACCEPT → PREPARE → READY → PICKUP → DELIVER |
| SCN-ORD-002 | USR-CUS-001 | EXISTING_MENU_ITEM_B | SIM_UPI | PAYMENT_SUCCESS → ACCEPT → DELIVER |
| SCN-ORD-003 | USR-CUS-001 | EXISTING_MENU_ITEM_A | SIM_CARD | PAYMENT_FAILURE → ORDER_NOT_SENT_TO_KITCHEN |
| SCN-ORD-004 | USR-CUS-001 | EXISTING_MENU_ITEM_B | COD | KITCHEN_REJECT → ORDER_CANCELLED |

Replace `EXISTING_MENU_ITEM_A/B` with actual dish IDs after importing the existing catalogue. Select quantities/prices so valid successful checkout scenarios meet the ₹500 minimum food subtotal. Do not bypass checkout validation.

# 11. Promotion seed

One optional promotion for testing the promotion display and validation flow. It is disabled until a product owner confirms the commercial rules.

| promotion_id | code | type | value | minimum_subtotal | usage_limit | status |
|---|---|---|---:|---:|---:|---|
| PROMO-TEST-001 | POCWELCOME | FIXED_AMOUNT | 50 | 500 | 10 | DRAFT |

Validity dates, region applicability, per-customer limit and stacking rules must be set before activation. Do not assume this promotion is approved for customers.

# 12. Support seed

## 12.1 Support categories

| category_code | label | active |
|---|---|---:|
| ORDER_STATUS | Order status | true |
| PAYMENT_ISSUE | Payment issue | true |
| DELIVERY_ISSUE | Delivery issue | true |
| MISSING_ITEM | Missing item | true |
| FOOD_QUALITY | Food quality | true |
| OTHER | Other | true |

## 12.2 Sample support ticket

| ticket_id | customer_id | category | subject | status |
|---|---|---|---|---|
| TKT-TEST-001 | USR-CUS-001 | ORDER_STATUS | Demo support request | OPEN |

# 13. Menu and ingredient import references

Do not create duplicate menu or ingredient records. Import the existing catalogue and ingredient mapping, preserving their original stable identifiers where possible.

After import, verify that each menu item has:
- A category.
- An approved selling price.
- An active/inactive status.
- A kitchen availability mapping.
- A preparation-time value if shown to customers.

Verify that each ingredient has:
- A stable ingredient ID.
- A canonical base unit.
- A purchase unit and conversion factor if procurement units differ.
- A reorder threshold if low-stock alerts are enabled.

For every orderable dish, ensure an approved recipe version exists with:
- Yield/portion standard.
- Ingredient quantities and units.
- Preparation steps.
- Approval status and approver.
- Allergen data only when verified.

**No recipe quantities, prices, taxes, delivery fees or stock balances have been fabricated in this seed pack.**

# 14. RAG starter document records

These are document registry records only. They do not publish invented policy content into production knowledge collections.

| document_id | portal | category | title | status |
|---|---|---|---|---|
| CUS-KB-001 | CUSTOMER | FAQ | How to place an order | DRAFT |
| CUS-KB-002 | CUSTOMER | POLICY | Delivery and serviceability policy | DRAFT |
| CUS-KB-003 | CUSTOMER | POLICY | Cancellation and refund policy | DRAFT |
| KIT-KB-001 | KITCHEN | SOP | Kitchen order acceptance SOP | DRAFT |
| KIT-KB-002 | KITCHEN | SOP | Preparation and handover SOP | DRAFT |
| KIT-KB-003 | KITCHEN | FOOD_HANDLING | Approved food handling guidance | DRAFT |
| MGT-KB-001 | MANAGEMENT | SOP | Delivery exception escalation | DRAFT |
| MGT-KB-002 | MANAGEMENT | POLICY | Refund approval policy | DRAFT |
| MGT-KB-003 | MANAGEMENT | ANALYTICS | KPI definitions | DRAFT |

Before ingestion, add content, source reference, owner, approver, version, effective date, scope, content hash and approval status. Only approved documents may be published to RAG.

# 15. Dashboard design tokens

Use the already supplied colour schemas:

| Portal | Primary/other approved colours |
|---|---|
| Customer | `#FFF21A`, `#171717`, `#A66BFF` |
| Kitchen | `#D5360C`, `#E6D58D`, `#101010` |
| Unified Management | `#021861`, `#255DCE`, `#DE1110` |

The alternate palette `#A8C9CB`, `#FFFFFF`, `#F45B0B` is not assigned here because its final portal ownership is not confirmed. No new colour palette is generated.

# 16. Seed import order

1. Region.
2. Kitchen.
3. Role definitions (use the approved RBAC catalogue).
4. Users.
5. Role assignments.
6. Customer address.
7. Delivery configuration.
8. Kitchen settings.
9. Existing ingredient catalogue and mappings.
10. Existing menu catalogue.
11. Approved recipes and recipe versions.
12. Approved opening inventory balances.
13. Payment simulator configuration.
14. Delivery agent profile.
15. Promotion and support fixtures.
16. RAG document registry records.

Use idempotent upserts with stable seed IDs. Seed scripts must be safe to run repeatedly and must never overwrite operational data outside the local/test environment.

# 17. Values requiring product-owner confirmation

| Item | Status |
|---|---|
| Actual kitchen address and coordinates | Replace synthetic fixture |
| Actual dish prices | Not supplied in this generated pack |
| Recipe quantities and preparation steps | Use approved recipe source |
| Opening inventory quantities/lots/expiry | Enter from approved test stock |
| Delivery fee | Awaiting confirmation |
| Tax classification/rate | Confirm with accounting/product owner |
| Kitchen capacity | `10` is test default; confirm |
| Promotion terms | Draft; do not activate |
| Customer/kitchen/management knowledge text | Must be reviewed and approved |
| Delivery Agent colour schema | Reuse approved source if one exists |

---

# 18. Ready-to-use generation boundary

This seed pack generates the minimum synthetic identity, region, kitchen, configuration and workflow-fixture records needed to start a local POC.

It intentionally does not fabricate:
- The existing 104 menu items.
- Existing ingredient names or mappings.
- Recipe quantities.
- Menu prices or tax rates.
- Opening stock balances.
- Real customer or employee information.
- Approved legal, food-safety or business policy content.

**Next import action:** load these fixtures into the development database, then import the existing menu/ingredient source files and connect their real IDs to recipe and inventory records.
