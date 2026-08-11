import { test, expect } from "@playwright/test";

test("local app serves a same-origin shell", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/Novel Translator/);
});
