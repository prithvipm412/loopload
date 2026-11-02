import { chromium, expect as baseExpect } from "@playwright/test";
const expect = baseExpect.configure({ timeout: 60000 });
const base = process.env.QA_BASE_URL || "http://localhost:5173";
const browser = await chromium.launch({
  args: [
    "--enable-webgl",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
  ],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(60000);
const errors = [];
const responses = [];
const plans = new Map();
page.on("pageerror", (e) => errors.push(e.message));
page.on("response", async (r) => {
  if (!r.url().startsWith("http://localhost:8000/api")) return;
  responses.push({ url: r.url(), status: r.status() });
  if (r.url().endsWith("/plan") && r.ok()) {
    const body = r.request().postDataJSON();
    plans.set(body.mode, await r.json());
  }
});
await page.addInitScript(() => {
  window.__apiFallback = [];
  window.addEventListener("api-fallback", (e) =>
    window.__apiFallback.push(e.detail),
  );
});
async function realData() {
  expect(await page.evaluate(() => window.__apiFallback)).toEqual([]);
  await expect(page.locator(".header-meta")).toContainText("Live workspace");
}
try {
  await page.goto(base);
  await expect(
    page.getByRole("heading", { name: "A better week for every truck." }),
  ).toBeVisible();
  await page.getByTestId("timeline-play").click();
  await page.getByTestId("timeline-scrubber").fill("0");
  await expect(
    page
      .getByTestId("pooling-card")
      .locator(".pool-stat")
      .first()
      .locator("strong"),
  ).not.toHaveText("Loading…", { timeout: 90000 });
  await realData();
  expect(plans.has("baseline")).toBeTruthy();
  expect(plans.has("ai")).toBeTruthy();
  expect(plans.has("ai_solo")).toBeTruthy();
  const baseline = plans.get("baseline"),
    ai = plans.get("ai");
  await expect(page.getByTestId("counter-empty-km")).toHaveText(
    `${Math.round(baseline.metrics.empty_km).toLocaleString("en-IN")} km`,
  );
  await page.getByTestId("ai-plan-button").click();
  await expect(page.getByTestId("counter-empty-km")).toHaveText(
    `${Math.round(ai.metrics.empty_km).toLocaleString("en-IN")} km`,
  );
  await expect(page.getByTestId("counter-loads")).toHaveText(
    String(ai.metrics.loads_served),
  );
  await expect(page.getByTestId("counter-co2").locator("..")).toContainText(
    "CO2 per load",
  );
  await expect(
    page.getByTestId("plan-highlights").locator("article"),
  ).toHaveCount(Math.min(3, ai.highlights?.length || 0));
  await page.getByTestId("truck-row-T01").click();
  await expect(page.getByTestId("truck-drawer")).toContainText("TN39AB1201");
  await page.getByTestId("truck-drawer-close").click();
  await page.getByRole("button", { name: "Open hero truck" }).click();
  await expect(
    page.getByTestId("truck-drawer").locator(".leg-reason").first(),
  ).toBeVisible();
  await page.getByTestId("truck-drawer-close").click();
  const replanResponse = page.waitForResponse(
    (r) => r.url().endsWith("/api/replan") && r.request().method() === "POST",
  );
  await page.getByTestId("cancel-load-button").click();
  const response = await replanResponse;
  expect(response.ok()).toBeTruthy();
  const replanned = await response.json();
  await expect(page.getByTestId("replan-toast")).toContainText("Re-planned");
  if (replanned.changed_trucks?.length)
    await expect(page.locator(".truck-row.changed")).toHaveCount(
      replanned.changed_trucks.length,
    );
  await page.waitForTimeout(3200);
  await expect(page.locator(".truck-row.changed")).toHaveCount(0);
  await realData();
  await page.getByTestId("nav-forecast").click();
  await expect(
    page.getByTestId("hot-lanes-list").getByRole("button"),
  ).toHaveCount(8);
  await expect(
    page.getByTestId("forecast-chart").locator("h2"),
  ).not.toContainText("Loading");
  await page.getByTestId("hot-lanes-list").getByRole("button").nth(1).click();
  await realData();
  await page.getByTestId("nav-driver").click();
  await expect(page.getByTestId("driver-phone")).toBeVisible();
  for (const lang of ["en", "hi", "kn", "ta"]) {
    await page.getByTestId(`lang-${lang}`).click();
    await expect(page.getByTestId("driver-phone")).toHaveAttribute(
      "lang",
      lang,
    );
  }
  await realData();
  expect(errors).toEqual([]);
  expect(responses.filter((r) => r.status >= 400)).toEqual([]);
  console.log(
    JSON.stringify(
      {
        result: "PASS",
        pages: ["/", "T01 drawer", "hero drawer", "/forecast", "/driver/T01"],
        baseline: baseline.metrics.empty_pct,
        ai: ai.metrics.empty_pct,
        changed_trucks: replanned.changed_trucks,
        realApiResponses: responses.length,
        fallbacks: 0,
      },
      null,
      2,
    ),
  );
} finally {
  await browser.close();
}
