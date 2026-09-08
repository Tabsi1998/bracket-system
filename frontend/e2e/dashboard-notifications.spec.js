const { test, expect } = require("@playwright/test");

test("dashboard notifications stay compact and expand into a bounded list", async ({ page }) => {
  await page.route("**/api/**", (route) => route.fulfill({ contentType: "application/json", body: "{}" }));
  await page.route("**/api/sponsors**", (route) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/api/auth/me", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ id: "user-1", username: "Testplayer", role: "player" }) }));
  await page.route("**/api/notifications/me", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(Array.from({ length: 30 }, (_, index) => ({ id: `notification-${index}`, title: `Testhinweis ${index + 1}`, created_at: "2026-09-08T10:00:00Z" }))) }));
  await page.goto("/dashboard");
  const consent = page.getByRole("button", { name: /alle akzeptieren/i });
  if (await consent.count()) await consent.click();
  const panel = page.getByTestId("dashboard-notifications");
  await expect(panel.getByText("Testhinweis 3", { exact: true })).toBeVisible();
  await expect(panel.getByText("Testhinweis 4", { exact: true })).toHaveCount(0);
  await panel.getByRole("button", { name: "Alle 30 anzeigen" }).click();
  await expect(panel.getByRole("button")).toHaveAttribute("aria-expanded", "true");
  expect(await page.locator("#dashboard-notification-list").evaluate((node) => node.scrollHeight > node.clientHeight && node.clientHeight <= 384)).toBe(true);
  await panel.getByRole("button", { name: "Weniger anzeigen" }).click();
  await expect(panel.getByText("Testhinweis 4", { exact: true })).toHaveCount(0);
});
