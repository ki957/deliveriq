# Auth feature

**Purpose and scope:** the shared, portal-themed login page (DDR-99) for mobile OTP sign-in, new-customer registration and trusted devices. Lost-mobile recovery is **not built** (DDR-41).

| Item          | Value                                                                                                                 |
| ------------- | --------------------------------------------------------------------------------------------------------------------- |
| UI screens    | `/:portal/login` (customer, kitchen, delivery, management)                                                            |
| API endpoints | `POST /api/v1/auth/otp/request`, `POST /api/v1/auth/otp/verify`, `POST /api/v1/auth/trusted-login` (generated client) |
| Permissions   | Public. After sign-in, the portal route guard checks `GET /api/v1/me`                                                 |
| States        | Sending, code entry, name needed (new customer), error messages for 400/422/429/503, signed in (redirect)             |
| Tests         | `login-page.test.tsx` (flow, errors, safe redirect); Playwright login per portal (`tests/e2e`)                        |

## Behaviour

- One message for every outcome of a code request, so the page never reveals whether a number is registered.
- New customer: the backend answers 422 to the first code submission; the page asks for a name and resubmits the same code.
- "Trust this device for 7 days" is unticked by default. On load the page tries a trusted-device sign-in once; failure is silent.
- `?next=` is accepted only for paths inside the same portal (no open redirect).
- Client-side checks are only for usability; the backend validates everything.
