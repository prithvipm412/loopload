# Master prompt: Codex 3 (FRONTEND)

You are building the **demo UI** for LoopLoad, shown live to judges at an Ideathon tomorrow morning. It's an AI planner that turns one-off truck trips into week-long loaded loops across India. The UI is the "wow": an India map where **coral dashed empty legs turn into solid sage-green loaded legs** when you press **AI Plan**, while impact counters drop.

**Read first:** `AGENTS.md`, `docs/CONTRACT.md` (JSON shapes in §4, API in §7) and `docs/FEATURES.md` (section F and the demo script).

You work in `~/Projects/loopload-cx3` on branch `feat/frontend`.
**You may only create or edit files under `frontend/`.** Commit after each working step. Never push to `main`.

---

## Stack (use exactly this)

- Vite + React 18 + TypeScript, created inside `frontend/`.
- Tailwind CSS, framer-motion and lucide-react icons.
- `deck.gl` (`@deck.gl/react`, `@deck.gl/layers`, `@deck.gl/geo-layers`, `@deck.gl/extensions`) with `react-map-gl/maplibre` and `maplibre-gl`. The basemap is CARTO Positron, a light map (`https://basemaps.cartocdn.com/gl/positron-gl-style/style.json`), so **no API token is needed**. Tint it warm with a beige overlay, or lower its saturation, so it blends with the off-white UI.
- Recharts for charts and react-router for pages.
- `src/api.ts` has typed fetchers for every endpoint. If `import.meta.env.VITE_USE_MOCKS === "true"`, it returns data from `src/mocks/*.json` instead. **Default to mocks until CC confirms the backend is up.** `VITE_API_URL` defaults to `http://localhost:8000`.
- `src/types.ts` holds TypeScript types that mirror CONTRACT §4 exactly.

## Visual direction (light, warm, pastel; NOT dark or navy)

- **Base:** off-white page `#FAF7F2`, beige panels `#F3EDE3`, cards `#FFFDF9` with 1px `#E6DCCB` borders, text `#2E2A24`, muted text `#7A7064`.
- **Pastel accents, used sparingly:**
  - sage green `#7FBF9A` for loaded legs and "better" chips
  - soft coral `#E8857A` for empty legs (dashed) and "worse" chips
  - peach `#F4B183` for hot lanes and forecast arcs
  - lavender `#A99BE0` as the primary accent (AI Plan button, active toggle)
  - sky blue `#9CCBE8` for charts and the timeline
  - butter yellow `#F3D98B` for compliance warnings
- **Contrast:** lines on the map must stay clearly visible on the light basemap. Use 3–4 px widths and slightly deeper strokes (sage `#5FA67F`, coral `#D9695E`) if the pastels look washed out.
- **Buttons:** the AI Plan button is lavender with dark text `#2E2A24`, has a soft shadow, and gets a gentle glow and pulse before it's first clicked.
- **Charts:** Recharts on cards, with pastel fills, thin grid lines `#EDE5D8` and no heavy borders.
- **Type:** Inter (or "DM Sans" for headings). Large friendly numbers, rounded-2xl cards, soft shadows (`0 4px 20px rgba(120,100,70,0.08)`), generous spacing.
- **Smooth animations everywhere:** counters tween (framer-motion), legs fade and morph on plan switch, and panels slide in.
- It must look calm, premium and readable on a 1440×900 projector in a bright room. No emoji, no neon, no dark mode.

## P0-1: Mocks (first 20 min)

Create `src/mocks/scenario.json`, `plan_baseline.json`, `plan_ai.json` and `compare.json` in the exact contract shapes.

- Use the real 25 cities from CONTRACT §2 and about 10 trucks.
- The baseline has about 35% empty km. The AI plan has about 12% empty km, with clear loops.
- Include the hero truck T01: TPR→DEL (Textiles), DEL→JAI (FMCG), JAI→NAG (Marble), NAG→TPR (Oranges).
- Paths can be straight lines `[[lonA,latA],[lonB,latB]]` with a midpoint added, so they curve slightly.
- Include 2 legs with compliance issues (`EWAY_EXPIRES`).

