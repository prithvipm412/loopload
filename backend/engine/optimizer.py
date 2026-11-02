"""Profit-oriented full-truckload routing with optional pickup/delivery pairs."""
from copy import deepcopy
from datetime import datetime, timezone
import math
import time
from uuid import uuid4

from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from ortools.sat.python import cp_model


def _elapsed(drive, config):
    limit = config['max_drive_h_per_day']
    return drive + math.floor(drive / limit) * (24 - limit)


def _leg(truck, seq, origin, destination, depart, arrive, matrix, config, load=None):
    indices = {city: i for i, city in enumerate(matrix['cities'])}
    km = matrix['distance_km'][indices[origin]][indices[destination]]
    litres = km / config['mileage_kmpl']
    return dict(truck_id=truck['id'], seq=seq, kind='loaded' if load else 'empty',
                **{'from': origin, 'to': destination}, load_id=load['id'] if load else None,
                depart_h=round(depart, 6), arrive_h=round(arrive, 6), distance_km=round(km, 1),
                revenue_inr=load['freight_inr'] if load else 0,
                diesel_inr=round(litres * config['diesel_inr_per_l']),
                toll_inr=round(km * config['toll_inr_per_km']),
                co2_kg=round(litres * config.get('co2_kg_per_l', 2.68), 1), path=[])


def _metrics(legs, loads_total, trucks, config):
    total = sum(l['distance_km'] for l in legs)
    loaded = sum(l['distance_km'] for l in legs if l['kind'] == 'loaded')
    revenue = sum(l['revenue_inr'] for l in legs)
    diesel = sum(l['diesel_inr'] for l in legs)
    toll = sum(l['toll_inr'] for l in legs)
    idle = 0.0
    for truck in trucks:
        route = sorted((l for l in legs if l['truck_id'] == truck['id']), key=lambda l: l['seq'])
        idle += sum(max(0, b['depart_h']-a['arrive_h']) for a,b in zip(route,route[1:]))
    return dict(total_km=round(total, 1), loaded_km=round(loaded, 1),
                empty_km=round(total-loaded, 1), empty_pct=round(100*(total-loaded)/total, 1) if total else 0.0,
                revenue_inr=revenue, diesel_inr=diesel, toll_inr=toll, profit_inr=revenue-diesel-toll,
                co2_kg=round(sum(l['co2_kg'] for l in legs), 1),
                loads_served=len({l['load_id'] for l in legs if l['load_id']}), loads_total=loads_total,
                trucks_used=len({l['truck_id'] for l in legs}),
                idle_h=round(idle, 1))


def _finish(routes, scenario, config, started, mode='ai', solver=None):
    trucks = {t['id']: t for t in scenario['trucks']}
    legs = [l for r in routes for l in r['legs']]
    served = {l['load_id'] for l in legs if l['load_id']}
    for route in routes:
        route['totals'] = _metrics(route['legs'], len(scenario['loads']), [trucks[route['truck_id']]], config)
    plan = dict(plan_id='ai-'+uuid4().hex[:8], mode=mode,
                created_at=datetime.now(timezone.utc).isoformat(), solve_time_s=round(time.monotonic()-started, 3),
                trucks=routes, unassigned_loads=[l['id'] for l in scenario['loads'] if l['id'] not in served],
                metrics=_metrics(legs, len(scenario['loads']), scenario['trucks'], config))
    if solver:
        plan['solver'] = solver
    return plan


