import { test, expect } from "@playwright/test";
test("judge demo: plan, inspect compliance, cancel a load, forecast and Kannada driver", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "A better week for every truck." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Pause playback" }).click();
  await page.getByLabel("Week time", { exact: true }).fill("0");
  await expect(page.locator(".mode-badge")).toHaveText("Baseline");
  await page.getByRole("button", { name: "AI Plan", exact: true }).click();
  await expect(page.locator(".mode-badge")).toHaveText("AI plan");
  await expect(page.locator(".metric").first().locator("strong")).toHaveText(
    "3,450 km",
  );
  await page.getByRole("button", { name: "Open hero truck" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByRole("dialog").getByText("open body · 21 t"),
  ).toBeVisible();
  await expect(page.getByRole("dialog").locator(".leg-card")).toHaveCount(4);
  await expect(
    page.getByRole("dialog").getByText(/E-way bill expires/),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button", { name: "Simulate: cancel a load" }).click();
  await expect(page.getByRole("status")).toContainText("Re-planned in 1.8 s");
  await expect(page.locator(".truck-row.changed")).toHaveCount(1);
  await page.getByRole("link", { name: "Demand forecast" }).click();
  await expect(
    page.getByRole("heading", { name: "Hot lanes", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".lane-row")).toHaveCount(8);
  await page.locator(".lane-row").nth(1).click();
  await expect(page.locator(".forecast-chart h2")).toHaveText("DEL → JAI");
  await page.getByRole("link", { name: "Driver view", exact: true }).click();
  await page.getByRole("button", { name: "ಕನ್ನಡ", exact: true }).click();
  await expect(page.locator(".phone")).toHaveAttribute("lang", "kn");
  await expect(
    page.getByRole("heading", { name: "ಈ ವಾರ", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".phone")).toContainText("ಮುಂದಿನ ಪಿಕಪ್");
  await page.screenshot({ path: "test-results/driver-kn.png", fullPage: true });
  expect(errors).toEqual([]);
});
test("light projector layout and narrow screen stay within viewport", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".map-panel")).toBeVisible();
  await expect(page.locator("body")).toHaveCSS(
    "background-color",
    "rgba(0, 0, 0, 0)",
  );
  await expect(page.locator("html")).toHaveCSS(
    "background-color",
    "rgb(250, 247, 242)",
  );
  await page.waitForTimeout(2000);
  await page.screenshot({ path: "test-results/dashboard.png", fullPage: true });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.goto("/driver/T01");
  await expect(page.locator(".phone")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
