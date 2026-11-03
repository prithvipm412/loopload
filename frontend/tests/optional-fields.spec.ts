import { test, expect } from "@playwright/test";
test("optional reasons, AI highlights, judge metrics and temporary replan highlights", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByTestId("timeline-play").click();
  await page.getByTestId("timeline-scrubber").fill("0");
  await expect(page.getByTestId("plan-highlights")).toHaveCount(0);
  const baseBounds = await page.locator(".impact-panel").boundingBox();
  await page.getByTestId("ai-plan-button").click();
  await expect(
    page.getByTestId("plan-highlights").locator("article"),
  ).toHaveCount(3);
  await expect(page.getByTestId("counter-co2")).toHaveText("1.11 t");
  await expect(page.getByTestId("counter-co2").locator("..")).toContainText(
    "Total CO2 30 t",
  );
  await expect(page.getByTestId("counter-loads")).toHaveText("27");
  expect(await page.getByTestId("pooling-card").innerText()).toMatch(
    /\+₹[\d.,]+ L\s*\/ week/,
  );
  await expect(page.getByTestId("pooling-card")).toContainText(
    "Profit / active truck",
  );
  const endBounds = await page.locator(".impact-panel").boundingBox();
  expect(endBounds!.height).toBeCloseTo(baseBounds!.height, 0);
  await page.getByTestId("truck-row-T01").click();
  await expect(
    page.getByTestId("truck-drawer").locator(".leg-reason"),
  ).toHaveCount(4);
  await expect(
    page.getByTestId("truck-drawer").locator(".leg-reason").first(),
  ).toContainText("textiles pickup");
  await page.getByTestId("truck-drawer-close").click();
  await page.getByTestId("cancel-load-button").click();
  await expect(page.getByTestId("replan-toast")).toBeVisible();
  await expect(page.getByTestId("truck-row-T01")).toHaveClass(/changed/);
  await page.waitForTimeout(3200);
  await expect(page.locator(".truck-row.changed")).toHaveCount(0);
});
