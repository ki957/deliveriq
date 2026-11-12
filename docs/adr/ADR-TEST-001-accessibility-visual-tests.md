# ADR-TEST-001 axe-core, device emulation, screenshot regression

**Status:** Accepted · **Date:** 2026-11-12

## Context
Portal documents require keyboard access, visible focus, contrast and mobile-first layouts. The target is WCAG 2.2 AA (DDR-23).

## Decision
Dev-only additions to Playwright: `@axe-core/playwright` for automated accessibility checks, Playwright device emulation for mobile Customer and Delivery tests, and `toHaveScreenshot` for visual regression with baselines committed. No external SaaS. Chromium only, headless, 2 workers locally; heavy suites in GitHub Actions.

## Consequences
- Automated checks do not prove full WCAG compliance; manual keyboard and screen-reader review is still required at Task 21.
- Screenshot baselines must be reviewed when UI changes.

## References
DDR-23, DDR-24, DDR-62.
