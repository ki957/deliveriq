# DeliverIQ frontend

One React + TypeScript + Vite app for the four portals (DDR-03), styled with Tailwind and shadcn/ui-style components (ADR-UI-001). Layout follows `docs/CODE_STRUCTURE_DESIGN.md` §6.

| Path | Contents |
|---|---|
| `src/app/` | Router, landing page, portal shell, route config types |
| `src/shared/api/` | Typed client generated from `backend/openapi.json` (DDR-81); adds the CSRF header |
| `src/shared/auth/` | `useMe` (`GET /api/v1/me`) and `RequirePortal` route guard |
| `src/shared/theme/tokens.css` | Design tokens and per-portal palettes (DDR-21, DDR-100), contrast-tested |
| `src/shared/ui/` | Button, status badge, screen states, placeholder wordmark, "Not built yet" page |
| `src/portals/<portal>/` | Navigation config per portal (source-listed screens, owning task) |
| `src/features/auth/` | Shared login page (see its README) |

## Commands

```bash
npm ci
npm run dev           # http://127.0.0.1:5173, proxies /api to the API on :8000 (`make up` first)
npm run api:generate  # after backend schema changes (`make openapi`)
npm run typecheck && npm run lint && npm test && npm run api:check
```

From the repo root: `make frontend-check`; `make e2e` runs the Playwright suites (needs `make up` and `make fixtures`). Local sign-in uses the seed numbers `+91-00000-00001`…`06` with the test code `123456` (local/test only).

## Rules

- The UI mirrors `/api/v1/me`; the backend is the security boundary (PL-06).
- Every screen not built yet shows "Not built yet" with its plan task; nothing pretends to work.
- Status is always text + icon + colour; touch targets ≥ 44 px; visible 2 px focus ring.
