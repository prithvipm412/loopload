# Live visual QA — 1440 × 900

Captured against the real API at `http://localhost:8000`, with `VITE_USE_MOCKS=false`. All PNGs are exactly 1440 × 900 at 1× device scale. The capture rejects API fallback, waits for Inter and CARTO Positron, checks that the basemap canvas fills its card, and verifies that all basemap symbol labels are hidden.

- `dashboard.png`: baseline, paused at Monday 08:00; all impact, comparison, fleet and pooling panels fit the projector viewport.
- `dashboard-ai.png`: AI mode, settled counters, three plan highlights, and absolute weekly/per-truck profit.
- `truck-drawer-T01.png`: the real AI result for T01. The current backend leaves T01 idle.
- `truck-drawer-T04.png`: the actual hero loop returned by the current backend, including per-leg reasons and compliance warnings.
- `forecast.png`: all eight hot lanes, 16 historical weeks, the forecast confidence band, and the full-card map.
- `driver-T01.png`: the real T01 driver view and its no-pickup state, inside the 390 × 780 phone frame.

The API currently assigns the four hero loads to **T04**, rather than T01. The UI follows the returned plan without substituting mock trips. Mock mode still retains the requested T01 hero loop.

The map refits on container/window resize, starts near 80°E / 22°N, and uses that fitted zoom as its minimum. Zoom is capped at 7 and the controlled camera is bounded to 60–100°E / 2–38°N. The basemap covers the entire card, including neighbouring land and sea, with only LoopLoad's city labels shown.

To refresh, start the real backend and `npm run dev` in `frontend/`, then run `npm run qa:visual`. Set `QA_BASE_URL` to use a different local frontend server. The script also checks horizontal overflow and panel/phone bounds at 1440 × 900.
