"""Re-solve future work while preserving every already-departed leg."""
from copy import deepcopy
import math
import time

from engine.optimizer import _finish, plan_optimized


def replan(plan: dict, event: dict, scenario: dict, matrix: dict, config: dict) -> dict:
    """Complete in-flight legs, apply an event, and optimize the remaining week."""
    started = time.monotonic()
    at = event['at_h']
    if not math.isfinite(at) or at < 0:
        raise ValueError('at_h must be a finite nonnegative hour')
    updated = deepcopy(scenario)
    old_routes = {r['truck_id']: r['legs'] for r in plan['trucks']}
    frozen = {t['id']: [deepcopy(l) for l in old_routes.get(t['id'], []) if l['depart_h'] < at]
              for t in updated['trucks']}
    served = {l['load_id'] for legs in frozen.values() for l in legs if l['load_id']}
    for truck in updated['trucks']:
        history = frozen[truck['id']]
        ready = max(at, truck['available_from_h'])
        if history:
            last = history[-1]
            truck['start_city'] = last['to']
            ready = max(ready, last['arrive_h'] + (config['load_unload_h'] if last['kind']=='loaded' else 0))
        truck['available_from_h'] = ready

    kind = event['type']
    if kind == 'cancel_load':
        if event['load_id'] not in {l['id'] for l in updated['loads']}:
            raise ValueError('Unknown load_id')
        # An in-flight consignment must still finish; retain its historical record.
        updated['loads'] = [l for l in updated['loads'] if l['id'] != event['load_id'] or l['id'] in served]
    elif kind == 'delay_truck':
        truck = next((t for t in updated['trucks'] if t['id']==event['truck_id']), None)
        if truck is None:
            raise ValueError('Unknown truck_id')
        delay = event['delay_h']
        if not math.isfinite(delay) or delay < 0:
            raise ValueError('delay_h must be a finite nonnegative duration')
        truck['available_from_h'] += delay
    elif kind == 'new_load':
        load = deepcopy(event['load'])
        if load['id'] in {l['id'] for l in updated['loads']}:
            raise ValueError('New load_id already exists')
        updated['loads'].append(load)
    else:
        raise ValueError(f'Unknown replan event: {kind}')

    remaining = dict(updated, loads=[l for l in updated['loads'] if l['id'] not in served])
    # The demo comparison budget is for the original fleet starts. Recomputing it
    # after a disruption can prevent a reachable job from being completed.
    # An explicitly supplied allowance still applies to the remaining work.
    future_config = dict(config, optimizer_empty_km_budget=config.get('optimizer_empty_km_budget'))
    future = plan_optimized(remaining, matrix, future_config, pooled=plan['mode']!='ai_solo', time_limit_s=5)
    future_routes = {r['truck_id']: r['legs'] for r in future['trucks']}
    routes, changed = [], []
    def schedule(legs):
        return [(l['kind'],l['from'],l['to'],l['load_id'],l['depart_h'],l['arrive_h']) for l in legs]
    for truck in scenario['trucks']:
        tid = truck['id']
        history = frozen[tid]
        suffix = future_routes.get(tid, [])
        for i, leg in enumerate(suffix, start=len(history)):
            leg['seq'] = i
        legs = history + suffix
        routes.append(dict(truck_id=tid, legs=legs))
        if schedule(legs) != schedule(old_routes.get(tid, [])):
            changed.append(tid)
    # Use original starts when computing whole-week totals, including frozen history.
    metrics_scenario = dict(updated, trucks=deepcopy(scenario['trucks']))
    result = _finish(routes, metrics_scenario, config, started, future['mode'], future.get('solver'))
    result.update(replan_of=plan['plan_id'], changed_trucks=changed)
    return result
