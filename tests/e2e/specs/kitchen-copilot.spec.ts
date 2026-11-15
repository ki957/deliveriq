import { expect, test } from "@playwright/test";
import { SEED, signIn } from "./helpers";

test("Kitchen Staff can use the read-only Kitchen Copilot", async ({
  page,
}) => {
  await signIn(page, "kitchen", SEED.kitchenStaff);
  await page.goto("/kitchen/copilot");
  await expect(
    page.getByRole("heading", { name: "Kitchen Copilot" }),
  ).toBeVisible();
  await expect(
    page.getByText(/cannot change orders, recipes, or stock/),
  ).toBeVisible();
  await page
    .getByLabel("Question")
    .fill("What should I know about today's kitchen guidance?");
  await page.getByRole("button", { name: "Ask Copilot" }).click();
  await expect(page.getByText(/reduced retrieval/)).toBeVisible();
  await expect(page.getByText(/Simulated response/)).toBeVisible();
});
