# Record the LoopLoad demo

Run these commands after the lead merges the integrated backend and frontend.
This data-agent checkout currently has no `app.main` or Vite application.
The recorder has not been run against the app.

## 1. Start the backend

In terminal 1, from the repository root:

```sh
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd backend
PYTHONPATH=. .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 2. Start the frontend

In terminal 2, from the repository root:

```sh
cd frontend
npm install
VITE_USE_MOCKS=false VITE_API_URL=http://localhost:8000 npm run dev -- --host 0.0.0.0 --port 5173 --strictPort
```

The integrated API client must append `/api` once. If that client instead expects
`VITE_API_URL` to include the API prefix, use `http://localhost:8000/api`.
Check `http://localhost:8000/api/health` and `http://localhost:5173` before capture.

## 3. Install recorder tools

In terminal 3, from the repository root (keeps recorder-only packages separate):

```sh
python3.12 -m venv demo/.venv
demo/.venv/bin/python -m pip install playwright
demo/.venv/bin/python -m playwright install chromium
```

On Linux, install browser system libraries with
`demo/.venv/bin/python -m playwright install --with-deps chromium` instead.
The API requirements file is unchanged.

## 4. Inspect selectors, then record when ready

Dry run opens Chromium and visits `/`, `/forecast`, and `/driver/T01`.
It logs selector matches and missing controls. It does not reset the API, click,
select a language, save screenshots, or enable video recording:

```sh
demo/.venv/bin/python scripts/record_demo.py --dry-run --headed
```

Drawer controls may be missing in dry run because it does not click T01. For
manual inspection, open T01 in the app and use the test IDs below.
Only run the full capture once the integrated app is ready:

```sh
demo/.venv/bin/python scripts/record_demo.py
```

Add `--headed` to watch Chromium. Defaults are frontend
`http://localhost:5173` and backend `http://localhost:8000`; override them with
`--url` and `--api-url`. Each capture uses Chromium at 1440×900, including video.

Full capture first executes `scripts/demo_reset.sh`, then records Baseline
(3 seconds), AI Plan (4 seconds), T01's drawer (4 seconds), optional cancellation
(4 seconds), forecast (4 seconds), and the driver view in Kannada (3 seconds).
Screenshots are taken after each pause and after closing the drawer. Map and
page-readiness waits can make the overall video longer than those pauses.

Output files, relative to the repository root:

- `demo/loopload_demo.webm`
- `demo/01_baseline.png`
- `demo/02_ai_plan.png`
- `demo/03_truck_T01.png`
- `demo/04_drawer_closed.png`
- `demo/05_cancel_load.png`
- `demo/06_forecast.png`
- `demo/07_driver_T01.png`
- `demo/08_driver_kannada.png`

New captures replace those filenames. Generated media is ignored by Git.
Missing controls and individual failed steps are logged and the tour continues.
A reset failure is also logged: the resulting recording then uses the current
scenario. Browser/dependency startup failures return 1 with a readable error;
missing UI controls do not terminate capture. Video is finalized by closing the
browser context before saving, as required by
[Playwright's video API](https://playwright.dev/python/docs/api/class-video).

## Frontend selector contract

The recorder uses exactly the frontend-provided `data-testid` names:

| Test ID | Element / behavior |
| --- | --- |
| `ai-plan-button` | Clickable AI Plan button. |
| `truck-row-T01` | Clickable T01 row opening the truck drawer. |
| `truck-drawer` | T01 drawer container, visible while open. |
| `truck-drawer-close` | Close button inside the drawer. |
| `cancel-load-button` | Optional “Simulate: cancel a load” button. |
| `replan-toast` | Replanning notification after cancellation; may be absent in dry run. |
| `nav-forecast` | Forecast navigation link or button. |
| `hot-lanes-list` | Forecast hot-lanes list, visible when content loads. |
| `driver-phone` | Driver phone view containing T01 content. |
| `lang-kn` | Clickable Kannada language button. |

Baseline selection and language dropdown fallback use accessible names and
visible text without requesting extra test IDs. Map loading uses a visible,
nonzero-sized canvas and waits for requests to settle; this is best effort and
cannot independently confirm all map tiles have loaded. Forecast navigation
prefers `nav-forecast` and falls back to opening `/forecast` directly.