def _chain_seed(scenario, matrix, config):
    """Build a small pool of promising chains to warm-start the routing search."""
    cities = {c:i for i,c in enumerate(matrix['cities'])}
    distance = matrix['distance_km']
    travel = [[math.ceil(_elapsed(d,config)*60)/60 for d in row] for row in matrix['duration_h']]
    cost = config['diesel_inr_per_l']/config['mileage_kmpl']+config['toll_inr_per_km']
    service = math.ceil(config['load_unload_h']*60)/60
    loads = scenario['loads']
    candidates = []
    for v, truck in enumerate(scenario['trucks']):
        compatible = [(i,l,cities[l['origin']],cities[l['destination']]) for i,l in enumerate(loads)
                      if l['truck_type']==truck['type'] and l['weight_t']<=truck['capacity_t']]
        beam = [(0, 0, truck['available_from_h'], cities[truck['start_city']], ())]
        seen = {}
        for depth in range(6):
            expanded = []
            for profit, empty, now, city, path in beam:
                for i, load, origin, destination in compatible:
                    if i in path or distance[city][origin] > config.get('optimizer_seed_radius_km', 500):
                        continue
                    pickup = max(now+travel[city][origin], math.ceil(load['pickup_start_h']*60)/60)
                    arrival = pickup+service+travel[origin][destination]
                    finish = arrival+service
                    if pickup > load['pickup_end_h'] or arrival > load['deliver_by_h'] or finish > config['horizon_h']:
                        continue
                    gain = load['freight_inr']-round(distance[city][origin]*cost)-round(distance[origin][destination]*cost)
                    next_path = path+(i,)
                    state = (profit+gain, empty+distance[city][origin], finish, destination, next_path)
                    key = (destination, frozenset(next_path))
                    if key not in seen or finish < seen[key][2]:
                        seen[key] = state
                        expanded.append(state)
            if not expanded:
                break
            # Keep both high-profit chains and fast chains with room for a next load.
            best_profit = sorted(expanded,key=lambda x:(-x[0],x[1],x[2]))[:12]
            best_rate = sorted(expanded,key=lambda x:(-x[0]/max(1,x[2]-truck['available_from_h']),x[1]))[:12]
            beam = list({x[4]:x for x in best_profit+best_rate}.values())
        for state in sorted(seen.values(),key=lambda x:(-x[0],x[1]))[:40]:
            if state[0]>0:
                candidates.append((v,state))
    if not candidates:
        return [[] for _ in scenario['trucks']]
    model = cp_model.CpModel()
    choices = [model.NewBoolVar(f'chain_{i}') for i in range(len(candidates))]
    per_vehicle, per_load = {}, {}
    for choice,(v,state) in zip(choices,candidates):
        per_vehicle.setdefault(v,[]).append(choice)
        for i in state[4]:
            per_load.setdefault(i,[]).append(choice)
    for group in list(per_vehicle.values())+list(per_load.values()):
        model.AddAtMostOne(group)
    if config.get('optimizer_empty_km_budget') is not None:
        model.Add(sum(math.ceil(state[1]*1000)*choice for choice,(_,state) in zip(choices,candidates))
                  <= math.floor(config['optimizer_empty_km_budget']*1000))
    model.Maximize(sum(round(state[0])*choice for choice,(_,state) in zip(choices,candidates)))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = .4
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    status = solver.Solve(model)
    result = [[] for _ in scenario['trucks']]
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for choice,(v,state) in zip(choices,candidates):
            if solver.Value(choice):
                result[v] = list(state[4])
    return result


