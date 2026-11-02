import { test, expect } from "@playwright/test";
test("automation IDs identify every requested control and counter", async ({
  page,
}) => {
  await page.goto("/");
  for (const id of [
    "ai-plan-button",
    "mode-toggle-baseline",
    "mode-toggle-ai",
    "solve-time-badge",
    "counter-empty-km",
    "counter-diesel",
    "counter-co2",
    "counter-revenue",
    "counter-loaded-pct",
    "counter-loads",
    "map-canvas",
    "timeline-play",
    "timeline-scrubber",
    "cancel-load-button",
    "pooling-card",
    "owner-filter",
    "nav-dashboard",
    "nav-forecast",
    "nav-driver",
  ]) {
    await expect(page.getByTestId(id)).toHaveCount(1);
  }
  for (let i = 1; i <= 20; i++)
    await expect(
      page.getByTestId(`truck-row-T${String(i).padStart(2, "0")}`),
    ).toHaveCount(1);
  await page.getByTestId("timeline-play").click();
  await page.getByTestId("timeline-scrubber").fill("0");
  await page.getByTestId("mode-toggle-ai").click();
  await page.getByTestId("truck-row-T01").click();
  await expect(page.getByTestId("truck-drawer")).toBeVisible();
  await expect(page.getByTestId("compliance-badge")).toHaveCount(4);
  await page.getByTestId("truck-drawer-close").click();
  await page.getByTestId("cancel-load-button").click();
  await expect(page.getByTestId("replan-toast")).toContainText("Re-planned");
  await page.getByTestId("nav-forecast").click();
  await expect(page.getByTestId("hot-lanes-list")).toBeVisible();
  await expect(page.getByTestId("forecast-chart")).toBeVisible();
  await page.getByTestId("nav-driver").click();
  await expect(page.getByTestId("driver-phone")).toBeVisible();
  for (const lang of ["en", "hi", "kn", "ta"]) {
    await page.getByTestId(`lang-${lang}`).click();
    await expect(page.getByTestId("driver-phone")).toHaveAttribute(
      "lang",
      lang,
    );
  }
});
