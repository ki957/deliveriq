import { expect, test } from "@playwright/test";

import { expectNoAxeViolations, SEED, signIn } from "./helpers";

test("CA reviews an exact Operational Actions proposal before confirmation", async ({ page }) => {
  await signIn(page, "management", SEED.centralAdmin);
  await page.goto("/management/actions");
  await expect(page.getByRole("heading", { name: "Operational Actions" })).toBeVisible();
  await expect(page.getByText(/simulated model in this local demo/)).toBeVisible();

  const kitchens = await page.request.get("/api/v1/management/kitchens");
  expect(kitchens.ok()).toBeTruthy();
  const kitchen = ((await kitchens.json()) as { id: string }[])[0];
  expect(kitchen).toBeDefined();
  const settingsResponse = await page.request.get(`/api/v1/kitchen/settings?kitchen_id=${kitchen.id}`);
  expect(settingsResponse.ok()).toBeTruthy();
  const settings = (await settingsResponse.json()) as {
    mode: string;
    normal_capacity: { value: number };
    busy_capacity: { value: number };
  };
  const mode = settings.mode === "BUSY" ? "NORMAL" : "BUSY";
  await page.getByLabel("Action request").fill(
    `Set kitchen ${kitchen.id} to ${mode} with normal capacity ${settings.normal_capacity.value} and busy capacity ${settings.busy_capacity.value}. Reason: E2E preview`,
  );
  await page.getByRole("button", { name: "Preview change" }).click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("Review exact change")).toBeVisible();
  await expect(dialog.getByText("E2E preview")).toBeVisible();
  await expect(dialog.getByText(mode, { exact: true })).toBeVisible();
  await expectNoAxeViolations(page);
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(dialog).not.toBeVisible();
  const unchanged = await page.request.get(`/api/v1/kitchen/settings?kitchen_id=${kitchen.id}`);
  expect(((await unchanged.json()) as { mode: string }).mode).toBe(settings.mode);
});

test("RM cannot open or call Operational Actions", async ({ page }) => {
  await signIn(page, "management", SEED.regionalManager);
  await page.goto("/management/actions");
  await expect(page.getByRole("heading", { name: "Operational Actions" })).not.toBeVisible();
  const response = await page.request.post("/api/v1/management/ai/actions/proposals", {
    headers: { "X-DeliverIQ-CSRF": "1" },
    data: { request: "Create a promotion" },
  });
  expect(response.status()).toBe(403);
});
