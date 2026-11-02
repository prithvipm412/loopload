# Visual QA — 1440 × 900

Captured in mock mode using Playwright Chromium, with the light theme, Inter loaded, and CARTO Positron loaded. All PNGs are exactly 1440 × 900 at 1× device scale.

- `dashboard.png`: baseline, playback paused at Monday 08:00; includes pooling and owner filter.
- `truck-drawer-T01.png`: AI plan, T01's four loaded legs and full-week Gantt; the leg list scrolls.
- `forecast.png`: all eight hot lanes, the latest 16 historical weeks, forecast confidence band, and hot-lane map.
- `driver-T01.png`: English driver view in the 390 × 780 phone frame; its week list scrolls inside the phone.

To refresh, start `npm run dev` in `frontend/`, then run `npm run qa:visual`. The capture script verifies there is no horizontal overflow and that dashboard panels, forecast panels, and phone fit inside the projector viewport. Set `QA_BASE_URL` to capture a different local server.
