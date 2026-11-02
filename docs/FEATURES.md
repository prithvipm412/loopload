# LoopLoad: Demo Feature List

LoopLoad plans **chains of trips, not single trips**, so trucks from small Indian fleet owners carry cargo on almost every leg.
This file lists every feature in the Ideathon demo, how it is built, and who builds it.

**Priority**
- **P0**: must work for the demo tomorrow morning.
- **P1**: makes the demo stronger. Build only after all P0 work is done.
- **P2**: stretch goals, or things to mention in the pitch only.

**Owners**
- **CC**: Claude Code, the lead (backend API and integration).
- **CX1**: Codex account 1 (optimiser).
- **CX2**: Codex account 2 (data, forecasting, compliance).
- **CX3**: Codex account 3 (frontend).

---

## A. Data & scenario (CX2)

| # | Feature | P | How we build it |
|---|---|---|---|
| A1 | **25 Indian freight cities** | P0 | A fixed list in `CONTRACT.md` §2 (codes, names, lat/lon). Saved to `backend/data/cities.json`. |
| A2 | **Road distance & time matrix** | P0 | Calls the public OSRM `/table` API once for all 25 cities and caches the result to `backend/data/matrix.json`. If OSRM fails, falls back to haversine × 1.3 for distance and distance ÷ 45 km/h for time. |
| A3 | **Road paths for the map** | P0 | Calls OSRM `/route` for each city pair that actually appears in a plan and caches it to `backend/data/paths.json`. The geometry is simplified to at most 60 points. If OSRM fails, uses a straight line. |
| A4 | **Scenario generator** | P0 | `generate_scenario(seed)` creates 6 owners, 20 trucks and about 140 loads over a 7-day week, using real seasonal flows (see `CONTRACT.md` §5). It is seeded, so every run gives the same demo. |
| A5 | **Realistic money numbers** | P0 | Freight is distance × ₹38–55/km. Diesel is ₹90/L at 4 km/L. Toll is ₹5/km. Cargo values are per commodity. All of these are constants in `config` and labelled as assumptions. |
| A6 | **Demo-tuned scenario** | P0 | The scenario must give the baseline at least 30% empty km, so the AI improvement is clear. CX2 tunes it together with CC. |

## B. Planning engines

| # | Feature | P | Owner | How we build it |
|---|---|---|---|---|
| B1 | **Baseline planner ("how it works today")** | P0 | CC | A greedy, one-trip-at-a-time simulation. Each truck takes the nearest load it can reach. After delivering, it waits up to 48 h for a load starting within 150 km. If none comes, it drives home empty. |
| B2 | **AI chain optimiser** | P0 | CX1 | Google OR-Tools pickup-and-delivery with time windows (PDPTW). All trucks from all owners are solved together. It handles one load at a time (FTL), truck type and capacity, pickup windows, deadlines, and driver driving hours per day. The objective is to maximise profit: dropping a load costs its freight value, and every km costs diesel + toll. Guided local search runs with a 10 s limit. |
| B3 | **Metrics engine** | P0 | CC | Computes total, loaded and empty km, empty %, revenue, diesel ₹, toll ₹, profit ₹, CO₂ kg (2.68 kg per litre of diesel), loads served and idle hours. The same function is used for the baseline and the AI plan. |
| B4 | **Live re-plan** | P1 | CX1 | `replan(plan, event)` handles a cancelled load, a delayed truck or a new load. Legs already done are frozen, and the rest of the week is re-solved with a 5 s limit. |
| B5 | **Pooled vs solo comparison** | P1 | CX1 | The same optimiser runs once per owner (solo) and once for everyone (pooled), to show the benefit of pooling. |
| B6 | **Forecast-aware planning** | P2 | CX1 | Forecast loads are added as optional nodes worth expected value, so trucks end the week near hot lanes. |

## C. Forecasting (CX2)

| # | Feature | P | How we build it |
|---|---|---|---|
| C1 | **Synthetic demand history** | P0 | 104 weeks of weekly load counts per lane, built from seasonality: onions Oct–Jan, cotton Oct–Mar, oranges Nov–Feb, festival FMCG Sep–Nov, wheat Apr–Jun. Noise is added. |
| C2 | **Next-week forecast per lane** | P0 | statsmodels Holt-Winters with additive yearly seasonality (52 weeks). Predicts 4 weeks ahead with a ±1.96σ band. |
| C3 | **Hot lanes** | P0 | The top 8 lanes by predicted loads next week, with change vs the last 4-week average. Shown as arcs on the map. |

