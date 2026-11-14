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
  // Loaded by `make e2e-setup` only (fixtures load-e2e-agent).
  e2eAgent: "+91-00000-00007",
  // Loaded by `make e2e-setup` only (fixtures load-e2e-region): RM of TEST region REG-ETE-001.
  otherRegionalManager: "+91-00000-00008",
} as const;

export const MOCK_OTP = "123456"; // MOCK_OTP fixed test code, local/test only (#15 §4.2)

/** Sign in through the real login page with the mock OTP. */
export async function signIn(page: Page, portal: string, mobile: string): Promise<void> {
  // Parallel projects sign in the same seed numbers: a newer code request replaces an older one, so
  // the older verify is refused ("invalid or has expired"). That is the correct rule; retry with a new code.
  for (let attempt = 1; ; attempt++) {
    await page.goto(`/${portal}/login`);
    await requestCode(page, mobile);
    await page.getByLabel("6-digit code").fill(MOCK_OTP);
    await page.getByRole("button", { name: "Sign in" }).click();
    const home = new RegExp(`/${portal}$`);
    const refused = page.getByRole("alert").filter({ hasText: "invalid or has expired" });
    await expect.poll(async () => home.test(page.url()) || (await refused.isVisible())).toBe(true);
    if (home.test(page.url())) return;
    expect(attempt, "sign-in kept being superseded by a parallel sign-in").toBeLessThan(5);
    await page.waitForTimeout(200 * attempt);
  }
}

/**
 * A new TEST customer number (`+9100000` + 5 digits, accepted in local/test only). Each ordering test
 * gets its own customer, so parallel projects never share a persisted cart.
 */
export function newTestMobile(): string {
  return `+91-00000-${10000 + Math.floor(Math.random() * 90000)}`;
}

/**
 * On an open customer login page: register a new customer with the mock OTP (DDR-97). Random TEST
 * numbers accumulate in local/test databases; if the number already has an account, that sign-in is
 * ended and a fresh number is tried, so every caller gets a brand-new customer.
 */
export async function registerCustomer(page: Page, mobile: string, name: string): Promise<void> {
  const loginUrl = page.url();
  let number = mobile;
  for (let attempt = 1; ; attempt++) {
    await requestCode(page, number);
    await page.getByLabel("6-digit code").fill(MOCK_OTP);
    await page.getByRole("button", { name: "Sign in" }).click();
    const askName = page.getByLabel("Your name");
    await expect.poll(async () => (await askName.isVisible()) || !page.url().includes("/login")).toBe(true);
    if (await askName.isVisible()) break;
    expect(attempt, "kept drawing TEST numbers that already have accounts").toBeLessThan(5);
    const out = await page.request.post("/api/v1/auth/logout", { headers: { "X-DeliverIQ-CSRF": "1" } });
    expect(out.status()).toBe(204);
    await page.goto(loginUrl);
    number = newTestMobile();
  }
  await page.getByLabel("Your name").fill(name);
  await page.getByRole("button", { name: "Sign in" }).click();
}

async function requestCode(page: Page, mobile: string): Promise<void> {
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
