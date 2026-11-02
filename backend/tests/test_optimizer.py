"""CX1 optimizer checks, self-contained until the data branch is merged."""
from copy import deepcopy
import json
from pathlib import Path
import time

import pytest

from app.config import CONFIG as APP_CONFIG
from engine import optimizer

# API what-if tests mutate the application config; benchmark the contract defaults.
CONFIG = deepcopy(APP_CONFIG)
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


@pytest.fixture(scope='module')
def generated():
    from data.generator import generate_scenario
    from data.distance import get_matrix
    scenario = generate_scenario(42)
    matrix = get_matrix(scenario['cities'])
    started = time.monotonic()
    plan = optimizer.plan_optimized(scenario,matrix,CONFIG)
    return scenario,matrix,plan,time.monotonic()-started


def test_generated_seed_42(generated):
    from engine.baseline import plan_baseline
    from engine.metrics import compute_metrics
    scenario,matrix,plan,elapsed = generated
    baseline = plan_baseline(scenario,matrix,CONFIG)
    assert_feasible(plan,scenario,matrix)
    assert elapsed <= 10
    assert plan['metrics']['empty_km'] <= baseline['metrics']['empty_km']*.5
    assert plan['metrics']['profit_inr'] > baseline['metrics']['profit_inr']
    before = deepcopy(plan)
    assert compute_metrics(plan,scenario) == before['metrics']
    assert [r['totals'] for r in plan['trucks']] == [r['totals'] for r in before['trucks']]
    print(f"Seed 42: baseline empty {baseline['metrics']['empty_km']:.1f} km, profit INR {baseline['metrics']['profit_inr']}; pooled empty {plan['metrics']['empty_km']:.1f} km, profit INR {plan['metrics']['profit_inr']}, {elapsed:.2f}s")


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


def replan_data():
    """A known schedule with one loaded, one empty, then another loaded leg."""
    scenario, _ = fixture_data()
    scenario['cities'] = scenario['cities'][:3]
    scenario['trucks'] = scenario['trucks'][:1]
    scenario['owners'] = scenario['owners'][:1]
    config = dict(CONFIG, horizon_h=24, load_unload_h=1)
    matrix = dict(cities=['TPR','DEL','JAI'],distance_km=[[0,45,90],[45,0,45],[90,45,0]],
                  duration_h=[[0,1,2],[1,0,1],[2,1,0]],source='haversine')
    a = dict(scenario['loads'][0],id='A',origin='TPR',destination='DEL',
             pickup_start_h=1,pickup_end_h=2,deliver_by_h=6,freight_inr=10000)
    b = dict(a,id='B',origin='JAI',destination='TPR',pickup_start_h=6,pickup_end_h=9,deliver_by_h=15)
    scenario['loads'] = [a,b]
    legs = [dict(truck_id='T01',seq=0,kind='loaded',**{'from':'TPR','to':'DEL'},load_id='A',
                 depart_h=2,arrive_h=3,distance_km=45,revenue_inr=10000,diesel_inr=1012,
                 toll_inr=225,co2_kg=30.2,path=[[77.34,11.11],[77.21,28.61]],compliance={'ok':True,'issues':[]}),
            dict(truck_id='T01',seq=1,kind='empty',**{'from':'DEL','to':'JAI'},load_id=None,
                 depart_h=4,arrive_h=5,distance_km=45,revenue_inr=0,diesel_inr=1012,
                 toll_inr=225,co2_kg=30.2,path=[]),
            dict(truck_id='T01',seq=2,kind='loaded',**{'from':'JAI','to':'TPR'},load_id='B',
                 depart_h=7,arrive_h=9,distance_km=90,revenue_inr=10000,diesel_inr=2025,
                 toll_inr=450,co2_kg=60.3,path=[])]
    plan = dict(plan_id='ai-old',mode='ai',trucks=[dict(truck_id='T01',legs=legs)],unassigned_loads=[])
    return scenario,matrix,config,plan


@pytest.mark.parametrize('at', [2.5,4.5,7])
def test_replan_cancellation_preserves_departed_legs(at):
    from engine.replan import replan
    scenario,matrix,config,old = replan_data()
    snapshot = deepcopy((scenario,old))
    frozen = [l for l in old['trucks'][0]['legs'] if l['depart_h'] < at]
    result = replan(old,dict(type='cancel_load',load_id='B',at_h=at),scenario,matrix,config)
    assert result['trucks'][0]['legs'] == frozen
    assert 'B' not in result['unassigned_loads']
    assert result['metrics']['loads_total'] == 1
    assert result['plan_id'] != old['plan_id']
    assert result['replan_of'] == old['plan_id']
    assert result['changed_trucks'] == ['T01']
    assert (scenario,old) == snapshot