## D. Compliance (CX2)

| # | Feature | P | How we build it |
|---|---|---|---|
| D1 | **E-way bill check** | P0 | An e-way bill is required for consignments over ₹50,000. Validity is 1 day per 200 km (minimum 1 day). The bill must still be valid at planned arrival, and Part B must match the truck. |
| D2 | **Truck checks** | P0 | Weight must be within capacity, the truck type must match, and the national permit must be valid. These are mock fields from the generator. |
| D3 | **Planted issues for the demo** | P0 | The generator gives about 5% of loads an expiring or missing e-way bill, so the check catches something live. |

## E. Backend API (CC)

| # | Feature | P | How we build it |
|---|---|---|---|
| E1 | **FastAPI app** | P0 | Endpoints are listed in `CONTRACT.md` §4. Plans are held in memory. CORS is open for the Vite dev server. |
| E2 | **Compare endpoint** | P0 | `GET /api/compare` returns the baseline and AI metrics plus their difference. This is the "money shot". |
| E3 | **Integration tests** | P0 | `pytest`: the AI plan has less empty km than the baseline, no plan breaks the contract shape, and every endpoint returns 200. |
| E4 | **One-command run** | P0 | `make dev`, or `./run.sh`, starts the backend on :8000 and the frontend on :5173. |

## F. Frontend (CX3)

Built with React + Vite + TypeScript, Tailwind, deck.gl over a light MapLibre CARTO Positron basemap (no token needed), Recharts and framer-motion. Light off-white and beige theme with pastel accents (sage, coral, peach, lavender, sky).

| # | Feature | P | How we build it |
|---|---|---|---|
| F1 | **Live India map** | P0 | City dots, with legs drawn as a deck.gl `PathLayer`. **Loaded legs are solid sage green and empty legs are dashed coral** (`PathStyleExtension`). |
| F2 | **"AI Plan" button** | P0 | Switches from the baseline plan to the AI plan. The legs cross-fade, and the counters animate down. |
| F3 | **Impact counters** | P0 | Empty km, wasted diesel ₹, CO₂ kg, revenue ₹ and loaded %, comparing baseline and AI. |
| F4 | **Animated trucks** | P0 | A `TripsLayer` with timestamps from the leg departure and arrival times, plus play/pause and a week scrubber. |
| F5 | **Truck week drawer** | P0 | Click a truck to see its 7-day timeline: legs, cargo, ₹ per leg, rest stops and compliance badges. |
| F6 | **Forecast page** | P1 | History + forecast line chart with a band, a hot-lanes list, and an `ArcLayer` on the map. |
| F7 | **Driver app view** | P1 | `/driver/:truckId` in a phone frame: next pickup, cargo and route, with an EN / हिंदी / ಕನ್ನಡ / தமிழ் toggle using static strings. |
| F8 | **Cancel-a-load button** | P1 | Calls `/api/replan`, shows a toast ("Re-planned in 1.8 s") and animates the changed legs. |
| F9 | **Owner filter + pooling card** | P1 | Filter the map by owner, and show solo vs pooled profit. |
| F10 | **Mock mode** | P0 | Works fully from `src/mocks/*.json` when `VITE_USE_MOCKS=true`, so the frontend never waits on the backend. |

## G. Stretch (P2)

- Deploy: frontend on Vercel, backend on Render.
- What-if slider for diesel price or fleet size.
- CSV upload of real loads.
- Carbon report PDF for shippers.

---

## Demo script (3 minutes)

1. Open the map on **Baseline**. Lots of red dashed legs, with the counters showing empty km and wasted ₹.
2. Click **AI Plan**. The routes turn into loops, most legs turn green, and the counters drop.
3. Click a truck to open its full week: Tiruppur → Delhi → Jaipur → Nagpur → home, with ₹ per leg.
4. Show the compliance badge catching an expiring e-way bill.
5. Click **Cancel a load**. It re-plans live.
6. Open the forecast page with the hot lanes for next week (onion season out of Nashik).
7. Open the driver view on a phone frame and switch the language to Kannada.
