import { expect, test } from "@playwright/test";

import { expectNoAxeViolations, SEED, signIn } from "./helpers";

test("CA reviews tested Builder Agent diff before opening a mocked pull request", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page, "management", SEED.centralAdmin);
  await page.goto("/management/builder-agent");
  await expect(page.getByRole("heading", { name: "Builder Agent" })).toBeVisible();
  await page.getByLabel("Change request").fill("Add a short local mock preview note.");
  await page.getByRole("button", { name: "Prepare diff" }).click();

  const review = page.getByRole("region", { name: "Review Builder Agent diff" });
  await expect(review).toBeVisible();
  await expect(review.getByText(/Unit tests: passed \(mock sandbox runner; code not executed\)/)).toBeVisible({
    timeout: 30_000,
  });
  await expect(review.getByText(/diff --git/)).toBeVisible();
  await expectNoAxeViolations(page);
  await review.getByRole("button", { name: "Confirm and open pull request" }).click();
  await expect(review.getByRole("link", { name: /pull\/mock-/ })).toBeVisible();
  await expect(review.getByText(/builder-agent\//)).toBeVisible();
});

test("RM cannot open the Builder Agent page or call its backend", async ({ page }) => {
  await signIn(page, "management", SEED.regionalManager);
  await page.goto("/management/builder-agent");
  await expect(page.getByRole("heading", { name: "Builder Agent" })).not.toBeVisible();
  const response = await page.request.post("/api/v1/management/ai/builder/tasks", {
    headers: { "X-DeliverIQ-CSRF": "1" },
    data: { request: "Make a small example change." },
  });
  expect(response.status()).toBe(403);
});
