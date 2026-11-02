# LoopLoad: Parallel Build Plan (tonight)

Four agents work at the same time, each in its own **git worktree** (a separate folder and branch), so they never overwrite each other.

| Agent | Terminal command | Folder | Branch | Builds |
|---|---|---|---|---|
| **CC**: Claude Code (lead) | `claude` | `~/Projects/loopload` | `main` | API, baseline, metrics, merging, tests, README |
| **CX1** | `cx1` | `~/Projects/loopload-cx1` | `feat/optimizer` | OR-Tools optimiser, re-plan, pooling |
| **CX2** | `cx2` | `~/Projects/loopload-cx2` | `feat/data-forecast` | Cities, OSRM matrix, scenario generator, compliance, forecasting |
| **CX3** | `cx3` | `~/Projects/loopload-cx3` | `feat/frontend` | React + deck.gl demo UI |

## Step 1: One-time setup (5 minutes, in your Mac terminal)

```bash
cd ~/Projects/loopload
git init -b main
git add .
git commit -m "LoopLoad: feature plan, contract and agent prompts"
gh repo create prithvipm412/loopload --public --source=. --remote=origin --push

git worktree add ../loopload-cx1 -b feat/optimizer
git worktree add ../loopload-cx2 -b feat/data-forecast
git worktree add ../loopload-cx3 -b feat/frontend
```

## Step 2: Start all four agents (four terminal tabs)

```bash
# Tab 1
cd ~/Projects/loopload && claude
#   then type:  Read prompts/00_claude_code_lead.md and follow it exactly.

# Tab 2
cd ~/Projects/loopload-cx1 && cx1
#   then type:  Read prompts/01_codex1_optimizer.md and follow it exactly.

# Tab 3
cd ~/Projects/loopload-cx2 && cx2
#   then type:  Read prompts/02_codex2_data_forecast.md and follow it exactly.

# Tab 4
cd ~/Projects/loopload-cx3 && cx3
#   then type:  Read prompts/03_codex3_frontend.md and follow it exactly.
```

## Step 3: Timeline and checkpoints

| Time (IST) | What happens |
|---|---|
| **T+0** | All four agents start. |
| **T+0 → T+60 min** | **Round 1.** CX2 ships cities + matrix + generator first. CX1 builds the optimiser on a tiny local fixture. CX3 builds the UI on mock JSON. CC builds config, baseline, metrics and the API skeleton. |
| **T+60** | **Checkpoint 1.** Tell CC: *"Checkpoint 1: merge feat/data-forecast."* Then tell CX1 and CX3: *"Run `git merge main` and continue."* |
| **T+60 → T+2h45** | **Round 2.** CX1 tunes the optimiser on the real scenario. CX2 builds compliance + forecasting. CX3 builds the map, the AI toggle and the truck drawer. CC builds all endpoints and tests. |
| **T+2h45** | **Checkpoint 2 (core backend done).** Tell CC: *"Checkpoint 2: merge feat/optimizer and feat/data-forecast, run all tests, push."* |
| **T+2h45 → T+4h45** | **Round 3: P1 features.** Re-plan, pooling, forecast page, driver view. CX3 switches from mocks to the real API. |
| **T+4h45** | **Checkpoint 3.** Tell CC: *"Checkpoint 3: merge feat/frontend, run the full demo end to end, push."* |
| **Morning** | Rehearse the demo script in `docs/FEATURES.md`. Fix only what breaks the script. |

## Rules for every agent

1. Only edit files you own (`docs/CONTRACT.md` §8).
2. Commit on your branch after every working step: `git add -A && git commit -m "<what works>"`.
3. Never rename fields in the contract. If you're blocked by the contract, stop and say so.
4. P0 first. Don't start P1 until all your P0 items pass their checks.
5. Don't push to `main`. Only CC merges into `main` and pushes.

## If something goes wrong

- **OSRM is down or rate-limited:** the haversine × 1.3 fallback is already in the plan. Keep going.
- **OR-Tools finds no solution:** CX1 widens time windows by 20% and retries. If it still fails, it uses the greedy chain planner fallback described in its prompt.
- **An agent hits its usage limit:** move its remaining P0 items to CC, and skip that agent's P1.
- **Merge conflict:** CC resolves it, keeping the file owner's version.
