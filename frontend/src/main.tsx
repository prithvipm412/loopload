import React, { useEffect, useState, useRef } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Routes,
  Route,
  NavLink,
  Link,
  useParams,
} from "react-router-dom";
import { motion, AnimatePresence, animate } from "framer-motion";
import {
  ArrowUpRight,
  ArrowDownRight,
  ArrowRight,
  Truck as TruckIcon,
  Sparkles,
  Play,
  Pause,
  X,
  Check,
  ShieldCheck,
  AlertTriangle,
  MapPin,
  Layers,
  ChartNoAxesCombined,
  Navigation,
  RotateCcw,
  ChevronRight,
  Leaf,
  Fuel,
  Route as RouteIcon,
  IndianRupee,
  Package,
  Clock,
} from "lucide-react";
import {
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ComposedChart,
  Area,
  Line,
} from "recharts";
import { api, mockMode } from "./api";
import type { Scenario, Plan, Compare, Forecast, Leg, Truck } from "./types";
import { money, num, compact, dayTime } from "./format";
import RouteMap from "./RouteMap";
import PlanHighlights from "./PlanHighlights";
import { i18n, type Language } from "./i18n";
import "./styles.css";
const PLAN_TRANSITION_SECONDS = 0.9;
function Counter({
  value,
  format = num,
}: {
  value: number;
  format?: (v: number) => string;
}) {
  const [v, setV] = useState(value);
  const current = useRef(value);
  useEffect(() => {
    const c = animate(current.current, value, {
      duration: PLAN_TRANSITION_SECONDS,
      ease: "easeInOut",
      onUpdate: (next) => {
        current.current = next;
        setV(next);
      },
    });
    return () => c.stop();
  }, [value]);
  return <>{format(v)}</>;
}
function App() {
  const [data, setData] = useState<{
    scenario: Scenario;
    baseline: Plan;
    ai: Plan;
    compare: Compare;
  } | null>(null);
  const [toast, setToast] = useState("");
  const [error, setError] = useState(false);
  const loadStarted = useRef(false);
  const notify = (s: string) => setToast(s);
  const [fallbackActive, setFallbackActive] = useState(false);
  const load = async () => {
    setError(false);
    try {
      const [scenario, baseline, ai] = await Promise.all([
        api.scenario(),
        api.plan("baseline"),
        api.plan("ai"),
      ]);
      // Compare can take 15+ seconds on a cold backend. Keep the skeleton up.
      // Fetch after plans are cached to avoid requesting duplicate solves.
      const compare = await api.compare();
      setData({ scenario, baseline, ai, compare });
    } catch {
      setError(true);
    }
  };
  useEffect(() => {
    const fallback = (e: Event) => {
      setFallbackActive(true);
      notify((e as CustomEvent<string>).detail);
    };
    window.addEventListener("api-fallback", fallback);
    if (!loadStarted.current) {
      loadStarted.current = true;
      load();
    }
    return () => window.removeEventListener("api-fallback", fallback);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 5000);
    return () => clearTimeout(t);
  }, [toast]);
  return (
    <BrowserRouter>
      <header>
        <Link className="brand" to="/">
          <span className="brand-mark">
            <RouteIcon size={24} />
          </span>
          <span>
            LoopLoad<small>Every leg loaded</small>
          </span>
        </Link>
        <nav>
          <NavLink data-testid="nav-dashboard" to="/" end>
            <Layers size={15} /> Fleet planner
          </NavLink>
          <NavLink data-testid="nav-forecast" to="/forecast">
            <ChartNoAxesCombined size={15} /> Demand forecast
          </NavLink>
          <NavLink data-testid="nav-driver" to="/driver/T01">
            <TruckIcon size={15} /> Driver view
          </NavLink>
        </nav>
        <div className="header-meta">
          <span className="status-dot" />
          {mockMode
            ? "Demo workspace"
            : fallbackActive
              ? "Demo fallback"
              : "Live workspace"}
          <span className="avatar">RT</span>
        </div>
      </header>
      {data ? (
        <Routes>
          <Route
            path="/"
            element={
              <Dashboard
                {...data}
                notify={notify}
                onPlanUpdate={(next) =>
                  setData((current) =>
                    current
                      ? {
                          ...current,
                          ai: next,
                          compare: {
                            baseline: current.baseline.metrics,
                            ai: next.metrics,
                            delta: {
                              empty_km:
                                next.metrics.empty_km -
                                current.baseline.metrics.empty_km,
                              empty_pct:
                                next.metrics.empty_pct -
                                current.baseline.metrics.empty_pct,
                              profit_inr:
                                next.metrics.profit_inr -
                                current.baseline.metrics.profit_inr,
                              co2_kg:
                                next.metrics.co2_kg -
                                current.baseline.metrics.co2_kg,
                              loads_served:
                                next.metrics.loads_served -
                                current.baseline.metrics.loads_served,
                            },
                          },
                        }
                      : current,
                  )
                }
              />
            }
          />
          <Route path="/forecast" element={<ForecastPage {...data} />} />
          <Route path="/driver/:truckId" element={<DriverPage {...data} />} />
          <Route
            path="*"
            element={
              <div className="empty-state">
                Page not found. <Link to="/">Return to fleet planner</Link>
              </div>
            }
          />
        </Routes>
      ) : (
        <div
          className="loading"
          data-testid="loading-skeleton"
          aria-busy="true"
        >
          {error ? (
            <>
              <h2>Unable to load the workspace</h2>
              <button onClick={load}>Try again</button>
            </>
          ) : (
            <>
              <div className="skeleton title-skeleton" />
              <div className="skeleton map-skeleton" />
              <p>Preparing your fleet’s week…</p>
            </>
          )}
        </div>
      )}
      <AnimatePresence>
        {toast && (
          <motion.div
            role="status"
            data-testid={
              toast.startsWith("Re-planned") ? "replan-toast" : undefined
            }
            className="toast"
            initial={{ y: 30, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <ShieldCheck size={18} />
            {toast}
            <button
              aria-label="Dismiss notification"
              onClick={() => setToast("")}
            >
              <X size={16} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
      <footer>
        Built for the road ahead.
        <span>9–15 November 2026 · All times IST · Demo estimates</span>
      </footer>
    </BrowserRouter>
  );
}
interface Data {
  scenario: Scenario;
  baseline: Plan;
  ai: Plan;
  compare: Compare;
}
function Dashboard({
  scenario,
  baseline,
  ai,
  compare,
  notify,
  onPlanUpdate,
}: Data & { notify: (s: string) => void; onPlanUpdate: (plan: Plan) => void }) {
  const [mode, setMode] = useState<"baseline" | "ai">("baseline");
  const [aiPlan, setAiPlan] = useState(ai);
  const [previous, setPrevious] = useState<Plan>();
  const [blend, setBlend] = useState(1);
  const [selected, setSelected] = useState("");
  const [time, setTime] = useState(8);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(4);
  const [owner, setOwner] = useState("");
  const [busy, setBusy] = useState(false);
  const [changed, setChanged] = useState<string[]>([]);
  const plan = mode === "baseline" ? baseline : aiPlan;
  const heroIds = new Set(scenario.loads.slice(0, 4).map((l) => l.id));
  const heroTruckId =
    [...aiPlan.trucks].sort(
      (a, b) =>
        b.legs.filter((l) => l.load_id && heroIds.has(l.load_id)).length -
        a.legs.filter((l) => l.load_id && heroIds.has(l.load_id)).length,
    )[0]?.truck_id ?? "T01";
  const heroWeek = plan.trucks.find((t) => t.truck_id === heroTruckId);
  const loadedHeroLegs =
    heroWeek?.legs.filter(
      (l) => l.kind === "loaded" && l.load_id && heroIds.has(l.load_id),
    ).length ?? 0;
  useEffect(() => {
    if (!changed.length) return;
    const timer = setTimeout(() => setChanged([]), 3000);
    return () => clearTimeout(timer);
  }, [changed]);
  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    const id = setInterval(() => {
      const now = performance.now();
      setTime((t) => (t + ((now - last) / 1000) * speed) % 168);
      last = now;
    }, 70);
    return () => clearInterval(id);
  }, [playing, speed]);
  const switchPlan = (next: "baseline" | "ai") => {
    if (next === mode) return;
    const target = next === "baseline" ? baseline : aiPlan;
    // Reversing an in-flight switch preserves the visible mixture.
    const start =
      previous?.plan_id === target.plan_id && blend < 1 ? 1 - blend : 0;
    setPrevious(plan);
    setBlend(start);
    setMode(next);
  };
  useEffect(() => {
    if (!previous) return;
    const c = animate(blend, 1, {
      duration: PLAN_TRANSITION_SECONDS * (1 - blend),
      ease: "easeInOut",
      onUpdate: setBlend,
      onComplete: () => setPrevious(undefined),
    });
    return () => c.stop();
    // Start once per destination plan; animation frames must not restart it.
  }, [plan]);
  const replan = async () => {
    const leg = aiPlan.trucks
      .find((t) => t.truck_id === heroTruckId)
      ?.legs.find((l) => l.load_id && l.depart_h >= time);
    if (!leg?.load_id) {
      notify(
        "No future hero-truck pickup at this time. Scrub earlier in the week.",
      );
      return;
    }
    setBusy(true);
    try {
      const next = await api.replan(aiPlan.plan_id, {
        type: "cancel_load",
        load_id: leg.load_id,
        at_h: time,
      });
      const ids =
        next.changed_trucks ??
        next.trucks
          .filter(
            (t) =>
              JSON.stringify(t.legs) !==
              JSON.stringify(
                aiPlan.trucks.find((p) => p.truck_id === t.truck_id)?.legs,
              ),
          )
          .map((t) => t.truck_id);
      setPrevious(plan);
      setBlend(0);
      setAiPlan(next);
      onPlanUpdate(next);
      setMode("ai");
      setChanged(ids);
      notify(
        `Re-planned in ${num(next.solve_time_s, 1)} s · ${ids.length} truck${ids.length === 1 ? "" : "s"} updated`,
      );
    } finally {
      setBusy(false);
    }
  };
  const waste = (p: Plan) =>
    p.trucks
      .flatMap((t) => t.legs)
      .filter((l) => l.kind === "empty")
      .reduce((s, l) => s + l.diesel_inr, 0);
  const metrics = [
    {
      label: "Empty km",
      testId: "counter-empty-km",
      value: plan.metrics.empty_km,
      base: baseline.metrics.empty_km,
      format: (v: number) => `${num(v)} km`,
      good: "down",
      icon: RouteIcon,
    },
    {
      label: "Wasted diesel",
      testId: "counter-diesel",
      value: waste(plan),
      base: waste(baseline),
      format: compact,
      good: "down",
      icon: Fuel,
    },
    {
      label: "CO2 per load",
      testId: "counter-co2",
      value:
        (plan.metrics.co2_kg_per_load ??
          (plan.metrics.loads_served
            ? plan.metrics.co2_kg / plan.metrics.loads_served
            : 0)) / 1000,
      base:
        (baseline.metrics.co2_kg_per_load ??
          (baseline.metrics.loads_served
            ? baseline.metrics.co2_kg / baseline.metrics.loads_served
            : 0)) / 1000,
      format: (v: number) => `${num(v, 2)} t`,
      subtext: `Total CO2 ${num(plan.metrics.co2_kg / 1000, 1)} t`,
      good: "down",
      icon: Leaf,
    },
    {
      label: "Freight revenue",
      testId: "counter-revenue",
      value: plan.metrics.revenue_inr,
      base: baseline.metrics.revenue_inr,
      format: compact,
      good: "up",
      icon: IndianRupee,
    },
    {
      label: "Loaded distance",
      testId: "counter-loaded-pct",
      value: 100 - plan.metrics.empty_pct,
      base: 100 - baseline.metrics.empty_pct,
      format: (v: number) => `${num(v, 1)}%`,
      good: "up",
      icon: TruckIcon,
    },
    {
      label: "Loads served",
      testId: "counter-loads",
      value: plan.metrics.loads_served,
      base: baseline.metrics.loads_served,
      format: num,
      good: "up",
      icon: Package,
    },
  ];
  return (
    <main className="dashboard-page">
      <section className="page-heading">
        <div>
          <div className="eyebrow">
            FLEET OPERATIONS <span>/</span> WEEK 46
          </div>
          <h1>A better week for every truck.</h1>
          <p>Less empty running. More earning. One connected fleet.</p>
        </div>
        <div className="week-tag">
          <Clock size={16} />
          <span>
            09 – 15 Nov, 2026<small>7-day planning horizon</small>
          </span>
        </div>
      </section>
      <section className="workspace-toolbar">
        <div className="segmented">
          <button
            data-testid="mode-toggle-baseline"
            className={mode === "baseline" ? "active" : ""}
            onClick={() => switchPlan("baseline")}
          >
            Today <span>Baseline</span>
          </button>
          <button
            data-testid="mode-toggle-ai"
            className={mode === "ai" ? "active" : ""}
            onClick={() => switchPlan("ai")}
          >
            <Sparkles size={14} /> LoopLoad AI
          </button>
        </div>
        <div className="toolbar-actions">
          <span data-testid="solve-time-badge" className="solve-badge">
            <span className="status-dot" />
            Solved in {num(plan.solve_time_s, 1)} s
          </span>
          <button
            data-testid="ai-plan-button"
            className="primary"
            onClick={() => switchPlan("ai")}
          >
            <Sparkles size={16} /> AI Plan <ArrowRight size={16} />
          </button>
        </div>
      </section>
      <motion.div
        className="dashboard-grid"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45 }}
      >
        <div className="map-column">
          <section className="map-panel">
            <div className="map-title">
              <div>
                <span className="eyebrow">THE CONNECTED FLEET</span>
                <h2>
                  {mode === "baseline"
                    ? "Same roads. Missed opportunities."
                    : "Every destination is a new beginning."}
                </h2>
              </div>
              <span className="map-pill">
                {scenario.cities.length} hubs · {scenario.trucks.length} trucks
              </span>
            </div>
            <RouteMap
              scenario={scenario}
              plan={plan}
              previous={previous}
              blend={blend}
              time={time}
              owner={owner}
              changed={changed}
              onSelect={setSelected}
            />
            <div className="map-legend">
              <span>
                <i className="line green" />
                Loaded trip
              </span>
              <span>
                <i className="line coral" />
                Empty running
              </span>
              <span>
                <i className="truck-dot" />
                Truck in motion
              </span>
            </div>
          </section>
          <div className="map-story panel">
            <span className="story-icon">
              <Sparkles size={19} />
            </span>
            <div>
              <strong>
                {mode === "ai"
                  ? loadedHeroLegs === 4
                    ? "A full loop. A fuller week."
                    : "A week with room to earn."
                  : "The return journey is the opportunity."}
              </strong>
              <p>
                {mode === "ai"
                  ? loadedHeroLegs === 4
                    ? `Tiruppur → Delhi → Jaipur → Nagpur → home. Four loaded legs on ${heroTruckId}.`
                    : `${loadedHeroLegs} hero-chain loads planned for ${heroTruckId}. Open the truck’s week.`
                  : "Plan the whole week to turn empty return trips into paying loads."}
              </p>
            </div>
            <button
              aria-label="Open hero truck"
              onClick={() => setSelected(heroTruckId)}
            >
              <ArrowUpRight size={18} />
            </button>
          </div>

          <section className="timeline panel">
            <div className="timeline-top">
              <button
                data-testid="timeline-play"
                className="play-button"
                aria-label={playing ? "Pause playback" : "Play playback"}
                onClick={() => setPlaying(!playing)}
              >
                {playing ? <Pause size={15} /> : <Play size={15} />}
              </button>
              <strong>{dayTime(time)}</strong>
              <span className="muted">Week playback</span>
              <div className="speed-control">
                {[1, 4, 16].map((s) => (
                  <button
                    className={speed === s ? "chosen" : ""}
                    key={s}
                    onClick={() => setSpeed(s)}
                  >
                    {s}×
                  </button>
                ))}
              </div>
              <button aria-label="Reset timeline" onClick={() => setTime(0)}>
                <RotateCcw size={14} />
              </button>
            </div>
            <input
              data-testid="timeline-scrubber"
              aria-label="Week time"
              type="range"
              min="0"
              max="168"
              step="0.1"
              value={time}
              onChange={(e) => setTime(+e.target.value)}
            />
            <div className="day-labels">
              {[
                "Mon 09",
                "Tue 10",
                "Wed 11",
                "Thu 12",
                "Fri 13",
                "Sat 14",
                "Sun 15",
              ].map((d) => (
                <span key={d}>{d}</span>
              ))}
            </div>
          </section>
          <div className="simulation panel">
            <div>
              <RotateCcw size={17} />
              <span>
                <strong>Plans change. Keep moving.</strong>
                <small>Cancel a future load and watch the fleet adapt.</small>
              </span>
            </div>
            <button
              data-testid="cancel-load-button"
              disabled={busy}
              onClick={replan}
            >
              {busy ? "Re-planning…" : "Simulate: cancel a load"}
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
        <aside className="impact-panel panel">
          <div className="section-title">
            <div>
              <span className="eyebrow">THE WEEK, AT A GLANCE</span>
              <h2>Your fleet’s impact</h2>
            </div>
            <span className={`mode-badge ${mode}`}>
              {mode === "ai" ? "AI plan" : "Baseline"}
            </span>
          </div>
          <div className="metric-grid">
            {metrics.map((m) => {
              const delta = m.value - m.base;
              const better = m.good === "down" ? delta < 0 : delta > 0;
              return (
                <div className="metric" data-metric={m.testId} key={m.label}>
                  <span className="metric-label">
                    <m.icon size={14} />
                    {m.label}
                  </span>
                  <strong data-testid={m.testId}>
                    <Counter value={m.value} format={m.format} />
                  </strong>
                  {m.subtext && (
                    <small className="metric-detail">{m.subtext}</small>
                  )}
                  <small
                    className={
                      delta === 0
                        ? "delta"
                        : better
                          ? "delta good"
                          : "delta bad"
                    }
                  >
                    {delta === 0 ? (
                      "Baseline reference"
                    ) : (
                      <>
                        {delta < 0 ? (
                          <ArrowDownRight size={11} />
                        ) : (
                          <ArrowUpRight size={11} />
                        )}{" "}
                        {m.testId === "counter-loads"
                          ? `${delta > 0 ? "+" : ""}${num(delta)} vs today`
                          : `${num((Math.abs(delta) / Math.max(1, m.base)) * 100, 1)}% vs today`}
                      </>
                    )}
                  </small>
                </div>
              );
            })}
          </div>
          <PlanHighlights plan={plan} />
          <Comparison compare={compare} />
          <div className="truck-list-heading">
            <h3>
              Your fleet <span>{plan.trucks.length}</span>
            </h3>
            <span className="muted">Loaded share</span>
          </div>
          <div className="truck-list">
            {plan.trucks.map((tp) => {
              const t = scenario.trucks.find((t) => t.id === tp.truck_id)!;
              return (
                <button
                  data-testid={`truck-row-${t.id}`}
                  className={`truck-row ${changed.includes(t.id) ? "changed" : ""}`}
                  key={t.id}
                  onClick={() => setSelected(t.id)}
                >
                  <span className="truck-icon">
                    <TruckIcon size={16} />
                  </span>
                  <span className="truck-info">
                    <strong>
                      {t.id}
                      <small>
                        {t.home_city} · {t.capacity_t} t
                      </small>
                    </strong>
                    <span className="mini-bar">
                      <i
                        style={{
                          width: `${tp.totals.total_km ? 100 - tp.totals.empty_pct : 0}%`,
                        }}
                      />
                    </span>
                  </span>
                  <span>
                    {num(tp.totals.total_km ? 100 - tp.totals.empty_pct : 0)}%
                  </span>
                  <ChevronRight size={14} />
                </button>
              );
            })}
          </div>
        </aside>
      </motion.div>
      <Pooling
        scenario={scenario}
        ai={aiPlan}
        plan={plan}
        baseline={baseline}
        owner={owner}
        setOwner={setOwner}
      />
      <AnimatePresence>
        {selected && (
          <TruckDrawer
            scenario={scenario}
            plan={plan}
            id={selected}
            onClose={() => setSelected("")}
          />
        )}
      </AnimatePresence>
    </main>
  );
}
function Comparison({ compare }: Pick<Data, "compare">) {
  const carbon = (m: Compare["ai"]) =>
    (m.co2_kg_per_load ?? (m.loads_served ? m.co2_kg / m.loads_served : 0)) /
    1000;
  const rows = [
    {
      label: "Empty km",
      baseline: compare.baseline.empty_km,
      ai: compare.ai.empty_km,
      format: (n: number) => `${num(n)} km`,
    },
    {
      label: "Profit ₹",
      baseline: compare.baseline.profit_inr,
      ai: compare.ai.profit_inr,
      format: compact,
    },
    {
      label: "CO2 per load",
      baseline: carbon(compare.baseline),
      ai: carbon(compare.ai),
      format: (n: number) => `${num(n, 2)} t`,
    },
  ];
  return (
    <section className="comparison" aria-label="Baseline and AI comparison">
      <div className="comparison-heading">
        <h3>One week. A better outcome.</h3>
        <div className="comparison-legend">
          <span>
            <i />
            Baseline
          </span>
          <span>
            <i />
            AI
          </span>
        </div>
      </div>
      <div className="comparison-cards">
        {rows.map((row) => {
          const max = Math.max(Math.abs(row.baseline), Math.abs(row.ai), 1);
          return (
            <article className="comparison-stat" key={row.label}>
              <h4>{row.label}</h4>
              <strong
                className="baseline-value"
                aria-label={`Baseline ${row.label}: ${row.format(row.baseline)}`}
              >
                {row.format(row.baseline)}
              </strong>
              <span className="value-track" aria-hidden="true">
                <i
                  style={{ width: `${(Math.abs(row.baseline) / max) * 100}%` }}
                />
              </span>
              <strong
                className="ai-value"
                aria-label={`AI ${row.label}: ${row.format(row.ai)}`}
              >
                {row.format(row.ai)}
              </strong>
              <span className="value-track ai" aria-hidden="true">
                <i style={{ width: `${(Math.abs(row.ai) / max) * 100}%` }} />
              </span>
            </article>
          );
        })}
      </div>
    </section>
  );
}
function TruckDrawer({
  scenario,
  plan,
  id,
  onClose,
}: {
  scenario: Scenario;
  plan: Plan;
  id: string;
  onClose: () => void;
}) {
  const truck = scenario.trucks.find((t) => t.id === id);
  const tp = plan.trucks.find((t) => t.truck_id === id);
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const before = document.activeElement as HTMLElement;
    close.current?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const nodes = Array.from(
          document.querySelectorAll<HTMLElement>(".drawer button,.drawer a"),
        );
        if (e.shiftKey && document.activeElement === nodes[0]) {
          e.preventDefault();
          nodes.at(-1)?.focus();
        } else if (!e.shiftKey && document.activeElement === nodes.at(-1)) {
          e.preventDefault();
          nodes[0]?.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", key);
      document.body.style.overflow = overflow;
      before?.focus();
    };
  }, []);
  if (!truck || !tp) return null;
  const city = (c: string) =>
    scenario.cities.find((x) => x.id === c)?.name || c;
  return (
    <>
      <motion.div
        className="overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />
      <motion.aside
        data-testid="truck-drawer"
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label={`${truck.id} truck week`}
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", damping: 30, stiffness: 260 }}
      >
        <div className="drawer-heading">
          <span className="eyebrow">TRUCK WEEK · {id}</span>
          <button
            data-testid="truck-drawer-close"
            ref={close}
            aria-label="Close truck drawer"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        <h1>{truck.reg_no}</h1>
        <p>{scenario.owners.find((o) => o.id === truck.owner_id)?.name}</p>
        <div className="truck-details">
          <span>
            <TruckIcon size={16} />
            {truck.type.replace("_", " ")} · {truck.capacity_t} t
          </span>
          <span>
            <Navigation size={16} />
            {truck.driver.name}
          </span>
          <Link to={`/driver/${id}`}>
            Driver view <ArrowUpRight size={13} />
          </Link>
        </div>
        <section className="gantt-section">
          <h3>A week on the road</h3>
          <div className="day-labels">
            {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => (
              <span key={i}>{d}</span>
            ))}
          </div>
          <div className="gantt">
            {tp.legs.map((l) => (
              <div
                title={`${city(l.from)} → ${city(l.to)} · ${dayTime(l.depart_h)}`}
                className={l.kind}
                key={l.seq}
                style={{
                  left: `${(l.depart_h / 168) * 100}%`,
                  width: `${(Math.max(0, Math.min(168, l.arrive_h) - l.depart_h) / 168) * 100}%`,
                }}
              >
                {l.arrive_h - l.depart_h >= 8 ? l.to : ""}
              </div>
            ))}
          </div>
          <div className="chart-legend">
            <span>
              <i style={{ background: "#7FBF9A" }} />
              Loaded
            </span>
            <span>
              <i style={{ background: "#E8857A" }} />
              Empty
            </span>
            <span>
              <i style={{ background: "#E6DCCB" }} />
              Rest / idle
            </span>
          </div>
        </section>
        <div className="leg-list">
          {!tp.legs.length && (
            <p className="rest-gap">No trips assigned this week.</p>
          )}
          {tp.legs.map((leg, i) => (
            <React.Fragment key={leg.seq}>
              {leg.depart_h > (i ? tp.legs[i - 1].arrive_h : 0) && (
                <div className="rest-gap">
                  <Clock size={12} />
                  {num(leg.depart_h - (i ? tp.legs[i - 1].arrive_h : 0), 1)} h
                  rest / idle
                </div>
              )}
              <LegCard leg={leg} scenario={scenario} />
            </React.Fragment>
          ))}
          {(tp.legs.at(-1)?.arrive_h ?? 0) < 168 && (
            <div className="rest-gap">
              <Clock size={12} />
              {num(168 - (tp.legs.at(-1)?.arrive_h ?? 0), 1)} h rest / idle
              through Sunday
            </div>
          )}
        </div>
        <div className="drawer-totals">
          <h3>Week totals</h3>
          <div>
            <span>Distance</span>
            <strong>{num(tp.totals.total_km)} km</strong>
          </div>
          <div>
            <span>Revenue</span>
            <strong>{money(tp.totals.revenue_inr)}</strong>
          </div>
          <div>
            <span>Diesel + tolls</span>
            <strong>{money(tp.totals.diesel_inr + tp.totals.toll_inr)}</strong>
          </div>
          <div className="profit">
            <span>Take-home profit</span>
            <strong>{money(tp.totals.profit_inr)}</strong>
          </div>
        </div>
      </motion.aside>
    </>
  );
}
function LegCard({ leg, scenario }: { leg: Leg; scenario: Scenario }) {
  const cargo = scenario.loads.find((l) => l.id === leg.load_id);
  return (
    <article className="leg-card">
      <div className="leg-title">
        <span className={`leg-number ${leg.kind}`}>{leg.seq + 1}</span>
        <h3>
          {scenario.cities.find((c) => c.id === leg.from)?.name}{" "}
          <ArrowRight size={14} />{" "}
          {scenario.cities.find((c) => c.id === leg.to)?.name}
        </h3>
        <span className={`kind-label ${leg.kind}`}>{leg.kind}</span>
      </div>
      <p>
        {cargo?.commodity || "Empty repositioning"} · {num(leg.distance_km)} km
      </p>
      <div className="leg-times">
        <span>{dayTime(leg.depart_h)}</span>
        <ArrowRight size={13} />
        <span>{dayTime(leg.arrive_h)}</span>
      </div>
      <div className="leg-money">
        <span>
          Revenue<strong>{money(leg.revenue_inr)}</strong>
        </span>
        <span>
          Diesel<strong>{money(leg.diesel_inr)}</strong>
        </span>
        <span>
          Profit
          <strong>
            {money(leg.revenue_inr - leg.diesel_inr - leg.toll_inr)}
          </strong>
        </span>
      </div>
      {leg.reason && (
        <p className="leg-reason">
          <Sparkles size={13} aria-hidden="true" />
          <span>{leg.reason}</span>
        </p>
      )}
      {leg.compliance ? (
        <div
          data-testid="compliance-badge"
          className={`compliance ${leg.compliance.ok && !leg.compliance.issues.length ? "ok" : "warning"}`}
        >
          {leg.compliance.ok && !leg.compliance.issues.length ? (
            <>
              <Check size={13} /> Compliance checked
            </>
          ) : (
            <>
              <AlertTriangle size={14} />
              <span>
                {leg.compliance.issues.map((i) => i.message).join(" · ")}
              </span>
            </>
          )}
        </div>
      ) : (
        <div data-testid="compliance-badge" className="compliance">
          Compliance pending
        </div>
      )}
    </article>
  );
}
function Pooling({
  scenario,
  ai,
  plan,
  baseline,
  owner,
  setOwner,
}: {
  scenario: Scenario;
  ai: Plan;
  plan: Plan;
  baseline: Plan;
  owner: string;
  setOwner: (s: string) => void;
}) {
  const [solo, setSolo] = useState<Plan>();
  const soloStarted = useRef(false);
  const profitDelta = plan.metrics.profit_inr - baseline.metrics.profit_inr;
  useEffect(() => {
    if (!soloStarted.current) {
      soloStarted.current = true;
      api.plan("ai_solo").then(setSolo);
    }
  }, []);
  return (
    <section data-testid="pooling-card" className="pooling panel">
      <div className="pooling-heading">
        <span className="pool-icon">
          <Layers size={20} />
        </span>
        <div>
          <span className="eyebrow">STRONGER TOGETHER</span>
          <h3>Small fleets. Shared possibilities.</h3>
          <p>Pooling connects more loads across owners.</p>
        </div>
      </div>
      <div className="pool-stat">
        <span>Solo owners’ profit</span>
        <strong>{solo ? compact(solo.metrics.profit_inr) : "Loading…"}</strong>
      </div>
      <ArrowRight size={20} color="#B9AC98" />
      <div className="pool-stat">
        <span>Pooled fleet profit</span>
        <strong className="sage">{compact(ai.metrics.profit_inr)}</strong>
      </div>
      <div className="pool-stat profit-gain">
        <span>Profit change vs today</span>
        <strong className={profitDelta >= 0 ? "sage" : ""}>
          {profitDelta === 0
            ? money(0)
            : `${profitDelta > 0 ? "+" : "−"}${compact(Math.abs(profitDelta))}`}
          <small> / week</small>
        </strong>
      </div>
      <div className="pool-stat">
        <span>Profit / active truck</span>
        <strong>
          {money(
            Math.round(
              plan.metrics.profit_inr / Math.max(1, plan.metrics.trucks_used),
            ),
          )}
        </strong>
      </div>
      <label className="owner-filter">
        View on map
        <select
          data-testid="owner-filter"
          aria-label="Filter routes by owner"
          value={owner}
          onChange={(e) => setOwner(e.target.value)}
        >
          <option value="">All owners</option>
          {scenario.owners.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </select>
      </label>
    </section>
  );
}
function ForecastPage({ scenario, ai }: Data) {
  const [lanes, setLanes] = useState<Forecast[]>([]);
  const [selected, setSelected] = useState("");
  const [history, setHistory] = useState<Forecast>();
  useEffect(() => {
    api.hotLanes().then(setLanes);
  }, []);
  useEffect(() => {
    if (!lanes.length) return;
    const lane = selected || lanes[0].lane;
    let active = true;
    api.forecast(lane).then((rows) => {
      if (active) setHistory(rows[0]);
    });
    return () => {
      active = false;
    };
  }, [selected, lanes]);
  const f = history;
  const series = f
    ? [
        ...f.history.slice(-16).map((x) => ({ week: x.week, actual: x.loads })),
        ...(f.history.length
          ? [
              {
                week: f.history.at(-1)!.week,
                predicted: f.history.at(-1)!.loads,
              },
            ]
          : []),
        ...f.forecast.map((x) => ({
          week: x.week,
          predicted: x.loads,
          band: [x.lower, x.upper],
        })),
      ]
    : [];
  return (
    <main>
      <section className="page-heading">
        <div>
          <span className="eyebrow">DEMAND INTELLIGENCE · NEXT FOUR WEEKS</span>
          <h1>Go where the next load is.</h1>
          <p>
            Seasonal signals turn tomorrow’s demand into today’s opportunity.
          </p>
        </div>
        <span className="forecast-badge">
          <Leaf size={16} /> November · peak onion season
        </span>
      </section>
      <div className="forecast-grid">
        <section data-testid="hot-lanes-list" className="panel hot-lanes">
          <span className="eyebrow">NEXT WEEK’S OPPORTUNITIES</span>
          <h2>Hot lanes</h2>
          <p>Ranked by forecast load volume</p>
          {lanes.length ? (
            lanes.map((l) => (
              <button
                className={`lane-row ${(selected || lanes[0].lane) === l.lane ? "selected" : ""}`}
                key={l.lane}
                onClick={() => setSelected(l.lane)}
              >
                <span className="lane-marker">
                  <ArrowUpRight size={18} />
                </span>
                <span>
                  <strong>
                    {l.origin} → {l.destination}
                  </strong>
                  <small>{l.commodity}</small>
                </span>
                <span className="lane-volume">
                  <strong>{num(l.forecast[0]?.loads || 0, 1)}</strong>
                  <small>loads next week</small>
                </span>
                <span
                  className={`lane-change ${l.change_pct < 0 ? "negative" : ""}`}
                >
                  {l.change_pct > 0 ? "+" : ""}
                  {num(l.change_pct, 1)}%
                </span>
              </button>
            ))
          ) : (
            <div className="skeleton" style={{ height: 300, marginTop: 20 }} />
          )}
          <div className="forecast-note">
            <AlertTriangle size={15} />
            Forecast estimates use synthetic seasonal demand. The band shows
            model uncertainty.
          </div>
        </section>
        <div>
          <section
            data-testid="forecast-chart"
            className="panel forecast-chart"
          >
            <div className="section-title">
              <div>
                <span className="eyebrow">DEMAND OUTLOOK</span>
                <h2>
                  {f ? `${f.origin} → ${f.destination}` : "Loading lane…"}
                </h2>
              </div>
              <span className="map-pill">{f?.commodity}</span>
            </div>
            <p>Weekly loads · last 16 weeks and four-week forecast</p>
            <ResponsiveContainer width="100%" height={250}>
              <ComposedChart
                data={series}
                margin={{ top: 25, right: 15, bottom: 0, left: -20 }}
              >
                <CartesianGrid
                  vertical={false}
                  stroke="#EDE5D8"
                  strokeDasharray="3 4"
                />
                <XAxis
                  dataKey="week"
                  tickFormatter={(v) =>
                    new Date(v).toLocaleDateString("en-IN", {
                      month: "short",
                      day: "numeric",
                    })
                  }
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 9, fill: "#7A7064" }}
                  minTickGap={30}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#7A7064" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  labelFormatter={(v) => String(v)}
                  contentStyle={{
                    background: "#FFFDF9",
                    border: "1px solid #E6DCCB",
                    borderRadius: 8,
                    fontSize: 11,
                  }}
                />
                <Area
                  name="Confidence range"
                  dataKey="band"
                  stroke="none"
                  fill="#A99BE0"
                  fillOpacity={0.18}
                  connectNulls
                />
                <Line
                  name="History"
                  dataKey="actual"
                  stroke="#5F91AF"
                  strokeWidth={2.5}
                  dot={false}
                  connectNulls
                />
                <Line
                  name="Forecast"
                  dataKey="predicted"
                  stroke="#8B78C3"
                  strokeWidth={2.5}
                  strokeDasharray="5 4"
                  dot={{ r: 3 }}
                  connectNulls
                />
                <Legend
                  wrapperStyle={{ fontSize: 11 }}
                  formatter={(value) => (
                    <span style={{ color: "#7A7064" }}>{value}</span>
                  )}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </section>
          <section className="map-panel forecast-map">
            <RouteMap
              scenario={scenario}
              plan={{ ...ai, trucks: [] }}
              blend={1}
              time={0}
              owner=""
              changed={[]}
              onSelect={() => {}}
              hot={lanes}
            />
            <div className="map-title">
              <div>
                <span className="eyebrow">FOLLOW THE OPPORTUNITY</span>
                <h2>India’s seasonal freight network</h2>
              </div>
            </div>
            <div className="map-legend">
              <span>
                <i className="line" style={{ borderColor: "#F4B183" }} />
                Arc width = next-week loads
              </span>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
function DriverPage({ scenario, ai }: Data) {
  const { truckId } = useParams();
  const truck = scenario.trucks.find((t) => t.id === truckId);
  const tp = ai.trucks.find((t) => t.truck_id === truckId);
  const [lang, setLang] = useState<Language>("en");
  const text = i18n[lang];
  const city = (id: string) =>
    (text.cities as Record<string, string>)[id] ||
    scenario.cities.find((c) => c.id === id)?.name ||
    id;
  const cargo = (leg: Leg) => {
    const name =
      scenario.loads.find((l) => l.id === leg.load_id)?.commodity || "";
    return (text.commodities as Record<string, string>)[name] || name;
  };
  const localTime = (h: number) =>
    `${text.days[Math.min(6, Math.floor(h / 24))]} ${dayTime(h).split(" ")[1]}`;
  if (!truck || !tp)
    return (
      <main>
        <h1>{text.notFound}</h1>
        <Link to="/">{text.home}</Link>
      </main>
    );
  const next = tp.legs.find((l) => l.kind === "loaded");
  const translated = {
    ...scenario,
    cities: scenario.cities.map((c) => ({ ...c, name: city(c.id) })),
  };
  return (
    <main className="driver-stage">
      <div data-testid="driver-phone" className="phone" lang={lang}>
        <div className="phone-top">
          <span>9:41</span>
          <span className="phone-speaker" />
          <span>5G ▰</span>
        </div>
        <div className="phone-content">
          <div className="driver-brand">
            <span className="brand-mark">
              <RouteIcon size={22} />
            </span>
            <strong>LoopLoad</strong>
            <span className="driver-avatar">{truck.driver.name[0]}</span>
          </div>
          <div className="language-switch">
            {(["en", "hi", "kn", "ta"] as Language[]).map((l) => (
              <button
                key={l}
                data-testid={`lang-${l}`}
                className={lang === l ? "active" : ""}
                onClick={() => setLang(l)}
              >
                {{ en: "EN", hi: "हिंदी", kn: "ಕನ್ನಡ", ta: "தமிழ்" }[l]}
              </button>
            ))}
          </div>
          <p className="driver-greeting">{text.hello}</p>
          <h1>{truck.driver.name}</h1>
          <div className="driver-reg">
            <TruckIcon size={13} />
            {truck.reg_no}
            <span>
              {text.capacity} {truck.capacity_t} {text.tonnes}
            </span>
          </div>
          {!next && (
            <section className="pickup-card driver-empty">
              <Package size={22} />
              <h2>{text.noPickup}</h2>
              <p>{text.noPickupDetail}</p>
            </section>
          )}
          {next && (
            <section className="pickup-card">
              <div className="pickup-eyebrow">
                <span className="status-dot" />
                {text.next}
              </div>
              <h2>
                {city(next.from)}
                <ArrowRight size={18} />
                {city(next.to)}
              </h2>
              <div className="pickup-cargo">
                <Package size={15} />
                <span>
                  {text.cargo}: {cargo(next)}
                </span>
              </div>
              <div className="pickup-times">
                <span>
                  {text.pickup}
                  <strong>{localTime(next.depart_h)}</strong>
                </span>
                <span>
                  {text.delivery}
                  <strong>{localTime(next.arrive_h)}</strong>
                </span>
              </div>
              <div
                data-testid="compliance-badge"
                className={`compliance ${next.compliance?.ok && !next.compliance.issues.length ? "ok" : "warning"}`}
              >
                <ShieldCheck size={13} />
                {next.compliance?.ok && !next.compliance.issues.length
                  ? text.compliance
                  : text.warning}
              </div>
            </section>
          )}
          <div className="driver-section-title">
            <h3>{text.route}</h3>
            <span>
              {num(tp.totals.total_km)} {text.km}
            </span>
          </div>
          <div className="driver-map">
            <RouteMap
              scenario={translated}
              plan={{ ...ai, trucks: [tp] }}
              blend={1}
              time={8}
              owner=""
              changed={[]}
              onSelect={() => {}}
              mini
            />
          </div>
          <h3 className="driver-week-title">{text.week}</h3>
          <div className="driver-week">
            {tp.legs.map((l) => (
              <article key={l.seq}>
                <span className={`week-dot ${l.kind}`} />
                <div>
                  <strong>
                    {city(l.from)} → {city(l.to)}
                  </strong>
                  <small>
                    {localTime(l.depart_h)} ·{" "}
                    {l.kind === "loaded" ? cargo(l) : text.empty}
                  </small>
                  {l.compliance && l.compliance.issues.length > 0 && (
                    <small className="driver-warning">
                      <AlertTriangle size={11} />
                      {text.warning}
                    </small>
                  )}
                </div>
                <span>{l.kind === "loaded" ? text.loaded : text.empty}</span>
              </article>
            ))}
          </div>
          <Link className="driver-back" to="/">
            {text.home}
            <ArrowUpRight size={13} />
          </Link>
        </div>
        <div className="phone-home" />
      </div>
    </main>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
