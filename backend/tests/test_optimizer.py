"""CX1 optimizer checks, self-contained until the data branch is merged."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import time

import pytest

from app.config import CONFIG
from engine import optimizer

FIXTURES = Path(__file__).parent / 'fixtures'


def fixture_data():
    return tuple(json.loads((FIXTURES / name).read_text()) for name in ('cx1_scenario.json', 'cx1_matrix.json'))


def assert_feasible(plan, scenario, matrix, config=CONFIG):
    loads = {l['id']: l for l in scenario['loads']}
    trucks = {t['id']: t for t in scenario['trucks']}
    cities = {c: i for i,c in enumerate(matrix['cities'])}
    assigned = set()
    fields = {'truck_id','seq','kind','from','to','load_id','depart_h','arrive_h',
              'distance_km','revenue_inr','diesel_inr','toll_inr','co2_kg','path'}
    for route in plan['trucks']:
        truck = trucks[route['truck_id']]
        city, now = truck['start_city'], truck['available_from_h']
        for seq, leg in enumerate(route['legs']):
            assert fields <= leg.keys()
            assert leg['seq'] == seq
            assert leg['truck_id'] == truck['id']
            assert leg['from'] == city
            assert leg['depart_h'] >= now-1e-5
            drive = matrix['duration_h'][cities[leg['from']]][cities[leg['to']]]
            assert leg['arrive_h']-leg['depart_h'] >= optimizer._elapsed(drive, config)-1e-5
            assert leg['arrive_h'] <= config['horizon_h']
            assert leg['path'] == []
            now = leg['arrive_h']
            city = leg['to']
            if leg['kind'] == 'loaded':
                load = loads[leg['load_id']]
                assert load['id'] not in assigned
                assigned.add(load['id'])
                assert (leg['from'],leg['to']) == (load['origin'],load['destination'])
                assert truck['type'] == load['truck_type']
                assert truck['capacity_t'] >= load['weight_t']
                pickup = leg['depart_h']-config['load_unload_h']
                assert load['pickup_start_h']-1e-5 <= pickup <= load['pickup_end_h']+1e-5
                assert leg['arrive_h'] <= load['deliver_by_h']+1e-5
                assert leg['revenue_inr'] == load['freight_inr']
                now += config['load_unload_h']
            else:
                assert leg['load_id'] is None
                assert leg['revenue_inr'] == 0
    assert assigned.isdisjoint(plan['unassigned_loads'])
    assert assigned | set(plan['unassigned_loads']) == set(loads)
    assert plan['metrics']['loads_served'] == len(assigned)


@pytest.fixture(scope='module')
def planned():
    scenario, matrix = fixture_data()
    started = time.monotonic()
    plan = optimizer.plan_optimized(scenario,matrix,CONFIG)
    return scenario,matrix,plan,time.monotonic()-started


def test_fixture_feasibility_and_runtime(planned):
    scenario,matrix,plan,elapsed = planned
    assert elapsed < 15
    assert plan['mode'] == 'ai'
    assert plan['plan_id'].startswith('ai-')
    assert plan['metrics']['loads_served'] >= 10
    assert_feasible(plan,scenario,matrix)


def test_chains_reduce_empty_distance(planned):
    scenario,matrix,plan,_ = planned
    cities = {c:i for i,c in enumerate(matrix['cities'])}
    trucks = {t['id']:t for t in scenario['trucks']}
    # Same served jobs, each dispatched from home and returned home immediately.
    naive_empty = sum(matrix['distance_km'][cities[trucks[r['truck_id']]['home_city']]][cities[l['from']]]
                      + matrix['distance_km'][cities[l['to']]][cities[trucks[r['truck_id']]['home_city']]]
                      for r in plan['trucks'] for l in r['legs'] if l['kind']=='loaded')
    assert plan['metrics']['empty_km'] < naive_empty
    print(f"Fixture: {plan['metrics']['loads_served']}/20 loads; empty {plan['metrics']['empty_km']:.1f} km vs home-return {naive_empty:.1f} km; profit INR {plan['metrics']['profit_inr']}; solve {plan['solve_time_s']:.2f}s")


def test_incompatible_and_impossible_loads_are_dropped():
    scenario,matrix = fixture_data()
    scenario['loads'] = deepcopy(scenario['loads'][:3])
    scenario['loads'][0]['weight_t'] = 100
    scenario['loads'][1]['truck_type'] = 'reefer'
    scenario['loads'][2]['deliver_by_h'] = 0
    original = deepcopy(scenario)
    plan = optimizer.plan_optimized(scenario,matrix,CONFIG,time_limit_s=.1)
    assert plan['metrics']['loads_served'] == 0
    assert scenario == original


def test_empty_fleet_and_loads():
    scenario,matrix = fixture_data()
    scenario['loads'] = []
    plan = optimizer.plan_optimized(scenario,matrix,CONFIG,time_limit_s=.1)
    assert plan['metrics']['profit_inr'] == 0
    assert len(plan['trucks']) == 5
    scenario['trucks'] = []
    assert optimizer.plan_optimized(scenario,matrix,CONFIG,time_limit_s=.1)['trucks'] == []


def test_greedy_fallback_is_feasible(monkeypatch):
    scenario,matrix = fixture_data()
    calls = []
    def fail(*args, **kwargs):
        calls.append(args)
        return None
    monkeypatch.setattr(optimizer, '_routing', fail)
    plan = optimizer.plan_optimized(scenario,matrix,CONFIG,time_limit_s=.1)
    assert len(calls) == 2
    assert plan['solver'] == 'greedy_fallback'
    assert plan['metrics']['loads_served'] > 0
    assert_feasible(plan,scenario,matrix)


@pytest.mark.skipif(importlib.util.find_spec('data.generator') is None, reason='Data branch not merged yet')
def test_generated_seed_42():
    from data.generator import generate_scenario
    from data.distance import get_matrix
    scenario = generate_scenario(42)
    matrix = get_matrix(scenario['cities'])
    plan = optimizer.plan_optimized(scenario,matrix,CONFIG)
    assert_feasible(plan,scenario,matrix)


def test_solo_does_not_share_loads():
    scenario,matrix = fixture_data()
    plan = optimizer.plan_optimized(scenario,matrix,CONFIG,pooled=False,time_limit_s=1)
    assert plan['mode'] == 'ai_solo'
    assert_feasible(plan,scenario,matrix)
    assert len(plan['trucks']) == len(scenario['trucks'])


def test_available_from_is_respected():
    scenario,matrix = fixture_data()
    scenario['trucks'] = [dict(scenario['trucks'][0], available_from_h=100)]
    scenario['loads'] = [dict(scenario['loads'][4], pickup_start_h=0, pickup_end_h=20)]
    plan = optimizer.plan_optimized(scenario,matrix,CONFIG,time_limit_s=.1)
    assert plan['metrics']['loads_served'] == 0
    assert_feasible(plan,scenario,matrix)
