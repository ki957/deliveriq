# Customers module (addresses and serviceability)

**Purpose and scope:** saved delivery addresses and the serviceability rule (CU-01–CU-04; #1 §6; DDR-55, DDR-110). Profile, preferences and favourites are later work.

| Item | Value |
| --- | --- |
| UI screens | Location picker and saved addresses (Task 6B) |
| API endpoints | Public `GET /api/v1/serviceability?lat=&lng=` (no location stored) · `GET/POST /api/v1/me/addresses` · `POST /api/v1/me/addresses/{id}/default` · `DELETE /api/v1/me/addresses/{id}` |
| Service functions | `check`, `check_point`, `owned_address`, `kitchen`, `list_addresses`, `add_address`, `make_default`, `delete_address` |
| Tables | `app.customer_addresses` (migration 0009), `app.kitchens`, `app.config_settings` |
| Permissions | Serviceability: public. Addresses: `customer.addresses.manage` (CUSTOMER, own only; others' are 404) |
| Tests | `tests/test_domain.py` (both rules, inclusive limits, road fails alone with fixed stub values); `orders/tests/test_checkout_integration.py` |

## Rules implemented

- **Both rules (CU-03):** straight-line ≤ `SERVICEABILITY_STRAIGHT_LINE_MAX` (4 km) by PostGIS **and** road ≤ `SERVICEABILITY_ROAD_DISTANCE_MAX` (6 km) through the road-distance adapter (`shared/geo.py`).
- **Estimated road distance (DDR-110 (6)):** the stub is straight-line × 1.4 and is always flagged `road_km_estimated`, so the UI shows "road distance: estimated". OSRM is added with the `osrm` profile in Task 9.
- **Kitchen location** is a labelled synthetic fixture (DDR-39); responses carry `kitchen_location_is_synthetic`.
- **Addresses:** the first is the default; one default per customer (unique index); deletion is soft so past orders keep their snapshot.
- **Out of area (CU-04, DDR-110 (7)):** the response says which rule failed; no invented list of nearby areas.