def test_replan_inflight_cancellation_completes_delivery():
    from engine.replan import replan
    scenario,matrix,config,old = replan_data()
    result = replan(old,dict(type='cancel_load',load_id='A',at_h=2.5),scenario,matrix,config)
    assert result['trucks'][0]['legs'][0] == old['trucks'][0]['legs'][0]
    assert sum(l['load_id']=='A' for l in result['trucks'][0]['legs']) == 1
    for leg in result['trucks'][0]['legs'][1:]:
        assert leg['depart_h'] >= 4
    assert result['solve_time_s'] <= 5


def test_replan_delayed_truck_cannot_serve_missed_window():
    from engine.replan import replan
    scenario,matrix,config,old = replan_data()
    event = dict(type='delay_truck',truck_id='T01',delay_h=12,at_h=2.5)
    result = replan(old,event,scenario,matrix,config)
    assert result['trucks'][0]['legs'] == old['trucks'][0]['legs'][:1]
    assert result['unassigned_loads'] == ['B']
    assert result['metrics']['loads_served'] == 1
    # A delay beyond the horizon leaves an idle truck, without forcing a fleet fallback.
    event['delay_h'] = 100
    result = replan(old,event,scenario,matrix,config)
    assert result['trucks'][0]['legs'] == old['trucks'][0]['legs'][:1]
    assert 'solver' not in result


def test_replan_new_load_after_inflight_empty_leg():
    from engine.replan import replan
    scenario,matrix,config,old = replan_data()
    new = dict(scenario['loads'][0],id='C',origin='JAI',destination='DEL',
               pickup_start_h=5,pickup_end_h=6,deliver_by_h=12,freight_inr=20000)
    result = replan(old,dict(type='new_load',load=new,at_h=4.5),scenario,matrix,config)
    legs = result['trucks'][0]['legs']
    assert legs[:2] == old['trucks'][0]['legs'][:2]
    assert any(l['load_id']=='C' for l in legs)
    assert all(l['depart_h'] >= 6 for l in legs[2:])
    assert [l['seq'] for l in legs] == list(range(len(legs)))
    assert sum(l['load_id']=='A' for l in legs) == 1
    assert result['metrics']['loads_total'] == 3


def test_seed_42_pooling_profit(generated):
    scenario,matrix,pooled,_ = generated
    solo = optimizer.plan_optimized(scenario,matrix,CONFIG,pooled=False)
    assert_feasible(solo,scenario,matrix)
    assert solo['mode'] == 'ai_solo'
    assert pooled['metrics']['profit_inr'] >= solo['metrics']['profit_inr']
    print(f"Pooling seed 42: pooled INR {pooled['metrics']['profit_inr']}; solo INR {solo['metrics']['profit_inr']}")


def test_replan_short_delay_moves_next_departure():
    from engine.replan import replan
    scenario,matrix,config,old = replan_data()
    result = replan(old,dict(type='delay_truck',truck_id='T01',delay_h=2,at_h=2.5),scenario,matrix,config)
    legs = result['trucks'][0]['legs']
    assert legs[0] == old['trucks'][0]['legs'][0]
    assert any(l['load_id']=='B' for l in legs)
    assert legs[1]['depart_h'] >= 6  # Delivery at 3h, unload until 4h, then delay 2h.


def test_replan_after_week_preserves_all_history():
    from engine.replan import replan
    scenario,matrix,config,old = replan_data()
    result = replan(old,dict(type='cancel_load',load_id='B',at_h=100),scenario,matrix,config)
    assert result['trucks'][0]['legs'] == old['trucks'][0]['legs']
    assert result['changed_trucks'] == []
    assert result['metrics']['loads_served'] == 2


def test_seed_42_replan(generated):
    from engine.replan import replan
    scenario,matrix,old,_ = generated
    cancel = next(l['load_id'] for r in old['trucks'] for l in r['legs']
                  if l['kind']=='loaded' and l['depart_h'] >= 30)
    result = replan(old,dict(type='cancel_load',load_id=cancel,at_h=30),scenario,matrix,CONFIG)
    by_truck = {r['truck_id']:r for r in result['trucks']}
    for route in old['trucks']:
        frozen = [l for l in route['legs'] if l['depart_h'] < 30]
        assert by_truck[route['truck_id']]['legs'][:len(frozen)] == frozen
    revised = dict(scenario,loads=[l for l in scenario['loads'] if l['id'] != cancel])
    assert_feasible(result,revised,matrix)
    assert result['solve_time_s'] <= 5
    assert result['replan_of'] == old['plan_id']
    print(f"Replan seed 42: {result['solve_time_s']:.2f}s, {len(result['changed_trucks'])} trucks changed")