def _routing(scenario, matrix, config, seconds, widen=False):
    routing_started = time.monotonic()
    trucks, loads = scenario['trucks'], scenario['loads']
    if not trucks or not loads:
        return [dict(truck_id=t['id'], legs=[]) for t in trucks]
    cities = {c: i for i, c in enumerate(matrix['cities'])}
    # Node metadata: city, service minutes, load index, pickup flag.
    service = math.ceil(config['load_unload_h']*60)
    nodes = [(t['start_city'], 0, None, False) for t in trucks]
    for i, load in enumerate(loads):
        nodes.extend([(load['origin'], service, i, True), (load['destination'], service, i, False)])
    end = len(nodes)
    nodes.append((None, 0, None, False))
    manager = pywrapcp.RoutingIndexManager(len(nodes), len(trucks), list(range(len(trucks))), [end]*len(trucks))
    routing = pywrapcp.RoutingModel(manager)
    horizon = math.floor(config['horizon_h']*60)
    cost_per_km = config['diesel_inr_per_l']/config['mileage_kmpl'] + config['toll_inr_per_km']
    distances, durations = matrix['distance_km'], matrix['duration_h']
    # Native matrix evaluators avoid Python callbacks in the local-search hot loop.
    node_cities = [cities[n[0]] if n[0] is not None else None for n in nodes]
    costs, times = [], []
    for a, ca in enumerate(node_cities):
        costs.append([0 if ca is None or cb is None else round(distances[ca][cb]*cost_per_km)
                      for cb in node_cities])
        times.append([nodes[a][1] + (0 if ca is None or cb is None else
                      math.ceil(_elapsed(durations[ca][cb], config)*60)) for cb in node_cities])
    nudge = config.get('optimizer_home_nudge', 0.0)
    if nudge:
        for vehicle, truck in enumerate(trucks):
            home = cities[truck['home_city']]
            vehicle_costs = [row[:] for row in costs]
            for a, ca in enumerate(node_cities[:-1]):
                vehicle_costs[a][end] = round(distances[ca][home]*cost_per_km*nudge)
            routing.SetArcCostEvaluatorOfVehicle(routing.RegisterTransitMatrix(vehicle_costs), vehicle)
    else:
        routing.SetArcCostEvaluatorOfAllVehicles(routing.RegisterTransitMatrix(costs))
    routing.AddDimension(routing.RegisterTransitMatrix(times), horizon, horizon, False, 'Time')
    dimension = routing.GetDimensionOrDie('Time')
    def demand(index):
        node = nodes[manager.IndexToNode(index)]
        return 0 if node[2] is None else (1 if node[3] else -1)
    routing.AddDimensionWithVehicleCapacity(routing.RegisterUnaryTransitCallback(demand), 0, [1]*len(trucks), True, 'Capacity')
    solver = routing.solver()
    if config.get('optimizer_empty_km_budget') is not None:
        # Only pickup -> its delivery carries freight; all other city moves are empty.
        empty_costs = []
        for a, ca in enumerate(node_cities):
            empty_costs.append([0 if ca is None or cb is None or
                               (nodes[a][3] and nodes[a][2] == nodes[b][2])
                               else math.ceil(distances[ca][cb]*1000)
                               for b, cb in enumerate(node_cities)])
        budget = max(0, math.floor(config['optimizer_empty_km_budget']*1000))
        routing.AddDimension(routing.RegisterTransitMatrix(empty_costs), 0, budget, True, 'EmptyKm')
        empty_dimension = routing.GetDimensionOrDie('EmptyKm')
        solver.Add(sum(empty_dimension.CumulVar(routing.End(v)) for v in range(len(trucks))) <= budget)
    for v, truck in enumerate(trucks):
        available = math.ceil(truck['available_from_h']*60)
        if available > horizon:
            return None
        dimension.CumulVar(routing.Start(v)).SetRange(max(0, available), horizon)
        routing.AddVariableMinimizedByFinalizer(dimension.CumulVar(routing.Start(v)))
        routing.AddVariableMinimizedByFinalizer(dimension.CumulVar(routing.End(v)))
    for i, load in enumerate(loads):
        p, d = [manager.NodeToIndex(len(trucks)+2*i+j) for j in (0, 1)]
        lower, upper = math.ceil(load['pickup_start_h']*60), math.floor(load['pickup_end_h']*60)
        deadline = math.floor(load['deliver_by_h']*60)
        if widen:
            expansion = math.ceil((upper-lower)*.2)
            lower, upper, deadline = max(0, lower-expansion), upper+expansion, math.ceil(deadline*1.2)
        if lower > min(horizon, upper) or deadline < 0 or upper < 0:
            solver.Add(routing.ActiveVar(p) == 0)
            solver.Add(routing.ActiveVar(d) == 0)
        else:
            dimension.CumulVar(p).SetRange(max(0, lower), min(horizon, upper))
            dimension.CumulVar(d).SetRange(0, min(horizon, deadline))
        allowed = [v for v,t in enumerate(trucks) if t['type']==load['truck_type'] and t['capacity_t']>=load['weight_t']]
        routing.VehicleVar(p).SetValues(allowed+[-1])
        routing.AddPickupAndDelivery(p, d)
        solver.Add(routing.VehicleVar(p) == routing.VehicleVar(d))
        solver.Add(routing.ActiveVar(p) == routing.ActiveVar(d))
        # Capacity one enforces delivery before any further pickup.
        solver.Add(dimension.CumulVar(p) <= dimension.CumulVar(d))
        penalty = round(load['freight_inr'] * load.get('probability', 1))
        routing.AddDisjunction([p], (penalty+1)//2)
        routing.AddDisjunction([d], penalty//2)
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = getattr(routing_enums_pb2.FirstSolutionStrategy,
        config.get('optimizer_first_solution', 'PATH_CHEAPEST_ARC'))
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.log_search = config.get('optimizer_log_search', False)
    seed = _chain_seed(scenario, matrix, config)
    node_routes = [[len(trucks)+2*i+j for i in route for j in (0,1)] for route in seed]
    params.time_limit.FromMilliseconds(max(1, int((seconds-(time.monotonic()-routing_started)-.02)*1000)))
    routing.CloseModelWithParameters(params)
    initial = routing.ReadAssignmentFromRoutes(node_routes, True)
    solution = (routing.SolveFromAssignmentWithParameters(initial, params) if initial is not None
                else routing.SolveWithParameters(params))
    if solution is None:
        return None
    routes = []
    for v, truck in enumerate(trucks):
        legs, index = [], routing.Start(v)
        while not routing.IsEnd(index):
            nxt = solution.Value(routing.NextVar(index))
            a, b = manager.IndexToNode(index), manager.IndexToNode(nxt)
            if b != end:
                city_a, city_b = nodes[a][0], nodes[b][0]
                load = loads[nodes[a][2]] if nodes[a][3] and nodes[a][2] == nodes[b][2] else None
                if city_a != city_b or load:
                    depart = (solution.Min(dimension.CumulVar(index))+nodes[a][1])/60
                    arrive = solution.Min(dimension.CumulVar(nxt))/60
                    legs.append(_leg(truck, len(legs), city_a, city_b, depart, arrive, matrix, config, load))
            index = nxt
        routes.append(dict(truck_id=truck['id'], legs=legs))
    return routes


def _valid(routes, scenario, config):
    """A widened search may suggest routes but must never relax published promises."""
    loads = {l['id']: l for l in scenario['loads']}
    for route in routes:
        for leg in route['legs']:
            if leg['load_id']:
                load = loads[leg['load_id']]
                pickup = leg['depart_h']-config['load_unload_h']
                if not (load['pickup_start_h']-1e-5 <= pickup <= load['pickup_end_h']+1e-5 and leg['arrive_h'] <= load['deliver_by_h']+1e-5):
                    return False
    return True


def _greedy(scenario, matrix, config):
    remaining = list(scenario['loads'])
    lookup = {city: i for i,city in enumerate(matrix['cities'])}
    cost = config['diesel_inr_per_l']/config['mileage_kmpl']+config['toll_inr_per_km']
    routes = []
    empty_left = config.get('optimizer_empty_km_budget')
    def travel(a,b):
        return _elapsed(matrix['duration_h'][lookup[a]][lookup[b]], config)
    for truck in scenario['trucks']:
        city, now, legs = truck['start_city'], truck['available_from_h'], []
        while True:
            candidates = []
            for load in remaining:
                if load['truck_type'] != truck['type'] or load['weight_t'] > truck['capacity_t']:
                    continue
                pickup = max(now+travel(city, load['origin']), load['pickup_start_h'])
                depart = pickup+config['load_unload_h']
                arrive = depart+travel(load['origin'],load['destination'])
                finish = arrive+config['load_unload_h']
                km = matrix['distance_km'][lookup[city]][lookup[load['origin']]]
                if empty_left is not None and km > empty_left+1e-9:
                    continue
                if pickup <= load['pickup_end_h'] and arrive <= load['deliver_by_h'] and finish <= config['horizon_h']:
                    score = load['freight_inr']*load.get('probability',1)-km*cost
                    loaded_km = matrix['distance_km'][lookup[load['origin']]][lookup[load['destination']]]
                    if score-loaded_km*cost > 0:
                        candidates.append((score, load['id'], load, pickup, depart, arrive, finish))
            if not candidates:
                break
            _, _, load, pickup, depart, arrive, finish = max(candidates, key=lambda c:(c[0], c[1]))
            if empty_left is not None:
                empty_left -= matrix['distance_km'][lookup[city]][lookup[load['origin']]]
            if city != load['origin']:
                legs.append(_leg(truck,len(legs),city,load['origin'],now,pickup,matrix,config))
            legs.append(_leg(truck,len(legs),load['origin'],load['destination'],depart,arrive,matrix,config,load))
            city, now = load['destination'], finish
            remaining.remove(load)
        routes.append(dict(truck_id=truck['id'],legs=legs))
    return routes


def plan_optimized(scenario: dict, matrix: dict, config: dict, pooled: bool = True,
                   time_limit_s: int | None = None) -> dict:
    """Maximize profit within the demo's >=50% empty-km reduction target.

    The default empty-distance allowance is 49% of baseline empty km. Override
    ``optimizer_empty_km_budget`` with a kilometre value, or None to disable it.
    Solo owners claim loads in scenario order and share the allowance by fleet size.
    """
    started = time.monotonic()
    scenario = deepcopy(scenario)
    config = dict(config)
    if 'optimizer_empty_km_budget' not in config:
        # The demo's stated goal is >=50% fewer empty km than today's dispatch.
        # Keep the rupee objective intact, subject to that fleet-wide constraint.
        from engine.baseline import plan_baseline
        baseline = plan_baseline(scenario, matrix, config)
        config['optimizer_empty_km_budget'] = baseline['metrics']['empty_km']*.49
    seconds = time_limit_s if time_limit_s is not None else config['solver_time_limit_s']
    deadline = started + max(.001, seconds) - .10
    fallback = False
    def solve(part, budget, solve_config=None):
        solve_config = config if solve_config is None else solve_config
        nonlocal fallback
        inactive = [t for t in part['trucks'] if t['available_from_h'] >= config['horizon_h']]
        if inactive:
            active_ids = {t['id'] for t in inactive}
            active = dict(part, trucks=[t for t in part['trucks'] if t['id'] not in active_ids])
        else:
            active = part
        remaining_time = lambda: max(.001, min(budget, deadline-time.monotonic()))
        routes = _routing(active,matrix,solve_config,remaining_time())
        if routes is None:
            routes = _routing(active,matrix,solve_config,remaining_time(),True)
            if routes is not None and not _valid(routes,part,solve_config):
                routes = None
        if routes is None:
            fallback = True
            routes = _greedy(active,matrix,solve_config)
        by_id = {r['truck_id']: r for r in routes}
        return [by_id.get(t['id'],dict(truck_id=t['id'],legs=[])) for t in part['trucks']]
    if pooled:
        routes = solve(scenario,seconds)
    else:
        routes, remaining = [], list(scenario['loads'])
        owner_ids = list(dict.fromkeys([o['id'] for o in scenario['owners']]+[t['owner_id'] for t in scenario['trucks']]))
        for owner in owner_ids:
            trucks = [t for t in scenario['trucks'] if t['owner_id']==owner]
            if not trucks:
                continue
            part = dict(scenario,trucks=trucks,loads=remaining)
            owner_config = dict(config)
            if config.get('optimizer_empty_km_budget') is not None:
                owner_config['optimizer_empty_km_budget'] *= len(trucks)/max(1,len(scenario['trucks']))
            result = solve(part,seconds/max(1,len(owner_ids)),owner_config)
            routes.extend(result)
            served = {l['load_id'] for r in result for l in r['legs'] if l['load_id']}
            remaining = [l for l in remaining if l['id'] not in served]
    return _finish(routes,scenario,config,started,'ai' if pooled else 'ai_solo', 'greedy_fallback' if fallback else None)
