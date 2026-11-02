"""Build offline UI fixtures from checked-in backend data without changing it.

Baseline uses the backend implementation. AI fixtures use a deterministic beam
search for demo purposes until the real optimizer is integrated. They are not
presented as optimizer validation.
"""
import copy
import json
import pathlib
import sys

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent
BACKEND = ROOT.parent / 'backend'
sys.path.insert(0, str(BACKEND))
from app.config import CONFIG, elapsed_h
from engine.baseline import plan_baseline
from engine.compliance import check_leg
from engine.metrics import compute_metrics, leg_costs


def read(path):
    return json.loads(path.read_text())


scenario = read(BACKEND / 'data/scenario.json')
matrix = read(BACKEND / 'data/matrix.json')
paths = read(BACKEND / 'data/paths.json')
config = {**CONFIG, 'diesel_inr_per_l': read(BACKEND / 'data/assumptions.json')['diesel_inr_per_l']}
index = {city: i for i, city in enumerate(matrix['cities'])}
cities = {city['id']: city for city in scenario['cities']}
loads = {load['id']: load for load in scenario['loads']}
trucks = {truck['id']: truck for truck in scenario['trucks']}


def distance(a, b):
    return matrix['distance_km'][index[a]][index[b]]


def travel(a, b):
    return elapsed_h(matrix['duration_h'][index[a]][index[b]], config)


def leg(truck, seq, a, b, depart, arrive, load=None):
    km = distance(a, b)
    costs = leg_costs(km, config)
    return dict(truck_id=truck['id'], seq=seq, kind='loaded' if load else 'empty',
                **{'from': a}, to=b, load_id=load['id'] if load else None,
                depart_h=round(depart, 1), arrive_h=round(arrive, 1), distance_km=round(km, 1),
                revenue_inr=load['freight_inr'] if load else 0,
                diesel_inr=round(costs['diesel_inr']), toll_inr=round(costs['toll_inr']),
                co2_kg=round(costs['co2_kg'], 1), path=[])


def extension(truck, position, ready, load, seq):
    if truck['type'] != load['truck_type'] or truck['capacity_t'] < load['weight_t']:
        return None
    at_pickup = ready + travel(position, load['origin'])
    start = max(at_pickup, load['pickup_start_h'])
    if start > load['pickup_end_h']:
        return None
    depart = start + config['load_unload_h']
    arrive = depart + travel(load['origin'], load['destination'])
    if arrive + config['load_unload_h'] > 168 or arrive > load['deliver_by_h']:
        return None
    legs = []
    if position != load['origin']:
        legs.append(leg(truck, seq, position, load['origin'], ready, at_pickup))
    legs.append(leg(truck, seq + len(legs), load['origin'], load['destination'], depart, arrive, load))
    return legs, arrive + config['load_unload_h']


def mock_ai(pooled=True):
    used = set()
    result = []
    reg_owner = {t['reg_no']: t['owner_id'] for t in trucks.values()}
    for truck in scenario['trucks']:
        if truck['id'] == 'T01':
            legs, ready, position = [], truck['available_from_h'], truck['start_city']
            for load in scenario['loads'][:4]:
                new, ready = extension(truck, position, ready, load, len(legs))
                legs.extend(new)
                position = load['destination']
                used.add(load['id'])
        else:
            # Each beam state contains (score, position, ready, load IDs, legs).
            beam = [(0, truck['start_city'], truck['available_from_h'], frozenset(), [])]
            best = beam[0]
            for _ in range(5):
                candidates = []
                for score, position, ready, taken, legs in beam:
                    for load in scenario['loads'][4:]:
                        if load['id'] in used or load['id'] in taken:
                            continue
                        # Solo mock uses the bill vehicle's owner as load affinity.
                        bill = load['eway_bill']
                        if not pooled and bill and reg_owner.get(bill['vehicle_reg'], truck['owner_id']) != truck['owner_id']:
                            continue
                        extension_result = extension(truck, position, ready, load, len(legs))
                        if not extension_result:
                            continue
                        new, free = extension_result
                        cost = sum(x['diesel_inr'] + x['toll_inr'] for x in new)
                        empty = sum(x['distance_km'] for x in new if x['kind'] == 'empty')
                        value = score + load['freight_inr'] - cost - empty * 45
                        candidate = (value, load['destination'], free, taken | {load['id']}, legs + new)
                        candidates.append(candidate)
                        if value > best[0]:
                            best = candidate
                if not candidates:
                    break
                beam = sorted(candidates, key=lambda x: (-x[0], x[2], sorted(x[3])))[:12]
            legs = best[4]
            used.update(best[3])
        result.append(dict(truck_id=truck['id'], legs=legs, totals={}))
    return dict(plan_id='ai-demo0042' if pooled else 'ai-solo0042', mode='ai' if pooled else 'ai_solo',
                created_at='2026-11-02T22:40:00+05:30', solve_time_s=8.2,
                trucks=result, unassigned_loads=sorted(set(loads) - used), metrics={})


def finish(plan):
    for tp in plan['trucks']:
        for item in tp['legs']:
            a, b = item['from'], item['to']
            item['path'] = paths.get(f'{a}-{b}') or [[cities[a]['lon'], cities[a]['lat']], [cities[b]['lon'], cities[b]['lat']]]
            item['compliance'] = check_leg(item, loads.get(item['load_id']), trucks[tp['truck_id']], config)
    compute_metrics(plan, scenario)
    reasons={"L001":"Starts in Tiruppur with a confirmed textiles pickup.","L002":"Collects FMCG in Delhi after unloading textiles.","L003":"Links Jaipur to Nagpur with another paying load.","L004":"Carries oranges back to the Tiruppur home hub."}
    for tp in plan['trucks']:
        for item in tp['legs']:
            if tp['truck_id']=='T01':item['reason']=reasons.get(item['load_id'],'Returns home without a matching load.')
        tp['totals']['co2_kg_per_load']=round(tp['totals']['co2_kg']/tp['totals']['loads_served'],2) if tp['totals']['loads_served'] else 0
    plan['metrics']['co2_kg_per_load']=round(plan['metrics']['co2_kg']/plan['metrics']['loads_served'],2) if plan['metrics']['loads_served'] else 0
    if plan['mode']!='baseline':plan['highlights']=['T01: four loaded legs. One loop.',f"{plan['metrics']['loads_served']} loads across {plan['metrics']['trucks_used']} active trucks.",f"{plan['metrics']['empty_pct']}% empty fleet distance."]
    return plan


baseline = plan_baseline(copy.deepcopy(scenario), matrix, config)
baseline.update(plan_id='baseline-demo0042', created_at='2026-11-02T22:40:00+05:30', solve_time_s=0.2)
plans = {'baseline': finish(baseline), 'ai': finish(mock_ai()), 'solo': finish(mock_ai(False))}
compare = dict(baseline=plans['baseline']['metrics'], ai=plans['ai']['metrics'], delta={
    key: round(plans['ai']['metrics'][key] - plans['baseline']['metrics'][key], 1)
    for key in ['empty_km', 'empty_pct', 'profit_inr', 'co2_kg', 'loads_served']})
forecasts = sorted(read(BACKEND / 'forecast/forecast.json'), key=lambda f: -f['forecast'][0]['loads'])
outputs = {'scenario': scenario, 'compare': compare, 'forecast': forecasts,
           **{f'plan_{name}': plan for name, plan in plans.items()}}
for name, data in outputs.items():
    (ROOT / 'src/mocks' / f'{name}.json').write_text(json.dumps(data, indent=2) + '\n')
for name, plan in plans.items():
    print(name, plan['metrics'])
