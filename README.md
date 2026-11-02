# LoopLoad

**AI that plans a truck's whole week in advance, so it never has to drive back empty.**

Most of India's trucks belong to small operators who find return loads one trip at a time, through calls and WhatsApp. So trucks wait for days or drive home empty. LoopLoad is an AI trip-chain planner. It forecasts where cargo will be, builds the most profitable multi-state loop for each truck, and pools small fleets so they plan like one large company.

> Ideathon demo, built at the NHCE Ideathon 2026. The data is synthetic but realistic. See the assumptions below.

## What's in the demo
- A live India map where empty legs (red, dashed) turn into loaded legs (green) when you press **AI Plan**
- Baseline ("how it works today") vs the AI optimiser, with empty km, profit, diesel and CO₂ compared
- A full week per truck, with e-way bill and permit compliance checks
- Live re-planning when a load is cancelled
- Demand forecasting and hot lanes for next week
- A driver app view in English, Hindi, Kannada and Tamil

## Docs
- [`docs/FEATURES.md`](docs/FEATURES.md): every feature, how it's built, and who builds it
- [`docs/CONTRACT.md`](docs/CONTRACT.md): shared data shapes, API and file ownership
- [`docs/PLAN.md`](docs/PLAN.md): parallel build plan with 4 agents (Claude Code + 3 Codex)
- [`prompts/`](prompts/): master prompt for each agent

## Tech
Python · FastAPI · Google OR-Tools · statsmodels · OSRM / OpenStreetMap · React · deck.gl · MapLibre · Tailwind

## Quick start
_Coming at Checkpoint 3: `make setup && make dev`_

## Assumptions
Diesel ₹90/L, 4 km/L, toll ₹5/km, CO₂ 2.68 kg/L of diesel, freight ₹38–55/km. These are all configurable in `backend/app/config.py`. The scenario and demand history are synthetic, generated from real seasonal freight flows.
