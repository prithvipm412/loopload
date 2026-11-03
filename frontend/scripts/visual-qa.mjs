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
page.setDefaultTimeout(90000);
const errors = [];
await page.addInitScript(() => {
  window.__apiFallback = [];
  window.addEventListener("api-fallback", (e) =>
    window.__apiFallback.push(e.detail),
  );
});
page.on("pageerror", (e) => errors.push(e.message));
const base = process.env.QA_BASE_URL || "http://localhost:5173";
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
    (await page
      .getByTestId("map-canvas")
      .getAttribute("data-basemap-labels-visible")) !== "0"
  )
    throw Error("Basemap symbol labels are still visible");
  const fullCanvas = await page.getByTestId("map-canvas").evaluate((root) => {
    const box = root.getBoundingClientRect();
    const canvas = root
      .querySelector(".maplibregl-canvas")
      .getBoundingClientRect();
    return (
      Math.abs(box.width - canvas.width) < 1 &&
      Math.abs(box.height - canvas.height) < 1
    );
  });
  if (!fullCanvas) throw Error("MapLibre canvas does not fill the card");
  if ((await page.evaluate(() => window.__apiFallback)).length)
    throw Error("Live screenshot rejected: API fallback occurred");
  if (
    !(await page.locator(".header-meta").innerText()).includes("Live workspace")
  )
    throw Error("Live API mode is required for release screenshots");
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
  await page.waitForFunction(
    () =>
      document.querySelector('[data-testid="pooling-card"] .pool-stat strong')
        ?.textContent !== "Loading…",
  );
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
  await page.waitForFunction(
    () =>
      document
        .querySelector('[data-testid="map-canvas"]')
        ?.getAttribute("data-transitioning") === "false",
  );
  await page.waitForTimeout(250);
  const clipped = await page
    .locator('[data-testid="plan-highlights"] article')
    .evaluateAll((cards) =>
      cards.some((card) => card.scrollHeight > card.clientHeight + 1),
    );
  if (clipped) throw Error("An AI highlight is clipped");
  await capture("dashboard-ai");
  await page.getByTestId("truck-row-T01").click();
  await page.waitForTimeout(600);
  await capture("truck-drawer-T01");
  await page.getByTestId("truck-drawer-close").click();
  await page.getByRole("button", { name: "Open hero truck" }).click();
  await page.waitForTimeout(600);
  const hero = (
    await page.locator(".drawer-heading .eyebrow").innerText()
  ).match(/T\d+/)?.[0];
  if (hero && hero !== "T01") await capture(`truck-drawer-${hero}`);
  await page.getByTestId("truck-drawer-close").click();
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
