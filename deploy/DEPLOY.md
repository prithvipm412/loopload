# Deploy LoopLoad

These steps use the integrated repository after the lead merges the API, engines,
and frontend. This data-agent checkout does not yet include `backend/app/main.py`
or the Vite application. The lead merges and pushes; these instructions do not
publish anything automatically.

## Render backend

1. Have the lead push the integrated branch to the GitHub repository.
2. Sign in to <https://dashboard.render.com>, select **New → Blueprint**, and
   connect that repository. Select the integrated branch.
3. Set **Blueprint Path** to `deploy/render.yaml` (the file is not at repo root).
4. Review the `loopload-api` web service and confirm **Free** before applying.
   The blueprint uses Dockerfile `backend/Dockerfile`, repository-root build
   context `.`, port `8000`, and health check `/api/health`. Leave the service
   root directory unset. No database, disk, or secret is required.
5. Apply the blueprint and wait for the service to become **Live**. If the name
   is already taken, choose a unique service name before applying.
6. Copy its actual HTTPS origin, for example `https://loopload-api.onrender.com`.
   Verify:

   ```sh
   curl --fail --show-error https://loopload-api.onrender.com/api/health
   python3 scripts/smoke_demo.py --base-url https://loopload-api.onrender.com --timeout 300
   ./scripts/demo_reset.sh https://loopload-api.onrender.com
   ```

   Substitute the actual origin in all commands. The smoke script exercises
   regeneration and replanning, so run reset afterward.

Render's [Blueprint reference](https://render.com/docs/blueprint-spec) documents
these fields and custom blueprint paths. Free services sleep after 15 idle
minutes and can take about a minute to wake; changes to their filesystem and
in-memory plans are lost on restart. Open `/api/health` before presenting.
See [Free service limits](https://render.com/docs/free).

The image includes `scenario.json`, `matrix.json`, `paths.json`, `history.json`,
and `forecast.json`; dependency installation needs network at build time.
Cached data needs no OSRM or forecast fitting at runtime. Uncached map routes
use the data layer's straight-line fallback if OSRM is unreachable. Keep the
committed JSON files in the build; do not regenerate caches during startup.

## Vercel frontend

1. Sign in to <https://vercel.com>, choose **Add New → Project**, and import the
   same integrated GitHub repository and production branch.
2. Set **Root Directory** to `frontend`, **Framework Preset** to **Vite**,
   **Build Command** to `npm run build`, and **Output Directory** to `dist`.
   Use the default install command (or `npm ci` when a lockfile is committed).
3. Add `VITE_API_URL` with the Render HTTPS origin, for example
   `https://loopload-api.onrender.com`, and `VITE_USE_MOCKS=false`. Enable both
   variables for Production and Preview. The frontend API client must append
   `/api` exactly once; if its configured base includes `/api`, put that suffix
   in this variable instead. Check the integrated client before deploying.
4. Deploy. Vite embeds these variables during the build, so redeploy after
   changing either value. See [Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite).
5. Open the Vercel URL and verify the browser's network requests reach the
   Render origin. The API must allow the Vercel origin through CORS; the lead
   owns that configuration. Check the map, AI button, forecast, and driver view.
   For client-side routes, the frontend must supply a Vercel rewrite to
   `/index.html`; ask the frontend owner if direct `/driver/T01` requests 404.

## Local rehearsal and offline verification

From the repository root, build and start the integrated backend:

```sh
docker build -f backend/Dockerfile -t loopload-backend .
docker run --rm --name loopload-api -p 8000:8000 loopload-backend
```

Use a clean clone for the build so local virtual environments are not copied
into the image. In another terminal:

```sh
python3 scripts/smoke_demo.py
./scripts/demo_reset.sh
```

For a rehearsal with no external network, start with
`docker run --rm --network none --name loopload-api loopload-backend` and run
`docker exec loopload-api python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/api/health").read().decode())'`.
To exercise all endpoints in that isolated container, copy the smoke script in
with `docker cp scripts/smoke_demo.py loopload-api:/tmp/smoke_demo.py`, then run
`docker exec loopload-api python /tmp/smoke_demo.py --timeout 300`.

Reset uses the contract's regeneration endpoint to restore seed 42, 20 trucks,
and 140 loads. That endpoint must invalidate all API plan/compare caches. The
reset script checks that a pre-reset plan ID is no longer retrievable and fails
if invalidation is missing. It preserves the offline road and forecast caches.
Solver wall-clock limits can vary plan IDs, solve times, and exact solutions;
reset guarantees identical scenario inputs and an empty API plan cache.
