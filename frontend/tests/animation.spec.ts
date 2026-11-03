import { test, expect } from "@playwright/test";
// Virtual RAF avoids making software-WebGL speed part of the animation contract.
test.beforeEach(async ({ page }) => {
  const start = new Date("2026-11-09T00:00:00+05:30");
  await page.clock.install({ time: start });
  await page.clock.pauseAt(new Date(start.getTime() + 100));
  await page.goto("/");
  await page
    .getByTestId("timeline-play")
    .evaluate((el: HTMLElement) => el.click());
  await page.evaluate(() => document.fonts.ready);
  await page.clock.runFor(800);
});
const read = async (page: any) =>
  page.evaluate(() => {
    const map = document.querySelector<HTMLElement>(
      '[data-testid="map-canvas"]',
    )!;
    const selectors = [
      ".map-panel",
      ".impact-panel",
      ".timeline",
      ".simulation",
      ".pooling",
      '[data-testid="counter-empty-km"]',
      '[data-testid="counter-diesel"]',
      '[data-testid="truck-row-T01"]',
    ];
    return {
      blend: Number(map.dataset.transitionProgress),
      active: map.dataset.transitioning === "true",
      value: Number(
        document
          .querySelector('[data-testid="counter-empty-km"]')!
          .textContent!.replace(/[^\d.]/g, ""),
      ),
      bounds: selectors.map((s) => {
        const r = document.querySelector(s)!.getBoundingClientRect();
        return [r.x, r.y, r.width, r.height];
      }),
    };
  });
test("900 ms crossfade and number tween preserve panel geometry", async ({
  page,
}) => {
  const before = await read(page);
  await page
    .getByTestId("ai-plan-button")
    .evaluate((el: HTMLElement) => el.click());
  const samples = [];
  for (let time = 100; time <= 1100; time += 100) {
    await page.clock.runFor(100);
    samples.push({ time, ...(await read(page)) });
  }
  expect(samples.some((s) => s.blend > 0.1 && s.blend < 0.9)).toBeTruthy();
  expect(samples.find((s) => s.time === 800)!.active).toBeTruthy();
  expect(samples.find((s) => s.time === 1000)!.blend).toBe(1);
  expect(samples.at(-1)!.active).toBeFalsy();
  expect(new Set(samples.map((s) => s.value)).size).toBeGreaterThan(4);
  expect(samples.at(-1)!.value).toBeLessThan(before.value);
  let drift = 0;
  for (const sample of samples)
    sample.bounds.forEach((box, j) =>
      box.forEach(
        (n, k) => (drift = Math.max(drift, Math.abs(n - before.bounds[j][k]))),
      ),
    );
  expect(drift).toBeLessThan(1);
  console.log(
    `900 ms crossfade/tween verified; maximum layout drift ${drift.toFixed(2)} px`,
  );
});
test("reversing a switch keeps counters continuous", async ({ page }) => {
  await page
    .getByTestId("ai-plan-button")
    .evaluate((el: HTMLElement) => el.click());
  await page.clock.runFor(250);
  const before = await read(page);
  await page
    .getByTestId("mode-toggle-baseline")
    .evaluate((el: HTMLElement) => el.click());
  await page.clock.runFor(20);
  const after = await read(page);
  expect(Math.abs(after.value - before.value)).toBeLessThan(500);
  await page.clock.runFor(1100);
  await expect(page.getByTestId("counter-empty-km")).toHaveText("21,503 km");
  await expect(page.getByTestId("map-canvas")).toHaveAttribute(
    "data-transitioning",
    "false",
  );
});
