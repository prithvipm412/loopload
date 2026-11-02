#!/usr/bin/env python3
"""Write a print-friendly demo/carbon_report.html using API plans or JSON fixtures.

Usage: python3 scripts/carbon_report.py
       python3 scripts/carbon_report.py --baseline baseline.json --ai ai.json
       python3 scripts/carbon_report.py --fixtures frontend/src/mocks --offline

Diesel litres = total_km / mileage_kmpl (contract assumption: 4 km/L).
CO2 uses the plans' co2_kg metric; savings are signed baseline minus AI.
This is a demo estimate, not a carbon-credit or lifecycle assessment.
"""
import argparse
from datetime import datetime, timezone
from html import escape
import json
import math
from pathlib import Path
import sys
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT=ROOT/'demo/carbon_report.html'


def numeric(value, label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    return float(value)


def plan_metrics(plan):
    if not isinstance(plan,dict) or not isinstance(plan.get('trucks'),list):
        raise ValueError('Expected a Plan JSON with trucks and metrics')
    metrics=plan['metrics']
    result={key:numeric(metrics[key],key) for key in ('co2_kg','total_km','empty_km')}
    if any(v<0 for v in result.values()) or result['empty_km']>result['total_km']:
        raise ValueError('Plan emissions and distances must be nonnegative; empty km cannot exceed total km')
    return result


def request(origin, path, timeout, body=None):
    req=Request(origin.rstrip('/')+path,
                data=json.dumps(body).encode() if body is not None else None,
                headers={'Content-Type':'application/json','Accept':'application/json'},
                method='POST' if body is not None else 'GET')
    with urlopen(req,timeout=timeout) as response:
        if response.status!=200:
            raise ValueError(f'{path}: HTTP {response.status}')
        return json.load(response)


def from_api(origin, timeout):
    comparison=request(origin,'/api/compare',timeout)
    baseline=request(origin,'/api/plan',timeout,{'mode':'baseline'})
    ai=request(origin,'/api/plan',timeout,{'mode':'ai'})
    scenario=request(origin,'/api/scenario',timeout)
    for mode,plan in [('baseline',baseline),('ai',ai)]:
        if plan.get('mode')!=mode:
            raise ValueError(f'Expected {mode} plan from API')
        for key,value in plan_metrics(plan).items():
            if not math.isclose(value,numeric(comparison[mode][key],key),abs_tol=.2,rel_tol=1e-6):
                raise ValueError(f'/api/compare and {mode} plan disagree on {key}; retry with stable API caches')
    return baseline,ai,scenario,f'Live API · {origin}'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def fixture_objects(value):
    """Accept plain, list, and nested {baseline, ai, scenario} JSON fixtures."""
    if isinstance(value,dict):
        if ('metrics' in value and 'trucks' in value) or ('owners' in value and 'cities' in value):
            yield value
        else:
            for child in value.values():
                yield from fixture_objects(child)
    elif isinstance(value,list):
        for child in value:
            yield from fixture_objects(child)


def from_fixtures(directory, scenario_path):
    plans={};scenario=None;files={}
    for path in sorted(Path(directory).rglob('*.json')):
        try:
            objects=fixture_objects(read_json(path))
            for value in objects:
                if value.get('mode') in ('baseline','ai') and 'metrics' in value:
                    plans[value['mode']]=value;files[value['mode']]=path.name
                if 'owners' in value and 'cities' in value:
                    scenario=value
        except (OSError,ValueError):
            continue
    if not all(mode in plans for mode in ('baseline','ai')):
        raise ValueError(f'No baseline and AI Plan JSON fixtures found in {directory}')
    scenario=scenario or read_json(scenario_path)
    return plans['baseline'],plans['ai'],scenario,f"Fixture data · {files['baseline']} / {files['ai']} (not live results)"


def calculate(baseline, ai, scenario, mileage=4):
    mileage=numeric(mileage,'mileage_kmpl')
    if mileage<=0:
        raise ValueError('mileage_kmpl must be positive')
    totals={mode:plan_metrics(plan) for mode,plan in [('baseline',baseline),('ai',ai)]}
    owners={owner['id']:owner for owner in scenario['owners']}
    membership={truck['id']:truck['owner_id'] for truck in scenario['trucks']}
    rows={oid:dict(owner=owner['name'],owner_id=oid,baseline_co2=0.,ai_co2=0.,baseline_km=0.,ai_km=0.,baseline_empty=0.,ai_empty=0.) for oid,owner in owners.items()}
    for mode,plan in [('baseline',baseline),('ai',ai)]:
        seen=set()
        for truck in plan['trucks']:
            tid=truck['truck_id']
            if tid in seen:
                raise ValueError(f'Duplicate {mode} truck {tid}')
            seen.add(tid)
            if tid not in membership or membership[tid] not in rows:
                raise ValueError(f'Cannot attribute {tid} to an owner in the scenario')
            row=rows[membership[tid]]
            # Use leg totals to avoid depending on stale per-truck cached totals.
            for leg in truck['legs']:
                emissions=numeric(leg['co2_kg'],'leg co2_kg')
                km=numeric(leg['distance_km'],'leg distance_km')
                if emissions<0 or km<0 or leg['kind'] not in ('loaded','empty'):
                    raise ValueError('Invalid truck leg emissions, distance, or kind')
                row[f'{mode}_co2']+=emissions
                row[f'{mode}_km']+=km
                if leg['kind']=='empty':
                    row[f'{mode}_empty']+=numeric(leg['distance_km'],'leg distance_km')
        tolerance=max(.3,.11*sum(len(t['legs']) for t in plan['trucks']))
        for metric,suffix in [('co2_kg','co2'),('total_km','km'),('empty_km','empty')]:
            actual=sum(row[f'{mode}_{suffix}'] for row in rows.values())
            if not math.isclose(actual,totals[mode][metric],abs_tol=tolerance,rel_tol=1e-6):
                raise ValueError(f'{mode} fleet {metric} does not reconcile with its truck legs')
    for row in rows.values():
        row['saved_co2']=row['baseline_co2']-row['ai_co2']
        row['saved_litres']=(row['baseline_km']-row['ai_km'])/mileage
        row['removed_empty']=row['baseline_empty']-row['ai_empty']
    saved=totals['baseline']['co2_kg']-totals['ai']['co2_kg']
    return dict(baseline=totals['baseline'],ai=totals['ai'],saved_co2=saved,
                saved_pct=saved/totals['baseline']['co2_kg']*100 if totals['baseline']['co2_kg'] else None,
                saved_litres=(totals['baseline']['total_km']-totals['ai']['total_km'])/mileage,
                removed_empty=totals['baseline']['empty_km']-totals['ai']['empty_km'],
                owners=list(rows.values()),mileage=mileage,week=scenario['week_start'])


CSS='''
@page { size: A4; margin: 13mm; }
* { box-sizing:border-box } body { margin:0; background:#FAF7F2; color:#293C35;
font:14px/1.5 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
main { max-width:1000px; margin:36px auto; padding:38px; }
header { display:flex; justify-content:space-between; gap:20px; border-bottom:1px solid #DADFD3; padding-bottom:22px }
.brand { font-size:13px; font-weight:750; letter-spacing:.15em; text-transform:uppercase; color:#647D69 }
h1 { margin:8px 0; font-size:36px; line-height:1.15; letter-spacing:-.04em } p { margin:7px 0 }
.meta { max-width:300px; text-align:right; color:#68736B; font-size:11px; overflow-wrap:anywhere }
.cards { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:26px 0 }
.card { background:#E3EBDD; padding:22px 18px; border-radius:15px; border:1px solid #CEDAC7 }
.card.coral { background:#F3DDD3; border-color:#E8C8BA }.value { display:block; font-size:32px; font-weight:750; letter-spacing:-.03em }
.label { font-size:12px; color:#53645A }.comparison { padding:14px 18px; background:#FFFDF9; border-radius:10px; border:1px solid #E7E1D6 }
h2 { margin:26px 0 12px; font-size:17px } table { width:100%; border-collapse:collapse; font-size:12px }
th { background:#E3EBDD; text-align:right; font-size:11px; color:#4E6756 } td,th { padding:10px 8px; border-bottom:1px solid #E2E2D8 }
th:first-child,td:first-child { text-align:left } td { text-align:right; font-variant-numeric:tabular-nums } tr { break-inside:avoid }
tfoot { font-weight:700 } .notes { color:#69746B; font-size:11px; margin-top:23px }.notice { padding:15px; border-radius:10px; background:#F3DDD3 }
footer { border-top:1px solid #DADFD3; margin-top:20px; padding-top:12px; font-size:11px; color:#69746B }
@media print { body { print-color-adjust:exact; -webkit-print-color-adjust:exact } main { margin:0; padding:0; max-width:none }
h1 { font-size:30px }.value { font-size:27px }.cards { margin:20px 0 } .card { padding:16px 12px } td,th { padding:8px 6px } }
@media screen and (max-width:650px) { main { padding:20px; margin:0 }.cards { grid-template-columns:1fr } header { display:block }.meta { text-align:left } }
'''


def render(data, source, error=None):
    esc=lambda value:escape(str(value),quote=True)
    stamp=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    if data:
        fmt=lambda value:f'{value:,.1f}'
        values=[fmt(data['saved_co2']),fmt(data['saved_litres']),fmt(data['removed_empty'])]
        percent=f"{data['saved_pct']:.1f}% change from baseline" if data['saved_pct'] is not None else 'No baseline emissions; percentage unavailable'
        comparison=(f"Baseline <strong>{fmt(data['baseline']['co2_kg'])} kg CO₂</strong> → "
                    f"AI <strong>{fmt(data['ai']['co2_kg'])} kg CO₂</strong> · {esc(percent)}")
        rows=''.join(f"<tr><td>{esc(row['owner'])}</td><td>{fmt(row['baseline_co2'])}</td><td>{fmt(row['ai_co2'])}</td><td>{fmt(row['saved_co2'])}</td><td>{fmt(row['saved_litres'])}</td><td>{fmt(row['removed_empty'])}</td></tr>" for row in data['owners'])
        totals=f"<tfoot><tr><td>Fleet total</td><td>{fmt(data['baseline']['co2_kg'])}</td><td>{fmt(data['ai']['co2_kg'])}</td><td>{values[0]}</td><td>{values[1]}</td><td>{values[2]}</td></tr></tfoot>"
        week=esc(data['week'][:10]); mileage=data['mileage']
    else:
        values=['—']*3;comparison='No savings claimed until baseline and AI plans are available.'
        rows='<tr><td colspan="6">Owner figures unavailable — supply plans and their scenario.</td></tr>'
        totals='';week='Awaiting scenario';mileage=4
    notice=f'<p class="notice">{esc(error)}</p>' if error else ''
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>LoopLoad · Weekly carbon report</title><style>{CSS}</style></head><body><main>
<header><div><div class="brand">LoopLoad / Impact report</div><h1>Less empty running.<br>A lighter footprint.</h1><p>Weekly fleet carbon comparison · {week}</p></div>
<div class="meta">{esc(source)}<br>Generated {stamp}</div></header>{notice}
<section class="cards" aria-label="Fleet savings">
<div class="card"><span class="value">{values[0]}</span><span class="label">kg CO₂ saved</span></div>
<div class="card"><span class="value">{values[1]}</span><span class="label">diesel litres saved</span></div>
<div class="card coral"><span class="value">{values[2]}</span><span class="label">empty kilometres removed</span></div></section>
<p class="comparison">{comparison}</p><h2>Impact by fleet owner</h2>
<table><thead><tr><th scope="col">Owner</th><th scope="col">Baseline<br>CO₂ (kg)</th><th scope="col">AI<br>CO₂ (kg)</th><th scope="col">CO₂ saved<br>(kg)</th><th scope="col">Diesel saved<br>(L)</th><th scope="col">Empty km<br>removed</th></tr></thead><tbody>{rows}</tbody>{totals}</table>
<p class="notes">Method: operational diesel use is estimated at {mileage:g} km/L across loaded and empty legs. CO₂ figures come from plan metrics; the demo uses 2.68 kg CO₂/L. Savings = baseline − AI; negative values indicate an increase and are never clipped. Owner figures are summed from truck legs and checked against fleet totals. This is a synthetic demo estimate, not a certified emissions or lifecycle assessment.</p>
<footer>LoopLoad · More freight carried. Fewer empty kilometres. · Print → Save as PDF · A4 portrait</footer>
</main></body></html>'''


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://localhost:8000')
    parser.add_argument('--timeout',type=float,default=180)
    parser.add_argument('--fixtures',type=Path,default=ROOT/'frontend/src/mocks')
    parser.add_argument('--offline',action='store_true',help='use fixture JSON without contacting API')
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--ai',type=Path)
    parser.add_argument('--scenario',type=Path,default=ROOT/'backend/data/scenario.json')
    parser.add_argument('--mileage-kmpl',type=float,default=4)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args(argv)
    if bool(args.baseline)!=bool(args.ai):
        parser.error('--baseline and --ai must be supplied together')
    source='Data unavailable';data=None;error=None
    try:
        if args.baseline:
            inputs=(read_json(args.baseline),read_json(args.ai),read_json(args.scenario),
                    f'Plan JSON · {args.baseline.name} / {args.ai.name}')
        else:
            try:
                if args.offline:
                    raise ValueError('Offline fixture mode requested')
                inputs=from_api(args.base_url,args.timeout)
            except (OSError,ValueError,KeyError,TypeError) as exc:
                print(f'API unavailable or inconsistent ({exc}); trying fixture plans.',file=sys.stderr)
                inputs=from_fixtures(args.fixtures,args.scenario)
        baseline,ai,scenario,source=inputs
        data=calculate(baseline,ai,scenario,args.mileage_kmpl)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(f'Data unavailable: {exc}',file=sys.stderr)
        error='Baseline and AI plans are unavailable or could not be validated. Start the API or provide matching plan JSON fixtures to calculate this report.'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(render(data,source,error),encoding='utf-8')
    print(f'Wrote {args.output}')
    if data:
        print(f"CO2 saved {data['saved_co2']:,.1f} kg; diesel saved {data['saved_litres']:,.1f} L; empty km removed {data['removed_empty']:,.1f}")
    return 0 if data else 1


if __name__=='__main__':
    sys.exit(main())
