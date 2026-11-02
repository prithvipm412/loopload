#!/usr/bin/env python3
"""Exercise CONTRACT §7 against a running API. Regenerates and replans demo data."""
import argparse
import json
import math
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

METRICS = ('total_km', 'loaded_km', 'empty_km', 'empty_pct', 'revenue_inr',
           'diesel_inr', 'toll_inr', 'profit_inr', 'co2_kg', 'loads_served',
           'loads_total', 'trucks_used', 'idle_h')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def metrics(value):
    require(isinstance(value, dict), 'metrics must be an object')
    require(all(number(value.get(k)) for k in METRICS), 'missing or invalid metric')
    require(0 <= value['empty_pct'] <= 100, 'empty percentage outside 0–100')
    require(0 <= value['loads_served'] <= value['loads_total'], 'invalid served load count')
    require(value['co2_kg'] >= 0, 'negative CO2')


def compliance(value):
    require(isinstance(value, dict) and isinstance(value.get('ok'), bool), 'invalid compliance result')
    require(isinstance(value.get('issues'), list), 'missing compliance issues')
    codes = {'EWAY_MISSING', 'EWAY_EXPIRES', 'EWAY_VEHICLE_MISMATCH',
             'OVER_CAPACITY', 'TRUCK_TYPE_MISMATCH', 'PERMIT_EXPIRED'}
    for issue in value['issues']:
        require(issue.get('code') in codes and issue.get('severity') in ('error', 'warning')
                and isinstance(issue.get('message'), str), 'invalid compliance issue')


def scenario(value):
    require(isinstance(value, dict), 'scenario must be an object')
    for key in ('cities', 'owners', 'trucks', 'loads'):
        require(isinstance(value.get(key), list) and value[key], f'missing scenario {key}')
    require(len(value['cities']) == 25, 'expected 25 hubs')
    require(isinstance(value.get('week_start'), str), 'missing week_start')
    require(any(t['id'] == 'T01' for t in value['trucks']), 'missing T01')


def truck_plan(value):
    require(isinstance(value, dict) and isinstance(value.get('truck_id'), str), 'invalid TruckPlan')
    require(isinstance(value.get('legs'), list), 'missing legs')
    metrics(value.get('totals'))
    for leg in value['legs']:
        require(leg.get('kind') in ('loaded', 'empty'), 'invalid leg kind')
        require(leg.get('truck_id') == value['truck_id'], 'leg belongs to another truck')
        require(number(leg.get('depart_h')) and number(leg.get('arrive_h'))
                and leg['depart_h'] <= leg['arrive_h'], 'invalid leg times')
        require(isinstance(leg.get('path'), list) and len(leg['path']) >= 2, 'missing map path')
        compliance(leg.get('compliance'))


def plan(value, mode=None):
    require(isinstance(value, dict) and isinstance(value.get('plan_id'), str), 'missing plan ID')
    require(value.get('mode') in ('baseline', 'ai', 'ai_solo'), 'invalid plan mode')
    if mode:
        require(value['mode'] == mode, f'expected {mode} plan')
    require(number(value.get('solve_time_s')) and value['solve_time_s'] >= 0, 'invalid solve time')
    require(isinstance(value.get('created_at'), str), 'missing created_at')
    require(isinstance(value.get('unassigned_loads'), list), 'missing unassigned_loads')
    require(isinstance(value.get('trucks'), list), 'missing truck plans')
    for truck in value['trucks']:
        truck_plan(truck)
    metrics(value.get('metrics'))


def forecasts(value):
    require(isinstance(value, list) and value, 'forecast list is empty')
    for lane in value:
        require(all(isinstance(lane.get(k), str) for k in ('lane', 'origin', 'destination', 'commodity')),
                'invalid forecast lane')
        require(len(lane.get('history', [])) == 104, 'expected 104 history weeks')
        require(lane.get('forecast'), 'missing forecast points')
        require(number(lane.get('change_pct')), 'invalid forecast change')
        for point in lane['forecast']:
            require(all(number(point.get(k)) for k in ('loads', 'lower', 'upper')),
                    'invalid forecast band')
            require(0 <= point['lower'] <= point['loads'] <= point['upper'], 'unordered forecast band')


