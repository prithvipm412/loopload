import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  timeout: 45000,
  use: {
    baseURL: "http://127.0.0.1:5180",
    viewport: { width: 1440, height: 900 },
    launchOptions: {
      args: [
        "--enable-webgl",
        "--use-gl=angle",
        "--use-angle=swiftshader",
        "--enable-unsafe-swiftshader",
      ],
    },
  },
  webServer: [
    {
      command: "npm run dev -- --port 5180",
      env: { VITE_USE_MOCKS: "true" },
      url: "http://127.0.0.1:5180",
      reuseExistingServer: true,
    },
    {
      command: "npm run dev -- --port 5181",
      url: "http://127.0.0.1:5181",
      env: { VITE_USE_MOCKS: "false", VITE_API_URL: "http://127.0.0.1:9" },
      reuseExistingServer: true,
    },
  ],
  reporter: "list",
});
