import { test, expect } from "@playwright/test";
test("map fills its card, refits on resize, and keeps the India camera locked", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByTestId("timeline-play").click();
  const map = page.getByTestId("map-canvas");
  await expect(map).toHaveAttribute("data-view-longitude", "80.0000");
  await expect(map).toHaveAttribute("data-view-latitude", "22.0000");
  await expect(map).toHaveAttribute("data-max-zoom", "7");
  await expect(map).toHaveAttribute("data-max-bounds", "60,2,100,38");
  const fills = () =>
    map.evaluate((el) => {
      const root = el.getBoundingClientRect();
      const canvas = el
        .querySelector(".maplibregl-canvas")!
        .getBoundingClientRect();
      return (
        Math.abs(root.width - canvas.width) < 1 &&
        Math.abs(root.height - canvas.height) < 1
      );
    });
  await expect.poll(fills).toBeTruthy();
  await map.hover();
  await page.mouse.wheel(0, 3000);
  await page.waitForTimeout(600);
  expect(
    Number(await map.getAttribute("data-view-zoom")),
  ).toBeGreaterThanOrEqual(Number(await map.getAttribute("data-min-zoom")));
  await page.setViewportSize({ width: 1280, height: 720 });
  await expect.poll(fills).toBeTruthy();
  await expect(map).toHaveAttribute("data-view-longitude", "80.0000");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(fills).toBeTruthy();
  await expect(map).toHaveAttribute("data-view-latitude", "22.0000");
});