class Smoke:
    def __init__(self, base_url, timeout):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.errors = []
        self.passed = 0

    def check(self, method, path, validator, body=None):
        label = f'{method} {path}'
        try:
            data = json.dumps(body).encode() if body is not None else None
            request = Request(self.base_url + path, data=data, method=method,
                              headers={'Accept': 'application/json', 'Content-Type': 'application/json'})
            with urlopen(request, timeout=self.timeout) as response:
                require(response.status == 200, f'expected 200, got {response.status}')
                value = json.load(response)
            validator(value)
            self.passed += 1
            print(f'PASS {label}')
            return value
        except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError, IndexError) as error:
            self.errors.append(f'{label}: {error}')
            print(f'FAIL {label}: {error}', file=sys.stderr)
            return None

    def skip(self, label):
        self.errors.append(f'{label}: dependency failed')
        print(f'FAIL {label}: dependency failed', file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://localhost:8000', help='API origin without /api')
    parser.add_argument('--timeout', type=float, default=180, help='seconds per request')
    args = parser.parse_args(argv)
    require(urlsplit(args.base_url).scheme in ('http', 'https'), 'base URL must use HTTP(S)')
    require(args.timeout > 0, 'timeout must be positive')
    smoke = Smoke(args.base_url, args.timeout)
    smoke.check('GET', '/api/health', lambda v: require(v == {'ok': True}, 'health is not ok'))
    smoke.check('GET', '/api/scenario', scenario)
    def regenerated(value):
        scenario(value)
        require(len(value['trucks']) == 20 and len(value['loads']) == 140, 'wrong regenerated fleet size')
    current = smoke.check('POST', '/api/scenario/regenerate', regenerated,
                          {'seed': 42, 'n_trucks': 20, 'n_loads': 140})
    plans = {}
    for mode in ('baseline', 'ai', 'ai_solo'):
        result = smoke.check('POST', '/api/plan', lambda v, m=mode: plan(v, m), {'mode': mode})
        if result is not None:
            plans[mode] = result
            pid = quote(result['plan_id'], safe='')
            smoke.check('GET', f'/api/plan/{pid}',
                        lambda v, expected=result: (plan(v), require(v['plan_id'] == expected['plan_id'], 'plan ID changed')))
    def compare(value):
        metrics(value['baseline']); metrics(value['ai'])
        require(all(number(value['delta'].get(k)) for k in
                    ('empty_km', 'empty_pct', 'profit_inr', 'co2_kg', 'loads_served')), 'invalid comparison delta')
    comparison = smoke.check('GET', '/api/compare', compare)
    all_forecasts = smoke.check('GET', '/api/forecast', forecasts)
    if all_forecasts:
        lane = all_forecasts[0]['lane']
        smoke.check('GET', '/api/forecast?' + urlencode({'lane': lane}),
                    lambda v: (forecasts(v), require(len(v) == 1 and v[0]['lane'] == lane, 'lane filter failed')))
    else:
        smoke.skip('GET /api/forecast?lane=...')
    smoke.check('GET', '/api/hot-lanes?n=8',
                lambda v: (forecasts(v), require(len(v) == 8, 'expected eight hot lanes')))
    hero_week = None
    if current and 'ai' in plans:
        ai = plans['ai']
        query = urlencode({'plan_id': ai['plan_id']})
        def week(value):
            require(value['truck']['id'] == 'T01', 'wrong truck')
            truck_plan(value['plan'])
            require(value['plan']['truck_id'] == 'T01', 'wrong truck plan')
        hero_week = smoke.check('GET', '/api/trucks/T01/week?' + query, week)
        owner = next(t['owner_id'] for t in current['trucks'] if t['id'] == 'T01')
        def owner_summary(value):
            require(value['owner']['id'] == owner, 'wrong owner')
            metrics(value['metrics'])
            require(isinstance(value.get('trucks'), list), 'missing owner truck plans')
            for truck in value['trucks']:
                truck_plan(truck)
        smoke.check('GET', f'/api/owners/{quote(owner, safe="")}/summary?' + query, owner_summary)
        served = [leg['load_id'] for truck in ai['trucks'] for leg in truck['legs'] if leg['kind'] == 'loaded']
        if served:
            smoke.check('GET', f'/api/compliance/{quote(served[0], safe="")}?' + query, compliance)
        else:
            smoke.skip('GET /api/compliance/{load_id}: AI served no loads')
        ids = {load['id'] for load in current['loads']}
        new_load = dict(current['loads'][0])
        new_load['id'] = next(f'L{i:03d}' for i in range(999, 0, -1) if f'L{i:03d}' not in ids)
        events = [dict(type='delay_truck', truck_id='T01', delay_h=2, at_h=0),
                  dict(type='cancel_load', load_id=served[-1] if served else current['loads'][-1]['id'], at_h=0),
                  dict(type='new_load', load=new_load, at_h=0)]
        for event in events:
            smoke.check('POST', '/api/replan', plan, {'plan_id': ai['plan_id'], 'event': event})
    else:
        for label in ('GET /api/trucks/T01/week', 'GET /api/owners/{owner_id}/summary',
                      'GET /api/compliance/{load_id}', 'POST /api/replan'):
            smoke.skip(label)
    print('\nDemo summary')
    for mode in ('baseline', 'ai'):
        if mode in plans:
            p = plans[mode]; m = p['metrics']
            print(f"{mode:8} empty {m['empty_pct']:.1f}% | profit INR {m['profit_inr']:,.0f} | "
                  f"CO2 {m['co2_kg']:,.1f} kg | loads {m['loads_served']}/{m['loads_total']} | "
                  f"solve {p['solve_time_s']:.2f}s")
    if hero_week:
        print("T01's AI week:")
        for leg in hero_week['plan']['legs']:
            print(f"  {leg['seq']:2} {leg['kind']:6} {leg['from']}→{leg['to']} "
                  f"{leg['depart_h']:.1f}–{leg['arrive_h']:.1f}h "
                  f"{leg.get('load_id') or '-'} ({leg['distance_km']:.1f} km)")
        if not hero_week['plan']['legs']:
            print('  No trips assigned')
    print(f'\n{smoke.passed} checks passed; {len(smoke.errors)} failed.')
    if smoke.errors:
        for error in smoke.errors:
            print(f'  {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, KeyError, TypeError, StopIteration) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        sys.exit(1)
