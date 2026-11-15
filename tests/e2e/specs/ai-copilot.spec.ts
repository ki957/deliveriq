import { expect, test } from "@playwright/test";
import { expectNoAxeViolations, SEED, signIn } from "./helpers";

test("CA sees the read-only Management Copilot with labelled status", async ({ page }) => {
  await signIn(page, "management", SEED.centralAdmin);
  await page.goto("/management/ai");
  await expect(page.getByRole("heading", { name: "Management AI Copilot" })).toBeVisible();
  await expect(page.getByText(/Knowledge: pending approval/)).toBeVisible();
  await expect(page.getByText(/Conversation memory: 6 turns/)).toBeVisible();
  await page.getByLabel("Question").fill("show operational status");
  await page.getByRole("button", { name: "Ask Copilot" }).click();
  await expect(page.getByText("Simulated data")).toBeVisible();
  await expect(page.getByText("Management Copilot response.")).toBeVisible();
  await expectNoAxeViolations(page);
});
