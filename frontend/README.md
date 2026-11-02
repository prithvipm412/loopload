# LoopLoad frontend

React 18 / Vite / TypeScript demo UI. All pages use the warm light palette and CARTO Positron.

## Run

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. The real API is enabled in `.env.local` (`VITE_USE_MOCKS=false`) and defaults to `http://localhost:8000`. Start the backend before opening the frontend. Failed requests automatically use the offline fixtures, show a toast, and change the workspace badge to **Demo fallback**. For fully offline data, set `VITE_USE_MOCKS=true` and restart Vite. Basemap tiles and the hosted Inter font require internet. Route overlays and demo interactions remain available when the basemap fails.

## Demo

1. Start on Today / Baseline; pause playback if desired.
2. Click **AI Plan** to crossfade routes and animate the impact counters.
3. Open **T01** to inspect its loaded loop. Open **T11** or **T13** to inspect an actual expiring e-way bill.
4. Set the time early in the week and click **Simulate: cancel a load**. Only future pickups can be cancelled. Mock re-planning converts that trip into empty repositioning and recalculates all totals; the real API performs optimization.
5. Open **Demand forecast**, then select a hot lane.
6. Open **Driver view** and switch between EN, Hindi, Kannada, and Tamil.
7. Use the owner selector below the dashboard to dim other owners’ routes.

## Checks

```sh
npm run build
npx playwright install chromium
npm test
```

Browser tests cover the demo flow, compliance drawer, cancellation feedback, forecasts, translation, and projector/mobile layout. Screenshots are saved under the ignored `test-results/` folder.

`python3 generate-mocks.py` copies `backend/data/scenario.json` exactly (25 hubs, 6 owners, 20 trucks, 140 loads), uses cached road paths, and copies the real forecast data. It reads backend modules without writing backend files. The baseline fixture uses the real baseline planner. AI and solo fixtures use a deterministic frontend demo heuristic, pending integration with the actual optimizer. All totals and compliance results use the shared backend functions and diesel assumption.

The current data gives 43.1% baseline empty km versus 8.6% in the offline AI fixture. More loads are served, so absolute fleet CO₂ increases; the UI reports that increase. Some baseline empty returns finish after 168 h: the drawer shows the next-week time, and the Gantt clips at the week boundary. Idle trucks show zero loaded distance and a full week of rest / idle.

## Real API

The backend is now enabled with `VITE_USE_MOCKS=false` in `.env.local`. `VITE_API_URL` defaults to `http://localhost:8000`. Every contract endpoint has a typed fetcher in `src/api.ts`; failed requests show a toast and use demo data. The initial workspace keeps its skeleton until comparison finishes (up to 60 seconds). Plan requests allow 45 seconds, solo planning 90 seconds, and replan requests 45 seconds. Duplicate initial solves are suppressed during React Strict Mode. Optional `reason`, `highlights`, `changed_trucks`, and `co2_kg_per_load` fields support missing/null values. Carbon intensity is derived from total carbon and served loads when the API omits it.

## QA

`npm test` runs mock, outage, slow-response, optional-field, and animation regression checks on dedicated test ports 5180/5181. It does not change `.env.local`. Browser tests run serially to avoid contention between software WebGL contexts.

With the frontend and backend running, `npm run qa:live` checks every page, the actual comparison values, all driver languages, and cancellation against real API responses; it rejects any mock fallback. `npm run qa:visual` refreshes `screenshots/` at 1440 × 900.

The opportunity card is below the India-focused map. Comparison cards show actual baseline and AI values for empty km, profit, and CO2 per load. Loads served is a plain count; profit gain is rupees per week, with profit per active truck beside it.
