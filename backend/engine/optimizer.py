"""Profit-oriented full-truckload routing with optional pickup/delivery pairs."""
from copy import deepcopy
from datetime import datetime, timezone
import math
import time
from uuid import uuid4

from ortools.constraint_solver import pywrapcp, routing_enums_pb2


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
    # Idle time includes service, waiting and unused time across the entire horizon.
    busy = sum(l['arrive_h'] - l['depart_h'] for l in legs)
    return dict(total_km=round(total, 1), loaded_km=round(loaded, 1),
                empty_km=round(total-loaded, 1), empty_pct=round(100*(total-loaded)/total, 1) if total else 0.0,
                revenue_inr=revenue, diesel_inr=diesel, toll_inr=toll, profit_inr=revenue-diesel-toll,
                co2_kg=round(sum(l['co2_kg'] for l in legs), 1),
                loads_served=len({l['load_id'] for l in legs if l['load_id']}), loads_total=loads_total,
                trucks_used=len({l['truck_id'] for l in legs}),
                idle_h=round(max(0, sum(max(0, config['horizon_h']-t['available_from_h']) for t in trucks)-busy), 1))


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


def _routing(scenario, matrix, config, seconds, widen=False):
    trucks, loads = scenario['trucks'], scenario['loads']
    if not trucks:
        return []
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
    def distance(a, b):
        return distances[cities[nodes[a][0]]][cities[nodes[b][0]]]
    def cost(a, b):
        a, b = manager.IndexToNode(a), manager.IndexToNode(b)
        return 0 if a == end or b == end else round(distance(a, b)*cost_per_km)
    def transit(a, b):
        a, b = manager.IndexToNode(a), manager.IndexToNode(b)
        if a == end or b == end:
            return nodes[a][1]
        drive = durations[cities[nodes[a][0]]][cities[nodes[b][0]]]
        return math.ceil(_elapsed(drive, config)*60) + nodes[a][1]
    routing.SetArcCostEvaluatorOfAllVehicles(routing.RegisterTransitCallback(cost))
    routing.AddDimension(routing.RegisterTransitCallback(transit), horizon, horizon, False, 'Time')
    dimension = routing.GetDimensionOrDie('Time')
    def demand(index):
        node = nodes[manager.IndexToNode(index)]
        return 0 if node[2] is None else (1 if node[3] else -1)
    routing.AddDimensionWithVehicleCapacity(routing.RegisterUnaryTransitCallback(demand), 0, [1]*len(trucks), True, 'Capacity')
    solver = routing.solver()
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
        solver.Add(dimension.CumulVar(p) <= dimension.CumulVar(d))
        penalty = round(load['freight_inr'] * load.get('probability', 1))
        routing.AddDisjunction([p], penalty)
        routing.AddDisjunction([d], 0)
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromMilliseconds(max(1, round(seconds*1000)))
    solution = routing.SolveWithParameters(params)
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
                if pickup <= load['pickup_end_h'] and arrive <= load['deliver_by_h'] and finish <= config['horizon_h']:
                    score = load['freight_inr']*load.get('probability',1)-km*cost
                    loaded_km = matrix['distance_km'][lookup[load['origin']]][lookup[load['destination']]]
                    if score-loaded_km*cost > 0:
                        candidates.append((score, load['id'], load, pickup, depart, arrive, finish))
            if not candidates:
                break
            _, _, load, pickup, depart, arrive, finish = max(candidates, key=lambda c:(c[0], c[1]))
            if city != load['origin']:
                legs.append(_leg(truck,len(legs),city,load['origin'],now,pickup,matrix,config))
            legs.append(_leg(truck,len(legs),load['origin'],load['destination'],depart,arrive,matrix,config,load))
            city, now = load['destination'], finish
            remaining.remove(load)
        routes.append(dict(truck_id=truck['id'],legs=legs))
    return routes


def plan_optimized(scenario: dict, matrix: dict, config: dict, pooled: bool = True,
                   time_limit_s: int | None = None) -> dict:
    """Plan compatible FTL chains; solo owners claim loads in scenario owner order."""
    started = time.monotonic()
    scenario = deepcopy(scenario)
    seconds = time_limit_s if time_limit_s is not None else config['solver_time_limit_s']
    fallback = False
    def solve(part, budget):
        nonlocal fallback
        routes = _routing(part,matrix,config,budget)
        if routes is None:
            routes = _routing(part,matrix,config,budget,True)
            if routes is not None and not _valid(routes,part,config):
                routes = None
        if routes is None:
            fallback = True
            routes = _greedy(part,matrix,config)
        return routes
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
            result = solve(part,seconds/max(1,len(owner_ids)))
            routes.extend(result)
            served = {l['load_id'] for r in result for l in r['legs'] if l['load_id']}
            remaining = [l for l in remaining if l['id'] not in served]
    return _finish(routes,scenario,config,started,'ai' if pooled else 'ai_solo', 'greedy_fallback' if fallback else None)
