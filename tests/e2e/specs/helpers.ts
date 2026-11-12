import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

// The six #15 §4 seed users, loaded by `make fixtures` (local/test only).
export const SEED = {
  customer: "+91-00000-00001",
  delivery: "+91-00000-00002",
  kitchenStaff: "+91-00000-00003",
  kitchenManager: "+91-00000-00004",
  regionalManager: "+91-00000-00005",
  centralAdmin: "+91-00000-00006",
} as const;

export const MOCK_OTP = "123456"; // MOCK_OTP fixed test code, local/test only (#15 §4.2)

/** Sign in through the real login page with the mock OTP. */
export async function signIn(page: Page, portal: string, mobile: string): Promise<void> {
  await page.goto(`/${portal}/login`);
  // Parallel workers share the six seed numbers, so one worker can start the 30 s resend cooldown
  // just before another asks for a code. The limiter is correct; the test resets it and retries.
  for (let attempt = 1; ; attempt++) {
    // Test-only endpoint (never mounted in production).
    const reset = await page.request.post("/api/v1/_test/reset-otp-limits", {
      headers: { "X-DeliverIQ-CSRF": "1" },
    });
    expect(reset.status()).toBe(204);
    await page.getByLabel("Mobile number").fill(mobile);
    await page.getByRole("button", { name: "Send code" }).click();
    const code = page.getByLabel("6-digit code");
    const limited = page.getByRole("alert").filter({ hasText: "Too many attempts" });
    await expect(code.or(limited)).toBeVisible();
    if (await code.isVisible()) break;
    expect(attempt, "OTP request kept being rate-limited").toBeLessThan(5);
    await page.waitForTimeout(250 * attempt);
  }
  await page.getByLabel("6-digit code").fill(MOCK_OTP);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(new RegExp(`/${portal}$`));
}

/** WCAG 2.2 A/AA automated checks. Automated checks do not prove full compliance (DDR-23). */
export async function expectNoAxeViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const summary = results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`);
  expect(summary).toEqual([]);
}

export async function expectNoHorizontalScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}
