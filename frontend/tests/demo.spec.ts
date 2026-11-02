import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const fixture = (name: string) =>
  JSON.parse(
    readFileSync(new URL(`../src/mocks/${name}.json`, import.meta.url), "utf8"),
  );
const aiFixture = fixture("plan_ai");
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
    `${aiFixture.metrics.empty_km.toLocaleString("en-IN", { maximumFractionDigits: 0 })} km`,
  );
  await page.getByRole("button", { name: "Open hero truck" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByRole("dialog").getByText("open body · 21 t"),
  ).toBeVisible();
  await expect(page.getByRole("dialog").locator(".leg-card")).toHaveCount(4);
  await expect(
    page.getByRole("dialog").locator(".kind-label.loaded"),
  ).toHaveCount(4);

  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const issueTruck = aiFixture.trucks.find((t) =>
    t.legs.some((l) =>
      l.compliance.issues.some((i) => i.code === "EWAY_EXPIRES"),
    ),
  );
  await page
    .locator(".truck-row")
    .filter({ hasText: issueTruck.truck_id })
    .click();
  await expect(
    page.getByRole("dialog").getByText(/E-way bill expires/),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Simulate: cancel a load" }).click();
  await expect(page.getByRole("status")).toContainText("Re-planned in 1.8 s");
  await expect(page.locator(".truck-row.changed")).toHaveCount(1);
  await page.getByRole("link", { name: "Demand forecast" }).click();
  await expect(
    page.getByRole("heading", { name: "Hot lanes", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".lane-row")).toHaveCount(8);
  await page.locator(".lane-row").nth(1).click();
  await expect(page.locator(".forecast-chart h2")).toHaveText("NSK → BLR");
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

test("API outage shows an error toast and retains the interactive mock dashboard", async ({
  page,
}) => {
  await page.goto("http://127.0.0.1:5174/");
  await expect(
    page.getByRole("heading", { name: "A better week for every truck." }),
  ).toBeVisible();
  await expect(page.getByRole("status")).toContainText(
    "API unavailable. Showing demo data.",
  );
  await page.getByRole("button", { name: "AI Plan", exact: true }).click();
  await expect(page.locator(".mode-badge")).toHaveText("AI plan");
});

test("fixture totals and deltas agree with their legs and preserve the hero loop", async () => {
  const baseline = fixture("plan_baseline");
  const solo = fixture("plan_solo");
  const compare = fixture("compare");
  const scenario = fixture("scenario");
  expect(scenario.cities).toHaveLength(25);
  expect(scenario.trucks).toHaveLength(20);
  expect(scenario).toEqual(
    JSON.parse(
      readFileSync(
        new URL("../../backend/data/scenario.json", import.meta.url),
        "utf8",
      ),
    ),
  );
  for (const plan of [baseline, aiFixture, solo]) {
    const legs = plan.trucks.flatMap((t) => t.legs);
    expect(plan.metrics.empty_km).toBeCloseTo(
      legs
        .filter((l) => l.kind === "empty")
        .reduce((n, l) => n + l.distance_km, 0),
      1,
    );
    expect(plan.metrics.revenue_inr).toBe(
      legs.reduce((n, l) => n + l.revenue_inr, 0),
    );
    expect(plan.metrics.profit_inr).toBe(
      plan.metrics.revenue_inr -
        plan.metrics.diesel_inr -
        plan.metrics.toll_inr,
    );
    expect(plan.metrics.loads_served).toBe(
      legs.filter((l) => l.kind === "loaded").length,
    );
    expect(plan.unassigned_loads.length + plan.metrics.loads_served).toBe(
      scenario.loads.length,
    );
    for (const truck of plan.trucks) {
      for (const leg of truck.legs) {
        if (plan.mode !== "baseline")
          expect(leg.arrive_h).toBeLessThanOrEqual(168);
        expect(leg.arrive_h).toBeGreaterThan(leg.depart_h);
        expect(leg.path.length).toBeGreaterThanOrEqual(2);
        const city = scenario.cities.find((c) => c.id === leg.from)!;
        expect(leg.path[0][0]).toBeCloseTo(city.lon, 1);
        expect(leg.path[0][1]).toBeCloseTo(city.lat, 1);
        if (leg.kind === "loaded")
          expect(scenario.loads.some((l) => l.id === leg.load_id)).toBeTruthy();
        else expect(leg.load_id).toBeNull();
      }
    }
  }
  expect(aiFixture.metrics.empty_pct).toBeLessThan(15);
  expect(baseline.metrics.empty_pct).toBeGreaterThan(30);
  expect(compare.delta.empty_km).toBeCloseTo(
    aiFixture.metrics.empty_km - baseline.metrics.empty_km,
    1,
  );
  expect(aiFixture.trucks[0].legs.map((l) => [l.from, l.to, l.kind])).toEqual([
    ["TPR", "DEL", "loaded"],
    ["DEL", "JAI", "loaded"],
    ["JAI", "NAG", "loaded"],
    ["NAG", "TPR", "loaded"],
  ]);
  expect(
    aiFixture.trucks.flatMap((t) => t.legs).filter((l) => !l.compliance.ok),
  ).toHaveLength(2);
});

test("real-data edge cases: idle trucks, week overrun and warning-only compliance", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByRole("button", { name: "Pause playback" }).click();
  await page.locator(".truck-row").filter({ hasText: "T02" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "No trips assigned this week.",
  );
  await expect(page.getByRole("dialog")).toContainText("168 h rest / idle");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Open hero truck" }).click();
  await expect(page.getByRole("dialog")).toContainText("(+1w)");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "AI Plan", exact: true }).click();
  await page.locator(".truck-row").filter({ hasText: "T03" }).click();
  await expect(
    page.getByRole("dialog").locator(".compliance.warning"),
  ).toContainText("update Part B");
  expect(errors).toEqual([]);
});
