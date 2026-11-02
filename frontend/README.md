# LoopLoad frontend

React 18 / Vite / TypeScript demo UI. All pages use the warm light palette and CARTO Positron.

## Run

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Mock mode is enabled in `.env.local`; no backend is needed. Basemap tiles and the hosted Inter font require internet. Route overlays and demo interactions remain available when the basemap fails.

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

After the lead confirms the backend is ready, set `VITE_USE_MOCKS=false` in `.env.local` and restart Vite. `VITE_API_URL` defaults to `http://localhost:8000`. Every contract endpoint has a typed fetcher in `src/api.ts`; failed requests show a toast and use demo data. Keep scenario and plan responses on the same backend version to avoid mixing live and demo identifiers.