## P0-2: Main dashboard (`/`)

The layout has a top bar, a full-bleed map on the left (about 70% wide), a right panel (30%) and a bottom timeline.

- **Top bar:** the "LoopLoad" wordmark with the tagline "Every leg loaded", and a segmented toggle **Today (Baseline) | LoopLoad AI**. The **AI Plan** button is big, glowing and accent-coloured. A small "Solved in 8.2 s" badge shows `solve_time_s`.
- **Map:**
  - ScatterplotLayer for cities with name labels (TextLayer).
  - PathLayer for legs. Loaded legs are solid green. Empty legs are red with `PathStyleExtension({dash:true})` and `getDashArray: [6,4]`. Width is about 3 px, and the hovered leg is highlighted.
  - TripsLayer for animated trucks. Build timestamps by interpolating each leg's path between `depart_h` and `arrive_h`. The trail length is about 6 h.
  - Tooltip on a leg: from → to, cargo, km, ₹, loaded/empty.
  - Click a truck or leg to open the **Truck drawer**.
- **Switching plans:** fade the old legs out and the new ones in over about 900 ms, and tween all counters.
- **Right panel:**
  - Impact counters: **Empty km**, **Wasted diesel ₹** (diesel spent on empty legs), **CO₂ (t)**, **Revenue ₹**, **Loaded %**, **Loads served**. Each shows the value for the current mode and a small delta chip vs the baseline (green when better).
  - A Recharts grouped bar (Baseline vs AI) for empty km, profit and CO₂ from `/api/compare`.
  - A list of trucks with mini loaded/empty bars. Clicking one opens the drawer.
- **Bottom timeline:** play/pause, a speed control (1×/4×/16×) and a scrubber over 0–168 h with day labels Mon–Sun. It drives the TripsLayer `currentTime`.

## P0-3: Truck drawer

A right slide-over showing the truck's reg no, owner, type, capacity and driver. It has a **7-day Gantt-style timeline** of legs (green or red blocks, with grey rest/idle gaps). Below it is a leg list: from → to, commodity, depart/arrive as day + time, km, revenue, diesel, profit, and a compliance badge (green check, or a red badge with the issue message). Totals are at the bottom.

## P0-4: Polish and resilience

- Show a loading skeleton while fetching, and an error toast if the API fails, then fall back to mocks automatically.
- Every number uses Indian formatting (₹1,85,000 and lakh/crore where large) with the `en-IN` locale.

## P1 (after all P0 work is done)

- **Forecast page (`/forecast`):** a hot-lanes list (lane, commodity, next-week loads, change %), a line chart of history + forecast with a confidence band (Recharts Area + Line), and the map with an `ArcLayer` for hot lanes in amber, with width scaled by loads.
- **Re-plan:** a "Simulate: cancel a load" button on the dashboard. It picks a load on the hero truck, POSTs `/api/replan` with `{type:"cancel_load", load_id, at_h: currentTime}`, highlights `changed_trucks`, and shows the toast "Re-planned in X s".
- **Pooling card:** shows Solo owners vs Pooled profit from `POST /api/plan {mode:"ai_solo"}` vs the AI plan, with an owner filter dropdown that dims the other owners' legs.
- **Driver view (`/driver/:truckId`):** a phone frame (390×780) centred on a beige background. It shows the next pickup card, the cargo, a mini route map and the week list. Language toggle EN / हिंदी / ಕನ್ನಡ / தமிழ் uses a static `i18n.ts` dictionary covering every label on this screen.

## Switching to the real API

When the user says the backend is up, set `VITE_USE_MOCKS=false` in `frontend/.env.local`, check that every page works against `http://localhost:8000`, and fix any type mismatches on your side. If the backend shape differs from the contract, tell the user which field. Don't change the contract.

---

After each item, commit and print a short status with what works and what's next.
