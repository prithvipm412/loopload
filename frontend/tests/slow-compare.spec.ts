import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const fixture = (name: string) =>
  JSON.parse(
    readFileSync(new URL(`../src/mocks/${name}.json`, import.meta.url), "utf8"),
  );
test("cold comparison keeps its skeleton beyond 15 seconds without falling back", async ({
  page,
}) => {
  test.setTimeout(45000);
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const headers = {
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET,POST,OPTIONS",
      "access-control-allow-headers": "Content-Type",
    };
    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers });
      return;
    }
    let data;
    if (path.endsWith("/scenario")) data = fixture("scenario");
    else if (path.endsWith("/compare")) {
      await new Promise((resolve) => setTimeout(resolve, 16000));
      data = fixture("compare");
    } else if (path.endsWith("/plan")) {
      const mode = request.postDataJSON().mode;
      data = fixture(mode === "ai_solo" ? "plan_solo" : `plan_${mode}`);
    } else throw Error(`Unexpected API request ${path}`);
    await route.fulfill({
      status: 200,
      headers,
      contentType: "application/json",
      body: JSON.stringify(data),
    });
  });
  await page.goto("http://127.0.0.1:5181/");
  await expect(page.getByTestId("loading-skeleton")).toBeVisible();
  await page.waitForTimeout(15050);
  await expect(page.getByTestId("loading-skeleton")).toBeVisible();
  await expect(page.getByTestId("ai-plan-button")).toBeVisible({
    timeout: 15000,
  });
  await expect(
    page.getByText("API unavailable. Showing demo data."),
  ).toHaveCount(0);
  await expect(page.locator(".header-meta")).toContainText("Live workspace");
});
