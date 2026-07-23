import { expect, test } from "@playwright/test";

const ANALYST = { email: "analyst@nexguard.local", password: "NexGuardAnalyst!23" };

test.describe("SOC console", () => {
  test("analyst signs in and reaches the live dashboard", async ({ page }) => {
    await page.goto("/login");

    await page.getByLabel("Email").fill(ANALYST.email);
    await page.getByLabel("Password").fill(ANALYST.password);
    await page.getByRole("button", { name: /sign in/i }).click();

    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByRole("heading", { name: "Executive Dashboard" })).toBeVisible();

    // The seeded HDFS alerts render (block ids look like blk_...).
    await expect(page.getByText(/blk_/).first()).toBeVisible();
  });

  test("navigates to the Alert Explorer", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(ANALYST.email);
    await page.getByLabel("Password").fill(ANALYST.password);
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    await page.getByRole("link", { name: "Alert Explorer" }).click();
    await expect(page).toHaveURL(/\/alerts/);
    await expect(page.getByRole("heading", { name: "Alert Explorer" })).toBeVisible();
  });
});
