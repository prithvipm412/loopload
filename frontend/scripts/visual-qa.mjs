import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const out = fileURLToPath(new URL("../screenshots/", import.meta.url));
await mkdir(out, { recursive: true });
const browser = await chromium.launch({
  args: [
    "--enable-webgl",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
  ],
});
const page = await browser.newPage({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
});
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const base = process.env.QA_BASE_URL || "http://127.0.0.1:5173";
async function ready() {
  await page.evaluate(() => document.fonts.ready);
  await page.locator('[data-testid="map-canvas"] canvas').first().waitFor();
  await page.waitForFunction(
    () =>
      document
        .querySelector('[data-testid="map-canvas"]')
        ?.getAttribute("data-basemap-status") === "ready",
    null,
    { timeout: 15000 },
  );
  await page.waitForTimeout(1800);
  if (
    await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
  )
    throw Error("Horizontal overflow");
}
async function withinViewport(selectors) {
  const boxes = await page.locator(selectors).evaluateAll((nodes) =>
    nodes.map((n) => ({
      name: n.className,
      rect: n.getBoundingClientRect().toJSON(),
    })),
  );
  for (const { name, rect } of boxes)
    if (rect.left < 0 || rect.top < 0 || rect.right > 1440 || rect.bottom > 900)
      throw Error(`${name} extends outside the 1440×900 viewport`);
}
async function capture(name) {
  await page.screenshot({ path: `${out}${name}.png`, fullPage: false });
  console.log(`Saved ${name}.png (1440×900)`);
}
try {
  await page.goto(base);
  await page.getByTestId("timeline-play").click();
  await page.getByTestId("timeline-scrubber").fill("8");
  await ready();
  await withinViewport(
    ".map-panel,.impact-panel,.pooling,.timeline,.simulation",
  );
  await capture("dashboard");
  console.log(
    "Dashboard bounds",
    await page
      .locator(".map-panel,.impact-panel,.pooling,.timeline")
      .evaluateAll((nodes) =>
        nodes.map((n) => ({
          class: n.className,
          top: n.getBoundingClientRect().top,
          bottom: n.getBoundingClientRect().bottom,
        })),
      ),
  );
  await page.getByTestId("ai-plan-button").click();
  await page.waitForTimeout(1100);
  await page.getByTestId("truck-row-T01").click();
  await page.waitForTimeout(600);
  await capture("truck-drawer-T01");
  await page.goto(`${base}/forecast`);
  await page
    .getByTestId("hot-lanes-list")
    .getByRole("button")
    .first()
    .waitFor();
  await ready();
  await withinViewport(".hot-lanes,.forecast-chart,.forecast-map");
  await capture("forecast");
  await page.goto(`${base}/driver/T01`);
  await page.getByTestId("driver-phone").waitFor();
  await ready();
  await withinViewport(".phone");
  await capture("driver-T01");
  if (errors.length) throw Error(errors.join("\n"));
} finally {
  await browser.close();
}
