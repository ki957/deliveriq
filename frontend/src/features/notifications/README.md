# Notifications feature (in-app notifications)

**Purpose and scope:** the Notifications page and header bell for customers, agents and Kitchen Managers (CU-25, DL-16, KI-23; DDR-115 (10)). Backend: `notifications` module; live updates: `shared/realtime` (`me` topic).

| Item          | Value                                                                                                                               |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| UI screens    | `/customer/notifications`, `/kitchen/notifications` (KM), `/delivery/notifications`; `NotificationsBell` in the portal header       |
| API endpoints | `GET /api/v1/me/notifications` · `POST /api/v1/me/notifications/read` (generated client)                                            |
| Permissions   | Signed in; the kitchen page needs `kitchen.inventory.view` (KM). The bell shows only where the page is in the portal's navigation   |
| States        | Loading, empty ("No notifications in the last 30 days"), error, denied; "Mark all as read"; each item marks itself read when opened |
| Tests         | `notifications.test.tsx`; E2E `tests/e2e/specs/realtime.spec.ts`                                                                    |

## Behaviour

- Each kind is worded here from ids (order number, ingredient name) and links to the order, the delivery home or the kitchen inventory.
- The page states the channels: "In-app only, kept for 30 days. SMS: Not configured (DDR-40)." Test data is badged.
- New notifications arrive live; while live updates are down the inbox is checked every 30 s.
- On phones the header shows the Sign out icon only (its name stays for screen readers), so the header fits 360 px with the bell.
